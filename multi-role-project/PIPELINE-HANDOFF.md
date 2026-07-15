---
inclusion: auto
description: Pipeline handoff protocol for EKS worker agents — always loaded for pipeline awareness
---

# Pipeline Handoff Protocol — EKS Worker Agents

## Agent-to-Role Mapping (Pipeline Mode)

| Agent | Pipeline Role | Stage |
|---|---|---|
| SpongeBob 🧽 | Full-Stack Developer | Stage 2 (Build) |
| PatrickStar ⭐ | QA Engineer | Stage 3 (Test) |
| Squidward 🎵 | CloudOps Engineer | Stage 4 (Deploy) |
| MrKrab 🦀 | Architect + Compliance Auditor | Stage 2 (Design) + Stage 6 (Audit) |

## Pipeline Activation

Pipeline mode activates when a task in `TODO.md` contains the tag `[pipeline]`:

```markdown
- [ ] `T-0010` | high | [pipeline] Build user auth module | source:admin | 2026-05-05
```

When `[pipeline]` is present:
1. Agent adopts their assigned pipeline role constraints
2. Handoff protocol (§4 Task Interchange) is mandatory between stages
3. Gate criteria must be met before handoff

When `[pipeline]` is NOT present:
- Agent operates normally with full autonomy (existing behavior)

## Handoff Flow (via agent-memory TODO)

```
MrKrab (Architect)
  │  Produces: architecture.md, api-contracts/
  │  Handoff: task-handoff.md → SpongeBob's TODO.md
  ▼
SpongeBob (Dev)
  │  Produces: src/, tests/unit/
  │  Handoff: task-handoff.md → PatrickStar's TODO.md
  ▼
PatrickStar (QA)
  │  Produces: qa-reports/, test results
  │  Pass → Handoff: task-handoff.md → Squidward's TODO.md
  │  Fail → Handoff: bug report → SpongeBob's TODO.md
  ▼
Squidward (CloudOps)
  │  Produces: deployment log, monitoring config
  │  Handoff: task-handoff.md → MrKrab's TODO.md (for review + audit)
  ▼
MrKrab (Compliance Auditor)
  │  Produces: audit report, sign-off
  │  Pass → Done
  │  Fail → Handoff: findings → responsible agent's TODO.md
```

## Handoff Task Format (Pipeline Extension)

Extend the standard task-handoff.md with pipeline metadata:

```markdown
---
task_id: T-NNNN
from: SpongeBob
to: PatrickStar
priority: high
created: 2026-05-05
pipeline_stage: "Stage 2 → Stage 3"
pipeline_role_from: Full-Stack-Dev
pipeline_role_to: QA
---

# Task: QA Review — User Auth Module

## Context
Implementation complete for user auth module per architecture from MrKrab.

## Deliverables for Review
- Branch: `spongebob-20260505-user-auth`
- Architecture ref: `mrkrab-20260505-user-auth/architecture.md`
- Requirements ref: `mrkrab-20260505-user-auth/requirements.md`

## Handoff Checklist (Dev → QA)
- [x] All features implemented per requirements
- [x] Unit tests written and passing
- [x] Code follows architecture design and API contracts
- [x] No known bugs or TODO hacks
- [x] Branch pushed and ready for review

## QA Acceptance Criteria
- All integration tests pass
- Security testing (prompt injection, auth bypass) clean
- Performance within thresholds
```

## Pipeline Branch Naming

When in pipeline mode, workspace branches include the pipeline stage:

```
<prefix>-<date>-pipeline-<stage>-<description>
```

Examples:
- `mrkrab-20260505-pipeline-design-user-auth`
- `spongebob-20260505-pipeline-build-user-auth`
- `patrickstar-20260505-pipeline-test-user-auth`
- `squidward-20260505-pipeline-deploy-user-auth`
- `mrkrab-20260505-pipeline-audit-user-auth`
