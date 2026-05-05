# AgentCore Memory Solution

Deploy [Amazon Bedrock AgentCore Memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html) as a standalone CloudFormation stack. Provides short-term and long-term memory for AI agents.

## Architecture

```
┌─────────────────────────────────────────────────┐
│              AgentCore Memory                    │
│                                                  │
│  Short-term memory (raw events, per-session)     │
│       ↓ strategies extract insights ↓            │
│  Long-term memory (facts, summaries, prefs)      │
│                                                  │
│  Strategies:                                     │
│    • Semantic  → /facts/{actorId}/               │
│    • Summary   → /summaries/{actorId}/{session}/ │
│    • UserPref  → /users/{actorId}/preferences/   │
└─────────────────────────────────────────────────┘
         ↑ CreateEvent / SearchMemoryRecords ↑
┌─────────────────────────────────────────────────┐
│         AgentCore Runtime (your agent)           │
│  Reads MEMORY_<NAME>_ID env var automatically    │
└─────────────────────────────────────────────────┘
```

## Deploy

```bash
# Basic — semantic + summarization (default)
python deploy.py --stack-name my-agent-memory --region us-west-2

# All strategies
python deploy.py --stack-name my-agent-memory \
  --enable-semantic true \
  --enable-summarization true \
  --enable-user-preference true

# Wire to an existing AgentCore Runtime
python deploy.py --stack-name my-agent-memory \
  --runtime-arn arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/my_agent-XXXXXXXXXX
```

## Parameters

| Parameter | Default | Description |
|---|---|---|
| `--stack-name` | `agentcore-memory` | CloudFormation stack name |
| `--region` | `us-west-2` | AWS region |
| `--memory-name` | `AgentMemory` | Memory resource name (alphanumeric + underscore) |
| `--event-expiry-days` | `30` | Short-term memory retention (3–365 days) |
| `--enable-semantic` | `true` | Extract facts from conversations |
| `--enable-summarization` | `true` | Generate session summaries |
| `--enable-user-preference` | `false` | Track user preferences |
| `--runtime-arn` | *(empty)* | Existing AgentCore Runtime ARN to auto-wire |

## Stack Outputs

| Output | Description |
|---|---|
| `MemoryId` | Memory resource ID (pass to your agent) |
| `MemoryArn` | Memory resource ARN |
| `MemoryStatus` | CREATING → ACTIVE |

## Integration

### With AgentCore Runtime (recommended)

The deploy script can auto-wire memory to an existing runtime via `--runtime-arn`. It sets `MEMORY_<NAME>_ID` as an environment variable on the runtime. The Strands agent framework picks this up automatically.

### With the longrun-solution stack

To add memory to `ecs-bedrock-agentcore-longrun-solution`:

1. Deploy this memory stack
2. Pass the `MemoryId` output to the longrun stack's AgentCore Runtime:
   ```bash
   python deploy.py --stack-name sandbox-longrun-0426-memory \
     --runtime-arn arn:aws:bedrock-agentcore:us-west-2:256358067059:runtime/sandbox_longrun_0426_agent-XXXXXXXXXX
   ```

### Manual (boto3)

```python
import boto3
from bedrock_agentcore.memory import MemorySessionManager

session_manager = MemorySessionManager(
    memory_id="<MemoryId from stack output>",
    region_name="us-west-2"
)

session = session_manager.create_memory_session(
    actor_id="user-123",
    session_id="session-abc"
)

# Write conversation turns
session.add_turns(messages=[...])

# Search long-term memory
records = session.search_long_term_memories(
    query="what does the user prefer?",
    namespace_path="/",
    top_k=5
)
```

## Memory Types

| Type | Retention | What it stores |
|---|---|---|
| **Short-term** | `EventExpiryDays` | Raw conversation events (turn-by-turn) |
| **Long-term** | Permanent | Extracted facts, summaries, preferences |

## Cleanup

```bash
aws cloudformation delete-stack --stack-name my-agent-memory --region us-west-2
```

## Files

```
ecs-bedrock-agentcore-memory-solution/
├── agentcore-memory.yaml   # CloudFormation template
├── deploy.py               # Deploy script with runtime wiring
└── README.md               # This file
```

---

## Cross-Account MCP Scanning (v0.2.0)

The longrun orchestrator supports scanning other AWS accounts via a one-click IAM role deployment.

### How It Works

```
User → "scan account 123456789012 for public SGs"
  → Intent router classifies as TIER 4 (cross_account_scan)
  → Backend builds assume-role prompt with target account role ARN
  → Agent assumes role via AWS CLI → runs scan in target account
  → Result returned to user
```

### IAM Role Chain

```
AgentCore Runtime Role (ReadOnlyAccess)
  → sts:AssumeRole → arn:aws:iam::<target>:role/OpenAB-ReadOnlyAccess
```

### One-Click Setup (Target Account)

Users deploy a ReadOnly role in their account via CloudFormation Quick-Create:

```
https://<region>.console.aws.amazon.com/cloudformation/home#/stacks/quickcreate?
  stackName=OpenAB-ReadOnlyAccess
  &templateURL=<s3-template-url>
  &param_TrustedAccountId=<operator-account>
  &param_TrustedRoleName=<stack>-McpAssumeRole
  &param_ExternalId=openab-scan
```

The template deploys:
- `OpenAB-ReadOnlyAccess` IAM role
- Trust: operator account's McpAssumeRole + ExternalId
- Permissions: `ReadOnlyAccess` + `SecurityAudit` (no write)
- Revoke: delete the CloudFormation stack

### CFN Templates

| Template | Purpose |
|---|---|
| `agentcore-longrun-orchestrator-0.2.0.yaml` | Full stack with MCP IAM role + DynamoDB |
| `cross-account-readonly-role.yaml` | One-click target account role |

---

## Long-Running Task Management

Tasks that take minutes or hours are handled with:

- **Backend**: `GET /api/orchestrator/tasks/{task_id}/status` — polls AgentCore runtime for task completion
- **Backend**: `GET /api/orchestrator/warmup` — pre-warms the runtime (90s cold start)
- **Frontend**: Tasks persisted in `localStorage` — survive page refresh
- **Frontend**: "Check Status" button on running tasks — polls via REST (no WebSocket dependency)
- **Frontend**: Auto-prewarm on page load — fires warmup request in background

### API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/orchestrator/warmup` | GET/POST | Trigger runtime warm-up |
| `/api/orchestrator/tasks/{task_id}/status` | GET | Check task completion status |
| `/api/orchestrator/tasks` | GET | List recent tasks |
| `/api/orchestrator/sessions` | GET | List session logs from S3 |
