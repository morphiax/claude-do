---
name: plan
description: "Decompose a goal into a structured plan with enriched task specs and safety checks."
argument-hint: "<goal description>"
---

# Plan

Decompose a goal into a dependency-aware plan using a team of specialist agents. Output is a `.plan.json` file that `/execute` consumes. **This skill only plans — it does NOT execute.**

## Step 1: Context Scan

Skip if greenfield or purely conceptual.

1. `Glob` key directories, `Read` configs → identify stack, frameworks, build/test tools.
2. Check `CLAUDE.md`, linter configs → conventions.
3. `Grep`/`Glob` → which modules the goal touches.
4. `LSP(operation: "documentSymbol")` on a key source file. If symbols returned, record language in `context.lsp.available`. If TS/Python but LSP fails, recommend `typescript-language-server` or `pyright` in summary.

For large codebases (>50 source files), delegate to `Task(subagent_type: "Explore")`.

## Step 2: Validate the Goal

Use `AskUserQuestion` to clarify only when reasonable developers would choose differently and the codebase doesn't answer it:

- Scope boundaries, done-state, technical preferences, compatibility, priority.

If >12 tasks needed, suggest phases. Plan only phase 1.

## Step 3: Team-Based Decomposition

Spawn a planning team of specialist agents tailored to the goal. The team composition is dynamic — the number of agents (2-5), their roles, models, and collaboration pattern are determined by analyzing the goal, not hardcoded. This catches blind spots that single-agent decomposition misses while avoiding unnecessary agents for simple goals.

### 3a. Create Planning Team

```
TeamCreate:
  team_name: "do-plan"
  description: "Planning team for: {goal}"
```

### 3b. Design Team Composition

Use `mcp__sequential-thinking__sequentialthinking` to determine the right team for this goal. Analyze:

1. **What domains does the goal touch?** (architecture, implementation, security, performance, data, infrastructure, UX, testing, migration, etc.)
2. **How many specialist perspectives are needed?** (2-5 agents)
3. **What collaboration pattern fits?** (sequential pipeline, parallel independent analysis, or mixed)

Produce a **team roster** — for each agent:

- `name` — short identifier (for example, "architect," "security-reviewer," "data-specialist")
- `role` — one-line description of their mandate
- `model` — `opus` for architectural/analytical roles, `sonnet` for implementation-focused roles, `haiku` for verification-only roles
- `dependsOn` — list of agent names this agent should wait for (empty = starts immediately)
- `mandate` — what specifically this agent should analyze, produce, or review

**Sizing guidance:**

- **2 agents**: single-domain changes where one agent proposes and another reviews (for example, "add a config option")
- **3 agents**: standard multi-concern tasks — most goals land here (for example, "add an API endpoint")
- **4-5 agents**: complex cross-cutting work involving security, performance, migration, or multiple subsystems

**Required constraint**: At least one agent must have a review/risk-analysis mandate — covering missing dependencies, testing gaps, rollback scenarios, scope creep, and incorrect assumptions. This agent must depend on all proposing agents.

### 3c. Create Planning Tasks

For each agent in the roster, create a task using `TaskCreate`:

- **subject**: the agent's mandate in imperative form (for example, "Propose task breakdown," "Review plan for security gaps")
- **description**: the full mandate plus output expectations
- **activeForm**: present continuous form of the mandate

Wire dependencies with `TaskUpdate(addBlockedBy)` based on each agent's `dependsOn` list.

### 3d. Spawn Planning Agents

For each agent in the roster, spawn a teammate using the following template:

```
Task:
  subagent_type: "general-purpose"
  team_name: "do-plan"
  name: "{agent.name}"
  model: "{agent.model}"
  prompt: |
    You are a {agent.role} on a planning team.
    {if agent.dependsOn}Wait for {agent.dependsOn} to complete before starting.{endif}

    Goal: {goal}
    Codebase: {context from Step 1 — stack, conventions, relevant files}

    ## Your Mandate
    {agent.mandate}

    ## Output Requirements
    For task breakdowns (proposing agents):
    1. Read relevant code to understand current state
    2. Propose 3-12 tasks with clear dependencies
    3. For each task: subject, description (why + how it connects), type
       (research/implementation/testing/configuration), files to create/modify, files to read
    4. Assign wave numbers: wave 1 = no dependencies, wave 2+ = depends on earlier waves
    5. Granularity: each task ≤30 min effort. Merge tasks <5 min with adjacent ones
    6. Apply: backward chaining, MECE, dependency graph, pre-mortem

    For enrichment agents (grounding in codebase):
    1. Read each referenced file — verify paths, understand current code
    2. For each task, fill in agent specification fields:
       - role, model, approach, contextFiles, assumptions, acceptanceCriteria, constraints
    3. Validate feasibility — flag anything too complex for a single task
    4. Identify shared files between tasks and flag potential conflicts

    For review/risk agents:
    1. Check for missing dependencies, testing gaps, incorrect assumptions
    2. Verify shell commands in assumptions actually test what they claim
    3. Add rollback scenarios for each task
    4. Flag file conflicts between same-wave tasks
    5. Identify scope creep beyond the stated goal
    6. For each issue, provide a specific fix

    Focus on the sections relevant to your role. Skip sections that don't apply.

    Send your findings to the lead via SendMessage when done.
    Claim your task from the task list and mark it completed when finished.
```

**Parallel safety**: Agents with no `dependsOn` can be spawned simultaneously. Agents with dependencies are spawned after their prerequisites complete.

### 3e. Collect and Synthesize

After all teammates complete their tasks:

1. Collect findings from all agents (delivered via SendMessage)
2. Use `mcp__sequential-thinking__sequentialthinking` to synthesize:
   - Merge all agents' contributions in dependency order
   - Resolve conflicts between agents (reviewer corrections take priority)
   - Apply all review fixes
   - Ensure final task list is coherent and complete
3. Shut down teammates: `SendMessage(type: "shutdown_request")` to each
4. Clean up: `TeamDelete`

## Step 4: Enrich Tasks

Review synthesized output and fill any remaining gaps in agent fields.

**Description rule**: Explain _why_ and _how it connects to dependent tasks_ — not just _what_. Include specific files to reuse. An executor with zero context must be able to act on it.

### Agent Fields

- `role` — specialized role (for example, "database migration specialist")
- `expertise` — domain skills needed (optional — include when the domain is specialized)
- `model` — `opus` for research/architecture, `sonnet` for implementation/testing, `haiku` for verification-only tasks (running checks, no code writing)
- `approach` — tactical execution strategy
- `priorArt` — established concepts to apply (optional — include when non-obvious)
- `fallback` — alternative if primary approach fails (optional — include for risky steps)
- `contextFiles` — files the agent must read before starting: `[{path, reason, lines?}]`
- `assumptions` — codebase assertions with verification: `[{claim, verify (shell cmd), severity: blocking|warning}]`
- `acceptanceCriteria` — machine-checkable outcomes: `[{criterion, check (shell cmd)}]`
- `rollbackTriggers` — conditions to STOP: `["If X, STOP and return BLOCKED: reason"]`
- `constraints` — domain-specific rules from codebase analysis

### Metadata Fields

- `type` — `research` | `implementation` | `testing` | `configuration`
- `files` — files to create/modify
- `reads` — files to read (for conflict detection)

## Step 5: Auto-generate Safety

After decomposition, fill gaps:

- **File existence**: For each `metadata.files` that's a modification (not creation), add blocking assumption: `test -f {path}`.
- **Cross-task dependencies**: If task B modifies files created by task A and B is same/later wave, add blocking assumption: `test -f {file}`.
- **Rollback triggers**: Convert every blocking assumption to a rollback trigger.

## Step 6: Validate Plan

Check before writing:

1. No two same-wave tasks share `metadata.files`
2. No task's `metadata.reads` overlaps a same-wave task's `metadata.files`
3. All `blockedBy` are valid indices, no circular deps
4. Wave = 1 + max(blockedBy waves)
5. Every task has ≥1 assumption and ≥1 rollback trigger
6. Total tasks ≤ 12

Revise and re-validate on failure.

## Step 7: Write .plan.json

Write to project root:

```json
{
  "goal": "...",
  "context": {
    "stack": "TypeScript, Express, PostgreSQL",
    "conventions": "ESM imports, snake_case DB columns",
    "testCommand": "npm test",
    "buildCommand": "npm run build",
    "lsp": { "available": ["typescript"] }
  },
  "progress": {
    "currentWave": 0,
    "completedTasks": [],
    "surprises": [],
    "decisions": []
  },
  "tasks": [
    {
      "subject": "Set up database schema",
      "description": "Create the PostgreSQL schema with migrations. Tasks 1 and 2 depend on these tables. Use transactional DDL for atomicity.",
      "activeForm": "Setting up database schema",
      "status": "pending",
      "result": null,
      "attempts": 0,
      "metadata": {
        "type": "implementation",
        "files": ["db/migrations/001_init.sql", "db/schema.ts"],
        "reads": ["docs/schema-design.md"]
      },
      "wave": 1,
      "blockedBy": [],
      "agent": {
        "role": "database schema architect",
        "model": "sonnet",
        "approach": "Decompose schema into tables, use transactional DDL.",
        "contextFiles": [
          {
            "path": "docs/schema-design.md",
            "reason": "Data model requirements"
          }
        ],
        "assumptions": [
          {
            "claim": "PostgreSQL is installed",
            "verify": "psql --version",
            "severity": "blocking"
          }
        ],
        "acceptanceCriteria": [
          {
            "criterion": "Migration runs cleanly",
            "check": "psql -f db/migrations/001_init.sql"
          }
        ],
        "rollbackTriggers": [
          "If PostgreSQL is not installed, STOP and return BLOCKED: database required"
        ],
        "constraints": [
          "Use snake_case for column names",
          "All tables must have a primary key"
        ]
      }
    }
  ]
}
```

**Schema rules:**

- `tasks` is ordered — index is the task ID (0-based)
- `blockedBy` references task indices
- `wave`: 1 = no deps, 2+ = 1 + max(blockedBy waves)
- `status`: `pending` | `in_progress` | `completed` | `failed` | `blocked` | `skipped`
- `result`: null initially, brief one-line summary after execution
- `attempts`: 0 initially, incremented by executor
- `progress`: initialized empty, updated by `/execute` at runtime

## Step 8: Output Summary

```
Plan: {goal}
Tasks: {count} across {wave_count} waves

Wave 1:
- Task 0: {subject} ({model})
- Task 1: {subject} ({model})

Wave 2:
- Task 2: {subject} ({model}) [blocked by: 0, 1]

Context: {stack}
Test: {testCommand}

Run /execute to begin.
```

**Goal**: $ARGUMENTS
