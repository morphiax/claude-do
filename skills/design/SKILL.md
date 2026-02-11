---
name: design
description: "Decompose a goal into a structured plan with enriched task specs and safety checks."
argument-hint: "<goal description>"
---

# Design

Decompose a goal into `.design/plan.json` using a dynamically growing team of specialist agents. The lead spawns agents and manages lifecycle. ALL analytical work happens inside agents. **This skill only designs — it does NOT execute.**

**Do NOT use `EnterPlanMode`** — this skill IS the plan.

**Lead tool boundary**: `TeamCreate`, `TeamDelete`, `TaskCreate`, `TaskUpdate`, `TaskList`, `SendMessage`, `Task`, `AskUserQuestion`, and `Bash` (cleanup, verification, `python3 $PLAN_CLI` only). Never read source files, use MCP tools, `Grep`, `Glob`, or `LSP`. Every goal — simple or complex, code or research — goes through the team. The lead never analyzes directly.

**No polling**: Messages auto-deliver. Never use `sleep` or Bash loops to wait.

### Script Setup

Resolve the plugin root directory (containing `.claude-plugin/` and `skills/`). Set:

```
PLAN_CLI = {plugin_root}/skills/design/scripts/plan.py
```

All script calls: `python3 $PLAN_CLI <command> [args]` via Bash. Output is JSON with `{"ok": true/false, ...}`.

---

## Step 1: Pre-flight

1. `AskUserQuestion` only when reasonable developers would choose differently and the codebase doesn't answer it.
2. If >12 tasks likely needed, suggest phases. Design only phase 1.
3. Check existing plan: `python3 $PLAN_CLI status-counts .design/plan.json`. If `ok` and `isResume`: ask user "Existing plan has {counts} tasks. Overwrite?" If declined, stop.
4. Clean stale staging: `mkdir -p .design/history && find .design -mindepth 1 -maxdepth 1 ! -name history -exec rm -rf {} +`

## Step 2: Team + Goal Analyst

1. `TeamDelete(team_name: "do-design")` (ignore errors), `TeamCreate(team_name: "do-design")`. If TeamCreate fails, tell user Agent Teams is required and stop.
2. `TaskCreate` for analyst, then spawn:

```
Task(subagent_type: "general-purpose", team_name: "do-design", name: "analyst", model: opus, prompt: <ANALYST_PROMPT>)
```

### ANALYST_PROMPT

Fill `{goal}`:

```
You are the Goal Analyst. Deeply understand the goal, explore the codebase, and recommend the expert team.

**Goal**: {goal}

## Instructions

1. Use mcp__sequential-thinking__sequentialthinking (if available, else inline reasoning) to decompose the goal: real sub-problems vs stated goal, known patterns, prior art, actual complexity.

2. Explore the codebase: project manifests for stack/build/test commands, CLAUDE.md for conventions, grep/glob for relevant modules, LSP if available.

3. Propose 2-3 approaches with: name, description, pros/cons, effort (low/med/high), risk (low/med/high). Mark one recommended with rationale.

4. Assess complexity:
   - **minimal** — 1-3 tasks, single obvious approach
   - **standard** — 4-8 tasks, some design decisions
   - **full** — 9+ tasks, multiple approaches, cross-cutting concerns

5. Recommend 2-5 experts. Types: **architect** (analyzes codebase — what needs to happen) or **researcher** (searches externally — patterns, libraries, best practices). Each: name, role, type, model (opus/sonnet/haiku), one-line mandate.

## Output

Write .design/goal-analysis.json:
{"goal", "refinedGoal", "concepts", "priorArt", "codebaseContext": {"stack", "conventions", "testCommand", "buildCommand", "lsp", "relevantModules", "existingPatterns"}, "subProblems", "approaches": [{"name", "description", "pros", "cons", "effort", "risk", "recommended", "rationale"}], "complexity", "complexityRationale", "scopeNotes", "recommendedTeam": [{"name", "role", "type", "model", "mandate"}]}

Mark your task completed. Read ~/.claude/teams/do-design/config.json for the lead's name, then SendMessage "ANALYST_COMPLETE".
```

Wait for the analyst's message, then proceed to Complexity Branching.

**Fallback**: If analyst fails, do minimal inline analysis: read package.json for stack, compose default team.

## Complexity Branching

`python3 $PLAN_CLI extract-fields .design/goal-analysis.json complexity complexityRationale recommendedTeam`. Report complexity and expert count to user.

### Minimal Path

Skip Step 3. Spawn single plan-writer **Task subagent** (not teammate):

```
Task(subagent_type: "general-purpose", model: sonnet, prompt: <MINIMAL_PLAN_WRITER_PROMPT>)
```

#### MINIMAL_PLAN_WRITER_PROMPT

Fill `{goal}`:

```
Generate .design/plan.json for a minimal-complexity goal.

**Goal**: {goal}

1. Read .design/goal-analysis.json for context and recommended approach.
2. Generate 1-3 tasks. Each task needs:
   - subject, description (WHY + connection to dependents), activeForm, status: pending, result: null, attempts: 0, blockedBy: []
   - metadata: {type, files: {create:[], modify:[]}, reads}
   - agent: {role (kebab-case slug — becomes worker name), model, approach, contextFiles [{path, reason}], assumptions [{claim, verify (shell cmd), severity}], acceptanceCriteria [{criterion, check (shell cmd)}], rollbackTriggers, constraints}
   - File metadata must be accurate (workers use for git add). Acceptance criteria checks must be self-contained.
3. Safety: for each modify path, add blocking assumption `test -f {path}`. Convert blocking assumptions to rollback triggers.
4. Write .design/plan-draft.json: {schemaVersion: 3, goal, context: {stack, conventions, testCommand, buildCommand, lsp}, progress: {completedTasks: [], surprises: [], decisions: []}, tasks: [...]}. Omit `prompt` and `fileOverlaps` — scripts add them.
5. Set PLAN_CLI to {plugin_root}/skills/design/scripts/plan.py (resolve plugin root). Run in order:
   - `python3 $PLAN_CLI validate-structure .design/plan-draft.json`
   - `python3 $PLAN_CLI assemble-prompts .design/plan-draft.json`
   - `python3 $PLAN_CLI compute-overlaps .design/plan-draft.json`
6. `mv .design/plan-draft.json .design/plan.json`

Final line of output: {"taskCount": N, "maxDepth": N, "depthSummary": {"1": ["Task 0: subject"], ...}}
```

Quality gate: if taskCount > 3 or depth > 2, warn user. Fallback: write plan inline if subagent fails.

### Standard Path

Spawn experts + plan-writer (no critic). Plan-writer blockedBy all experts. Two-tier fallback applies.

### Full Path

Spawn experts + critic + plan-writer. Critic blockedBy experts, plan-writer blockedBy critic. Two-tier fallback applies.

## Step 3: Experts, Critic, Plan-Writer (standard/full)

Use `recommendedTeam` from analyst. Record expert count as `{expectedExpertCount}`.

1. Create TaskList entries: experts, critic (full only), plan-writer. Wire `blockedBy` via TaskUpdate.
2. Spawn all agents in parallel.

### ARCHITECT_PROMPT

Fill `{goal}`, `{name}`, `{role}`, `{mandate}`:

```
You are {name}, a {role} (domain architect) on a planning team.

**Goal**: {goal}
**Mandate**: {mandate}

Read .design/goal-analysis.json for context. Analyze the codebase through your domain lens — ensure MECE coverage within your mandate. Read source files, use LSP if available. Produce findings and task recommendations.

For each task: subject, description, type, files {create, modify}, dependencies (by subject), agent: {role (kebab-case), model, approach, contextFiles, assumptions [{claim, verify, severity}], acceptanceCriteria [{criterion, check}], rollbackTriggers, constraints}.

Write .design/expert-{name}.json with findings and tasks arrays. Mark your task completed.
```

### RESEARCHER_PROMPT

Fill `{goal}`, `{name}`, `{role}`, `{mandate}`:

```
You are {name}, a {role} (external researcher) on a planning team.

**Goal**: {goal}
**Mandate**: {mandate}

Read .design/goal-analysis.json for context. Use WebSearch/WebFetch to research: community best practices, libraries, idiomatic solutions, official docs. Evaluate findings against the project's stack. Read relevant source files to understand integration points.

For each task: subject, description, type, files {create, modify}, dependencies (by subject), agent: {role (kebab-case), model, approach (reference your research), contextFiles, assumptions, acceptanceCriteria, rollbackTriggers, constraints}.

Write .design/expert-{name}.json with research (findings with sources), recommendations, and tasks. Mark your task completed.
```

### CRITIC_PROMPT (full only)

Fill `{goal}`, `{expectedExpertCount}`:

```
You are the Critic. Stress-test expert proposals before the plan-writer assembles the final plan.

**Goal**: {goal}

Read .design/goal-analysis.json, then glob and read .design/expert-*.json (expect {expectedExpertCount}). For each expert: challenge assumptions, evaluate approach choices, check engineering calibration (over/under-engineered?), assess coherence across proposals. Propose specific adjustments. Verify claims by reading source where feasible.

Write .design/critic.json: {challenges: [{expert, issue, severity (blocking|major|minor), recommendation}], missingCoverage, approachRisks, coherenceIssues, verdict: "proceed|proceed-with-changes|major-rework-needed"}. Mark your task completed.
```

### PLAN_WRITER_PROMPT (standard/full)

Fill `{goal}`, `{expectedExpertCount}`:

```
You are the Plan Writer. Merge expert analyses into .design/plan.json.

**Goal**: {goal}

## Merge and Enrich

1. Read .design/goal-analysis.json for codebase context (use as plan context field).
2. Read .design/expert-*.json (expect {expectedExpertCount}). If .design/critic.json exists, read it.
3. Merge expert tasks: converging views increase confidence, diverging views use critic's assessment to break ties. Deduplicate, ensure MECE coverage. Address critic challenges: blocking (must resolve), major (should address), minor (note in decisions).

## Task Schema

Each task requires:
- subject, description (WHY + connection to dependents), activeForm, status: pending, result: null, attempts: 0, blockedBy (indices)
- metadata: {type, files: {create:[], modify:[]}, reads}
- agent: {role (kebab-case — becomes worker name), model, approach, contextFiles [{path, reason}], assumptions [{claim, verify (shell cmd), severity}], acceptanceCriteria [{criterion, check (shell cmd)}], rollbackTriggers, constraints}
- Add .design/goal-analysis.json to every task's contextFiles. Add relevant expert files.
- File metadata must be accurate (workers use for git add). Acceptance checks must be self-contained.

## Safety

For each modify path: add blocking assumption `test -f {path}`. Cross-task file overlaps: add blocking assumptions. Convert blocking assumptions to rollback triggers.

## Write and Finalize

1. Write .design/plan-draft.json: {schemaVersion: 3, goal, context, progress: {completedTasks: [], surprises: [], decisions: []}, tasks}. Omit `prompt` and `fileOverlaps`.
2. Set PLAN_CLI to {plugin_root}/skills/design/scripts/plan.py. Run in order (fix issues if any fail):
   - `python3 $PLAN_CLI validate-structure .design/plan-draft.json`
   - `python3 $PLAN_CLI assemble-prompts .design/plan-draft.json`
   - `python3 $PLAN_CLI compute-overlaps .design/plan-draft.json`
3. `mv .design/plan-draft.json .design/plan.json`

Mark your task completed. Read ~/.claude/teams/do-design/config.json for the lead's name. SendMessage with: {"taskCount": N, "maxDepth": N, "depthSummary": {...}}
```

After receiving the plan-writer's message: shut down teammates, delete team.

**Two-tier fallback** (if team fails to produce plan.json):
1. Retry with single plan-writer Task subagent reading expert/critic files.
2. Merge inline: process expert files one at a time, validate, run scripts, write plan.json directly.

## Step 4: Cleanup and Summary

1. Validate: `python3 $PLAN_CLI validate .design/plan.json`. Stop on failure.
2. Clean up TaskList (delete all planning tasks so `/do:execute` starts clean).
3. Summary: `python3 $PLAN_CLI summary .design/plan.json`. Display:

```
Plan: {goal}
Tier: {complexity}
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

**Goal**: $ARGUMENTS
