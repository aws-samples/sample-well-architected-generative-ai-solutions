# Deployment Scripts

Deployment automation for the Cloud Optimization Assistant (COA) platform using Bedrock AgentCore Runtime.

## Architecture Overview

The platform deploys as a single CloudFormation stack containing:
- **ECS Fargate** backend running the AgentCore runtime (`ecs-backend/`)
- **S3 + CloudFront** frontend (`frontend/`)
- **Cognito** authentication (user pool, clients, identity pool)
- **CodePipeline + CodeBuild** CI/CD for backend and frontend
- **VPC, ALB, ECR** networking and container infrastructure
- **SSM Parameters** for centralized configuration
- **IAM roles** for Bedrock AgentCore Runtime access

## Quick Start

### Deploy the Stack

```bash
python3 deploy_chatbot_stack.py \
  --stack-name coa \
  --region us-east-1 \
  --environment prod
```

This creates the S3 source bucket, uploads the CFN template, and deploys the full stack.

### Register AgentCore Agents

After the stack is deployed, register your Strands agents with the COA backend:

```bash
cd register-agentcore-runtime
./register_agent.sh
```

The interactive tool will:
- Auto-discover deployed Bedrock AgentCore runtimes
- Show registered vs unregistered agents
- Guide you through registration
- Verify chatbot integration

## Directory Contents

```
deployment-scripts/
├── cloud-optimization-assistant-0.1.4.yaml  # CloudFormation template
├── deploy_chatbot_stack.py                  # Main deployment script
├── buildspecs/
│   ├── backend-buildspec.yml                # CodeBuild: Docker build → ECR → ECS
│   └── frontend-buildspec.yml               # CodeBuild: frontend → S3 → CloudFront
├── register-agentcore-runtime/              # AgentCore agent registration tools
│   ├── register_agent.sh                    # One-click interactive registration
│   ├── interactive_agent_registration.py    # Interactive Python tool
│   ├── register_manual_agent.py             # CLI registration
│   ├── register_deployed_agents.py          # Batch registration
│   └── discover_agents.py                   # Discovery and status
├── generate_remote_role_stack.py            # Cross-account role CFN generator
├── generate_cognito_ssm_parameters.py       # Cognito SSM parameter setup
├── get_cognito_config.py                    # Retrieve Cognito config from SSM
├── update_cognito_callbacks.py              # Update Cognito callback URLs
├── validate_iam_and_update_template.py      # IAM validation utility
├── policies/                                # IAM policy templates for AgentCore
└── requirements.txt                         # Python dependencies
```

## Deployment Flow

1. **`deploy_chatbot_stack.py`** creates S3 bucket and deploys CFN stack
2. **CodePipeline** triggers on source.zip upload to S3:
   - **Backend build**: `ecs-backend/` → Docker image → private ECR → ECS deploy
   - **Frontend build**: `frontend/` → config.js injection → S3 → CloudFront invalidation
3. **Register agents**: `register-agentcore-runtime/register_agent.sh`

## Utilities

### Cognito Configuration

```bash
# Get all Cognito config from SSM
python3 get_cognito_config.py

# Get specific parameter
python3 get_cognito_config.py --parameter user_pool_id

# Export as environment variables
eval $(python3 get_cognito_config.py --format env)
```

### Cross-Account Roles

```bash
# Generate CFN template for cross-account read-only roles
python3 generate_remote_role_stack.py
```

### Update Cognito Callbacks

```bash
# Update callback URLs after CloudFront deployment
python3 update_cognito_callbacks.py
```

## Prerequisites

- AWS CLI configured with appropriate permissions
- Python 3.8+ with dependencies: `pip install -r requirements.txt`
- Access to Amazon Bedrock and AgentCore services
- Docker (for local builds)

## Required IAM Permissions

- `cloudformation:*` — Stack management
- `bedrock:*` — Bedrock model access
- `bedrock-agentcore:*` — AgentCore Runtime operations
- `ecs:*` — ECS cluster and service management
- `ecr:*` — Container registry
- `s3:*` — Source and frontend buckets
- `cognito-idp:*` — User pool management
- `iam:CreateRole`, `iam:AttachRolePolicy` — IAM role management
- `ssm:PutParameter`, `ssm:GetParameter` — Parameter Store
