# ECS Bedrock AgentCore Long-Running Solution

An async conversational orchestrator that dispatches long-running tasks to Bedrock AgentCore Runtimes and streams results back to users via WebSocket.

## Architecture

```
┌─────────────────┐     WebSocket      ┌──────────────────────┐
│  CloudScape UI  │◄──────────────────►│  ECS Fargate         │
│  (CloudFront)   │                    │  FastAPI Orchestrator │
└─────────────────┘                    └──────────┬───────────┘
                                                  │
                                    ┌─────────────┼─────────────┐
                                    │             │             │
                              ┌─────▼─────┐ ┌────▼────┐ ┌─────▼─────┐
                              │  Bedrock  │ │AgentCore│ │  AgentCore │
                              │  Claude   │ │Runtime 1│ │  Runtime N │
                              │  (Intent) │ │         │ │            │
                              └───────────┘ └─────────┘ └────────────┘
```

## Key Features

- **Async task dispatch** — User sends request, AI acknowledges immediately, runs task in background
- **Parallel execution** — Multiple tasks run simultaneously via `asyncio.create_task()`
- **Progressive disclosure** — Brief summary first, full detail on request
- **WebSocket streaming** — Real-time push when results arrive
- **AgentCore Runtime integration** — Tasks are dispatched to Bedrock AgentCore Runtimes

## User Experience Flow

```
User: Check my CloudFormation stacks
AI:   Sure, let me check that for you.
      ... (runs in background via AgentCore Runtime) ...
AI:   Result ready: Hello World!
      Would you like the full detail?
User: yes
AI:   [full detail response]
```

## Components

| Component | Description |
|-----------|-------------|
| `ecs-backend/` | FastAPI orchestrator with WebSocket, intent parsing, AgentCore invocation |
| `frontend-react/` | CloudScape-based chat UI (pre-built dist/) |
| `deployment-scripts/` | CloudFormation template, deploy script, buildspecs |
| `docs/` | Architecture documentation |

## Prerequisites

- AWS Account with Bedrock access
- A deployed AgentCore Runtime (ARN required)
- Python 3.11+
- Docker (for container builds)

## Deployment

The stack is fully self-contained — all resources (including source bucket, task log bucket, and SSM parameter for the API key) are managed by CloudFormation.

```bash
cd deployment-scripts

# Full deploy (infra → build → update)
python deploy.py \
  --stack-name agentcore-longrun \
  --region us-west-2 \
  --environment dev \
  --demo-mask-output true \
  --demo-read-only true

# Phase-by-phase
python deploy.py --stack-name agentcore-longrun --phase infra   # Create stack
python deploy.py --stack-name agentcore-longrun --phase build   # Build images
python deploy.py --stack-name agentcore-longrun --phase update  # Switch to real images
```

After deployment, update the API key:
```bash
aws ssm put-parameter \
  --name /agentcore-longrun/kiro-api-key \
  --value "your-api-key" \
  --type SecureString \
  --overwrite \
  --region us-west-2
```

### Stack Resources

The CloudFormation template provisions:

| Category | Resources |
|----------|-----------|
| Networking | VPC, 2 public subnets, IGW, route table |
| Compute | ECS Fargate cluster + service + task definition |
| Load Balancing | ALB with WebSocket support |
| CDN | CloudFront distribution |
| Storage | S3 static bucket, S3 source bucket, S3 task log bucket |
| Auth | Cognito User Pool + client |
| Build | 3 CodeBuild projects (backend, frontend, agent) |
| AI | Bedrock AgentCore Runtime (conditional) |
| Secrets | SSM Parameter for Kiro API key |
| IAM | Task role, execution role, build roles, runtime role |

## Local Development

```bash
cd ecs-backend
pip install -r requirements.txt
export AGENTCORE_RUNTIME_ARN="arn:aws:bedrock-agentcore:us-west-2:ACCOUNT:runtime/ID"
export BEDROCK_REGION="us-west-2"
uvicorn main:app --reload --port 8000
```

## Testing

```bash
cd ecs-backend
pip install -r tests/requirements-test.txt
pytest
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AGENTCORE_RUNTIME_ARN` | ARN of the AgentCore Runtime | (required) |
| `BEDROCK_REGION` | Region for Bedrock model calls | us-west-2 |
| `AGENTCORE_REGION` | Region for AgentCore Runtime | us-west-2 |
| `MODEL_ID` | Bedrock model for intent parsing | anthropic.claude-3-haiku-20240307-v1:0 |
| `DEMO_READ_ONLY` | Restrict to read-only operations | false |
| `DEMO_MASK_OUTPUT` | Mask resource IDs in output | false |
| `TASK_LOG_BUCKET` | S3 bucket for session/task logging | (set by CFN) |
| `PORT` | Server port | 8000 |

## Task Logging

Sessions and task results are automatically saved to S3 when a WebSocket disconnects or a task completes.

- **Storage**: `s3://{stack}-logs-{account}/sessions/{date}/{session_id}.json`
- **View**: `https://{cloudfront}/task-log.html`
- **API**: `GET /api/orchestrator/sessions?date=2026-04-27`
- **API**: `GET /api/orchestrator/sessions/{session_id}`

## License

MIT-0
