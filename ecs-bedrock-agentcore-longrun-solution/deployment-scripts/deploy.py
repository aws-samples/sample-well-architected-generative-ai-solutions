#!/usr/bin/env python3
"""Deploy the AgentCore Long-Running Orchestrator stack."""
import argparse
import boto3
import json
import os
import sys
import time


def get_args():
    parser = argparse.ArgumentParser(description="Deploy AgentCore Long-Running Orchestrator")
    parser.add_argument("--stack-name", default="agentcore-longrun", help="CloudFormation stack name")
    parser.add_argument("--region", default="us-west-2", help="AWS region")
    parser.add_argument("--runtime-arn", required=True, help="AgentCore Runtime ARN")
    parser.add_argument("--environment", default="prod", choices=["dev", "staging", "prod"])
    return parser.parse_args()


def create_source_bucket(stack_name, region):
    """Create S3 bucket for source code."""
    s3 = boto3.client("s3", region_name=region)
    account = boto3.client("sts").get_caller_identity()["Account"]
    bucket = f"{stack_name}-source-{account}-{region}"
    try:
        if region == "us-east-1":
            s3.create_bucket(Bucket=bucket)
        else:
            s3.create_bucket(Bucket=bucket, CreateBucketConfiguration={"LocationConstraint": region})
    except s3.exceptions.BucketAlreadyOwnedByYou:
        pass
    return bucket


def deploy_stack(stack_name, region, source_bucket, runtime_arn, environment):
    """Deploy the CloudFormation stack."""
    cfn = boto3.client("cloudformation", region_name=region)
    template_path = os.path.join(os.path.dirname(__file__), "agentcore-longrun-orchestrator-0.1.0.yaml")
    with open(template_path) as f:
        template_body = f.read()

    params = [
        {"ParameterKey": "SourceBucket", "ParameterValue": source_bucket},
        {"ParameterKey": "AgentCoreRuntimeArn", "ParameterValue": runtime_arn},
        {"ParameterKey": "Environment", "ParameterValue": environment},
        {"ParameterKey": "BedrockRegion", "ParameterValue": region},
    ]

    try:
        cfn.describe_stacks(StackName=stack_name)
        cfn.update_stack(StackName=stack_name, TemplateBody=template_body, Parameters=params, Capabilities=["CAPABILITY_IAM"])
        print(f"Updating stack: {stack_name}")
    except cfn.exceptions.ClientError as e:
        if "does not exist" in str(e):
            cfn.create_stack(StackName=stack_name, TemplateBody=template_body, Parameters=params, Capabilities=["CAPABILITY_IAM"])
            print(f"Creating stack: {stack_name}")
        else:
            raise

    print("Waiting for stack operation to complete...")
    waiter = cfn.get_waiter("stack_create_complete")
    try:
        waiter.wait(StackName=stack_name, WaiterConfig={"Delay": 15, "MaxAttempts": 60})
    except Exception:
        waiter = cfn.get_waiter("stack_update_complete")
        waiter.wait(StackName=stack_name, WaiterConfig={"Delay": 15, "MaxAttempts": 60})

    outputs = cfn.describe_stacks(StackName=stack_name)["Stacks"][0]["Outputs"]
    return {o["OutputKey"]: o["OutputValue"] for o in outputs}


def deploy_frontend(outputs, region):
    """Upload frontend assets to S3."""
    s3 = boto3.client("s3", region_name=region)
    bucket = outputs["StaticBucket"]
    dist_dir = os.path.join(os.path.dirname(__file__), "..", "frontend-react", "dist")

    for root, _, files in os.walk(dist_dir):
        for f in files:
            path = os.path.join(root, f)
            key = os.path.relpath(path, dist_dir)
            content_type = "text/html" if f.endswith(".html") else "application/javascript" if f.endswith(".js") else "text/css" if f.endswith(".css") else "application/octet-stream"
            s3.upload_file(path, bucket, key, ExtraArgs={"ContentType": content_type})
    print(f"Frontend deployed to s3://{bucket}")


def main():
    args = get_args()
    print(f"Deploying {args.stack_name} to {args.region}")

    source_bucket = create_source_bucket(args.stack_name, args.region)
    outputs = deploy_stack(args.stack_name, args.region, source_bucket, args.runtime_arn, args.environment)

    print("\nStack outputs:")
    for k, v in outputs.items():
        print(f"  {k}: {v}")

    deploy_frontend(outputs, args.region)
    print(f"\n✅ Deployment complete! URL: {outputs.get('CloudFrontURL', 'N/A')}")


if __name__ == "__main__":
    main()
