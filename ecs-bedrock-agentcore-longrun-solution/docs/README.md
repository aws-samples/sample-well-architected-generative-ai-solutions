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
- Python 3.12+
- Docker (for container builds)

## Deployment

```bash
cd deployment-scripts
python deploy.py \
  --stack-name agentcore-longrun \
  --region us-west-2 \
  --runtime-arn arn:aws:bedrock-agentcore:us-west-2:ACCOUNT:runtime/YOUR_RUNTIME_ID
```

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
| `PORT` | Server port | 8000 |

## License

MIT-0
