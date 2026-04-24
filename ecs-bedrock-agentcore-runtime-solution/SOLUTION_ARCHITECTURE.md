# ECS Bedrock AgentCore Runtime Solution

A cloud optimization assistant that uses Bedrock AgentCore Runtime with Strands Agents for AWS security assessments, cost optimization, and API operations. Features graceful degradation and dynamic agent discovery.

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                                  AWS Cloud                                        │
│                                                                                   │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────────────────┐      │
│  │  CloudFront   │────▶│  S3 Bucket   │     │  SSM Parameter Store          │      │
│  │  Distribution │     │  (Frontend)  │     │  /{prefix}/cognito/*          │      │
│  └──────┬───────┘     └──────────────┘     │  /{prefix}/agentcore/*        │      │
│         │                                   │  /{prefix}/bedrock/*          │      │
│         │ /api/*                            └──────────┬─────────────────────┘     │
│         ▼                                              │                           │
│  ┌──────────────┐     ┌──────────────────────────────────────────────────────┐    │
│  │     ALB      │────▶│  ECS Fargate Cluster                                  │    │
│  └──────────────┘     │                                                        │    │
│                       │  ┌──────────────────────────────────────────────────┐  │    │
│                       │  │  AgentCore Backend (main.py → agentcore/app.py)  │  │    │
│                       │  │                                                   │  │    │
│                       │  │  ┌─────────────────────────────────────────────┐  │  │    │
│                       │  │  │  Shared Layer                               │  │  │    │
│                       │  │  │  ├── AuthService (Cognito JWT)              │  │  │    │
│                       │  │  │  ├── ConfigService (SSM + env)              │  │  │    │
│                       │  │  │  ├── BedrockModelService                    │  │  │    │
│                       │  │  │  ├── CORS / Logging / Auth Middleware       │  │  │    │
│                       │  │  │  └── Validation & Error Handling            │  │  │    │
│                       │  │  └─────────────────────────────────────────────┘  │  │    │
│                       │  │                                                   │  │    │
│                       │  │  ┌─────────────────────────────────────────────┐  │  │    │
│                       │  │  │  AgentCore Layer                            │  │  │    │
│                       │  │  │  ├── AgentCore Discovery Service            │  │  │    │
│                       │  │  │  ├── AgentCore Invocation Service           │  │  │    │
│                       │  │  │  ├── Strands Agent Discovery Service        │  │  │    │
│                       │  │  │  ├── Strands LLM Orchestrator Service       │  │  │    │
│                       │  │  │  ├── Agent Registry Service                 │  │  │    │
│                       │  │  │  ├── Agent Unregistration Service           │  │  │    │
│                       │  │  │  └── Command Manager                        │  │  │    │
│                       │  │  └─────────────────────────────────────────────┘  │  │    │
│                       │  └──────────────────────────────────────────────────┘  │    │
│                       └──────────────────────────────────────────────────────────┘   │
│                                          │                                          │
│                    ┌─────────────────────┼─────────────────────┐                    │
│                    ▼                     ▼                     ▼                     │
│  ┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐        │
│  │  Strands Agent:       │ │  Strands Agent:       │ │  Strands Agent:       │        │
│  │  AWS API              │ │  WA Security           │ │  Cost Optimization    │        │
│  │  (strands-aws-api)    │ │  (strands-wa-sec)      │ │  (strands-aws-cost)   │        │
│  │                       │ │                        │ │                        │        │
│  │  ┌─────────────────┐ │ │  ┌──────────────────┐ │ │  ┌──────────────────┐ │        │
│  │  │ AWS API MCP      │ │ │  │ WA Security MCP  │ │ │  │ Cost Explorer    │ │        │
│  │  │ Server (local)   │ │ │  │ Server (local)   │ │ │  │ MCP Server       │ │        │
│  │  └─────────────────┘ │ │  └──────────────────┘ │ │  │ + Billing MCP    │ │        │
│  └──────────────────────┘ └──────────────────────┘ │  └──────────────────┘ │        │
│                                                     └──────────────────────┘        │
│                                                                                      │
│  ┌───────────────────────────────────────────────────────────────────────────┐       │
│  │  Bedrock AgentCore Runtime                                                 │       │
│  │  ├── Agent registration and discovery                                      │       │
│  │  ├── Runtime invocation (invoke_agent)                                     │       │
│  │  └── Lifecycle management                                                  │       │
│  └───────────────────────────────────────────────────────────────────────────┘       │
│                                                                                      │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                         │
│  │  Cognito     │     │  CodeBuild   │     │  Bedrock     │                         │
│  │  User Pool   │     │  + Pipeline  │     │  Claude      │                         │
│  └──────────────┘     └──────────────┘     └──────────────┘                         │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

```
User Request Flow:
1. User authenticates via Cognito
2. Frontend sends chat request to /api/chat via CloudFront → ALB
3. Backend validates JWT, routes to Strands LLM Orchestrator
4. Orchestrator discovers available agents via AgentCore Discovery
5. Routes to appropriate Strands Agent based on intent:
   - Security queries → strands-wa-sec agent
   - Cost queries → strands-aws-cost-optimization agent
   - AWS API queries → strands-aws-api agent
6. Agent invokes local MCP server tools for AWS API calls
7. Response streams back to user

Graceful Degradation:
- If AgentCore Runtime unavailable → falls back to minimal mode
- If specific agent unavailable → routes to alternative agent
- If SSM unavailable → falls back to environment variables
```

## Components

| Component | Path | Description |
|-----------|------|-------------|
| AgentCore Backend | `ecs-backend/` | FastAPI server with AgentCore integration, shared services, middleware |
| Frontend | `frontend/` | Vanilla HTML/JS/CSS frontend with prompt templates and agent management |
| Strands Agents | `strands-agents/` | Three containerized Strands agents with embedded MCP servers |
| Deployment Scripts | `deployment-scripts/` | CFN template, deploy scripts, agent registration tools, IAM policies |
| Documentation | `docs/` | Architecture, auth, cross-account, and config guides |

### Backend Architecture

The backend uses a layered architecture:

**Shared Layer** (`ecs-backend/shared/`):
| Module | Purpose |
|--------|---------|
| `services/config_service.py` | SSM Parameter Store config with env fallback |
| `services/auth_service.py` | Cognito JWT validation |
| `services/bedrock_model_service.py` | Bedrock model selection and invocation |
| `services/config_validation_service.py` | Configuration validation |
| `services/error_handler.py` | Centralized error handling |
| `middleware/auth_middleware.py` | Request authentication |
| `middleware/cors_middleware.py` | CORS configuration |
| `middleware/logging_middleware.py` | Request/response logging |
| `utils/parameter_manager.py` | Dynamic SSM parameter prefix management |

**AgentCore Layer** (`ecs-backend/agentcore/`):
| Module | Purpose |
|--------|---------|
| `app.py` | FastAPI app factory (full + minimal modes) |
| `services/agentcore_discovery_service.py` | Discovers registered AgentCore agents |
| `services/agentcore_invocation_service.py` | Invokes agents via AgentCore Runtime |
| `services/strands_agent_discovery_service.py` | Discovers Strands agents and their capabilities |
| `services/strands_llm_orchestrator_service.py` | LLM-based request routing to agents |
| `services/agent_registry_service.py` | Agent registration management |
| `services/agent_unregistration_service.py` | Agent cleanup and deregistration |
| `services/command_manager.py` | Command execution management |

### Strands Agents

| Agent | Path | MCP Server | Capabilities |
|-------|------|------------|--------------|
| AWS API | `strands-agents/strands-aws-api/` | Embedded AWS API MCP | General AWS API operations, resource listing, cross-account access |
| WA Security | `strands-agents/strands-wa-sec/` | Embedded WA Security MCP | Security findings, network/storage security, compliance checks |
| Cost Optimization | `strands-agents/strands-aws-cost-optimization/` | Cost Explorer + Billing MCP | Cost analysis, savings plans, rightsizing, budget management |

Each agent runs as a separate container with:
- Strands Agents framework for LLM orchestration
- Bedrock AgentCore SDK for runtime registration
- Local MCP server for AWS API tool execution
- OpenTelemetry instrumentation

## Technology Stack

- **Runtime**: Python 3.12 on Amazon Linux 2023
- **Framework**: FastAPI + Uvicorn
- **Frontend**: Vanilla HTML/JS/CSS with prompt template system
- **Auth**: Amazon Cognito
- **AI**: Amazon Bedrock (Claude) + Strands Agents + Bedrock AgentCore Runtime
- **Infrastructure**: ECS Fargate, ALB, CloudFront, S3, SSM Parameter Store
- **CI/CD**: CodeBuild + CodePipeline
- **Observability**: OpenTelemetry

## Deployment

```bash
# Deploy the full stack
cd deployment-scripts
python3 deploy_chatbot_stack.py --stack-name coa --region us-east-1

# Register agents with AgentCore
cd deployment-scripts/register-agentcore-runtime
./register_agent.sh

# Or use interactive registration
python3 interactive_agent_registration.py
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PARAM_PREFIX` | SSM parameter path prefix | `coa` |
| `AWS_DEFAULT_REGION` | AWS region | `us-east-1` |
| `BACKEND_MODE` | Backend mode | `agentcore` |
| `ENABLE_STRANDS_AGENTS` | Enable Strands agent support | `true` |
| `ENABLE_AGENTCORE_RUNTIME` | Enable AgentCore Runtime | `true` |
| `ENABLE_GRACEFUL_DEGRADATION` | Enable fallback behavior | `true` |
| `FORCE_REAL_AGENTCORE` | Force full AgentCore mode | `false` |
| `DISABLE_AUTH` | Disable auth for local testing | `false` |
| `LOG_LEVEL` | Logging level | `INFO` |

## Local Development

```bash
cd ecs-backend
pip install -r requirements.txt
export PARAM_PREFIX=coa
export AWS_DEFAULT_REGION=us-east-1
export DISABLE_AUTH=true
uvicorn main:app --reload --port 8000

# Or use Docker Compose
cd ecs-backend/deployment
docker compose up -d
```

See `ecs-backend/LOCAL_TESTING_GUIDE.md` for detailed local development instructions.

## License

MIT-0
