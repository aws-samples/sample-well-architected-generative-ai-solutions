#!/usr/bin/env python3
"""Deploy the AgentCore Long-Running Orchestrator stack (multi-phase)."""
import argparse
import boto3
import os
import sys
import time
import zipfile
import tempfile


def get_args():
    parser = argparse.ArgumentParser(description="Deploy AgentCore Long-Running Orchestrator")
    parser.add_argument("--stack-name", default="agentcore-longrun", help="CloudFormation stack name")
    parser.add_argument("--region", default="us-west-2", help="AWS region")
    parser.add_argument("--environment", default="prod", choices=["dev", "staging", "prod"])
    parser.add_argument("--demo-mask-output", default="false", choices=["true", "false"])
    parser.add_argument("--demo-read-only", default="false", choices=["true", "false"])
    parser.add_argument("--phase", default="all", choices=["infra", "build", "update", "all"],
                        help="infra=create stack with placeholder, build=build images, update=switch to real image, all=full deploy")
    return parser.parse_args()


def upload_source(source_bucket, region):
    """Zip and upload backend + agent source to S3."""
    s3 = boto3.client("s3", region_name=region)
    base = os.path.join(os.path.dirname(__file__), "..")

    for name, paths in [
        ("backend-source.zip", ["ecs-backend", "deployment-scripts/buildspecs"]),
        ("agent-source.zip", ["kiro-agentcore-runtime", "deployment-scripts/buildspecs"]),
    ]:
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
                for p in paths:
                    full = os.path.join(base, p)
                    if os.path.isdir(full):
                        for root, _, files in os.walk(full):
                            for f in files:
                                fp = os.path.join(root, f)
                                zf.write(fp, os.path.relpath(fp, base))
                    elif os.path.isfile(full):
                        zf.write(full, os.path.relpath(full, base))
            s3.upload_file(tmp.name, source_bucket, name)
            os.unlink(tmp.name)
            print(f"  Uploaded {name} to s3://{source_bucket}/{name}")


def deploy_stack(stack_name, region, args, backend_image="public.ecr.aws/nginx/nginx:alpine",
                 create_runtime=False, runtime_arn=""):
    cfn = boto3.client("cloudformation", region_name=region)
    template_path = os.path.join(os.path.dirname(__file__), "agentcore-longrun-orchestrator-0.1.0.yaml")
    with open(template_path) as f:
        template_body = f.read()

    params = [
        {"ParameterKey": "Environment", "ParameterValue": args.environment},
        {"ParameterKey": "BedrockRegion", "ParameterValue": region},
        {"ParameterKey": "BackendImage", "ParameterValue": backend_image},
        {"ParameterKey": "CreateAgentCoreRuntime", "ParameterValue": "true" if create_runtime else "false"},
        {"ParameterKey": "AgentCoreRuntimeArn", "ParameterValue": runtime_arn},
        {"ParameterKey": "DemoMaskOutput", "ParameterValue": args.demo_mask_output},
        {"ParameterKey": "DemoReadOnly", "ParameterValue": args.demo_read_only},
    ]

    try:
        cfn.describe_stacks(StackName=stack_name)
        is_update = True
    except cfn.exceptions.ClientError:
        is_update = False

    if is_update:
        try:
            cfn.update_stack(StackName=stack_name, TemplateBody=template_body, Parameters=params,
                             Capabilities=["CAPABILITY_IAM"])
            print(f"Updating stack: {stack_name}")
        except cfn.exceptions.ClientError as e:
            if "No updates" in str(e):
                print("No stack updates needed.")
                outputs = cfn.describe_stacks(StackName=stack_name)["Stacks"][0].get("Outputs", [])
                return {o["OutputKey"]: o["OutputValue"] for o in outputs}
            raise
        waiter = cfn.get_waiter("stack_update_complete")
    else:
        cfn.create_stack(StackName=stack_name, TemplateBody=template_body, Parameters=params,
                         Capabilities=["CAPABILITY_IAM"])
        print(f"Creating stack: {stack_name}")
        waiter = cfn.get_waiter("stack_create_complete")

    print("Waiting for stack operation to complete...")
    waiter.wait(StackName=stack_name, WaiterConfig={"Delay": 15, "MaxAttempts": 80})

    outputs = cfn.describe_stacks(StackName=stack_name)["Stacks"][0].get("Outputs", [])
    return {o["OutputKey"]: o["OutputValue"] for o in outputs}


def get_stack_outputs(stack_name, region):
    cfn = boto3.client("cloudformation", region_name=region)
    outputs = cfn.describe_stacks(StackName=stack_name)["Stacks"][0].get("Outputs", [])
    return {o["OutputKey"]: o["OutputValue"] for o in outputs}


def run_codebuild(project_name, region):
    cb = boto3.client("codebuild", region_name=region)
    build = cb.start_build(projectName=project_name)
    build_id = build["build"]["id"]
    print(f"  Started build: {build_id}")

    while True:
        resp = cb.batch_get_builds(ids=[build_id])
        status = resp["builds"][0]["buildStatus"]
        phase = resp["builds"][0].get("currentPhase", "?")
        if status == "IN_PROGRESS":
            print(f"  Build {phase}...")
            time.sleep(15)
        elif status == "SUCCEEDED":
            print(f"  Build SUCCEEDED")
            return True
        else:
            print(f"  Build FAILED: {status}")
            return False


def deploy_frontend(outputs, region):
    s3 = boto3.client("s3", region_name=region)
    bucket = outputs["StaticBucket"]
    dist_dir = os.path.join(os.path.dirname(__file__), "..", "frontend-react", "dist")
    if not os.path.isdir(dist_dir):
        print(f"Warning: {dist_dir} not found, skipping frontend deploy")
        return

    content_types = {".html": "text/html", ".js": "application/javascript", ".css": "text/css",
                     ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png"}
    for root, _, files in os.walk(dist_dir):
        for f in files:
            path = os.path.join(root, f)
            key = os.path.relpath(path, dist_dir)
            ext = os.path.splitext(f)[1]
            ct = content_types.get(ext, "application/octet-stream")
            s3.upload_file(path, bucket, key, ExtraArgs={"ContentType": ct})
    print(f"Frontend deployed to s3://{bucket}")


def main():
    args = get_args()
    stack_name = args.stack_name
    region = args.region
    print(f"Deploying {stack_name} to {region} (phase: {args.phase})")

    if args.phase in ("infra", "all"):
        print("\n=== Phase 1: Deploy infrastructure with placeholder image ===")
        outputs = deploy_stack(stack_name, region, args)
        source_bucket = outputs["SourceBucket"]
        print("\nStack outputs:")
        for k, v in outputs.items():
            print(f"  {k}: {v}")
        print("\n  Uploading source code...")
        upload_source(source_bucket, region)
        deploy_frontend(outputs, region)

    if args.phase in ("build", "all"):
        outputs = get_stack_outputs(stack_name, region)
        print("\n=== Phase 2: Build backend image ===")
        if not run_codebuild(outputs["BackendBuildProject"], region):
            print("ERROR: Backend build failed!")
            sys.exit(1)

        print("\n=== Phase 3: Build agent image ===")
        if not run_codebuild(outputs["AgentBuildProject"], region):
            print("ERROR: Agent build failed!")
            sys.exit(1)

    if args.phase in ("update", "all"):
        print("\n=== Phase 4: Update ECS with real backend image ===")
        outputs = get_stack_outputs(stack_name, region)
        backend_image = f"{outputs['BackendECRRepo']}:latest"
        outputs = deploy_stack(stack_name, region, args,
                               backend_image=backend_image, create_runtime=True)
        print("\nFinal stack outputs:")
        for k, v in outputs.items():
            print(f"  {k}: {v}")

    print(f"\n✅ Phase '{args.phase}' complete!")


if __name__ == "__main__":
    main()
