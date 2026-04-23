# AgentCore Runtime — Integration Profiles

## Overview

The Kiro CLI AgentCore runtime connects to external services via MCP (Model Context Protocol) servers. Each integration (GitHub, JIRA, Slack, etc.) is an MCP server that the agent can use as a tool.

Integrations are configured via a **profile** — a JSON document that declares which services to enable and what credentials they require. The runtime reads this at startup and passes the MCP servers to the Kiro CLI session.

## Configuration

### Environment Variable

```
INTEGRATION_PROFILE=s3://bucket/profiles/demo.json    # load from S3
INTEGRATION_PROFILE=/app/profiles/default.json         # load from local file
INTEGRATION_PROFILE=                                    # no integrations (default)
```

### Profile Format

```json
{
  "version": "1.0",
  "integrations": [
    {
      "name": "github",
      "enabled": true,
      "mcp_server": {
        "command": "uvx",
        "args": ["--from", "github-mcp-server", "github-mcp-server"],
        "env": {
          "GITHUB_TOKEN": "${GITHUB_TOKEN}"
        }
      },
      "required_env": ["GITHUB_TOKEN"],
      "description": "GitHub repository access — PRs, issues, code search"
    },
    {
      "name": "jira",
      "enabled": true,
      "mcp_server": {
        "command": "uvx",
        "args": ["--from", "jira-mcp-server", "jira-mcp-server"],
        "env": {
          "JIRA_API_KEY": "${JIRA_API_KEY}",
          "JIRA_BASE_URL": "${JIRA_BASE_URL}"
        }
      },
      "required_env": ["JIRA_API_KEY", "JIRA_BASE_URL"],
      "description": "JIRA issue tracking — create, update, search tickets"
    },
    {
      "name": "slack",
      "enabled": false,
      "mcp_server": {
        "command": "uvx",
        "args": ["--from", "slack-mcp-server", "slack-mcp-server"],
        "env": {
          "SLACK_TOKEN": "${SLACK_TOKEN}",
          "SLACK_WEBHOOK_URL": "${SLACK_WEBHOOK_URL}"
        }
      },
      "required_env": ["SLACK_TOKEN"],
      "description": "Slack messaging — send notifications, read channels"
    },
    {
      "name": "aws-api",
      "enabled": true,
      "mcp_server": {
        "command": "uvx",
        "args": ["--from", "awslabs.aws-api-mcp-server@latest", "awslabs.aws-api-mcp-server"],
        "env": {}
      },
      "required_env": [],
      "description": "AWS API access — uses container IAM role"
    }
  ]
}
```

### Key Design Decisions

1. **`${VAR}` substitution** — env var references in the profile are resolved at runtime from the container's environment. Credentials are never stored in the profile itself.

2. **`required_env` validation** — at startup, the runtime checks that all required env vars are present. If any are missing, that integration is skipped with a warning (not a crash).

3. **`enabled` flag** — integrations can be toggled without removing them from the profile.

4. **Adding a new integration** — just add an entry to the JSON. No code changes, no container rebuild.

## How Credentials Are Passed

Credentials flow through environment variables, which can be set via:

| Method | Use Case |
|--------|----------|
| AgentCore `environmentVariables` | Set at runtime registration (`create_agent_runtime`) |
| ECS task definition env vars | Set in CFN template or task def |
| AWS Secrets Manager + ECS | Reference secrets in task def (`valueFrom`) |
| SSM Parameter Store | Fetch at startup via wrapper.py |

### Recommended: Secrets Manager for Production

```yaml
# In ECS task definition
ContainerDefinitions:
  - Environment:
      - Name: INTEGRATION_PROFILE
        Value: s3://bucket/profiles/prod.json
    Secrets:
      - Name: GITHUB_TOKEN
        ValueFrom: arn:aws:secretsmanager:us-west-2:123456789:secret:github-pat
      - Name: JIRA_API_KEY
        ValueFrom: arn:aws:secretsmanager:us-west-2:123456789:secret:jira-key
```

This way:
- Profile defines *what* integrations exist (no secrets)
- Secrets Manager holds *credentials* (encrypted, rotatable)
- ECS injects both into the container at runtime

## Runtime Behavior

At startup (`wrapper.py`):

```
1. Read INTEGRATION_PROFILE (from S3 or local file)
2. For each integration where enabled=true:
   a. Check required_env vars are present
   b. Resolve ${VAR} references in mcp_server.env
   c. Add to mcpServers list
3. Pass mcpServers to kiro-cli session/new
4. Agent now has access to all configured tools
```

## Example Profiles

### Demo (AWS only)
```json
{
  "version": "1.0",
  "integrations": [
    {"name": "aws-api", "enabled": true, "mcp_server": {"command": "uvx", "args": ["--from", "awslabs.aws-api-mcp-server@latest", "awslabs.aws-api-mcp-server"], "env": {}}, "required_env": []}
  ]
}
```

### Dev Team (AWS + GitHub + Slack)
```json
{
  "version": "1.0",
  "integrations": [
    {"name": "aws-api", "enabled": true, ...},
    {"name": "github", "enabled": true, ...},
    {"name": "slack", "enabled": true, ...}
  ]
}
```

### Incident Response (AWS + GitHub + JIRA + Slack + PagerDuty)
All integrations enabled with appropriate credentials.
