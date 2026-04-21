"""Deploy Kiro CLI as AgentCore containerConfiguration runtime."""
import boto3
import os
import sys

REGION = os.getenv("AWS_REGION", "us-west-2")
ACCOUNT = boto3.client("sts").get_caller_identity()["Account"]
ECR_REPO = f"{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/kiro-agentcore:latest"
ROLE_ARN = f"arn:aws:iam::{ACCOUNT}:role/coav2-bedrock-agentcore-runtime-role"


def deploy():
    client = boto3.client("bedrock-agentcore-control", region_name=REGION)

    # KIRO_API_KEY from env or prompt
    api_key = os.getenv("KIRO_API_KEY")
    if not api_key:
        print("Error: KIRO_API_KEY environment variable required")
        sys.exit(1)

    resp = client.create_agent_runtime(
        agentRuntimeName="kiro_mcp_agent",
        roleArn=ROLE_ARN,
        networkConfiguration={"networkMode": "PUBLIC"},
        agentRuntimeArtifact={
            "containerConfiguration": {
                "containerUri": ECR_REPO,
            }
        },
        environmentVariables={
            "KIRO_API_KEY": api_key,
        },
    )

    print(f"Runtime ARN: {resp['agentRuntimeArn']}")
    print(f"Runtime ID: {resp['agentRuntimeId']}")
    print(f"Status: {resp['status']}")


if __name__ == "__main__":
    deploy()
