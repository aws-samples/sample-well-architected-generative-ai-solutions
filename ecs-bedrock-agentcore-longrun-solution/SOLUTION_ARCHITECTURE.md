# ECS Bedrock AgentCore Long-Running Solution

An async conversational orchestrator that dispatches long-running tasks to Bedrock AgentCore Runtimes (powered by Kiro CLI) and streams results back to users via WebSocket. Designed for tasks that take seconds to minutes — infrastructure scans, code generation, incident response.

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                                  AWS Cloud                                    │
│                                                                               │
│  ┌──────────────┐     ┌──────────────┐                                       │
│  │  CloudFront   │────▶│  S3 Bucket   │                                       │
│  │  Distribution │     │  (React App) │                                       │
│  └──────┬───────┘     └──────────────┘                                       │
│         │                                                                     │
│         │ /api/*, /ws                                                         │
│         ▼                                                                     │
│  ┌──────────────┐     ┌──────────────────────────────────────────────┐       │
│  │     ALB      │────▶│  ECS Fargate — Orchestrator Service           │       │
│  └──────────────┘     │                                                │       │
│                       │  ┌──────────────────────────────────────────┐  │       │
│                       │  │  FastAPI Orchestrator (main.py)          │  │       │
│                       │  │                                          │  │       │
│                       │  │  ┌────────────────┐  ┌───────────────┐  │  │       │
│                       │  │  │ WebSocket      │  │ REST API      │  │  │       │
│                       │  │  │ Handler        │  │ /health, /    │  │  │       │
│                       │  │  └───────┬────────┘  └───────────────┘  │  │       │
│                       │  │          │                               │  │       │
│                       │  │          ▼                               │  │       │
│                       │  │  ┌────────────────────────────────────┐ │  │       │
│                       │  │  │ Intent Service                     │ │  │       │
│                       │  │  │ (Bedrock Claude — 3-tier routing)  │ │  │       │
│                       │  │  │                                    │ │  │       │
│                       │  │  │ Tier 1: Decline (non-AWS topics)   │ │  │       │
│                       │  │  │ Tier 2: Answer directly (knowledge)│ │  │       │
│                       │  │  │ Tier 3: Route to AgentCore Runtime │ │  │       │
│                       │  │  └───────────────┬────────────────────┘ │  │       │
│                       │  │                  │                       │  │       │
│                       │  │                  ▼                       │  │       │
│                       │  │  ┌────────────────────────────────────┐ │  │       │
│                       │  │  │ AgentCore Service                  │ │  │       │
│                       │  │  │ (Async dispatch + polling)         │ │  │       │
│                       │  │  │                                    │ │  │       │
│                       │  │  │ 1. invoke_agent() → task_id        │ │  │       │
│                       │  │  │ 2. Poll for completion             │ │  │       │
│                       │  │  │ 3. Push result via WebSocket       │ │  │       │
│                       │  │  └───────────────┬────────────────────┘ │  │       │
│                       │  └──────────────────┼──────────────────────┘  │       │
│                       └─────────────────────┼────────────────────────┘       │
│                                             │                                 │
│                                             ▼                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │  Bedrock AgentCore Runtime                                            │    │
│  │                                                                        │    │
│  │  ┌──────────────────────────────────────────────────────────────────┐  │    │
│  │  │  Kiro CLI + MCP Wrapper (wrapper.py)                             │  │    │
│  │  │                                                                   │  │    │
│  │  │  ┌─────────────────┐  ┌──────────────────┐  ┌────────────────┐  │  │    │
│  │  │  │ BedrockAgentCore│  │ Kiro CLI (ACP)   │  │ AWS API MCP    │  │  │    │
│  │  │  │ App SDK         │  │ Process Manager  │  │ Server (uvx)   │  │  │    │
│  │  │  │ (HTTP/ACP)      │  │                  │  │                │  │  │    │
│  │  │  └────────┬────────┘  └────────┬─────────┘  └────────────────┘  │  │    │
│  │  │           │                    │                                  │  │    │
│  │  │           │  invoke_agent()    │  kiro-cli chat                  │  │    │
│  │  │           └────────────────────┘                                  │  │    │
│  │  └──────────────────────────────────────────────────────────────────┘  │    │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                  │
│  │  Cognito     │     │  CodeBuild   │     │  Bedrock     │                  │
│  │  User Pool   │     │  + Pipeline  │     │  Claude      │                  │
│  └──────────────┘     └──────────────┘     └──────────────┘                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

```
User Request Flow (Async):
1. User connects via WebSocket (/ws)
2. User sends message (e.g., "Check my CloudFormation stacks")
3. Intent Service classifies via Bedrock Claude:
   - Tier 1 (non-AWS): Politely declines
   - Tier 2 (knowledge): Answers directly, no agent needed
   - Tier 3 (account action): Routes to AgentCore Runtime
4. For Tier 3:
   a. Orchestrator sends immediate acknowledgment ("Sure, let me check...")
   b. Dispatches task to AgentCore Runtime via invoke_agent()
   c. Task runs asynchronously (Kiro CLI executes via MCP tools)
   d. Orchestrator polls for completion
   e. When done, pushes result via WebSocket
5. User can request brief summary or full detail

Parallel Execution:
- Multiple tasks run simultaneously via asyncio.create_task()
- Each task gets a unique task_id for tracking
- Results arrive independently as they complete

Demo/Sandbox Mode:
- DEMO_READ_ONLY=true: Restricts to read-only AWS operations
- DEMO_MASK_OUTPUT=true: Masks resource IDs and names in output
```

## Components

| Component | Path | Description |
|-----------|------|-------------|
| Orchestrator Backend | `ecs-backend/` | FastAPI + WebSocket server with intent parsing and async task dispatch |
| React Frontend | `frontend-react/` | CloudScape-based chat UI (build with `npm run build`) |
| AgentCore Runtime | `kiro-agentcore-runtime/` | Kiro CLI wrapper registered as Bedrock AgentCore Runtime |
| Deployment Scripts | `deployment-scripts/` | CFN template, deploy script, CodeBuild buildspecs |
| Documentation | `docs/` | Architecture documentation |

### Orchestrator Services

| Service | File | Purpose |
|---------|------|---------|
| `parse_intent()` | `orchestrator/services/intent_service.py` | 3-tier intent classification using Bedrock Claude |
| `invoke_agentcore_runtime()` | `orchestrator/services/agentcore_service.py` | Async AgentCore Runtime invocation with polling and output masking |

### AgentCore Runtime (Kiro CLI Wrapper)

The `kiro-agentcore-runtime/` container runs:
- `wrapper.py` — HTTP/ACP wrapper using `bedrock-agentcore` SDK
- Kiro CLI — AI coding assistant with MCP tool access
- AWS API MCP Server — Provides AWS API tools to Kiro CLI
- AWS CLI — For direct AWS operations

The wrapper:
1. Receives `invoke_agent()` calls from the orchestrator
2. Spawns a Kiro CLI ACP process
3. Passes the user prompt to Kiro CLI
4. Collects the response and returns it

## Technology Stack

- **Runtime**: Python 3.12 on Amazon Linux 2023
- **Framework**: FastAPI + Uvicorn + WebSocket
- **Frontend**: React 18 + Vite + CloudScape Design System
- **Auth**: Amazon Cognito
- **AI**: Amazon Bedrock Claude (intent parsing) + Kiro CLI (task execution)
- **Infrastructure**: ECS Fargate (2 services), ALB, CloudFront, S3
- **CI/CD**: CodeBuild + CodePipeline (3 buildspecs: backend, frontend, agent)

## Deployment

The stack is fully self-contained — all resources are managed by CloudFormation with zero external dependencies.

```bash
cd deployment-scripts
python3 deploy.py \
  --stack-name agentcore-longrun \
  --region us-west-2 \
  --environment dev \
  --demo-mask-output true \
  --demo-read-only true
```

Deploy phases: `infra` → `build` → `update` (or `all` for full deploy).

After deployment, set the API key:
```bash
aws ssm put-parameter \
  --name /agentcore-longrun/kiro-api-key \
  --value "your-api-key" \
  --type SecureString --overwrite
```

The CloudFormation template (`agentcore-longrun-orchestrator-0.1.0.yaml`) provisions:
- VPC with 2 public subnets, IGW, route table
- ECS Fargate cluster + service + task definition
- ALB with WebSocket support + CloudFront distribution
- S3 buckets: static assets, source code, task logs
- Cognito User Pool + client
- 3 CodeBuild projects (backend, frontend, agent)
- Bedrock AgentCore Runtime (conditional)
- SSM Parameter for Kiro API key
- IAM roles for ECS tasks, builds, and AgentCore

## Environment Variables

### Orchestrator

| Variable | Description | Default |
|----------|-------------|---------|
| `AGENTCORE_RUNTIME_ARN` | ARN of the AgentCore Runtime | (required) |
| `BEDROCK_REGION` | Region for Bedrock Claude calls | `us-west-2` |
| `AGENTCORE_REGION` | Region for AgentCore Runtime | `us-west-2` |
| `MODEL_ID` | Bedrock model for intent parsing | `anthropic.claude-3-haiku-20240307-v1:0` |
| `DEMO_READ_ONLY` | Restrict to read-only operations | `false` |
| `DEMO_MASK_OUTPUT` | Mask resource IDs in output | `false` |
| `TASK_LOG_BUCKET` | S3 bucket for session/task logging | (set by CFN) |
| `PORT` | Server port | `8000` |

### AgentCore Runtime

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | HTTP port for ACP wrapper | `8080` |
| `AWS_DEFAULT_REGION` | AWS region | `us-west-2` |

## Task Logging

Sessions and task results are persisted to S3 automatically:

- **Trigger**: On task completion and WebSocket disconnect
- **Storage**: `s3://{stack}-logs-{account}/sessions/{date}/{session_id}.json`
- **Viewer**: `https://{cloudfront}/task-log.html`
- **API**:
  - `GET /api/orchestrator/sessions?date=YYYY-MM-DD` — list sessions
  - `GET /api/orchestrator/sessions/{id}` — fetch session detail

Each session JSON contains chat history, task list with status/timing, and full results.

## Local Development

```bash
# Orchestrator
cd ecs-backend
pip install -r requirements.txt
export AGENTCORE_RUNTIME_ARN="arn:aws:bedrock-agentcore:us-west-2:ACCOUNT:runtime/ID"
export BEDROCK_REGION="us-west-2"
uvicorn main:app --reload --port 8000

# Frontend
cd frontend-react
npm install
npm run dev
```

## Testing

```bash
cd ecs-backend
pip install -r tests/requirements-test.txt
pytest
```

## License

MIT-0
