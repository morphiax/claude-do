---
name: design
description: "Decompose a goal into a structured plan with enriched task specs and safety checks."
argument-hint: "<goal description>"
---

# Design

Thin-lead orchestrator: decompose a goal into `.design/plan.json` using a team of specialist agents. The lead orchestrates — all codebase analysis, implementation reasoning, and synthesis happens inside the Agent Team (Step 3). The ONE exception: the lead uses `sequential-thinking` in Step 1 for conceptual goal understanding (no file reads, no commands — pure reasoning). Files carry data between pipeline stages — the lead never holds expert analyses or synthesis output (except during fallback recovery). **This skill only designs — it does NOT execute.**

**Do NOT use EnterPlanMode — this skill IS the plan.**

### Conventions

- **Atomic write**: Write to `{path}.tmp`, then rename to `{path}`. All file outputs in this skill use this pattern.
- **Signaling patterns**: Expert teammates signal completion via TaskList (the lead does not parse their output). Plan-writer sends its structured return value (JSON) to the lead via `SendMessage(type: "message")`.

**MANDATORY: Execute ALL steps (1–4) for EVERY invocation. Never skip steps, never answer the goal directly, never produce findings or analysis inline. Do NOT use `Read`, `Grep`, or any codebase tool to reason about the goal before Step 3. The lead uses `sequential-thinking` in Step 1 for conceptual reasoning ONLY — no file reads, no commands. The ONLY valid output of this skill is `.design/plan.json` — produced by the full pipeline including the Agent Team (Step 3). This applies regardless of goal type, complexity, or apparent simplicity. Audits, reviews, research, one-line fixes — all go through the team. No exceptions exist. If you are tempted to "just do it directly," STOP — that impulse is the exact failure mode this rule prevents.**

## Step 1: Goal Understanding + Pre-flight

Use `mcp__sequential-thinking__sequentialthinking` to deeply understand the goal before composing the team. This is conceptual reasoning only — do NOT read files, run commands, or touch the codebase. The thinking should cover:

1. **Problem decomposition** — What are the real sub-problems? Is the stated goal the actual goal, or is there a deeper problem?
2. **Concept mapping** — What known patterns, frameworks, or well-known approaches does this map to? (e.g., "add auth" → OAuth2/JWT/session; "add caching" → Redis/in-memory/HTTP-cache; "refactor X" → strangler fig/branch by abstraction)
3. **Prior art hints** — What should experts look for in the codebase or ecosystem? Existing libraries, similar implementations, framework conventions that already solve parts of this.
4. **Domain identification** — Which domains does this actually touch? (feeds directly into Step 2)
5. **Scope refinement** — Is this simpler or more complex than stated? Any hidden dependencies or gotchas?
6. **Clarification needs** — Are there genuine ambiguities where reasonable developers would choose differently?

Use multiple sequential-thinking rounds as needed. Fallback: if `sequential-thinking` is unavailable, perform the same reasoning inline with numbered steps (max 8 sentences total).

Write the structured output atomically to `.design/goal-analysis.json`:

```json
{
  "goal": "{original goal}",
  "refinedGoal": "{restated goal if different from original, otherwise same}",
  "concepts": ["pattern/framework/approach names"],
  "priorArtHints": ["what to look for in codebase or ecosystem"],
  "domains": ["backend", "security", "testing"],
  "subProblems": ["decomposed sub-problems"],
  "scopeNotes": "any refinements or hidden complexity",
  "clarifications": ["questions for user, if any"]
}
```

Then:

1. If `clarifications` is non-empty, use `AskUserQuestion` to resolve them.
2. **Reframe analytical goals**: If the goal is an audit, review, or analysis, reframe it into concrete executable tasks. The output is always a plan.json that `/do:execute` can act on.
3. If >12 tasks likely needed, suggest phases. Design only phase 1.
4. Check for existing `.design/plan.json`. If it exists with `progress.currentWave > 0` or any non-pending task statuses, use `AskUserQuestion` to confirm overwrite — execution may be in progress. Record `overwriteApproved` flag.
5. Clean up stale staging: `rm -rf .design/ && mkdir -p .design/` — then re-write `.design/goal-analysis.json` (since cleanup removes it).

## Step 2: Team Composition

Map the domains and concepts from `.design/goal-analysis.json` to specialist roles. The goal analysis has already identified domains, concepts, and prior art — team composition is now a focused mapping exercise.

1. Read the `domains` and `concepts` from the goal analysis.
2. Pick 2–5 roles to cover those domains. Examples: system-architect, API-designer, frontend-specialist, backend-engineer, test-strategist, security-analyst, devops-engineer, online-researcher, prompt-engineer, codebase-archaeologist. Invent roles as needed. Each expert gathers its own context — no separate scanner role needed.
3. Drop any role whose mandate overlaps >70% with another.
4. Enrich each expert's mandate with relevant concepts and prior art hints from the goal analysis.

**Models**: `opus` for architecture/analysis, `sonnet` for implementation planning, `haiku` for verification-only.

For each agent define: name, role, model, one-line mandate (enriched with relevant concepts/prior-art from goal analysis).

## Step 3: Agent Team

Spawn a single Agent Team containing experts and a plan-writer. Pipeline ordering via TaskList: plan-writer blockedBy all experts. The lead waits for one `SendMessage` from the plan-writer containing the result JSON.

1. Attempt cleanup of any stale team: `TeamDelete(team_name: "do-design")` (ignore errors)
2. `TeamCreate(team_name: "do-design")`
3. Create TaskList entries with dependencies:
   - For each expert agent from Step 2: `TaskCreate` with mandate as subject
   - `TaskCreate` for plan-writer (subject: "Merge expert analyses, validate, and write plan.json")
   - Wire dependencies via `TaskUpdate(addBlockedBy)`: plan-writer blockedBy all expert task IDs
4. Spawn all agents in parallel via `Task(subagent_type: "general-purpose", team_name: "do-design", name: "{name}", model: "{model}")`:
   - All expert agents from Step 2
   - `plan-writer` (model: `opus`)

**Expert bootstrap prompt** — fill `{goal}`, `{name}`, `{role}`, `{mandate}`:

```
You are a {role} on a planning team.

**Goal**: {goal}
**Your name**: {name}
**Your mandate**: {mandate}

## Context
Read .design/goal-analysis.json for goal decomposition, concept mapping, prior art hints, and scope notes. Use this to focus your analysis — don't rediscover what's already been identified.

## Instructions

1. Analyze the goal through your domain lens — ensure MECE coverage within your mandate.
2. Gather the context you need: read relevant source files, configs, project structure, CLAUDE.md — whatever your domain requires. Use LSP (documentSymbol, goToDefinition) when available. Use WebSearch/WebFetch if external research is needed.
3. Follow up on prior art hints relevant to your domain — check if suggested libraries, patterns, or existing code actually exist and apply.
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

1. Read .design/goal-analysis.json for goal decomposition, concepts, and prior art hints.
2. Scan the codebase for project context: read package.json / pyproject.toml / Cargo.toml / go.mod for stack info, CLAUDE.md for conventions, linter/formatter configs. Build a context object: {stack, conventions, testCommand, buildCommand, lsp: {available: []}}. If LSP is available (try documentSymbol on a key source file), record it.
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
