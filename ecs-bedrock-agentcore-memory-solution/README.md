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
