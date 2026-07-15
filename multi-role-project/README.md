# Multi-Role Pipeline — Kiro Steering Pack

This folder is a **Kiro steering pack** designed to be deployed into `.kiro/steering/` in any kiro-cli workspace. It provides a structured delivery pipeline where an agent switches roles at each stage.

## Installation

### For EKS Agents (runtime pull)

Agents clone this into their kiro-cli working directory:

```bash
cd /home/agent
mkdir -p .kiro/steering
if [ ! -d agent-config ]; then gh repo clone juntinyeh-worker/agent-config; fi
cd agent-config && git fetch origin && git checkout origin/main -- multi-role-project/
cp agent-config/multi-role-project/* /home/agent/.kiro/steering/
```

Once installed, kiro-cli automatically:
- Loads `PIPELINE.md` and `SECURITY-RULES.md` on every prompt (`inclusion: auto`)
- Makes role files available via `#agent.PM`, `#agent.Architect`, etc. (`inclusion: manual`)

### For Local Kiro IDE

Copy into your project workspace:

```bash
cp multi-role-project/* your-project/.kiro/steering/
```

## File Inclusion Behavior

| File | Inclusion | Behavior |
|---|---|---|
| `PIPELINE.md` | `auto` | Always loaded — pipeline stage awareness in every prompt |
| `SECURITY-RULES.md` | `auto` | Always loaded — security rules enforced at all times |
| `agent.PM.md` | `manual` | Loaded when agent reads Stage 1 |
| `agent.Architect.md` | `manual` | Loaded when agent reads Stage 2 (Design) |
| `agent.Full-stack-dev.md` | `manual` | Loaded when agent reads Stage 3 (Build) |
| `agent.QA.md` | `manual` | Loaded when agent reads Stage 4 (Test) |
| `agent.CloudOps.md` | `manual` | Loaded when agent reads Stage 5 (Deploy) |
| `agent.Compliance-auditor.md` | `manual` | Loaded when agent reads Stage 6 (Audit) |
| `PIPELINE-HANDOFF.md` | `manual` | Reference for handoff format (cross-agent scenarios) |
| `FAQ.md` | `manual` | Usage guide |

## How It Works (Solo Pipeline)

When an agent installs this steering pack and picks up a `[pipeline]` task:

1. `PIPELINE.md` is auto-loaded → agent knows all stages and the flow
2. Agent starts at Stage 1, reads `#agent.PM` for PM role constraints
3. Completes Stage 1 → verifies handoff checklist → moves to Stage 2
4. Reads `#agent.Architect` → designs architecture
5. Continues through all stages, reading each role file as needed
6. Pipeline complete when Stage 6 audit passes

The `auto` files provide constant awareness. The `manual` files provide role-specific constraints only when the agent is in that stage.

## Updating

To update the steering pack on running agents:
1. Edit files in this folder
2. Push to `origin/main`
3. Agents pull latest on next `[pipeline]` task (they run `git fetch` + `git checkout origin/main`)

No pod restart needed — agents fetch fresh content each time they enter pipeline mode.
