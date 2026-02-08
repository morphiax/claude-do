---
name: design
description: "Decompose a goal into a structured plan with enriched task specs and safety checks."
argument-hint: "<goal description>"
---

# Design

Thin-lead orchestrator: decompose a goal into `.design/plan.json` using a team of specialist agents. The lead NEVER analyzes, reasons about, or evaluates the goal — it only orchestrates. All analytical work (audits, reviews, research, architecture) happens inside the Agent Team (Step 5). Files carry data between pipeline stages — the lead never holds expert analyses or synthesis output (except during fallback recovery). **This skill only designs — it does NOT execute.**

**Do NOT use EnterPlanMode — this skill IS the plan.**

### Conventions

- **Atomic write**: Write to `{path}.tmp`, then rename to `{path}`. All file outputs in this skill use this pattern.
- **Signaling patterns**: Expert teammates signal completion via TaskList (the lead does not parse their output). Plan-writer sends its structured return value (JSON) to the lead via `SendMessage(type: "message")`. Infrastructure subagents (context scan) return a one-line text summary as their FINAL line.

**MANDATORY: Execute ALL steps (1–6) for EVERY invocation. Never skip steps, never answer the goal directly, never produce findings or analysis inline. Do NOT use `sequential-thinking`, `Read`, `Grep`, or any analytical tool to reason about the goal before Step 5 — the lead's job is pipeline orchestration, not analysis. The ONLY valid output of this skill is `.design/plan.json` — produced by the full pipeline including the Agent Team (Step 5). This applies regardless of goal type, complexity, or apparent simplicity. Audits, reviews, research, one-line fixes — all go through the team. No exceptions exist. If you are tempted to "just do it directly," STOP — that impulse is the exact failure mode this rule prevents.**

## Step 1: Goal Validation

Use `AskUserQuestion` to clarify only when reasonable developers would choose differently and the codebase doesn't answer it: scope boundaries, done-state, technical preferences, compatibility, priority.

**Reframe analytical goals**: If the goal is an audit, review, or analysis, reframe it into concrete executable tasks ("audit X" becomes tasks that analyze specific areas, draft changes, and apply fixes). The output is always a plan.json that `/do:execute` can act on.

If >12 tasks likely needed, suggest phases. Design only phase 1.

## Step 2: Pre-flight

1. Check for existing `.design/plan.json`. If it exists with `progress.currentWave > 0` or any non-pending task statuses, use `AskUserQuestion` to confirm overwrite — execution may be in progress. Record `overwriteApproved` flag.
2. Clean up stale staging: `rm -rf .design/ && mkdir -p .design/`

## Step 3: Context Scan

Skip if greenfield or purely conceptual (heuristic: no codebase files exist, or the goal makes no reference to existing code or infrastructure). When in doubt, run the scan — it's cheap. Delegate to an Explore subagent to keep raw codebase data out of the lead's context:

```
Task:
  subagent_type: "general-purpose"
  prompt: <assembled prompt below>
```

**Explore subagent prompt** — fill `{goal}`:

```
Scan this codebase to build a context object for planning the following goal:

**Goal**: {goal}

## Instructions
1. Glob key directories (src/, lib/, app/, packages/), Read package.json / pyproject.toml / Cargo.toml / go.mod — identify stack, frameworks, build/test commands.
2. Read CLAUDE.md, linter/formatter configs — extract conventions.
3. Grep/Glob for modules, files, and patterns the goal touches.
4. LSP(documentSymbol) on a key source file. If symbols return, record in lsp.available.
5. Identify existing patterns relevant to the goal (test structure, API routes, migrations).

## Output
**Context efficiency**: Minimize text output. Write reasoning to .design/context-scan.log if needed. Target: under 100 tokens of non-JSON output.

Write atomically to .design/context.json. Schema (omit fields that don't apply):

    {"stack":"...","conventions":"...","testCommand":"...","buildCommand":"...","lsp":{"available":[]},"relevantModules":[],"existingPatterns":[]}

The FINAL line of your output MUST be a SHORT summary (one sentence): stack, key conventions, relevant modules. Do NOT return the full JSON — it is in the file.
```

Store only the one-line summary. The full context lives in `.design/context.json`.

## Step 4: Team Composition

Quick domain→role mapping. This step is a bounded exception to the no-analysis rule — perform lightweight domain mapping (max 3 sentences). Do NOT use `sequential-thinking` here — save deep analysis for the expert agents.

1. List the domains the goal touches (frontend, backend, data, security, infra, testing, etc.)
2. Pick 2–5 roles to cover those domains. Examples: system-architect, API-designer, frontend-specialist, backend-engineer, test-strategist, security-analyst, devops-engineer, online-researcher, prompt-engineer, codebase-archaeologist. Invent roles as needed.
3. Drop any role whose mandate overlaps >70% with another.

**Models**: `opus` for architecture/analysis, `sonnet` for implementation planning, `haiku` for verification-only.

For each agent define: name, role, model, one-line mandate. Keep mandates brief — the experts will determine their own analytical depth.

## Step 5: Expert-to-Plan Pipeline

Spawn a single Agent Team containing experts, a synthesizer, and a plan-writer. Pipeline ordering via TaskList: synthesizer blockedBy all experts, plan-writer blockedBy synthesizer. The lead waits for one `SendMessage` from the plan-writer containing the result JSON.

1. Attempt cleanup of any stale team: `TeamDelete(team_name: "do-design")` (ignore errors)
2. `TeamCreate(team_name: "do-design")`
3. Create TaskList entries with dependencies:
   - For each expert agent from Step 4: `TaskCreate` with mandate as subject
   - `TaskCreate` for synthesizer (subject: "Synthesize expert analyses into unified task array")
   - `TaskCreate` for plan-writer (subject: "Validate, enrich, and write plan.json")
   - Wire dependencies via `TaskUpdate(addBlockedBy)`: synthesizer blockedBy all expert task IDs, plan-writer blockedBy synthesizer task ID
4. Write `.design/team-briefing.json` atomically with:

```json
{
  "goal": "{goal}",
  "contextSummary": "{one-line summary from Step 3}",
  "teammates": [{ "name": "{name}", "role": "{role}", "mandate": "{mandate}" }],
  "expertProtocol": {
    "instructions": [
      "Read .design/context.json for full codebase context — if missing, proceed with goal-only analysis",
      "Analyze the ENTIRE goal through your domain lens — ensure MECE coverage",
      "Produce findings (risks, observations) and task recommendations with: subject, description, type, files (create/modify), waves, dependencies, agent specs (role, model, approach, contextFiles, assumptions, acceptanceCriteria, rollbackTriggers, constraints)"
    ],
    "output": "Write atomically to .design/expert-{name}.json with findings array and tasks array — use SendMessage for small coordination signals (NOT data payloads) — claim your task and mark done"
  }
}
```

5. Spawn all agents in parallel via `Task(subagent_type: "general-purpose", team_name: "do-design", name: "{name}", model: "{model}")`:
   - All expert agents from Step 4
   - `synthesizer` (model: `opus`)
   - `plan-writer` (model: `opus`)

**Expert bootstrap prompt** — fill placeholders (~50 tokens per expert):

```
Read .design/team-briefing.json for goal, teammates, and analysis protocol.
Your name: {name}. Your mandate: {mandate}.
Write findings to .design/expert-{name}.json.
Claim your task, mark done. FINAL line: one-line summary of findings.
```

**Synthesizer teammate prompt** — fill `{goal}`:

```
You are a synthesis agent on a planning team. Merge expert analyses into a unified task array.

**Goal**: {goal}

## Instructions
Your task in the TaskList is blocked by the expert agents. Once unblocked, proceed:

1. Read .design/context.json for codebase context.
2. Glob .design/expert-*.json and read each expert analysis.
3. Use mcp__sequential-thinking__sequentialthinking to merge (fallback: inline numbered reasoning):
   - Where experts converge, increase confidence
   - Where they diverge, investigate and choose the strongest position
   - Deduplicate overlapping tasks
   - Ensure MECE coverage — no gaps, no overlaps
   - Resolve conflicting wave assignments and dependencies
4. Produce tasks with all fields required by the plan schema (see plan-writer Phase 1 for field requirements).

## Output
**Context efficiency**: Minimize text output. Write reasoning to .design/synthesis.log if needed. Target: under 100 tokens of non-JSON output.

Write atomically to .design/tasks.json.
Claim your task from the task list and mark completed when done.
```

**Plan-writer teammate prompt** — fill `{goal}` and `{overwriteApproved}`:

```
You are a Plan Writer on a planning team. Validate, enrich, and write .design/plan.json.

**Goal**: {goal}
**Overwrite approved**: {true|false}

Your task in the TaskList is blocked by the synthesizer. Once unblocked, proceed:

## Phase 1: Validate Enrichment
Read .design/tasks.json and .design/context.json. For each task verify all required fields. Fill gaps:

Required agent fields: role, model, approach, contextFiles [{path, reason, lines?}], assumptions [{claim, verify (shell cmd), severity: blocking|warning}], acceptanceCriteria [{criterion, check (shell cmd)}], rollbackTriggers ["If X, STOP and return BLOCKED: reason"], constraints. Optional: expertise, priorArt, fallback.
Required metadata: type (research|implementation|testing|configuration), files {create:[], modify:[]}, reads.
Required task fields: subject, description, activeForm, status (pending), result (null), attempts (0), wave, blockedBy.

Description rule: explain WHY and how it connects to dependents — not just what. An executor with zero context must act on it.
Non-code goals: acceptance criteria may use content-based checks (grep). Rollback triggers reference content expectations.
Count gaps filled as gapsFilled.

## Phase 2: Auto-generate Safety
- File existence: for each path in metadata.files.modify, add blocking assumption `test -f {path}`
- Cross-task deps: if task B modifies/creates files overlapping task A (same/earlier wave), add blocking assumption `test -f {file}`
- Convert every blocking assumption to a rollback trigger

## Phase 3: Validate Plan (8 checks)
1. Tasks array >= 1 task. If 0, return error.
2. No two same-wave tasks share files in create or modify.
3. No task reads overlaps same-wave task creates/modifies.
4. All blockedBy valid indices. Topological sort — cycles → restructure.
5. Wave = 1 + max(blockedBy waves). Recalculate if mismatched.
6. Every task has >= 1 assumption and >= 1 rollback trigger.
7. Total tasks <= 12.
8. Max wave <= 4 (restructure for parallelism if exceeded).
Self-repair: fix and re-validate. After 2 attempts, include in validationIssues and proceed.

## Phase 4: Write .design/plan.json
Schema (schemaVersion 2): {schemaVersion: 2, goal, context: {stack, conventions, testCommand, buildCommand, lsp}, progress: {currentWave: 0, completedTasks: [], surprises: [], decisions: []}, tasks: [...]}
Each task uses the schema from Phase 1.

Schema rules: tasks ordered (index = ID, 0-based), blockedBy references indices, wave: 1 = no deps / 2+ = 1+max(blockedBy waves), status: pending|in_progress|completed|failed|blocked|skipped.

Write atomically to .design/plan.json.

## Output
**Context efficiency**: Minimize text output. Write reasoning to .design/plan-writer.log if needed. Target: under 100 tokens of non-JSON output.

Claim your task from the task list and mark completed when done.

Read ~/.claude/teams/do-design/config.json to discover the team lead's name. Send your result to the lead using `SendMessage`:

    type:      message
    recipient: {lead-name}
    content:   <FINAL-line JSON below>
    summary:   Plan written

JSON schema: {"taskCount": N, "waveCount": N, "gapsFilled": N, "validationIssues": [], "waveSummary": {"1": ["Task 0: subject"], ...}}
On unresolvable error, send JSON with `error` (string) and `validationIssues` (array) keys instead.
```

**Lead wait pattern**: After spawning all agents, the lead waits. The plan-writer's `SendMessage` is delivered automatically as a conversation turn. Parse the JSON from the message content.

**Timeout protection**: If agents haven't completed after a reasonable period, proceed with available results. Note which agents timed out.

After receiving the plan-writer's message: `SendMessage(type: "shutdown_request")` to each teammate, wait for confirmations, `TeamDelete(team_name: "do-design")`.

**Two-tier fallback** — triggered when the team fails to produce `.design/plan.json` (plan-writer message not received, teammate stall, or team infrastructure error):

- **Tier 1 — Sequential retry**: Shut down the team (`SendMessage(type: "shutdown_request")` to all, then `TeamDelete`). Retry with sequential Task subagents: spawn a synthesis subagent with the synthesizer prompt above, wait for completion, then spawn a plan-writer subagent with the plan-writer prompt above. Each reads the same `.design/expert-*.json` files the team would have consumed.
- **Tier 2 — Inline with context minimization**: If the sequential retry also fails, perform synthesis and plan writing inline with reduced memory pressure. Synthesizer: process one `.design/expert-*.json` file at a time, extract only the tasks array from each, merge incrementally into `.design/tasks.json`. Plan-writer: read only `.design/tasks.json` (skip `.design/context.json`), execute Phases 1-4 sequentially. Use `sequential-thinking` for merge logic (fallback: inline numbered reasoning).

## Step 6: Cleanup & Summary

1. **Lightweight verification** (lead): Run `python3 -c "import json; p=json.load(open('.design/plan.json')); assert p.get('schemaVersion') == 2, 'schemaVersion must be 2'"` to confirm schemaVersion. Use the plan-writer's stored `taskCount` and `waveCount` from its SendMessage for verification (no need to re-extract).
2. **Clean up TaskList**: Delete all tasks created during planning so `/do:execute` starts with a clean TaskList.
3. **Clean up intermediate files**: `rm -f .design/context.json .design/expert-*.json .design/tasks.json .design/team-briefing.json` — keep only `.design/plan.json`.

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
