---
name: design
description: "Decompose a goal into a structured plan with enriched task specs and safety checks."
argument-hint: "<goal description>"
---

# Design

Decompose a goal into `.design/plan.json` using a dynamic team of specialist experts. **This skill only designs — it does NOT execute.**

**Do NOT use `EnterPlanMode`** — this skill IS the plan.

**Lead boundaries**: Use only `TeamCreate`, `TeamDelete`, `TaskCreate`, `TaskUpdate`, `TaskList`, `SendMessage`, `Task`, `AskUserQuestion`, and `Bash` (cleanup, verification, `python3 $PLAN_CLI` only). Never read source files, use MCP tools, `Grep`, `Glob`, or `LSP`. The lead orchestrates — agents think.

**No polling**: Messages auto-deliver to your conversation automatically. Never use `sleep`, `for i in {1..N}`, or Bash loops to wait. Simply proceed with your work — when a teammate sends a message, it appears in your next turn. The system handles all delivery.

---

## Clarification Protocol

Ask clarifying questions before spawning agents when the goal has ambiguity that affects implementation approach.

**Ask `AskUserQuestion` when:**
- Multiple valid interpretations exist (e.g., "add pictures" = real photos vs stock images vs icons)
- Scope is underspecified (e.g., "upgrade" = visual refresh vs full rewrite vs new feature)
- Technology choice is open and impacts implementation significantly
- Data source is ambiguous (e.g., "show car images" — from where? user-provided? API? scraped?)

**Do NOT ask when:**
- Codebase contains the answer (existing patterns, conventions, similar features)
- Standard practice is clear (use existing test framework, follow existing component patterns)
- User preference doesn't materially change the approach
- The ambiguity is minor and any reasonable choice works

**Examples:**
| Goal | Question |
|------|----------|
| "add car pictures" | "Where should car images come from: actual dealership photos you provide, or generated stock images from an API?" |
| "improve performance" | "Which performance issue: initial load time, runtime speed, or bundle size?" |

### Script Setup

Resolve the plugin root directory (containing `.claude-plugin/` and `skills/`). Set:

```
PLAN_CLI = {plugin_root}/skills/design/scripts/plan.py
```

All script calls: `python3 $PLAN_CLI <command> [args]` via Bash. Output is JSON with `{"ok": true/false, ...}`.

---

## Flow

### 1. Pre-flight

1. **Check for ambiguity**: If the goal has multiple valid interpretations per the Clarification Protocol, use `AskUserQuestion` before proceeding.
2. If >12 tasks likely needed, suggest phases. Design only phase 1.
3. Check existing plan: `python3 $PLAN_CLI status .design/plan.json`. If `ok` and `isResume`: ask user "Existing plan has {counts} tasks. Overwrite?" If declined, stop.
4. Clean stale staging: `mkdir -p .design/history && find .design -mindepth 1 -maxdepth 1 ! -name history -exec rm -rf {} +`

### 2. Lead Research

The lead directly assesses the goal to determine needed perspectives.

1. Read the goal. Quick WebSearch (if external patterns/libraries relevant) or scan CLAUDE.md/package.json via Bash to understand stack.
2. Determine which expert perspectives add value:
   - **architect** — codebase structure, patterns, integration points
   - **researcher** — external libraries, best practices, prior art
   - **domain-specialist** — security, performance, i18n, accessibility, etc.
   - **analyst** — data requirements, API contracts, state management
3. Report the planned team composition to the user.

**For trivial goals** (1-3 tasks, single obvious approach): skip experts. Proceed directly to step 4 with a plan-writer Task subagent (not teammate).

### 3. Spawn Experts

Create the team and spawn experts in parallel.

1. `TeamDelete(team_name: "do-design")` (ignore errors), `TeamCreate(team_name: "do-design")`. If TeamCreate fails, tell user Agent Teams is required and stop.
2. `TaskCreate` for each expert and a plan-writer. Wire the plan-writer `blockedBy` all experts via TaskUpdate.
3. Spawn all experts in parallel using EXPERT_PROMPT, then the plan-writer using PLAN_WRITER_PROMPT.

**Expert types to choose from:**
| Type | Focus | When to include |
|------|-------|-----------------|
| architect | codebase architecture, patterns, integration | Any non-trivial goal touching existing code |
| researcher | external libraries, best practices, prior art | When external solutions/patterns may exist |
| domain-specialist | security, performance, i18n, accessibility | When domain concerns are material |
| analyst | data requirements, API contracts, state | When data flow/API design is complex |

### 4. Collect and Finalize

Wait for the plan-writer's message. Then:

1. Validate: `python3 $PLAN_CLI status .design/plan.json`. Stop if `ok: false`.
2. Shut down teammates, delete team.
3. Clean up TaskList (delete all planning tasks so `/do:execute` starts clean).
4. Summary: `python3 $PLAN_CLI summary .design/plan.json`. Display:

```
Plan: {goal}
Tasks: {taskCount}, max depth {maxDepth}
Models: {modelDistribution}

Depth 1:
- Task 0: {subject} ({model})

Depth 2:
- Task 2: {subject} ({model}) [blocked by: 0, 1]

Context: {stack}
Test: {testCommand}

Run /execute to begin.
```

**Fallback** (if team fails to produce plan.json):
1. Retry with single plan-writer Task subagent reading expert files.
2. Merge inline: process expert files one at a time, validate, run scripts, write plan.json directly.

---

## Agent Prompts

### EXPERT_PROMPT

Fill `{goal}`, `{name}`, `{role}`, `{focus}`, `{context}`:

```
You are {name}, a {role} on the do-design team.

**Goal**: {goal}
**Focus**: {focus}

{context}

Analyze through your perspective. Recommend tasks: subject, description, blockedBy, metadata {type, files, reads}, agent {role, model, approach, contextFiles, assumptions, acceptanceCriteria, rollbackTriggers, constraints}.

Write .design/expert-{name}.json or report directly to lead. Mark task completed.
```

**Focus examples:**
- architect: "codebase architecture, existing patterns, integration points"
- researcher: "external libraries, best practices, prior art with URLs and versions"
- security-specialist: "security implications, attack vectors, auth/authz concerns"
- performance-specialist: "performance optimization, bottlenecks, caching strategies"
- analyst: "data requirements, API contracts, state management"

**Context**: Lead provides relevant context based on goal (stack, conventions, relevant modules).

### PLAN_WRITER_PROMPT

Fill `{goal}`, `{expectedExpertCount}`:

```
You are the Plan Writer on the do-design team. Merge expert analyses into .design/plan.json.

**Goal**: {goal}

Read .design/expert-*.json (expect {expectedExpertCount}). If .design/critic.json exists, read it.

Merge expert tasks: converging views increase confidence, diverging views need judgment calls — record decisions in progress.decisions. Deduplicate and ensure MECE coverage.

## Task Schema

Fields: subject, description (WHY + connection to dependents), activeForm, status: pending, result: null, attempts: 0, blockedBy (indices), metadata: {type, files: {create:[], modify:[]}, reads}, agent: {role (kebab-case), model, approach, contextFiles [{path, reason}], assumptions [{claim, verify (shell cmd), severity}], acceptanceCriteria [{criterion, check (shell cmd)}], rollbackTriggers, constraints}

- Add relevant expert files to every task's contextFiles.
- File metadata must be accurate (workers use for git add). Acceptance checks must be self-contained shell commands.

## Safety

For each modify path: add blocking assumption `test -f {path}`. Cross-task file overlaps: add blocking assumptions. Convert blocking assumptions to rollback triggers.

## Finalize

1. Write .design/plan-draft.json: {schemaVersion: 3, goal, context, progress: {completedTasks: [], surprises: [], decisions: []}, tasks}. Omit `prompt` and `fileOverlaps` — scripts add them.
2. Set PLAN_CLI to {plugin_root}/skills/design/scripts/plan.py (resolve plugin root). Run:
   `python3 $PLAN_CLI finalize .design/plan-draft.json`
3. `mv .design/plan-draft.json .design/plan.json`

Mark your task completed. Read ~/.claude/teams/do-design/config.json for the lead's name and tell them the plan is ready with task count, max depth, and a brief summary.
```

### MINIMAL_PLAN_PROMPT (Task subagent, not teammate)

For trivial goals (1-3 tasks). Fill `{goal}`, `{context}`:

```
Generate .design/plan.json for a minimal-complexity goal.

**Goal**: {goal}

{context}

Generate 1-3 tasks following the task schema: subject, description (WHY + connection to dependents), activeForm, status: pending, result: null, attempts: 0, blockedBy: [], metadata: {type, files: {create:[], modify:[]}, reads}, agent: {role (kebab-case), model, approach, contextFiles [{path, reason}], assumptions [{claim, verify, severity}], acceptanceCriteria [{criterion, check}], rollbackTriggers, constraints}.

Safety: for each modify path, add blocking assumption `test -f {path}`. Convert blocking assumptions to rollback triggers.

Write .design/plan-draft.json: {schemaVersion: 3, goal, context: {stack, conventions, testCommand, buildCommand, lsp}, progress: {completedTasks: [], surprises: [], decisions: []}, tasks: [...]}. Omit `prompt` and `fileOverlaps`.

Set PLAN_CLI to {plugin_root}/skills/design/scripts/plan.py (resolve plugin root). Run:
`python3 $PLAN_CLI finalize .design/plan-draft.json`

Then: `mv .design/plan-draft.json .design/plan.json`
```

---

## Contracts

### plan.json (schemaVersion 3)

The authoritative interface between design and execute. Execute reads this file; design produces it.

**Fields**: schemaVersion, goal, context {stack, conventions, testCommand, buildCommand, lsp}, progress {completedTasks, surprises, decisions}, tasks[]

**Task fields**: subject, description, activeForm, status, result, attempts, blockedBy, prompt, fileOverlaps, metadata {type, files {create, modify}, reads}, agent {role, model, approach, contextFiles, assumptions, acceptanceCriteria, rollbackTriggers, constraints}

Scripts validate via `finalize` command.

### Analysis Artifacts

Preserved in `.design/` for execute workers to reference via contextFiles:
- `expert-{name}.json` — per-expert findings and task recommendations

**Goal**: $ARGUMENTS
