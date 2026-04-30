# AgentCore Dev Autonomous WS Solution

An AI-powered developer assistant that runs autonomously against your GitHub repository. Built on [Amazon Bedrock AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html) with [Kiro CLI](https://kiro.dev), it can read and write code, run tests, create branches, and open pull requests — all through natural language in a real-time streaming chat interface.

---

## Architecture

```
                          ┌──────────────────────────────────────────────────────┐
                          │                    AWS Cloud                         │
                          │                                                      │
┌──────────┐   HTTPS      │  ┌─────────────┐      ┌───────────────────────────┐  │
│          │──────────────▶│  │ CloudFront  │─────▶│  S3 (Static Frontend)     │  │
│  Browser │              │  │             │      └───────────────────────────┘  │
│          │◀─ ─ ─ ─ ─ ─ ─│  │  /api/* /ws │                                    │
└──────────┘   WebSocket  │  │      │      │      ┌───────────────────────────┐  │
                          │  │      ▼      │      │  ALB                      │  │
                          │  │  ┌───────┐  │─────▶│  (HTTP → ECS)             │  │
                          │  │  │ Cache │  │      └────────────┬──────────────┘  │
                          │  └──┴───────┴──┘                   │                 │
                          │                                    ▼                 │
                          │                    ┌───────────────────────────┐      │
                          │                    │  ECS Fargate              │      │
                          │                    │  Backend Orchestrator     │      │
                          │                    │  (FastAPI + WebSocket)    │      │
                          │                    └──┬──────────┬──────────┬─┘      │
                          │                       │          │          │         │
                          │              ┌────────┘    ┌─────┘    ┌────┘         │
                          │              ▼             ▼          ▼              │
                          │  ┌────────────────┐ ┌──────────┐ ┌──────────────┐   │
                          │  │ AgentCore      │ │ DynamoDB  │ │ S3           │   │
                          │  │ Runtime        │ │ (Tasks)   │ │ (Session     │   │
                          │  │ ┌────────────┐ │ └──────────┘ │  Logs)       │   │
                          │  │ │ Kiro CLI   │ │              └──────────────┘   │
                          │  │ │ + ACP      │ │                                 │
                          │  │ └────────────┘ │                                 │
                          │  └────────────────┘                                 │
                          └──────────────────────────────────────────────────────┘
```

### Request Flow

1. User sends a message via WebSocket from the browser
2. Backend routes intent through Bedrock Claude (Haiku) — classify as chat, decline, or agent task
3. For agent tasks, backend invokes AgentCore Runtime via HTTP with automatic retry on cold start
4. Agent container runs Kiro CLI to execute the task (code changes, tests, git ops, PRs)
5. Result streams back through the WebSocket chain to the browser in real-time

---

## Features

| Feature | Description |
|---|---|
| **Real-time streaming** | Agent responses appear progressively in the chat as they're generated — no waiting for the full result |
| **DevTool mode** | Agent is scoped to repository operations (code, tests, git, PRs) and blocked from infrastructure mutations |
| **Git graph** | Live Mermaid-rendered branch visualization fetched from the GitHub API |
| **Task memory** | Every task is persisted to DynamoDB with status, input, result, and repo context (7-day TTL) |
| **Session logs** | Full session JSON (chat history + all tasks) saved to S3 on disconnect |
| **Cold start retry** | Backend automatically retries up to 60s when the AgentCore agent is still initializing |
| **Intent routing** | Bedrock Claude classifies user messages into tiers: decline, direct answer, or route to agent |
| **Output masking** | Optional demo mode that redacts AWS resource IDs and names in responses |

---

## Folder Structure

```
ecs-bedrock-agentcore-dev-autonomous-ws-solution/
│
├── README.md                              ← You are here
│
├── ecs-backend/                           ← ECS Backend Orchestrator
│   ├── main.py                            ← Uvicorn entrypoint
│   ├── requirements.txt                   ← Python dependencies
│   ├── deployment/
│   │   └── Dockerfile                     ← Backend container image
│   └── orchestrator/
│       ├── app.py                         ← FastAPI app, WebSocket handler, task runner
│       └── services/
│           ├── intent_service.py           ← Bedrock Claude intent classification
│           ├── agentcore_service.py        ← AgentCore Runtime invocation + streaming
│           ├── task_memory_service.py      ← DynamoDB task persistence
│           ├── github_service.py           ← GitHub API → Mermaid git graph
│           └── devtool_service.py          ← Repo context enrichment
│
├── kiro-agentcore-runtime/                ← AgentCore Agent Container
│   ├── wrapper.py                         ← BedrockAgentCoreApp + Kiro CLI ACP
│   ├── Dockerfile                         ← ARM64 image with Kiro CLI, AWS CLI, GitHub CLI
│   └── profiles/
│       └── default.json                   ← MCP integration profile
│
├── frontend/                              ← Static Frontend
│   ├── developer-assistant-dev-v2.html    ← Main UI with streaming chat + git graph
│   └── task-log.html                      ← Session/task history viewer
│
└── deployment-scripts/                    ← Infrastructure
    ├── dev-autonomous-ws-solution.yaml    ← All-in-one CloudFormation template
    └── buildspecs/
        ├── backend-buildspec.yml          ← CodeBuild: backend container
        ├── agent-buildspec.yml            ← CodeBuild: agent container (ARM64)
        └── frontend-buildspec.yml         ← CodeBuild: frontend → S3
```

---

## AWS Resources Created

The CloudFormation template provisions **36 resources** in a single stack:

| Category | Resources |
|---|---|
| **Networking** | VPC, 2 public subnets, Internet Gateway, route table, 2 security groups |
| **Compute** | ECS Cluster, Fargate task definition, ECS service, ALB, target group, listener |
| **Containers** | 2 ECR repositories (backend + agent) |
| **AI Agent** | AgentCore Runtime (conditional), AgentCore IAM role |
| **Storage** | 3 S3 buckets (source artifacts, session logs, static frontend) |
| **Database** | DynamoDB table (task memory, PAY_PER_REQUEST, 7-day TTL) |
| **Secrets** | 2 SSM parameters (Kiro API key, GitHub PAT) |
| **CDN** | CloudFront distribution (S3 origin + ALB origin with WebSocket support) |
| **Auth** | Cognito user pool + client |
| **CI/CD** | 3 CodeBuild projects (backend, agent ARM64, frontend) |
| **IAM** | 5 roles (task, execution, build, AgentCore runtime, frontend build) |
| **Logging** | CloudWatch log group (14-day retention) |

---

## Deployment

### Prerequisites

- AWS CLI v2 configured with credentials
- An AWS account with [Amazon Bedrock model access](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html) enabled (Claude Haiku)
- A [Kiro API key](https://kiro.dev)
- A [GitHub Personal Access Token](https://github.com/settings/tokens) (for repo operations)

### Step 1 — Deploy the stack

```bash
STACK_NAME=my-dev-assistant
REGION=us-west-2

aws cloudformation create-stack \
  --stack-name $STACK_NAME \
  --region $REGION \
  --template-body file://deployment-scripts/dev-autonomous-ws-solution.yaml \
  --capabilities CAPABILITY_IAM \
  --parameters \
    ParameterKey=Environment,ParameterValue=dev \
    ParameterKey=BedrockRegion,ParameterValue=$REGION \
    ParameterKey=DevtoolMode,ParameterValue=true \
    ParameterKey=TargetRepoUrl,ParameterValue=https://github.com/your-org/your-repo

aws cloudformation wait stack-create-complete --stack-name $STACK_NAME --region $REGION
```

### Step 2 — Store secrets in SSM

```bash
aws ssm put-parameter \
  --name "/$STACK_NAME/kiro-api-key" \
  --value "YOUR_KIRO_API_KEY" \
  --type String --overwrite --region $REGION

aws ssm put-parameter \
  --name "/$STACK_NAME/gh-token" \
  --value "ghp_YOUR_GITHUB_PAT" \
  --type String --overwrite --region $REGION
```

### Step 3 — Package and upload source code

```bash
SOURCE_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`SourceBucket`].OutputValue' --output text)

# Backend
(cd ecs-backend && zip -r /tmp/backend-source.zip .) && \
  zip -rg /tmp/backend-source.zip deployment-scripts/buildspecs/backend-buildspec.yml && \
  aws s3 cp /tmp/backend-source.zip s3://$SOURCE_BUCKET/backend-source.zip

# Agent
(cd kiro-agentcore-runtime && zip -r /tmp/agent-source.zip .) && \
  zip -rg /tmp/agent-source.zip deployment-scripts/buildspecs/agent-buildspec.yml && \
  aws s3 cp /tmp/agent-source.zip s3://$SOURCE_BUCKET/agent-source.zip

# Frontend
(cd frontend && zip -r /tmp/frontend-source.zip .) && \
  zip -rg /tmp/frontend-source.zip deployment-scripts/buildspecs/frontend-buildspec.yml && \
  aws s3 cp /tmp/frontend-source.zip s3://$SOURCE_BUCKET/frontend-source.zip
```

### Step 4 — Build all containers

```bash
aws codebuild start-build --project-name $STACK_NAME-backend-build --region $REGION
aws codebuild start-build --project-name $STACK_NAME-agent-build --region $REGION
aws codebuild start-build --project-name $STACK_NAME-frontend-build --region $REGION
```

> Wait for all three builds to succeed before proceeding.

### Step 5 — Switch ECS to the real backend image

```bash
BACKEND_ECR=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`BackendECRRepo`].OutputValue' --output text)

aws cloudformation update-stack \
  --stack-name $STACK_NAME --region $REGION \
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

aws cloudformation wait stack-update-complete --stack-name $STACK_NAME --region $REGION
```

### Step 6 — Open the application

```bash
echo "https://$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontURL`].OutputValue' --output text | sed 's|https://||')"
```

---

## Configuration

### CloudFormation Parameters

| Parameter | Default | Description |
|---|---|---|
| `Environment` | `dev` | Environment tag (`dev`, `staging`, `prod`) |
| `BedrockRegion` | `us-west-2` | Region for Bedrock model calls |
| `DevtoolMode` | `true` | Restrict agent to code/git/PR operations |
| `TargetRepoUrl` | `<xxxx>` | GitHub repository URL the agent operates on |
| `DemoMaskOutput` | `false` | Redact AWS resource IDs in responses |
| `DemoReadOnly` | `false` | Block all write operations |
| `BackendImage` | nginx placeholder | Backend container URI (updated after first build) |
| `CreateAgentCoreRuntime` | `false` | Create AgentCore Runtime resource in the stack |
| `AgentCoreRuntimeArn` | *(empty)* | Use an existing AgentCore Runtime ARN |

### Environment Variables (ECS Task)

| Variable | Source | Description |
|---|---|---|
| `AGENTCORE_RUNTIME_ARN` | CFN output | AgentCore Runtime endpoint |
| `BEDROCK_REGION` | Parameter | Region for Claude intent routing |
| `DEVTOOL_MODE` | Parameter | Enable/disable devtool restrictions |
| `TARGET_REPO_URL` | Parameter | Default repository for agent operations |
| `TASK_LOG_BUCKET` | CFN resource | S3 bucket for session logs |
| `TASK_TABLE_NAME` | CFN resource | DynamoDB table for task memory |

---

## Updating

To deploy code changes after the initial setup:

```bash
# 1. Re-package the changed component (backend, agent, or frontend)
# 2. Upload to S3
aws s3 cp /tmp/backend-source.zip s3://$SOURCE_BUCKET/backend-source.zip

# 3. Trigger the build
aws codebuild start-build --project-name $STACK_NAME-backend-build --region $REGION

# 4. Force ECS to pick up the new image
aws ecs update-service \
  --cluster $STACK_NAME-cluster \
  --service $(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`ECSService`].OutputValue' --output text) \
  --force-new-deployment --region $REGION
```

---

## Cleanup

```bash
# Empty S3 buckets first (CloudFormation cannot delete non-empty buckets)
for bucket in $(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION \
  --query 'Stacks[0].Outputs[?contains(OutputKey,`Bucket`)].OutputValue' --output text); do
  aws s3 rm s3://$bucket --recursive
done

aws cloudformation delete-stack --stack-name $STACK_NAME --region $REGION
```

---

## Security Considerations

- SSM parameters store API keys as plaintext `String` type. For production, use `SecureString` with KMS encryption.
- The ALB is HTTP-only; CloudFront terminates TLS. For end-to-end encryption, add an ACM certificate to the ALB.
- The agent container runs with `ReadOnlyAccess` managed policy. Scope this down for production use.
- Cognito user pool is provisioned but not enforced on the frontend. Add authentication middleware for production.

---

## License

This project is licensed under the MIT-0 License. See the [LICENSE](../LICENSE) file.
