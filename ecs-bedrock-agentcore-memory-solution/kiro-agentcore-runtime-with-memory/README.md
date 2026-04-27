# Kiro CLI as AgentCore Runtime (PoC)

Packages Kiro CLI + MCP (aws-api-mcp-server) as a Bedrock AgentCore containerConfiguration runtime.

## How it works

```
invoke_agent_runtime(payload={"input": "check my S3 buckets"})
    → AgentCore container (port 8080)
        → wrapper.py receives HTTP POST
            → kiro-cli chat "check my S3 buckets" --no-interactive --trust-all-tools
                → Kiro uses MCP tools (aws-api) to answer
            → stdout captured → returned as JSON response
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `KIRO_API_KEY` | ✅ | Kiro API key for authentication |
| `AWS_REGION` | auto | AWS region (provided by AgentCore task role) |
| `PORT` | no | Server port (default: 8080) |

## Passing KIRO_API_KEY

AgentCore supports environment variables in the runtime configuration:

```python
client.create_agent_runtime(
    agentRuntimeName='kiro_mcp_agent',
    agentRuntimeArtifact={
        'containerConfiguration': {
            'containerUri': '123456789.dkr.ecr.us-west-2.amazonaws.com/kiro-agentcore:latest',
        }
    },
    environmentVariables={
        'KIRO_API_KEY': 'ksk_your_key_here',
    },
    ...
)
```

Or store in SSM Parameter Store / Secrets Manager and fetch at startup.

## Build & Deploy

```bash
# 1. Build ARM64 image (required by AgentCore)
docker buildx build --platform linux/arm64 -t kiro-agentcore:latest .

# 2. Push to ECR
aws ecr create-repository --repository-name kiro-agentcore --region us-west-2
docker tag kiro-agentcore:latest 256358067059.dkr.ecr.us-west-2.amazonaws.com/kiro-agentcore:latest
docker push 256358067059.dkr.ecr.us-west-2.amazonaws.com/kiro-agentcore:latest

# 3. Register as AgentCore runtime
python3 deploy_runtime.py
```

## Security Note

Never hardcode KIRO_API_KEY in the Dockerfile or source code.
Use AgentCore's `environmentVariables` parameter or fetch from Secrets Manager at startup.
