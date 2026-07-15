---
inclusion: auto
description: Delivery pipeline overview — always active to provide stage awareness
---

# Delivery Pipeline — Role-Based Agent Workflow

## Pipeline Overview

```
Stage 1        Stage 2           Stage 3     Stage 4       Stage 5              Stage 6
───────        ───────           ───────     ───────       ───────              ───────
  PM    ──→  Architect + Dev  ──→   QA   ──→  CloudOps  ──→  Architect+QA+PM  ──→  Audit
(plan)       (design+build)     (test)     (deploy)       (review gate)        (compliance)
                                   │                           │
                                   └── reject → back to Dev    └── reject → back to responsible role
```

## Stages

| Stage | Role(s) | Gate Criteria | Reject Target |
|---|---|---|---|
| 1. Plan | PM | Requirements + acceptance criteria complete | — |
| 2. Design + Build | Architect + Full-stack-dev | Architecture doc + working code + unit tests | — |
| 3. Test | QA | All tests pass, no critical bugs, security OK | → Stage 2 (Dev) |
| 4. Deploy | CloudOps | Stack deployed, health checks pass, monitoring live | → Stage 2 (Dev) or Stage 3 (QA) |
| 5. Review | Architect + QA + PM | Architecture compliance, test coverage, requirements met | → Stage 2, 3, or 4 |
| 6. Audit | Compliance-auditor | All compliance controls pass | → Responsible role |

## Available Roles (use `#` to activate)

| Steering File | Role | Pipeline Stages |
|---|---|---|
| `#role-pm` | Project Manager | Stage 1, Stage 5 (review) |
| `#role-architect` | Architect | Stage 2, Stage 5 (review lead) |
| `#role-dev` | Full-Stack Developer | Stage 2 |
| `#role-qa` | QA Engineer | Stage 3, Stage 5 (review) |
| `#role-cloudops` | CloudOps Engineer | Stage 4 |
| `#role-compliance` | Compliance Auditor | Stage 6 |

## Handoff Protocol

Each stage handoff requires:
1. Output artifacts committed to workspace branch
2. Handoff checklist completed (defined in each role file)
3. Next-stage role activated and briefed on inputs

## How to Use

1. This pipeline file is always loaded — you always have stage awareness
2. Activate a role with `#role-pm`, `#role-architect`, etc. in your prompt
3. Follow the handoff criteria before switching to the next stage
4. If a gate rejects, go back to the indicated stage and fix
