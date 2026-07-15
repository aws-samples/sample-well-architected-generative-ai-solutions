---
inclusion: manual
description: "FAQ — how to use multi-role pipeline in Kiro, session strategies, sub-agents"
---

# FAQ — Multi-Role Project in Kiro

## Single Session vs. Multiple Kiro Sessions

### Single Session Workflow

**How it works:** You stay in one Kiro chat session and switch roles by referencing steering files with `#` in your prompts.

| Aspect | Detail |
|---|---|
| Setup | Minimal — just use `#role-pm`, `#role-architect`, etc. |
| Context | Shared across all roles — the agent remembers everything from prior stages |
| Speed | Fast iteration, no window switching |
| Best for | Solo developers, small features, rapid prototyping |
| Trade-off | No isolation — QA "knows" how the code was written, which can introduce bias |

**Example flow:**
```
Prompt 1: "#role-pm Define requirements for feature X"
Prompt 2: "#role-architect Design the system for these requirements"
Prompt 3: "#role-dev Implement the design"
Prompt 4: "#role-qa Test the implementation against the acceptance criteria"
```

**Pros:**
- Zero overhead — start immediately
- Full context continuity between stages
- Easy to iterate back and forth between roles
- Handoff artifacts are naturally visible to the next role

**Cons:**
- Agent carries implementation bias into testing/review roles
- Long conversations may hit context limits
- No true "fresh eyes" on the work at each stage

---

### Multiple Kiro Sessions

**How it works:** You open separate Kiro windows or start fresh sessions for different pipeline stages. Each session loads only the relevant role's steering file.

| Aspect | Detail |
|---|---|
| Setup | One session per stage (or per role) with dedicated steering |
| Context | Isolated — each role starts fresh with only its inputs |
| Speed | Slower (switching windows, copy-pasting artifacts between sessions) |
| Best for | Critical features, security-sensitive work, team simulations |
| Trade-off | More overhead, but higher quality gates |

**Example flow:**
```
Session A (PM):       "#role-pm" → produce requirements.md
Session B (Architect): "#role-architect" → read requirements.md → produce architecture.md
Session C (Dev):      "#role-dev" → read architecture.md → implement code
Session D (QA):       "#role-qa" → read code + requirements → test independently
```

**Pros:**
- True isolation — QA doesn't know implementation shortcuts
- Each role evaluates work with fresh perspective
- Mimics real team dynamics and catches more issues
- Prevents context window exhaustion on large projects

**Cons:**
- Manual artifact passing between sessions (copy files, share docs)
- More time and effort to manage
- Requires discipline to follow the pipeline order

---

### When to Use Which

| Scenario | Recommendation |
|---|---|
| Quick bug fix or small feature | Single session |
| Large feature with multiple components | Multiple sessions |
| Security-critical work | Multiple sessions (QA isolation matters) |
| Exploring/prototyping | Single session |
| Simulating a real team review | Multiple sessions |
| Solo dev, tight deadline | Single session with inline role switching |

---

## Sub-Agents in Kiro

### What Are Sub-Agents?

Sub-agents are specialized autonomous agents that Kiro can delegate tasks to during a session. They run independently with their own context and tool access, complete a task, and return results to the main agent.

| Sub-Agent | Purpose |
|---|---|
| `context-gatherer` | Explores a codebase to identify relevant files and understand component interactions |
| `general-task-execution` | Executes well-defined subtasks autonomously with full tool access |
| `custom-agent-creator` | Creates new custom agent definitions for recurring task patterns |

### How Sub-Agents Work

1. The main agent (your Kiro chat) identifies a task suitable for delegation
2. It invokes a sub-agent with a specific prompt and optional file context
3. The sub-agent runs autonomously — reading files, running commands, making changes
4. Results are returned to the main agent, which continues the conversation

Sub-agents are only available in **Autopilot mode**.

---

### Can We Use Sub-Agents for the Multi-Role Pipeline?

**Short answer:** Partially — they complement the pipeline but don't replace role switching.

**What sub-agents CAN do:**

| Use Case | How |
|---|---|
| Codebase exploration before design | `context-gatherer` maps the repo before Architect designs |
| Parallel implementation tasks | `general-task-execution` handles independent coding subtasks |
| Generating boilerplate | Delegate scaffold creation while you focus on architecture |
| Running audits | Delegate compliance checklist verification to a sub-agent |

**What sub-agents CANNOT do (today):**

- Persist a role identity across multiple interactions
- Enforce pipeline gates or block the next stage
- Run as parallel long-lived roles
- Communicate with each other (only report back to parent)

**Practical hybrid approach:**

```
1. You (#role-pm): Define requirements
2. Delegate to sub-agent: "Gather context on the existing auth module"
3. You (#role-architect): Design using the gathered context
4. Delegate to sub-agent: "Implement the data access layer per this spec"
5. You (#role-qa): Review and test the implementation
```

---

### Sub-Agents vs. Multi-Role Pipeline

| Dimension | Sub-Agents | Multi-Role Pipeline |
|---|---|---|
| Purpose | Task delegation and parallelism | Governance, quality gates, role separation |
| Persistence | One-shot (complete and return) | Persona maintained across prompts |
| Isolation | Full (own context window) | Depends on session strategy |
| Communication | Returns results to parent only | Handoff via artifacts |
| Best for | Mechanical subtasks, exploration | Decision-making, reviews, approvals |

**Recommendation:** Use the pipeline for governance (what to do, who decides). Use sub-agents for execution speed (getting things done within each stage).
