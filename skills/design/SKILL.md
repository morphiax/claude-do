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
3. Check for existing `.design/plan.json`. If it exists with any non-pending task statuses, count task statuses and use `AskUserQuestion`: "Existing plan has {N completed}/{M failed}/{P pending} tasks. Overwrite and start fresh?" If user declines, output "Keeping existing plan. Run /do:execute to continue." and STOP.
4. Clean up stale staging: `rm -rf .design/ && mkdir -p .design/`

## Step 2: Team + Goal Analyst

Create the team and spawn a goal analyst as the first teammate. The analyst deeply understands the goal, explores the codebase, and recommends the expert team composition.

1. Attempt cleanup of any stale team: `TeamDelete(team_name: "do-design")` (ignore errors)
2. `TeamCreate(team_name: "do-design")`. If TeamCreate fails, tell user: "Agent Teams is required for /do:design. Ensure your Claude Code version supports Agent Teams and retry." Then STOP.
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
You are the Goal Analyst on a planning team. Your job is to deeply understand the goal, explore the codebase, propose high-level approaches, and recommend the expert team composition.

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

3. Propose 2–3 high-level approaches to solving the goal. For each approach:
   - name, description (1–2 sentences)
   - pros and cons (concrete, not generic)
   - effort estimate (low/medium/high)
   - risk level (low/medium/high)
   Mark one as recommended with a brief rationale. Consider: could this be solved differently than the obvious way? What would a pragmatist do vs a purist?

4. Assess goal complexity and determine the appropriate analysis tier:
   - **minimal** — 1-3 tasks, single obvious approach, minimal uncertainty (e.g., update a config value, add a simple endpoint)
   - **standard** — 4-8 tasks, some design decisions, moderate uncertainty (e.g., add feature with multiple files, refactor a module)
   - **full** — 9+ tasks, multiple viable approaches, cross-cutting concerns, significant uncertainty (e.g., architecture change, new subsystem, complex integration)
   Output: `complexity` (minimal|standard|full) and `complexityRationale` (1-2 sentences explaining the classification).
   For minimal goals: still output all fields, but `recommendedTeam` can be empty since no experts will be spawned.

5. Based on your understanding, recommend 2–5 expert roles. Each expert has a **type**:
   - `scanner` — analyzes the goal through a domain lens, produces findings and task recommendations. Use for well-understood domains where the main question is what needs to happen (test coverage, security review, API surface).
   - `architect` — designs HOW to solve a specific sub-problem. Proposes 2–3 concrete implementation strategies with tradeoffs, recommends one. Use when the sub-problem has multiple viable solutions and the choice materially affects the plan (state management approach, data model design, integration pattern).
   Aim for a mix — not all scanners, not all architects. The right ratio depends on how much of the goal is figuring out what to do vs figuring out how to do it.
   For each expert: name, role, type (scanner|architect), model (opus for architecture/analysis, sonnet for implementation, haiku for verification), one-line mandate enriched with specific concepts and prior art you found.

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
  "approaches": [
    {"name": "...", "description": "...", "pros": ["..."], "cons": ["..."], "effort": "low|medium|high", "risk": "low|medium|high", "recommended": true|false, "rationale": "why recommended or not"}
  ],
  "complexity": "minimal|standard|full",
  "complexityRationale": "1-2 sentences explaining the classification",
  "scopeNotes": "refinements or hidden complexity",
  "recommendedTeam": [
    {"name": "...", "role": "...", "type": "scanner|architect", "model": "opus|sonnet|haiku", "mandate": "..."}
  ]
}

Claim your task from the task list and mark completed when done.

Read ~/.claude/teams/do-design/config.json to discover the team lead's name. Send your result to the lead using SendMessage:

    type:      message
    recipient: {lead-name}
    content:   ANALYST_COMPLETE
    summary:   Goal analysis complete
```

**Lead waits** for the analyst's `SendMessage`. Once received, proceed to Complexity Branching.

**Fallback**: If the analyst fails to produce `.design/goal-analysis.json`, the lead performs minimal inline analysis: read package.json for stack, identify 2–3 obvious domains from the goal text, compose a default team. Log: "Analyst failed — using minimal team composition."

## Complexity Branching

Read `.design/goal-analysis.json` — extract `complexity`, `complexityRationale`, and `recommendedTeam`. Echo progress:

```
Complexity: {complexity} — {complexityRationale}
Experts recommended: {length of recommendedTeam}
```

Branch based on `complexity`:

### Minimal Path

Skip Step 3 entirely. Echo: `"Spawning lightweight plan-writer (minimal mode)"`

Spawn a single plan-writer **Task subagent** (NOT a teammate) to generate the plan directly from the analyst's output:

```
Task:
  subagent_type: "general-purpose"
  model: opus
  prompt: <minimal plan-writer prompt below>
```

**Minimal plan-writer prompt** — fill `{goal}`:

```
You are a lightweight plan writer. Generate .design/plan.json for a minimal-complexity goal using only the analyst's output — no expert files, no critic.

**Goal**: {goal}

## Instructions

1. Read .design/goal-analysis.json for goal decomposition, codebase context, approaches, and scope notes.

2. Using the analyst's recommended approach and sub-problems, generate a task list (1–3 tasks). For each task include all required fields:
   - subject, description, activeForm, status (pending), result (null), attempts (0), blockedBy (array of indices)
   - metadata: type (research|implementation|testing|configuration), files {create:[], modify:[]}, reads
   - agent: role, model (opus for architecture/analysis, sonnet for implementation, haiku for verification), approach, contextFiles [{path, reason}], assumptions [{claim, verify (shell cmd), severity: blocking|warning}], acceptanceCriteria [{criterion, check (shell cmd)}], rollbackTriggers ["If X, STOP and return BLOCKED: reason"], constraints

3. Description rule: explain WHY and how it connects to dependents — not just what. An executor with zero context must act on it.

4. Auto-generate safety:
   - File existence: for each path in metadata.files.modify, add blocking assumption `test -f {path}`
   - Convert every blocking assumption to a rollback trigger

5. Validate:
   - Tasks array >= 1 task
   - No concurrent file conflicts
   - All blockedBy valid indices, no cycles
   - Every task has >= 1 assumption and >= 1 rollback trigger
   - Total tasks <= 3

6. Write atomically to .design/plan.json with schema:
   {schemaVersion: 3, goal, context: {stack, conventions, testCommand, buildCommand, lsp}, progress: {completedTasks: [], surprises: [], decisions: []}, tasks: [...]}

## Output
**Context efficiency**: Minimize text output. Target: under 100 tokens of non-JSON output.

The FINAL line of your output MUST be a single JSON object (no markdown fencing):
{"taskCount": N, "maxDepth": N, "depthSummary": {"1": ["Task 0: subject"], ...}}
```

Parse the FINAL line of the subagent's return value as JSON. Store `taskCount`, `maxDepth`, and `depthSummary`.

**Quality gate**: Read `.design/plan.json` and check task count and max dependency depth. If taskCount > 3 or maxDepth > 2, echo: `"Plan generated in minimal mode has {taskCount} tasks (depth {maxDepth}) — consider re-running /do:design for full analysis."`

**Minimal fallback**: If the Task subagent fails, perform plan writing inline: read `.design/goal-analysis.json`, extract sub-problems and recommended approach, write a 1–3 task plan directly to `.design/plan.json`. Log: "Minimal plan-writer failed — writing plan inline."

Proceed to Step 4 (skip Step 3).

### Standard Path

Echo: `"Spawning {N} experts + plan-writer (no critic)"`

Proceed to Step 3 with these modifications:

- **Skip** critic task creation and critic agent spawning
- Plan-writer `blockedBy` references all expert task IDs directly (not critic)
- Plan-writer prompt: omit critic.json references (Phase 1 steps 4 and 6 are skipped — no critique to incorporate)

Two-tier fallback applies if the team fails.

### Full Path

Echo: `"Spawning {N} experts + critic + plan-writer"`

Proceed to Step 3 unchanged. Two-tier fallback applies if the team fails.

## Step 3: Grow Team with Experts, Critic, and Plan-Writer (standard/full only)

Read `.design/goal-analysis.json` to get the analyst's recommended team. Then grow the existing team by spawning experts, an optional critic, and a plan-writer. The pipeline ordering enforces: experts (parallel) → critic (full only) → plan-writer.

1. Read `.design/goal-analysis.json` — extract `recommendedTeam` array (each entry has a `type` field: `scanner` or `architect`). Record the array length as `{expectedExpertCount}` for use in critic and plan-writer prompts.
2. Create TaskList entries with dependencies:
   - For each recommended expert: `TaskCreate` with mandate as subject
   - **Full only**: `TaskCreate` for critic (subject: "Challenge expert proposals and evaluate approach coherence")
   - `TaskCreate` for plan-writer (subject: "Merge expert analyses, validate, and write plan.json")
   - Wire dependencies via `TaskUpdate(addBlockedBy)`:
     - **Full**: critic blockedBy all expert task IDs, plan-writer blockedBy critic task ID
     - **Standard**: plan-writer blockedBy all expert task IDs directly (no critic)
3. Spawn all new agents in parallel via `Task(subagent_type: "general-purpose", team_name: "do-design", name: "{name}", model: "{model}")`:
   - All expert agents from the recommendation (use scanner or architect prompt based on `type`)
   - **Full only**: `critic` (model: `opus`)
   - `plan-writer` (model: `opus`)

**Scanner prompt** — for experts with `type: "scanner"`. Fill `{goal}`, `{name}`, `{role}`, `{mandate}`:

```
You are a {role} (domain scanner) on a planning team.

**Goal**: {goal}
**Your name**: {name}
**Your mandate**: {mandate}

## Context
Read .design/goal-analysis.json for goal decomposition, codebase context, concept mapping, prior art, approaches, and scope notes. Use this to focus your analysis — the goal analyst has already explored the codebase and identified key patterns.

## Instructions

1. Analyze the goal through your domain lens — ensure MECE coverage within your mandate.
2. Gather additional context you need beyond what the analyst found: read specific source files, use LSP (documentSymbol, goToDefinition) when available, use WebSearch/WebFetch if external research is needed.
3. Follow up on prior art relevant to your domain — verify the analyst's findings and dig deeper where needed.
4. Produce findings (risks, observations) and task recommendations.

## Task Recommendations

For each task you recommend, include:
- subject, description, type (research|implementation|testing|configuration)
- files: {create: [], modify: []}
- dependencies (which other tasks must complete first, by subject reference)
- agent spec: role, model (opus for architecture/analysis, sonnet for implementation, haiku for verification), approach, contextFiles [{path, reason}], assumptions [{claim, verify (shell cmd), severity: blocking|warning}], acceptanceCriteria [{criterion, check (shell cmd)}], rollbackTriggers ["If X, STOP and return BLOCKED: reason"], constraints

## Output
**Context efficiency**: Minimize text output. Write reasoning to .design/expert-{name}.log if needed. Target: under 100 tokens of non-JSON output.

Write findings atomically to .design/expert-{name}.json with findings array and tasks array.
Claim your task from the task list and mark completed when done.
```

**Architect prompt** — for experts with `type: "architect"`. Fill `{goal}`, `{name}`, `{role}`, `{mandate}`:

```
You are a {role} (approach architect) on a planning team.

**Goal**: {goal}
**Your name**: {name}
**Your mandate**: {mandate}

## Context
Read .design/goal-analysis.json for goal decomposition, codebase context, concept mapping, prior art, approaches, and scope notes. Pay special attention to the approaches array — the analyst has proposed high-level strategies. Your job is to drill into the sub-problem your mandate covers and design the concrete implementation approach.

## Instructions

1. For your sub-problem, propose 2–3 concrete implementation strategies. For each:
   - Describe the approach in enough detail that an executor could act on it
   - List concrete pros and cons (performance, maintainability, complexity, risk)
   - Identify what assumptions each approach depends on
   - Note compatibility with the analyst's recommended high-level approach
2. Recommend one strategy with clear rationale. Explain what would change your recommendation.
3. Gather evidence: read source files, check existing patterns, use LSP if available, use WebSearch/WebFetch for external best practices.
4. Produce task recommendations for the chosen strategy.

## Task Recommendations

For each task you recommend, include:
- subject, description, type (research|implementation|testing|configuration)
- files: {create: [], modify: []}
- dependencies (which other tasks must complete first, by subject reference)
- chosenApproach: brief name of the strategy this task implements
- alternativesConsidered: names of rejected strategies (for the critic to review)
- agent spec: role, model (opus for architecture/analysis, sonnet for implementation, haiku for verification), approach, contextFiles [{path, reason}], assumptions [{claim, verify (shell cmd), severity: blocking|warning}], acceptanceCriteria [{criterion, check (shell cmd)}], rollbackTriggers ["If X, STOP and return BLOCKED: reason"], constraints

## Output
**Context efficiency**: Minimize text output. Write reasoning to .design/expert-{name}.log if needed. Target: under 100 tokens of non-JSON output.

Write findings atomically to .design/expert-{name}.json with:
- findings array (risks, observations)
- approaches array (the 2–3 strategies you evaluated, with pros/cons/recommendation)
- tasks array (for the chosen strategy)

Claim your task from the task list and mark completed when done.
```

**Critic teammate prompt** — fill `{goal}` and `{expectedExpertCount}`:

```
You are the Critic on a planning team. Your job is to stress-test the experts' proposals before the plan-writer assembles the final plan.

**Goal**: {goal}
**Expected expert count**: {expectedExpertCount}

Your task in the TaskList is blocked by the expert agents. Once unblocked, proceed:

## Instructions

1. Read .design/goal-analysis.json for the analyst's goal decomposition, approaches, and codebase context.
2. Glob .design/expert-*.json and read each expert analysis. Expected {expectedExpertCount} expert files. If fewer found, report missing experts.
3. For each expert output, challenge:
   - **Assumptions**: Are they valid? Can they be verified? What if they are wrong?
   - **Approach choices**: Did architects consider the right alternatives? Is the recommended approach actually the best one given the constraints? What are they optimizing for — is that the right thing to optimize?
   - **Missing risks**: What failure modes are not covered? What happens at the boundaries?
   - **Over-engineering**: Are any proposed tasks unnecessarily complex? Could simpler solutions work?
   - **Under-engineering**: Are any areas getting too little attention? Are there hidden dependencies or edge cases being ignored?
   - **Coherence**: Do the expert proposals fit together? Are there contradictions between experts?
   - **Goal alignment**: Does the aggregate plan actually solve what the user asked for, or has scope drifted?
4. Where you identify issues, propose specific adjustments (not vague concerns).
5. Verify claims by reading source files or checking the codebase where feasible.

## Output
**Context efficiency**: Minimize text output. Write reasoning to .design/critic.log if needed. Target: under 100 tokens of non-JSON output.

Write atomically to .design/critic.json with:
- challenges: [{expert, issue, severity (blocking|major|minor), recommendation}]
- missingCoverage: areas not addressed by any expert
- approachRisks: risks with the chosen approaches that experts did not flag
- coherenceIssues: contradictions or gaps between expert proposals
- verdict: overall assessment — proceed, proceed-with-changes, or major-rework-needed

Claim your task from the task list and mark completed when done.
```

**Plan-writer teammate prompt** — fill `{goal}` and `{expectedExpertCount}`:

```
You are the Plan Writer on a planning team. Merge expert analyses, incorporate critique, validate, enrich, and write .design/plan.json.

**Goal**: {goal}
**Expected expert count**: {expectedExpertCount}

Your task in the TaskList is blocked by expert tasks (and critic, if present). Once unblocked, proceed:

## Phase 1: Context & Merge

1. Read .design/goal-analysis.json for goal decomposition, codebase context, concepts, approaches, and prior art.
2. Use the codebaseContext from goal-analysis.json as the basis for plan.json's context field. Supplement with additional scans if needed (package.json, CLAUDE.md, linter configs).
3. Glob .design/expert-*.json and read each expert analysis. Expected {expectedExpertCount} expert files. If fewer found, report missing experts.
4. If .design/critic.json exists, read it for the critique. (Standard tier has no critic — skip steps 4 and 6 if absent.)
5. Merge expert task recommendations:
   - Where experts converge, increase confidence
   - Where they diverge, use the critic's assessment to break ties (or your own judgment if no critic)
   - Deduplicate overlapping tasks
   - Ensure MECE coverage — no gaps, no overlaps
   - Resolve conflicting dependencies
6. If critic output exists, address each challenge from the critic:
   - Blocking issues: must be resolved before proceeding — adjust the plan accordingly
   - Major issues: should be addressed — incorporate the critic's recommendation or document why not
   - Minor issues: note in decisions array, address if low-cost
   - Record each decision (accepted/rejected critique + rationale) in progress.decisions

## Phase 2: Validate & Enrich

For each task verify all required fields. Fill gaps:

Required agent fields: role, model, approach, contextFiles [{path, reason, lines?}], assumptions [{claim, verify (shell cmd), severity: blocking|warning}], acceptanceCriteria [{criterion, check (shell cmd)}], rollbackTriggers ["If X, STOP and return BLOCKED: reason"], constraints. Optional: expertise, priorArt, fallback.
Required metadata: type (research|implementation|testing|configuration), files {create:[], modify:[]}, reads.
Required task fields: subject, description, activeForm, status (pending), result (null), attempts (0), blockedBy.

Description rule: explain WHY and how it connects to dependents — not just what. An executor with zero context must act on it.
Non-code goals: acceptance criteria may use content-based checks (grep). Rollback triggers reference content expectations.
Count gaps filled as gapsFilled.

## Phase 3: Auto-generate Safety

- File existence: for each path in metadata.files.modify, add blocking assumption `test -f {path}`
- Cross-task deps: if task B modifies/creates files overlapping task A (in blockedBy transitive closure), add blocking assumption `test -f {file}`
- Convert every blocking assumption to a rollback trigger

## Phase 4: Validate Plan (7 checks)

1. Tasks array >= 1 task. If 0, return error.
2. No two concurrent tasks share files in create or modify. Concurrent = neither transitively depends on the other via blockedBy.
3. No task reads overlap a concurrent task's creates/modifies.
4. All blockedBy valid indices. Topological sort — cycles → restructure.
5. Every task has >= 1 assumption and >= 1 rollback trigger.
6. Total tasks <= 12.
7. Critical path length <= 4 (longest chain in blockedBy DAG). Restructure for parallelism if exceeded.
Self-repair: fix and re-validate. After 2 attempts, include in validationIssues and proceed.

## Phase 5: Write .design/plan.json

Schema (schemaVersion 3): {schemaVersion: 3, goal, context: {stack, conventions, testCommand, buildCommand, lsp}, progress: {completedTasks: [], surprises: [], decisions: []}, tasks: [...]}
Each task uses the schema from Phase 2.

Schema rules: tasks ordered (index = ID, 0-based), blockedBy references indices, status: pending|in_progress|completed|failed|blocked|skipped.

Write atomically to .design/plan.json.

## Output
**Context efficiency**: Minimize text output. Write reasoning to .design/plan-writer.log if needed. Target: under 100 tokens of non-JSON output.

Claim your task from the task list and mark completed when done.

Read ~/.claude/teams/do-design/config.json to discover the team lead's name. Send your result to the lead using SendMessage:

    type:      message
    recipient: {lead-name}
    content:   <FINAL-line JSON below>
    summary:   Plan written

JSON schema: {"taskCount": N, "maxDepth": N, "gapsFilled": N, "critiqueResolutions": N, "validationIssues": [], "depthSummary": {"1": ["Task 0: subject"], ...}}
Depth computation (display-only, not stored in plan.json): depth = 1 for tasks with empty blockedBy, otherwise 1 + max(depth of blockedBy tasks).
On unresolvable error, send JSON with error (string) and validationIssues (array) keys instead.
```

**Lead wait pattern**: After spawning all agents, the lead waits. The plan-writer's `SendMessage` is delivered automatically as a conversation turn. Parse the JSON from the message content.

**Timeout protection**: If agents haven't completed after a reasonable period, proceed with available results. Note which agents timed out.

After receiving the plan-writer's message: `SendMessage(type: "shutdown_request")` to each teammate, wait for confirmations, `TeamDelete(team_name: "do-design")`.

**Two-tier fallback** (standard/full only) — triggered when the team fails to produce `.design/plan.json` (plan-writer message not received, teammate stall, or team infrastructure error):

- **Tier 1 — Sequential retry**: Shut down the team (`SendMessage(type: "shutdown_request")` to all, then `TeamDelete`). Spawn a single plan-writer Task subagent (not teammate) with the plan-writer prompt above. It reads the same `.design/expert-*.json` files and `.design/critic.json` (full tier only).
- **Tier 2 — Inline with context minimization**: If the sequential retry also fails, perform merge and plan writing inline. Process one `.design/expert-*.json` file at a time, extract only the tasks array from each, merge incrementally into a combined task list. Read `.design/critic.json` for blocking issues only (full tier). Execute Phases 2–5 sequentially with reduced scope.

## Step 4: Cleanup & Summary

1. **Lightweight verification** (lead): Run `python3 -c "import json; p=json.load(open('.design/plan.json')); assert p.get('schemaVersion') == 3, 'schemaVersion must be 3'"` to confirm schemaVersion. Use the plan-writer's stored `taskCount` and `maxDepth` from its SendMessage for verification (no need to re-extract).
2. **Clean up TaskList**: Delete all tasks created during planning so `/do:execute` starts with a clean TaskList.
3. **Clean up intermediate files**: `rm -f .design/goal-analysis.json .design/expert-*.json .design/expert-*.log .design/critic.json .design/critic.log .design/plan-writer.log` — keep only `.design/plan.json`.

4. **Output summary** using stored plan-writer data (`depthSummary`, `taskCount`, `maxDepth`):

```
Plan: {goal}
Tier: {complexity}
Tasks: {taskCount}, max depth {maxDepth}
Models: {model distribution, for example: 2 opus, 3 sonnet, 1 haiku}

Depth 1:
- Task 0: {subject} ({model})
- Task 1: {subject} ({model})

Depth 2:
- Task 2: {subject} ({model}) [blocked by: 0, 1]

Context: {stack}
Test: {testCommand}

Run /execute to begin.
```

To compute model distribution: read `.design/plan.json`, count occurrences of each `agent.model` value across all tasks, format as `"{count} {model}"` joined by commas.

**Goal**: $ARGUMENTS
