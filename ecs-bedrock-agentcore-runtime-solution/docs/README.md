# Cloud Optimization Assistant - Documentation

Documentation for the Cloud Optimization Assistant (COA) platform using Bedrock AgentCore Runtime.

## Documentation Index

### Core Documentation
- **[Architecture Diagram](architecture_diagram.html)** — Interactive HTML diagram showing system architecture
- **[Cognito Centralization Guide](cognito-centralization-guide.md)** — Shared Cognito user pool implementation
- **[Cross-Account Role Setup](cross-account-role-setup.md)** — Cross-account IAM role deployment and security
- **[Parameter Store Configuration](parameter-store-configuration.md)** — Parameter Store usage and configuration management

### Deployment
- **[Deployment Scripts](../deployment-scripts/README.md)** — Automated deployment with `deploy_chatbot_stack.py`
- **[AgentCore Registration](../deployment-scripts/register-agentcore-runtime/README.md)** — Register Strands agents with the platform

### Backend
- **[ECS Backend](../ecs-backend/)** — AgentCore runtime backend (FastAPI on ECS Fargate)
- **[Local Testing Guide](../ecs-backend/LOCAL_TESTING_GUIDE.md)** — Run the backend locally

### Frontend
- **[Frontend](../frontend/)** — Web interface served via S3 + CloudFront

### Strands Agents
- **[strands-aws-api](../strands-agents/strands-aws-api/)** — AWS API agent
- **[strands-aws-cost-optimization](../strands-agents/strands-aws-cost-optimization/)** — Cost optimization agent
- **[strands-wa-sec](../strands-agents/strands-wa-sec/)** — Well-Architected security agent

## Component Overview

| Component | Location | Description |
|---|---|---|
| ECS Backend | `ecs-backend/` | AgentCore runtime with Strands agent discovery and invocation |
| Frontend | `frontend/` | Web interface with Cognito auth |
| Strands Agents | `strands-agents/` | Three Strands-based agents for AWS operations |
| Deployment | `deployment-scripts/` | CFN template, CI/CD buildspecs, registration tools |
| Docs | `docs/` | Architecture, auth, cross-account, and config guides |

## Quick Navigation

### Getting Started
1. Read the [Deployment Scripts README](../deployment-scripts/README.md)
2. Deploy: `python3 deployment-scripts/deploy_chatbot_stack.py --stack-name coa --region us-east-1`
3. Register agents: `cd deployment-scripts/register-agentcore-runtime && ./register_agent.sh`

### For Security Teams
- [Cross-Account Role Setup](cross-account-role-setup.md)
- [Cognito Centralization Guide](cognito-centralization-guide.md)

### For DevOps
- [Deployment Scripts](../deployment-scripts/README.md)
- [Parameter Store Configuration](parameter-store-configuration.md)
