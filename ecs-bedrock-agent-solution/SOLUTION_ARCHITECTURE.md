# ECS Bedrock Agent Solution

A cloud optimization assistant that uses Amazon Bedrock Agents with MCP (Model Context Protocol) servers to perform AWS security assessments and cloud optimization analysis.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AWS Cloud                                      │
│                                                                             │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────────────┐    │
│  │  CloudFront   │────▶│  S3 Bucket   │     │  SSM Parameter Store     │    │
│  │  Distribution │     │  (Frontend)  │     │  /coa/cognito/*          │    │
│  └──────┬───────┘     └──────────────┘     │  /coa/agent/*            │    │
│         │                                   │  /coa/bedrock/*          │    │
│         │ /api/*                            └──────────┬───────────────┘    │
│         ▼                                              │                    │
│  ┌──────────────┐     ┌──────────────────────────────────────────────┐     │
│  │     ALB      │────▶│  ECS Fargate Cluster                         │     │
│  └──────────────┘     │  ┌────────────────────────────────────────┐  │     │
│                       │  │  FastAPI Backend (main.py)              │  │     │
│                       │  │                                         │  │     │
│                       │  │  ┌─────────────┐  ┌──────────────────┐ │  │     │
│                       │  │  │ Auth Service │  │ Config Service   │ │  │     │
│                       │  │  │ (Cognito)   │  │ (SSM + .env)     │ │  │     │
│                       │  │  └─────────────┘  └──────────────────┘ │  │     │
│                       │  │                                         │  │     │
│                       │  │  ┌──────────────────────────────────┐  │  │     │
│                       │  │  │ LLM Orchestrator Service          │  │  │     │
│                       │  │  │ (Routes requests, executes tools) │  │  │     │
│                       │  │  └──────────────┬───────────────────┘  │  │     │
│                       │  │                 │                       │  │     │
│                       │  │       ┌─────────┴─────────┐            │  │     │
│                       │  │       ▼                   ▼            │  │     │
│                       │  │  ┌──────────┐    ┌──────────────┐     │  │     │
│                       │  │  │ Bedrock  │    │ MCP Client   │     │  │     │
│                       │  │  │ Agent    │    │ Service      │     │  │     │
│                       │  │  │ Service  │    └──────────────┘     │  │     │
│                       │  │  └────┬─────┘                         │  │     │
│                       │  └───────┼───────────────────────────────┘  │     │
│                       └──────────┼──────────────────────────────────┘     │
│                                  │                                         │
│                                  ▼                                         │
│  ┌───────────────────────────────────────────────────────────────────┐     │
│  │  Amazon Bedrock                                                    │     │
│  │  ┌─────────────────┐    ┌──────────────────────────────────────┐  │     │
│  │  │ Bedrock Agent   │───▶│ MCP Servers (Action Groups)          │  │     │
│  │  │ (WA Security)   │    │  ├── WA Security MCP Server          │  │     │
│  │  │                 │    │  └── AWS API MCP Server               │  │     │
│  │  └─────────────────┘    └──────────────────────────────────────┘  │     │
│  │                                                                    │     │
│  │  ┌─────────────────┐                                              │     │
│  │  │ Claude (Converse│    Foundation model for LLM orchestration    │     │
│  │  │ API)            │                                              │     │
│  │  └─────────────────┘                                              │     │
│  └───────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│  ┌──────────────┐     ┌──────────────┐                                     │
│  │  Cognito     │     │  CodeBuild   │     CI/CD pipeline for              │
│  │  User Pool   │     │  + CodePipeline│    backend & frontend builds      │
│  └──────────────┘     └──────────────┘                                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

```
User Request Flow:
1. User authenticates via Cognito (email/password)
2. React frontend sends chat message to /api/chat via CloudFront → ALB
3. FastAPI backend validates JWT token (AuthService)
4. LLM Orchestrator routes the request:
   a. Direct Bedrock Converse API call for general queries
   b. Bedrock Agent invocation for security assessments
5. Bedrock Agent orchestrates MCP server tool calls
6. Response streams back through WebSocket or HTTP response

Configuration Flow:
1. CloudFormation deploys SSM parameters under /coa/ prefix
2. ConfigService reads SSM at startup, falls back to environment variables
3. Agent IDs, Cognito config, and Bedrock settings stored in SSM
```

## Components

| Component | Path | Description |
|-----------|------|-------------|
| FastAPI Backend | `ecs-backend/` | Main API server with chat, health, and WebSocket endpoints |
| React Frontend | `frontend-react/` | CloudScape-based chat UI with Cognito auth |
| Legacy Frontend | `frontend/` | Original Vite + React frontend (CloudScape) |
| Bedrock Agents | `bedrock-agents/` | Agent configurations for WA security assessments |
| Deployment Scripts | `deployment-scripts/` | CFN template, Python deploy scripts, CodeBuild buildspecs |
| Documentation | `docs/` | Architecture diagrams, auth guides, config references |

### Backend Services

| Service | File | Purpose |
|---------|------|---------|
| `LLMOrchestratorService` | `services/llm_orchestrator_service.py` | Routes requests to Bedrock Converse API or Agent, discovers MCP tools |
| `BedrockAgentService` | `services/bedrock_agent_service.py` | Invokes Bedrock Agent for security assessments |
| `ConfigService` | `services/config_service.py` | SSM Parameter Store config with .env fallback |
| `AuthService` | `services/auth_service.py` | Cognito JWT token validation |
| `AWSConfigService` | `services/aws_config_service.py` | AWS account and region configuration |
| `MCPClientService` | `services/mcp_client_service.py` | MCP tool discovery (demo mode) |

### Bedrock Agent Configurations

| Agent | Path | Description |
|-------|------|-------------|
| WA Security (Multi-MCP) | `bedrock-agents/wa-security-agent-multi-mcps/` | Enhanced agent with parallel MCP orchestration, connection pooling, tool discovery |
| WA Security (Single MCP) | `bedrock-agents/wa-security-agent-single-wa-sec-mcp/` | Simpler agent using single WA Security MCP server |

## Technology Stack

- **Runtime**: Python 3.12 on Amazon Linux 2023
- **Framework**: FastAPI + Uvicorn
- **Frontend**: React 18 + Vite + CloudScape Design System
- **Auth**: Amazon Cognito
- **AI**: Amazon Bedrock (Claude via Converse API + Bedrock Agents)
- **Infrastructure**: ECS Fargate, ALB, CloudFront, S3, SSM Parameter Store
- **CI/CD**: CodeBuild + CodePipeline

## Deployment

```bash
# Deploy the full stack
cd deployment-scripts
python3 deploy_chatbot_stack.py --stack-name coa --region us-east-1

# Deploy frontend separately
python3 deploy_frontend.py --stack-name coa --region us-east-1
```

The CloudFormation template (`cloud-optimization-assistant-0.1.0.yaml`) provisions:
- VPC with public/private subnets
- ECS Fargate cluster and service
- ALB with HTTPS listener
- CloudFront distribution
- S3 bucket for frontend assets
- Cognito User Pool and App Client
- CodeBuild projects for backend and frontend
- CodePipeline for CI/CD
- SSM parameters for configuration
- IAM roles with least-privilege policies

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SSM_PREFIX` | SSM parameter path prefix | `/coa` |
| `AWS_DEFAULT_REGION` | AWS region | `us-east-1` |
| `ENHANCED_SECURITY_AGENT_ID` | Bedrock Agent ID | (from SSM) |
| `ENHANCED_SECURITY_AGENT_ALIAS_ID` | Bedrock Agent Alias ID | (from SSM) |
| `BEDROCK_REGION` | Region for Bedrock API calls | `us-east-1` |

## Local Development

```bash
cd ecs-backend
pip install -r requirements.txt
export SSM_PREFIX=/coa
export AWS_DEFAULT_REGION=us-east-1
uvicorn main:app --reload --port 8000
```

## License

MIT-0
