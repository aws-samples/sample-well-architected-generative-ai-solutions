#!/usr/bin/env python3
"""Deploy AgentCore Memory stack and optionally wire it to an existing AgentCore Runtime."""
import argparse
import boto3
import os
import sys
import time


def get_args():
    parser = argparse.ArgumentParser(description="Deploy AgentCore Memory")
    parser.add_argument("--stack-name", default="agentcore-memory", help="CloudFormation stack name")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--memory-name", default="AgentMemory", help="Memory resource name")
    parser.add_argument("--event-expiry-days", type=int, default=30, help="Short-term memory retention (3-365 days)")
    parser.add_argument("--enable-semantic", default="true", choices=["true", "false"])
    parser.add_argument("--enable-summarization", default="true", choices=["true", "false"])
    parser.add_argument("--enable-user-preference", default="false", choices=["true", "false"])
    parser.add_argument("--runtime-arn", default="", help="Existing AgentCore Runtime ARN to update with memory ID")
    return parser.parse_args()


def deploy_stack(args):
    cfn = boto3.client("cloudformation", region_name=args.region)
    template_path = os.path.join(os.path.dirname(__file__), "agentcore-memory.yaml")
    with open(template_path) as f:
        template_body = f.read()

    params = [
        {"ParameterKey": "MemoryName", "ParameterValue": args.memory_name},
        {"ParameterKey": "EventExpiryDays", "ParameterValue": str(args.event_expiry_days)},
        {"ParameterKey": "EnableSemantic", "ParameterValue": args.enable_semantic},
        {"ParameterKey": "EnableSummarization", "ParameterValue": args.enable_summarization},
        {"ParameterKey": "EnableUserPreference", "ParameterValue": args.enable_user_preference},
        {"ParameterKey": "ExistingAgentCoreRuntimeArn", "ParameterValue": args.runtime_arn},
    ]

    try:
        cfn.describe_stacks(StackName=args.stack_name)
        is_update = True
    except cfn.exceptions.ClientError:
        is_update = False

    if is_update:
        try:
            cfn.update_stack(StackName=args.stack_name, TemplateBody=template_body,
                             Parameters=params, Capabilities=["CAPABILITY_IAM"])
            print(f"Updating stack: {args.stack_name}")
        except cfn.exceptions.ClientError as e:
            if "No updates" in str(e):
                print("No stack updates needed.")
                return get_outputs(cfn, args.stack_name)
            raise
        waiter = cfn.get_waiter("stack_update_complete")
    else:
        cfn.create_stack(StackName=args.stack_name, TemplateBody=template_body,
                         Parameters=params, Capabilities=["CAPABILITY_IAM"])
        print(f"Creating stack: {args.stack_name}")
        waiter = cfn.get_waiter("stack_create_complete")

    print("Waiting for stack operation...")
    waiter.wait(StackName=args.stack_name, WaiterConfig={"Delay": 10, "MaxAttempts": 60})
    return get_outputs(cfn, args.stack_name)


def get_outputs(cfn, stack_name):
    outputs = cfn.describe_stacks(StackName=stack_name)["Stacks"][0].get("Outputs", [])
    return {o["OutputKey"]: o["OutputValue"] for o in outputs}


def wait_for_memory_active(memory_id, region):
    """Poll until memory status is ACTIVE."""
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    print(f"Waiting for memory {memory_id} to become ACTIVE...")
    for _ in range(30):
        resp = client.get_memory(memoryId=memory_id)
        status = resp.get("memory", resp).get("status", resp.get("status", "UNKNOWN"))
        if status == "ACTIVE":
            print(f"Memory is ACTIVE")
            return True
        if status == "FAILED":
            print(f"Memory FAILED: {resp}")
            return False
        print(f"  Status: {status}...")
        time.sleep(10)
    print("Timeout waiting for memory")
    return False


def update_runtime_env(runtime_arn, memory_id, memory_name, region):
    """Update an existing AgentCore Runtime to include the memory ID env var."""
    client = boto3.client("bedrock-agentcore-control", region_name=region)
    runtime_id = runtime_arn.split("/")[-1]
    env_key = f"MEMORY_{memory_name.upper()}_ID"

    try:
        runtime = client.get_agent_runtime(agentRuntimeId=runtime_id)
        current_env = runtime.get("environmentVariables", {})
        current_env[env_key] = memory_id
        client.update_agent_runtime(
            agentRuntimeId=runtime_id,
            environmentVariables=current_env,
        )
        print(f"Updated runtime {runtime_id}: {env_key}={memory_id}")
    except Exception as e:
        print(f"Failed to update runtime: {e}")
        print(f"Manually set env var {env_key}={memory_id} on your runtime.")


def main():
    args = get_args()
    print(f"Deploying {args.stack_name} to {args.region}")

    outputs = deploy_stack(args)
    print("\nStack outputs:")
    for k, v in outputs.items():
        print(f"  {k}: {v}")

    memory_id = outputs.get("MemoryId", "")
    if memory_id:
        wait_for_memory_active(memory_id, args.region)

    if args.runtime_arn and memory_id:
        print(f"\nWiring memory to runtime: {args.runtime_arn}")
        update_runtime_env(args.runtime_arn, memory_id, args.memory_name, args.region)

    print(f"\n✅ Done! Memory ID: {memory_id}")
    if not args.runtime_arn:
        print(f"\nTo wire to an existing runtime, re-run with:")
        print(f"  --runtime-arn <your-runtime-arn>")


if __name__ == "__main__":
    main()
