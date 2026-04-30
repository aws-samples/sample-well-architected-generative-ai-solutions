# ECS Bedrock AgentCore Dev Autonomous WS Solution

Self-contained developer assistant powered by Kiro CLI running on Amazon Bedrock AgentCore Runtime, with an ECS-based backend orchestrator and real-time streaming frontend.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────────┐
│  CloudFront  │────▶│  ALB (HTTP)   │────▶│  ECS Fargate        │
│  (frontend)  │     │  /api/* /ws   │     │  Backend Orchestrator│
└─────────────┘     └──────────────┘     └────────┬────────────┘
                                                   │
                              ┌─────────────────────┤
                              ▼                     ▼
                    ┌──────────────┐     ┌──────────────────┐
                    │  DynamoDB     │     │  AgentCore Runtime │
                    │  (task memory)│     │  (Kiro CLI + ACP)  │
                    └──────────────┘     └──────────────────┘
```

## Components

| Component | Path | Description |
|---|---|---|
| Backend Orchestrator | `ecs-backend/` | FastAPI app with WebSocket, intent routing (Claude), AgentCore invocation with retry |
| Agent Runtime | `kiro-agentcore-runtime/` | Kiro CLI ACP wrapper with async task management, deployed to AgentCore Runtime |
| Frontend | `frontend/` | Developer assistant UI (dev-v2) with real-time streaming + task log viewer |
| Deployment | `deployment-scripts/` | All-in-one CFN template + CodeBuild buildspecs |

## Deployment

### Prerequisites
- AWS CLI configured with appropriate permissions
- An AWS account with Bedrock model access enabled

### Step 1: Deploy the CloudFormation stack

```bash
STACK_NAME=my-dev-assistant

aws cloudformation create-stack \
  --stack-name $STACK_NAME \
  --template-body file://deployment-scripts/dev-autonomous-ws-solution.yaml \
  --capabilities CAPABILITY_IAM \
  --parameters \
    ParameterKey=Environment,ParameterValue=dev \
    ParameterKey=DevtoolMode,ParameterValue=true \
    ParameterKey=TargetRepoUrl,ParameterValue=https://github.com/your-org/your-repo

aws cloudformation wait stack-create-complete --stack-name $STACK_NAME
```

### Step 2: Set SSM secrets

```bash
aws ssm put-parameter --name "/$STACK_NAME/kiro-api-key" --value "YOUR_KIRO_API_KEY" --type String --overwrite
aws ssm put-parameter --name "/$STACK_NAME/gh-token" --value "YOUR_GITHUB_PAT" --type String --overwrite
```

### Step 3: Package and upload source

```bash
# Get stack outputs
SOURCE_BUCKET=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --query 'Stacks[0].Outputs[?OutputKey==`SourceBucket`].OutputValue' --output text)

# Package and upload backend
cd ecs-backend && zip -r /tmp/backend-source.zip . && cd ..
zip -r /tmp/backend-source.zip deployment-scripts/buildspecs/backend-buildspec.yml
aws s3 cp /tmp/backend-source.zip s3://$SOURCE_BUCKET/backend-source.zip

# Package and upload agent
cd kiro-agentcore-runtime && zip -r /tmp/agent-source.zip . && cd ..
zip -r /tmp/agent-source.zip deployment-scripts/buildspecs/agent-buildspec.yml
aws s3 cp /tmp/agent-source.zip s3://$SOURCE_BUCKET/agent-source.zip

# Package and upload frontend
cd frontend && zip -r /tmp/frontend-source.zip . && cd ..
zip -r /tmp/frontend-source.zip deployment-scripts/buildspecs/frontend-buildspec.yml
aws s3 cp /tmp/frontend-source.zip s3://$SOURCE_BUCKET/frontend-source.zip
```

### Step 4: Build containers

```bash
aws codebuild start-build --project-name $STACK_NAME-backend-build
aws codebuild start-build --project-name $STACK_NAME-agent-build
aws codebuild start-build --project-name $STACK_NAME-frontend-build
```

### Step 5: Update stack with real backend image

```bash
BACKEND_ECR=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --query 'Stacks[0].Outputs[?OutputKey==`BackendECRRepo`].OutputValue' --output text)

aws cloudformation update-stack \
  --stack-name $STACK_NAME \
  --use-previous-template \
  --capabilities CAPABILITY_IAM \
  --parameters \
    ParameterKey=BackendImage,ParameterValue=$BACKEND_ECR:latest \
    ParameterKey=Environment,UsePreviousValue=true \
    ParameterKey=BedrockRegion,UsePreviousValue=true \
    ParameterKey=DevtoolMode,UsePreviousValue=true \
    ParameterKey=TargetRepoUrl,UsePreviousValue=true \
    ParameterKey=DemoMaskOutput,UsePreviousValue=true \
    ParameterKey=DemoReadOnly,UsePreviousValue=true \
    ParameterKey=AgentCoreRuntimeArn,UsePreviousValue=true \
    ParameterKey=CreateAgentCoreRuntime,UsePreviousValue=true
```

### Step 6: Access the application

```bash
aws cloudformation describe-stacks --stack-name $STACK_NAME --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontURL`].OutputValue' --output text
```

## Features

- **Real-time streaming** — Agent responses stream to the frontend as they're generated
- **DevTool mode** — Scoped to repository operations (code, tests, git, PRs), blocks infra mutations
- **Task memory** — DynamoDB-backed task history with 7-day TTL
- **Session logs** — Full session JSON persisted to S3
- **Git graph** — Mermaid-rendered branch visualization from GitHub API
- **Agent retry** — Automatic retry when AgentCore agent is cold-starting
