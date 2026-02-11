---
name: design
description: "Decompose a goal into a structured plan with enriched task specs and safety checks."
argument-hint: "<goal description>"
---

# Design

Decompose a goal into `.design/plan.json` using an adaptive team of specialist agents. The lead manages team lifecycle. ALL analytical work happens inside agents. **This skill only designs — it does NOT execute.**

**Do NOT use `EnterPlanMode`** — this skill IS the plan.

**Lead boundaries**: Use only `TeamCreate`, `TeamDelete`, `TaskCreate`, `TaskUpdate`, `TaskList`, `SendMessage`, `Task`, `AskUserQuestion`, and `Bash` (cleanup, verification, `python3 $PLAN_CLI` only). Never read source files, use MCP tools, `Grep`, `Glob`, or `LSP`. The lead orchestrates — agents think.

**No polling**: Messages auto-deliver. Never use `sleep` or Bash loops to wait.

### Script Setup

Resolve the plugin root directory (containing `.claude-plugin/` and `skills/`). Set:

```
PLAN_CLI = {plugin_root}/skills/design/scripts/plan.py
```

All script calls: `python3 $PLAN_CLI <command> [args]` via Bash. Output is JSON with `{"ok": true/false, ...}`.

---

## Flow

### 1. Pre-flight

1. `AskUserQuestion` only when reasonable developers would disagree and the codebase doesn't answer it.
2. If >12 tasks likely needed, suggest phases. Design only phase 1.
3. Check existing plan: `python3 $PLAN_CLI status-counts .design/plan.json`. If `ok` and `isResume`: ask user "Existing plan has {counts} tasks. Overwrite?" If declined, stop.
4. Clean stale staging: `mkdir -p .design/history && find .design -mindepth 1 -maxdepth 1 ! -name history -exec rm -rf {} +`

### 2. Team + Analyst

Create the team and spawn a single goal analyst. The analyst does the deep thinking — understanding the problem, researching solutions, and recommending the expert team.

1. `TeamDelete(team_name: "do-design")` (ignore errors), `TeamCreate(team_name: "do-design")`. If TeamCreate fails, tell user Agent Teams is required and stop.
2. `TaskCreate` for analyst, then spawn:

```
Task(subagent_type: "general-purpose", team_name: "do-design", name: "analyst", model: opus, prompt: <ANALYST_PROMPT>)
```

**Fallback**: If analyst fails, do minimal inline analysis: read package.json/pyproject.toml for stack, compose a default team of one architect + one plan-writer.

### 3. Grow the Team

When the analyst messages back, read their findings:

```
python3 $PLAN_CLI extract-fields .design/goal-analysis.json complexity complexityRationale recommendedTeam
```

Report complexity and expert count to the user.

**If the analyst recommends no experts** (trivial goal, 1-3 tasks): skip experts. Spawn a single plan-writer Task subagent (not teammate) with model sonnet, reading only goal-analysis.json. Quality gate: warn if taskCount > 3 or depth > 2.

**Otherwise**: Create TaskList entries for each recommended expert and a plan-writer. Wire the plan-writer `blockedBy` all experts via TaskUpdate. Spawn all experts in parallel, then the plan-writer. Use the mandate-based prompts below — fill in `{goal}`, `{name}`, `{role}`, `{mandate}` from the analyst's `recommendedTeam`.

The lead uses judgment. The analyst might recommend 1 expert or 5. All architects, all researchers, or a mix. Spawn what makes sense for the goal.

### 4. Collect and Finalize

Wait for the plan-writer's message. Then:

1. Validate: `python3 $PLAN_CLI validate .design/plan.json`. Stop on failure.
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

**Two-tier fallback** (if team fails to produce plan.json):
1. Retry with single plan-writer Task subagent reading expert files.
2. Merge inline: process expert files one at a time, validate, run scripts, write plan.json directly.

---

## Agent Prompts

### ANALYST_PROMPT

The analyst is the most important agent. Research depth directly determines plan quality. Fill `{goal}`:

```
You are the Goal Analyst on the do-design team. Your job: deeply understand the goal, research the problem domain, explore the codebase, and recommend the expert team.

**Goal**: {goal}

## Research

Do genuine multi-hop research. Don't stop at the first answer.

- Use WebSearch iteratively: initial search -> read promising results via WebFetch -> follow references -> deeper search based on what you learned
- Find academic approaches, algorithms, and established methodologies relevant to the goal
- Evaluate existing libraries: name, URL, version, what it does, how it applies to this goal, concerns/limitations
- Identify community best practices and patterns
- Assess prior art: what has been tried before, what worked, what didn't

**Quality bar**: Your research should reach the depth of finding specific algorithms with names and references, specific libraries with URLs and version numbers, practical applicability assessments, and concrete tradeoffs. Surface-level summaries are not enough.

## Codebase

Explore the codebase to ground your research in reality:
- Project manifests for stack, build/test commands
- CLAUDE.md for conventions
- Relevant modules via grep/glob
- LSP if available

## Reasoning

Use mcp__sequential-thinking__sequentialthinking (if available, else inline reasoning) to decompose the goal: real sub-problems vs stated goal, known patterns, prior art, actual complexity.

## Output

Propose 2-3 approaches with: name, description, pros/cons, effort (low/med/high), risk (low/med/high). Mark one recommended with rationale.

Assess complexity: **minimal** (1-3 tasks, single obvious approach), **standard** (4-8 tasks, some design decisions), or **full** (9+ tasks, cross-cutting concerns).

Recommend experts. Types: **architect** (analyzes codebase — structure, patterns, what needs to change) or **researcher** (searches externally — patterns, libraries, best practices). Each: name (kebab-case), role, type, model (opus/sonnet/haiku), one-line mandate. For minimal goals, you may recommend zero experts (plan-writer handles it directly).

Write .design/goal-analysis.json:
{"goal", "refinedGoal", "concepts", "priorArt", "existingLibraries": [{"name", "url", "relevance", "description", "applicability", "concerns"}], "codebaseContext": {"stack", "conventions", "testCommand", "buildCommand", "lsp", "relevantModules", "existingPatterns"}, "subProblems", "approaches": [{"name", "description", "pros", "cons", "effort", "risk", "recommended", "rationale"}], "complexity", "complexityRationale", "scopeNotes", "recommendedTeam": [{"name", "role", "type", "model", "mandate"}]}

Mark your task completed. Read ~/.claude/teams/do-design/config.json for the lead's name and tell them what you found — complexity, key findings, and how many experts you recommend.
```

### ARCHITECT_PROMPT

Fill `{goal}`, `{name}`, `{role}`, `{mandate}`:

```
You are {name}, a {role} (domain architect) on the do-design team.

**Goal**: {goal}
**Mandate**: {mandate}

Read .design/goal-analysis.json for context. Analyze the codebase through your domain lens — ensure MECE coverage within your mandate. Read source files, use LSP if available. Challenge assumptions from goal-analysis.json where your findings disagree.

For each recommended task: subject, description, type, files {create, modify}, dependencies (by subject), agent: {role (kebab-case — becomes worker name), model, approach, contextFiles [{path, reason}], assumptions [{claim, verify (shell cmd), severity}], acceptanceCriteria [{criterion, check (shell cmd)}], rollbackTriggers, constraints}.

Write .design/expert-{name}.json with findings and tasks arrays. Mark your task completed and tell the lead what you found.
```

### RESEARCHER_PROMPT

Fill `{goal}`, `{name}`, `{role}`, `{mandate}`:

```
You are {name}, a {role} (external researcher) on the do-design team.

**Goal**: {goal}
**Mandate**: {mandate}

Read .design/goal-analysis.json for context. Use WebSearch/WebFetch for deep multi-hop research: academic papers, community best practices, libraries with URLs and version numbers, idiomatic solutions, official docs. Evaluate findings against the project's stack. Read relevant source files to understand integration points.

**Quality bar**: Find specific algorithms, specific libraries with URLs, practical applicability assessments, and concrete tradeoffs. Go beyond the analyst's initial research — follow citations, explore alternatives, validate claims.

For each recommended task: subject, description, type, files {create, modify}, dependencies (by subject), agent: {role (kebab-case — becomes worker name), model, approach (reference your research), contextFiles, assumptions, acceptanceCriteria, rollbackTriggers, constraints}.

Write .design/expert-{name}.json with research (findings with sources), recommendations, and tasks. Mark your task completed and tell the lead what you found.
```

### PLAN_WRITER_PROMPT

Fill `{goal}`, `{expectedExpertCount}`:

```
You are the Plan Writer on the do-design team. Merge expert analyses into .design/plan.json.

**Goal**: {goal}

Read .design/goal-analysis.json for codebase context (use as plan context field). Read .design/expert-*.json (expect {expectedExpertCount}). If .design/critic.json exists, read it.

Merge expert tasks: converging views increase confidence, diverging views need judgment calls — record decisions in progress.decisions. Deduplicate and ensure MECE coverage.

## Task Schema (every task needs all of these)

- subject, description (WHY this task matters + connection to dependents), activeForm, status: pending, result: null, attempts: 0, blockedBy (indices)
- metadata: {type, files: {create:[], modify:[]}, reads}
- agent: {role (kebab-case — becomes worker name), model, approach, contextFiles [{path, reason}], assumptions [{claim, verify (shell cmd), severity}], acceptanceCriteria [{criterion, check (shell cmd)}], rollbackTriggers, constraints}
- Add .design/goal-analysis.json to every task's contextFiles. Add relevant expert files.
- File metadata must be accurate (workers use for git add). Acceptance checks must be self-contained shell commands.

## Safety

For each modify path: add blocking assumption `test -f {path}`. Cross-task file overlaps: add blocking assumptions. Convert blocking assumptions to rollback triggers.

## Finalize

1. Write .design/plan-draft.json: {schemaVersion: 3, goal, context, progress: {completedTasks: [], surprises: [], decisions: []}, tasks}. Omit `prompt` and `fileOverlaps` — scripts add them.
2. Set PLAN_CLI to {plugin_root}/skills/design/scripts/plan.py (resolve plugin root). Run in order (fix issues if any fail):
   - `python3 $PLAN_CLI validate-structure .design/plan-draft.json`
   - `python3 $PLAN_CLI assemble-prompts .design/plan-draft.json`
   - `python3 $PLAN_CLI compute-overlaps .design/plan-draft.json`
3. `mv .design/plan-draft.json .design/plan.json`

Mark your task completed. Read ~/.claude/teams/do-design/config.json for the lead's name and tell them the plan is ready with task count, max depth, and a brief summary.
```

### MINIMAL_PLAN_WRITER_PROMPT (Task subagent, not teammate)

For trivial goals when analyst recommends no experts. Fill `{goal}`:

```
Generate .design/plan.json for a minimal-complexity goal.

**Goal**: {goal}

Read .design/goal-analysis.json for context and recommended approach. Generate 1-3 tasks following the task schema: subject, description (WHY + connection to dependents), activeForm, status: pending, result: null, attempts: 0, blockedBy: [], metadata: {type, files: {create:[], modify:[]}, reads}, agent: {role (kebab-case), model, approach, contextFiles [{path, reason}], assumptions [{claim, verify, severity}], acceptanceCriteria [{criterion, check}], rollbackTriggers, constraints}.

Safety: for each modify path, add blocking assumption `test -f {path}`. Convert blocking assumptions to rollback triggers.

Write .design/plan-draft.json: {schemaVersion: 3, goal, context: {stack, conventions, testCommand, buildCommand, lsp}, progress: {completedTasks: [], surprises: [], decisions: []}, tasks: [...]}. Omit `prompt` and `fileOverlaps`.

Set PLAN_CLI to {plugin_root}/skills/design/scripts/plan.py (resolve plugin root). Run in order:
- `python3 $PLAN_CLI validate-structure .design/plan-draft.json`
- `python3 $PLAN_CLI assemble-prompts .design/plan-draft.json`
- `python3 $PLAN_CLI compute-overlaps .design/plan-draft.json`

Then: `mv .design/plan-draft.json .design/plan.json`
```

---

## Contracts

### plan.json (schemaVersion 3)

The authoritative interface between design and execute. Execute reads this file; design produces it.

```json
{
  "schemaVersion": 3,
  "goal": "string",
  "context": {"stack", "conventions", "testCommand", "buildCommand", "lsp"},
  "progress": {"completedTasks": [], "surprises": [], "decisions": []},
  "tasks": [{
    "subject": "string",
    "description": "string (WHY + connection to dependents)",
    "activeForm": "string (present continuous)",
    "status": "pending",
    "result": null,
    "attempts": 0,
    "blockedBy": [0],
    "prompt": "string (assembled by script)",
    "fileOverlaps": [1, 2],
    "metadata": {"type": "string", "files": {"create": [], "modify": []}, "reads": []},
    "agent": {
      "role": "kebab-case-slug (becomes worker name)",
      "model": "opus|sonnet|haiku",
      "approach": "string",
      "contextFiles": [{"path": "string", "reason": "string"}],
      "assumptions": [{"claim": "string", "verify": "shell cmd", "severity": "blocking|warning"}],
      "acceptanceCriteria": [{"criterion": "string", "check": "shell cmd"}],
      "rollbackTriggers": ["string"],
      "constraints": ["string"]
    }
  }]
}
```

### Analysis Artifacts

Preserved in `.design/` for execute workers to reference via contextFiles:
- `goal-analysis.json` — analyst output (goal decomposition, research, approaches, recommended team)
- `expert-{name}.json` — per-expert findings and task recommendations
- `critic.json` — if a critic was part of the team (optional)

**Goal**: $ARGUMENTS
