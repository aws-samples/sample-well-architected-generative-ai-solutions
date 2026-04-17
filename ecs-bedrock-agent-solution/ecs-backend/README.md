# ECS Backend — Architecture & Integration Guide

## Overview

The ECS Backend is a **FastAPI** application that serves as the API layer for the Cloud Optimization MCP Web Interface. It integrates with **Amazon Bedrock** (Agents and Foundation Models) and **MCP (Model Context Protocol)** servers to provide AI-powered AWS cloud optimization assessments.

The backend runs on **Amazon ECS** and communicates with the frontend via REST endpoints and WebSocket connections for real-time chat.

## Architecture

```
┌─────────────┐      ┌──────────────────────────────────────────────────┐
│  Frontend    │      │  ECS Backend (FastAPI)                          │
│  (HTML/JS)  │◄────►│                                                  │
│             │ REST │  ┌──────────────┐   ┌─────────────────────────┐  │
│             │  +   │  │  main.py     │   │  LLM Orchestrator       │  │
│             │  WS  │  │  API Routes  │──►│  (Claude 3 Haiku)       │  │
└─────────────┘      │  │  WebSocket   │   │  - Intent analysis      │  │
                     │  └──────────────┘   │  - Tool routing         │  │
                     │                     │  - Response generation   │  │
                     │                     └──────────┬──────────────┘  │
                     │                                │                 │
                     │         ┌───────────────┬──────┴───────┐        │
                     │         ▼               ▼              ▼        │
                     │  ┌─────────────┐ ┌───────────┐ ┌────────────┐  │
                     │  │ Bedrock     │ │ MCP Client│ │ Config     │  │
                     │  │ Agent Svc   │ │ Service   │ │ Service    │  │
                     │  │ (WA Agent)  │ │           │ │ (SSM/.env) │  │
                     │  └──────┬──────┘ └───────────┘ └────────────┘  │
                     │         │                                       │
                     └─────────┼───────────────────────────────────────┘
                               │
               ┌───────────────┼───────────────┐
               ▼               ▼               ▼
        ┌────────────┐  ┌────────────┐  ┌────────────┐
        │  Bedrock   │  │ Security   │  │ AWS API    │
        │  Agent     │  │ MCP Server │  │ MCP Server │
        │  Runtime   │  │            │  │            │
        └────────────┘  └────────────┘  └────────────┘
```

## Components

### API Layer (`main.py`)

The FastAPI application exposes the following endpoints:

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/health` | GET | No | Health check for ECS/ALB monitoring |
| `/api/chat` | POST | Yes | REST chat endpoint |
| `/ws/{session_id}` | WS | No | WebSocket real-time chat |
| `/api/sessions/{id}/history` | GET | Yes | Chat session history |
| `/api/session/{id}/info` | GET | Yes | Session info with available tools |
| `/api/session/{id}/initialize` | POST | Yes | Initialize session with tool discovery |
| `/api/mcp/tools` | GET | Yes | List available MCP tools |
| `/api/aws-config` | GET | No | Current AWS configuration |
| `/api/aws-config` | POST | No | Update AWS configuration |
| `/api/config` | GET | Yes | Application config (sensitive values masked) |
| `/api/config/refresh` | POST | Yes | Refresh SSM config cache |
| `/api/config/ssm/parameters` | GET | Yes | List SSM parameters |

**Authentication** is handled via HTTP Bearer tokens, validated through Amazon Cognito (currently returns a demo user for development).

### Services

#### LLM Orchestrator (`services/llm_orchestrator_service.py`)

The primary intelligence layer. Uses a **two-pass LLM approach**:

1. **Analysis Pass** — Sends the user message to **Claude 3 Haiku** to determine intent and select appropriate tools
2. **Execution Pass** — Calls selected MCP tools and collects results
3. **Response Pass** — Feeds tool results back to the LLM to generate a human-readable response

**Fallback mode:** When Bedrock is unavailable, falls back to rule-based keyword matching:
- Security keywords → `CheckSecurityServices`
- Storage/encryption keywords → `CheckStorageEncryption`
- Network keywords → `CheckNetworkSecurity`

#### Bedrock Agent Service (`services/bedrock_agent_service.py`)

Integrates with a pre-configured **Amazon Bedrock Agent** (Well-Architected Security Agent) via the `InvokeAgent` API.

**Capabilities:**
- Streaming response processing
- **Return Control** handling — when the agent delegates tool execution back to the application
- JSON extraction from markdown responses for structured data
- Human-readable summary generation via **Claude 3.7 Sonnet**

**Supported MCP Action Groups:**

| Action Group | Functions | Description |
|---|---|---|
| `security-mcp-server` | `CheckSecurityServices` | Check GuardDuty, SecurityHub, Inspector status |
| | `GetSecurityFindings` | Retrieve security findings by service |
| | `CheckStorageEncryption` | S3/EBS encryption compliance check |
| `aws-api-mcp-server-public` | Generic | AWS API execution (placeholder) |

#### Config Service (`services/config_service.py`)

Manages application configuration with a priority chain:

1. **AWS SSM Parameter Store** (highest priority)
2. **Environment variables / `.env` file**
3. **Defaults**

Includes caching, automatic SSM prefix-based parameter discovery, and cache refresh capabilities. See [CONFIG_MANAGEMENT.md](./CONFIG_MANAGEMENT.md) for details.

#### Auth Service (`services/auth_service.py`)

Amazon Cognito integration for JWT token verification. Currently returns a demo user for development purposes.

#### AWS Config Service (`services/aws_config_service.py`)

Manages AWS credential configuration via STS. Supports cross-account role assumption for multi-account environments.

#### MCP Client Service (`services/mcp_client_service.py`)

Model Context Protocol client for tool discovery and execution. Operates in demo mode by default, returning a single demo tool.

#### Bedrock Chat Service (`services/bedrock_chat_service.py`)

Minimal scaffold for direct Bedrock chat without orchestration. Currently an echo service — reserved for future direct-model integration.

### Models (`models/chat_models.py`)

Pydantic models used across all services:

- **`ChatMessage`** — User or assistant message with optional tool executions
- **`ChatSession`** — Session container with message history and context
- **`ToolExecution`** — Record of a tool call (name, parameters, result, status)
- **`ToolExecutionStatus`** — Enum: `SUCCESS`, `ERROR`, `PENDING`
- **`BedrockResponse`** — Unified response model with structured data and human summary

## Bedrock Integration Summary

| Integration | API | Model / Agent | Status |
|---|---|---|---|
| LLM Orchestrator | `invoke_model` | Claude 3 Haiku | ✅ Functional |
| WA Security Agent | `invoke_agent` | Custom Bedrock Agent | ✅ Wired (needs config) |
| Summary Generation | `invoke_model` | Claude 3.7 Sonnet | ✅ Functional |
| Security MCP Tools | Return Control | 3 security functions | ⚠️ Mock responses |
| AWS API MCP Tools | Return Control | Generic AWS API calls | ⚠️ Placeholder |
| Direct Chat | `bedrock-runtime` | N/A | 🔲 Scaffold |

## Configuration

### Required Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AWS_DEFAULT_REGION` | AWS region | `us-east-1` |
| `USER_POOL_ID` | Cognito User Pool ID | — |
| `WEB_APP_CLIENT_ID` | Cognito App Client ID | — |
| `USE_ENHANCED_AGENT` | Enable Bedrock Agent service | `false` |

### SSM Parameters

| Parameter Path | Maps To |
|---|---|
| `/coa/agent/wa-security-agent/agent-id` | `ENHANCED_SECURITY_AGENT_ID` |
| `/coa/agent/wa-security-agent/alias-id` | `ENHANCED_SECURITY_AGENT_ALIAS_ID` |

## Running Locally

```bash
cd ecs-bedrock-agent-solution/ecs-backend

# Install dependencies
pip install -r requirements.txt

# Set required env vars
export AWS_DEFAULT_REGION=us-east-1
export USER_POOL_ID=your-pool-id
export WEB_APP_CLIENT_ID=your-client-id

# Run
python main.py
# Server starts on http://0.0.0.0:8000
```

## Testing

```bash
pip install pytest pytest-cov pytest-asyncio httpx

# Run all tests with coverage
python -m pytest tests/ --cov=. --cov-report=term-missing -v

# Current coverage: 90.41% (187 tests)
```

Coverage is enforced at 85% minimum via `pyproject.toml`.

## Dependencies

See [requirements.txt](./requirements.txt) for the full list. Key dependencies:

- **FastAPI** — Web framework
- **boto3** — AWS SDK (Bedrock, SSM, STS, Cognito)
- **Pydantic** — Data validation and models
- **websockets** — Real-time WebSocket support
- **python-jose / PyJWT** — JWT token handling
