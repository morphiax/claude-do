---
name: design
description: "Decompose a goal into a structured plan with enriched task specs and safety checks."
argument-hint: "<goal description>"
---

# Design

Thin-lead orchestrator: decompose a goal into `.design/plan.json` using a dynamically growing team of specialist agents. The lead is purely mechanical — it spawns agents, relays messages, and manages team lifecycle. ALL analytical work (goal understanding, codebase exploration, domain analysis, synthesis, plan writing) happens inside agents. **This skill only designs — it does NOT execute.**

**Do NOT use EnterPlanMode — this skill IS the plan.**

### Conventions

- **Atomic write**: Write to `{path}.tmp`, then rename to `{path}`. All file outputs in this skill use this pattern.
- **Signaling patterns**: Agents signal completion via TaskList and `SendMessage(type: "message")` to the lead. The lead parses JSON from message content.

**MANDATORY: Execute ALL steps (1–4) for EVERY invocation. The lead NEVER analyzes the goal, reads source files, or reasons about implementation. Do NOT use `sequential-thinking`, `Read`, `Grep`, or any analytical tool — the lead's job is agent lifecycle management. The ONLY valid output of this skill is `.design/plan.json` — produced by the agent team. This applies regardless of goal type, complexity, or apparent simplicity. Audits, reviews, research, one-line fixes — all go through the team. No exceptions exist. If you are tempted to "just do it directly," STOP — that impulse is the exact failure mode this rule prevents.**

## Step 1: Pre-flight

1. Use `AskUserQuestion` to clarify only when reasonable developers would choose differently and the codebase doesn't answer it: scope boundaries, done-state, technical preferences, compatibility, priority.
2. If >12 tasks likely needed, suggest phases. Design only phase 1.
3. Check for existing `.design/plan.json`. If it exists with `progress.currentWave > 0` or any non-pending task statuses, use `AskUserQuestion` to confirm overwrite — execution may be in progress. Record `overwriteApproved` flag.
4. Clean up stale staging: `rm -rf .design/ && mkdir -p .design/`

## Step 2: Team + Goal Analyst

Create the team and spawn a goal analyst as the first teammate. The analyst deeply understands the goal, explores the codebase, and recommends the expert team composition.

1. Attempt cleanup of any stale team: `TeamDelete(team_name: "do-design")` (ignore errors)
2. `TeamCreate(team_name: "do-design")`
3. `TaskCreate` for the goal analyst (subject: "Analyze goal and recommend team composition")
4. Spawn the goal analyst:

```
Task:
  subagent_type: "general-purpose"
  team_name: "do-design"
  name: "analyst"
  model: opus
  prompt: <analyst prompt below>
```

**Goal analyst prompt** — fill `{goal}`:

```
You are the Goal Analyst on a planning team. Your job is to deeply understand the goal, explore the codebase, and recommend what expert team should be spawned to design the plan.

**Goal**: {goal}

## Instructions

1. Use mcp__sequential-thinking__sequentialthinking (if available, otherwise inline numbered reasoning) to decompose the goal:
   - What are the real sub-problems? Is the stated goal the actual goal?
   - What known patterns, frameworks, or approaches does this map to?
   - What prior art exists in the codebase or ecosystem?
   - Is this simpler or more complex than stated?

2. Explore the codebase for context:
   - Read package.json / pyproject.toml / Cargo.toml / go.mod — identify stack, frameworks, build/test commands
   - Read CLAUDE.md, linter/formatter configs — extract conventions
   - Grep/Glob for modules, files, and patterns the goal touches
   - LSP(documentSymbol) on a key source file if available
   - Identify existing patterns relevant to the goal

3. Based on your understanding, recommend 2–5 expert roles to cover the goal's domains. For each expert:
   - name, role, model (opus for architecture/analysis, sonnet for implementation, haiku for verification)
   - one-line mandate enriched with specific concepts and prior art you found
   - what they should focus on that you didn't fully resolve

## Output

Write atomically to .design/goal-analysis.json:

{
  "goal": "{original goal}",
  "refinedGoal": "{restated if different}",
  "concepts": ["pattern/framework/approach names found"],
  "priorArt": ["actual findings from codebase — libraries, patterns, existing code"],
  "codebaseContext": {
    "stack": "...",
    "conventions": "...",
    "testCommand": "...",
    "buildCommand": "...",
    "lsp": {"available": []},
    "relevantModules": [],
    "existingPatterns": []
  },
  "subProblems": ["decomposed sub-problems"],
  "scopeNotes": "refinements or hidden complexity",
  "recommendedTeam": [
    {"name": "...", "role": "...", "model": "opus|sonnet|haiku", "mandate": "..."}
  ]
}

Claim your task from the task list and mark completed when done.

Read ~/.claude/teams/do-design/config.json to discover the team lead's name. Send your result to the lead using SendMessage:

    type:      message
    recipient: {lead-name}
    content:   ANALYST_COMPLETE
    summary:   Goal analysis complete
```

**Lead waits** for the analyst's `SendMessage`. Once received, proceed to Step 3.

**Fallback**: If the analyst fails to produce `.design/goal-analysis.json`, the lead performs minimal inline analysis: read package.json for stack, identify 2–3 obvious domains from the goal text, compose a default team. Log: "Analyst failed — using minimal team composition."

## Step 3: Grow Team with Experts + Plan-Writer

Read `.design/goal-analysis.json` to get the analyst's recommended team. Then grow the existing team by spawning experts and a plan-writer.

1. Read `.design/goal-analysis.json` — extract `recommendedTeam` array.
2. Create TaskList entries with dependencies:
   - For each recommended expert: `TaskCreate` with mandate as subject
   - `TaskCreate` for plan-writer (subject: "Merge expert analyses, validate, and write plan.json")
   - Wire dependencies via `TaskUpdate(addBlockedBy)`: plan-writer blockedBy all expert task IDs
3. Spawn all new agents in parallel via `Task(subagent_type: "general-purpose", team_name: "do-design", name: "{name}", model: "{model}")`:
   - All expert agents from the recommendation
   - `plan-writer` (model: `opus`)

**Expert bootstrap prompt** — fill `{goal}`, `{name}`, `{role}`, `{mandate}`:

```
You are a {role} on a planning team.

**Goal**: {goal}
**Your name**: {name}
**Your mandate**: {mandate}

## Context
Read .design/goal-analysis.json for goal decomposition, codebase context, concept mapping, prior art, and scope notes. Use this to focus your analysis — the goal analyst has already explored the codebase and identified key patterns.

## Instructions

1. Analyze the goal through your domain lens — ensure MECE coverage within your mandate.
2. Gather additional context you need beyond what the analyst found: read specific source files, use LSP (documentSymbol, goToDefinition) when available, use WebSearch/WebFetch if external research is needed.
3. Follow up on prior art relevant to your domain — verify the analyst's findings and dig deeper where needed.
4. Produce findings (risks, observations) and task recommendations.

## Task Recommendations

For each task you recommend, include:
- subject, description, type (research|implementation|testing|configuration)
- files: {create: [], modify: []}
- wave assignment (1 = no deps, 2+ = depends on earlier waves)
- dependencies (which other tasks must complete first, by subject reference)
- agent spec: role, model (opus for architecture/analysis, sonnet for implementation, haiku for verification), approach, contextFiles [{path, reason}], assumptions [{claim, verify (shell cmd), severity: blocking|warning}], acceptanceCriteria [{criterion, check (shell cmd)}], rollbackTriggers ["If X, STOP and return BLOCKED: reason"], constraints

## Output
**Context efficiency**: Minimize text output. Write reasoning to .design/expert-{name}.log if needed. Target: under 100 tokens of non-JSON output.

Write findings atomically to .design/expert-{name}.json with findings array and tasks array.
Claim your task from the task list and mark completed when done.
FINAL line: one-line summary of findings.
```

**Plan-writer teammate prompt** — fill `{goal}` and `{overwriteApproved}`:

```
You are the Plan Writer on a planning team. Merge expert analyses, validate, enrich, and write .design/plan.json.

**Goal**: {goal}
**Overwrite approved**: {overwriteApproved}

Your task in the TaskList is blocked by the expert agents. Once unblocked, proceed:

## Phase 1: Context & Merge

1. Read .design/goal-analysis.json for goal decomposition, codebase context, concepts, and prior art.
2. Use the codebaseContext from goal-analysis.json as the basis for plan.json's context field. Supplement with additional scans if needed (package.json, CLAUDE.md, linter configs).
3. Glob .design/expert-*.json and read each expert analysis.
4. Merge expert task recommendations:
   - Where experts converge, increase confidence
   - Where they diverge, investigate and choose the strongest position
   - Deduplicate overlapping tasks
   - Ensure MECE coverage — no gaps, no overlaps
   - Resolve conflicting wave assignments and dependencies

## Phase 2: Validate & Enrich

For each task verify all required fields. Fill gaps:

Required agent fields: role, model, approach, contextFiles [{path, reason, lines?}], assumptions [{claim, verify (shell cmd), severity: blocking|warning}], acceptanceCriteria [{criterion, check (shell cmd)}], rollbackTriggers ["If X, STOP and return BLOCKED: reason"], constraints. Optional: expertise, priorArt, fallback.
Required metadata: type (research|implementation|testing|configuration), files {create:[], modify:[]}, reads.
Required task fields: subject, description, activeForm, status (pending), result (null), attempts (0), wave, blockedBy.

Description rule: explain WHY and how it connects to dependents — not just what. An executor with zero context must act on it.
Non-code goals: acceptance criteria may use content-based checks (grep). Rollback triggers reference content expectations.
Count gaps filled as gapsFilled.

## Phase 3: Auto-generate Safety

- File existence: for each path in metadata.files.modify, add blocking assumption `test -f {path}`
- Cross-task deps: if task B modifies/creates files overlapping task A (same/earlier wave), add blocking assumption `test -f {file}`
- Convert every blocking assumption to a rollback trigger

## Phase 4: Validate Plan (8 checks)

1. Tasks array >= 1 task. If 0, return error.
2. No two same-wave tasks share files in create or modify.
3. No task reads overlaps same-wave task creates/modifies.
4. All blockedBy valid indices. Topological sort — cycles → restructure.
5. Wave = 1 + max(blockedBy waves). Recalculate if mismatched.
6. Every task has >= 1 assumption and >= 1 rollback trigger.
7. Total tasks <= 12.
8. Max wave <= 4 (restructure for parallelism if exceeded).
Self-repair: fix and re-validate. After 2 attempts, include in validationIssues and proceed.

## Phase 5: Write .design/plan.json

Schema (schemaVersion 2): {schemaVersion: 2, goal, context: {stack, conventions, testCommand, buildCommand, lsp}, progress: {currentWave: 0, completedTasks: [], surprises: [], decisions: []}, tasks: [...]}
Each task uses the schema from Phase 2.

Schema rules: tasks ordered (index = ID, 0-based), blockedBy references indices, wave: 1 = no deps / 2+ = 1+max(blockedBy waves), status: pending|in_progress|completed|failed|blocked|skipped.

Write atomically to .design/plan.json.

## Output
**Context efficiency**: Minimize text output. Write reasoning to .design/plan-writer.log if needed. Target: under 100 tokens of non-JSON output.

Claim your task from the task list and mark completed when done.

Read ~/.claude/teams/do-design/config.json to discover the team lead's name. Send your result to the lead using SendMessage:

    type:      message
    recipient: {lead-name}
    content:   <FINAL-line JSON below>
    summary:   Plan written

JSON schema: {"taskCount": N, "waveCount": N, "gapsFilled": N, "validationIssues": [], "waveSummary": {"1": ["Task 0: subject"], ...}}
On unresolvable error, send JSON with error (string) and validationIssues (array) keys instead.
```

**Lead wait pattern**: After spawning all agents, the lead waits. The plan-writer's `SendMessage` is delivered automatically as a conversation turn. Parse the JSON from the message content.

**Timeout protection**: If agents haven't completed after a reasonable period, proceed with available results. Note which agents timed out.

After receiving the plan-writer's message: `SendMessage(type: "shutdown_request")` to each teammate, wait for confirmations, `TeamDelete(team_name: "do-design")`.

**Two-tier fallback** — triggered when the team fails to produce `.design/plan.json` (plan-writer message not received, teammate stall, or team infrastructure error):

- **Tier 1 — Sequential retry**: Shut down the team (`SendMessage(type: "shutdown_request")` to all, then `TeamDelete`). Spawn a single plan-writer Task subagent (not teammate) with the plan-writer prompt above. It reads the same `.design/expert-*.json` files.
- **Tier 2 — Inline with context minimization**: If the sequential retry also fails, perform merge and plan writing inline. Process one `.design/expert-*.json` file at a time, extract only the tasks array from each, merge incrementally into a combined task list. Execute Phases 2–5 sequentially with reduced scope.

## Step 4: Cleanup & Summary

1. **Lightweight verification** (lead): Run `python3 -c "import json; p=json.load(open('.design/plan.json')); assert p.get('schemaVersion') == 2, 'schemaVersion must be 2'"` to confirm schemaVersion. Use the plan-writer's stored `taskCount` and `waveCount` from its SendMessage for verification (no need to re-extract).
2. **Clean up TaskList**: Delete all tasks created during planning so `/do:execute` starts with a clean TaskList.
3. **Clean up intermediate files**: `rm -f .design/goal-analysis.json .design/expert-*.json .design/expert-*.log .design/plan-writer.log` — keep only `.design/plan.json`.

4. **Output summary** using stored plan-writer data (`waveSummary`, `taskCount`, `waveCount`):

```
Plan: {goal}
Tasks: {taskCount} across {waveCount} waves

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
