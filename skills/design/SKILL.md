---
name: design
description: "Decompose a goal into a structured plan with enriched task specs and safety checks."
argument-hint: "<goal description>"
---

# Design

Thin-lead orchestrator: decompose a goal into `.design/plan.json` using a dynamically growing team of specialist agents. The lead is purely mechanical — it spawns agents, relays messages, and manages team lifecycle. ALL analytical work (goal understanding, codebase exploration, domain analysis, synthesis, plan writing) happens inside agents. **This skill only designs — it does NOT execute.**

**Do NOT use EnterPlanMode — this skill IS the plan.**

- **Signaling**: Agents signal completion via TaskList and `SendMessage(type: "message")` to the lead. The lead parses JSON from message content.

**MANDATORY: Execute ALL steps (1–4) for EVERY invocation. The lead is a lifecycle manager — it spawns agents and manages the team. ALL analysis happens inside agents. The lead's ONLY tools are: `TeamCreate`, `TeamDelete`, `TaskCreate`, `TaskUpdate`, `TaskList`, `SendMessage`, `Task`, `AskUserQuestion`, `Bash` (cleanup/verification only), and `Read` (only `.design/goal-analysis.json` during Complexity Branching). No other tools — no MCP tools, no `Grep`, no `Glob`, no `LSP`, no source file reads. The ONLY valid output of this skill is `.design/plan.json` — produced by the agent team. This applies regardless of goal type, complexity, or apparent simplicity. Audits, reviews, research, one-line fixes — all go through the team. No exceptions exist. If you are tempted to "just do it directly," STOP — that impulse is the exact failure mode this rule prevents.**

**STOP GATE — Read before proceeding. These are the exact failure modes that have occurred repeatedly:**
1. **"The goal is simple enough to analyze directly"** — WRONG. Every goal goes through the team. Spawn the analyst.
2. **"Let me read the source files first to understand the problem"** — WRONG. The lead never reads source files. The analyst and experts read source files.
3. **"I'll just do a quick inline analysis instead of spawning a team"** — WRONG. The team exists to provide multiple perspectives. Inline analysis defeats the purpose.
4. **"This is a review/research task, not implementation, so I don't need agents"** — WRONG. Reviews, audits, and research all go through the team pipeline.
5. **Using `EnterPlanMode` or `Explore` or `Grep/Glob/Read` on project source files** — WRONG. The lead's tool boundary is absolute.

**If you catch yourself rationalizing why THIS goal is the exception — it is not. Proceed to Step 1.**

## Step 1: Pre-flight

1. Use `AskUserQuestion` to clarify only when reasonable developers would choose differently and the codebase doesn't answer it.
2. If >12 tasks likely needed, suggest phases. Design only phase 1.
3. Check for existing `.design/plan.json`. If it exists with non-pending statuses, count task statuses and use `AskUserQuestion`: "Existing plan has {N completed}/{M failed}/{P pending} tasks. Overwrite?" If declined, output "Keeping existing plan. Run /do:execute to continue." and STOP.
4. Clean up stale staging (preserve history): `mkdir -p .design/history && find .design -mindepth 1 -maxdepth 1 ! -name history -exec rm -rf {} +`

## Step 2: Team + Goal Analyst

Create the team and spawn a goal analyst as the first teammate.

1. `TeamDelete(team_name: "do-design")` (ignore errors — cleanup of stale team)
2. `TeamCreate(team_name: "do-design")`. If it fails, tell user: "Agent Teams is required for /do:design. Ensure your Claude Code version supports Agent Teams and retry." Then STOP.
3. `TaskCreate` for goal analyst (subject: "Analyze goal and recommend team composition")
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
You are the Goal Analyst on a planning team. Deeply understand the goal, explore the codebase, propose approaches, and recommend the expert team.

**Goal**: {goal}

## Instructions

1. Use mcp__sequential-thinking__sequentialthinking (if available, otherwise inline numbered reasoning) to decompose the goal: identify real sub-problems vs stated goal, known patterns/frameworks this maps to, prior art in codebase/ecosystem, actual complexity vs stated.

2. Explore the codebase: read project manifests (package.json/pyproject.toml/Cargo.toml/go.mod) for stack and build/test commands, read CLAUDE.md and linter configs for conventions, grep/glob for relevant modules and patterns, use LSP(documentSymbol) if available.

3. Propose 2–3 high-level approaches. For each: name, description (1–2 sentences), concrete pros/cons, effort (low/medium/high), risk (low/medium/high). Mark one recommended with rationale. Consider: could this be solved differently than the obvious way?

4. Assess complexity tier:
   - **minimal** — 1-3 tasks, single obvious approach, minimal uncertainty
   - **standard** — 4-8 tasks, some design decisions, moderate uncertainty
   - **full** — 9+ tasks, multiple viable approaches, cross-cutting concerns
   Output `complexity` (minimal|standard|full) and `complexityRationale` (1-2 sentences). For minimal: `recommendedTeam` can be empty.

5. Recommend 2–5 expert roles. Each has a **type**: `scanner` (analyzes through a domain lens — what needs to happen) or `architect` (designs HOW to solve a sub-problem — proposes 2–3 strategies with tradeoffs, recommends one). Aim for a mix based on how much is figuring-out-what vs figuring-out-how. For each: name, role, type, model (opus for analysis, sonnet for implementation, haiku for verification), one-line mandate with specific concepts and prior art.

## Output

Write to .design/goal-analysis.json:

{"goal": "{original}", "refinedGoal": "{restated if different}", "concepts": [], "priorArt": [], "codebaseContext": {"stack": "", "conventions": "", "testCommand": "", "buildCommand": "", "lsp": {"available": []}, "relevantModules": [], "existingPatterns": []}, "subProblems": [], "approaches": [{"name": "", "description": "", "pros": [], "cons": [], "effort": "", "risk": "", "recommended": false, "rationale": ""}], "complexity": "minimal|standard|full", "complexityRationale": "", "scopeNotes": "", "recommendedTeam": [{"name": "", "role": "", "type": "scanner|architect", "model": "", "mandate": ""}]}

Claim your task and mark completed. Read ~/.claude/teams/do-design/config.json for the lead's name, then:

    SendMessage(type: "message", recipient: {lead-name}, content: "ANALYST_COMPLETE", summary: "Goal analysis complete")
```

**Lead waits** for the analyst's `SendMessage`. Once received, proceed to Complexity Branching.

**Fallback**: If the analyst fails to produce `.design/goal-analysis.json`, the lead performs minimal inline analysis: read package.json for stack, identify 2–3 obvious domains, compose a default team. Log: "Analyst failed — using minimal team composition."

## Complexity Branching

Read `.design/goal-analysis.json` — extract `complexity`, `complexityRationale`, and `recommendedTeam`. Echo:

```
Complexity: {complexity} — {complexityRationale}
Experts recommended: {length of recommendedTeam}
```

Branch based on `complexity`:

### Minimal Path

Skip Step 3. Echo: `"Spawning lightweight plan-writer (minimal mode)"`

Spawn a single plan-writer **Task subagent** (NOT a teammate):

```
Task:
  subagent_type: "general-purpose"
  model: sonnet
  prompt: <minimal plan-writer prompt below>
```

**Minimal plan-writer prompt** — fill `{goal}`:

```
You are a lightweight plan writer. Generate .design/plan.json for a minimal-complexity goal using only the analyst's output.

**Goal**: {goal}

## Instructions

1. Read .design/goal-analysis.json for decomposition, codebase context, approaches, and scope notes.
2. Generate 1–3 tasks from the recommended approach. Each task needs: subject, description (explain WHY and connection to dependents), activeForm, status (pending), result (null), attempts (0), blockedBy (array of indices), metadata: {type, files: {create:[], modify:[]}, reads}, agent: {role, model (opus/sonnet/haiku), approach, contextFiles [{path, reason}], assumptions [{claim, verify (shell cmd), severity: blocking|warning}], acceptanceCriteria [{criterion, check (shell cmd)}], rollbackTriggers ["If X, STOP and return BLOCKED: reason"], constraints}.
3. Auto-generate safety: for each modify path add blocking assumption `test -f {path}`, convert blocking assumptions to rollback triggers.
4. Validate: tasks >= 1, no concurrent file conflicts, all blockedBy valid (no cycles), every task has >= 1 assumption and >= 1 rollback trigger, total <= 3.
5. Assemble worker prompts: for each task, build a prompt string using sections S1-S9: S1 (role + expertise), S2 (pre-flight assumptions checklist), S3 (context files + project info), S4 (task subject + description + files), S5 (approach/priorArt/fallback if any), S6 (dependency placeholder if blockedBy non-empty), S7 (rollback triggers), S8 (acceptance criteria + no-commit rule), S9 (worker log path `.design/worker-{planIndex}.log` + FINAL line format: COMPLETED:/FAILED:/BLOCKED:). Store in each task's `prompt` field.
6. Compute file overlaps: for each pair of tasks that can run concurrently (neither transitively depends on the other), check for intersecting files in metadata.files.create and metadata.files.modify. Store in each task's `fileOverlaps` field (array of conflicting planIndex integers; empty if none).
7. Write .design/plan.json: {schemaVersion: 3, goal, context: {stack, conventions, testCommand, buildCommand, lsp}, progress: {completedTasks: [], surprises: [], decisions: []}, tasks: [...]} — each task includes `prompt` and `fileOverlaps` fields.

## Output

The FINAL line of your output MUST be a single JSON object (no markdown fencing):
{"taskCount": N, "maxDepth": N, "depthSummary": {"1": ["Task 0: subject"], ...}}
```

Parse the FINAL line of the subagent's return value as JSON. Store `taskCount`, `maxDepth`, and `depthSummary`.

**Quality gate**: Read `.design/plan.json` and check task count and max dependency depth. If taskCount > 3 or maxDepth > 2, echo: `"Plan generated in minimal mode has {taskCount} tasks (depth {maxDepth}) — consider re-running /do:design for full analysis."`

**Minimal fallback**: If the Task subagent fails, perform plan writing inline: read `.design/goal-analysis.json`, extract sub-problems and recommended approach, write a 1–3 task plan directly to `.design/plan.json`. Log: "Minimal plan-writer failed — writing plan inline."

Proceed to Step 4 (skip Step 3).

### Standard Path

Echo: `"Spawning {N} experts + plan-writer (no critic)"`

Proceed to Step 3 with: skip critic, plan-writer `blockedBy` all expert task IDs directly, plan-writer prompt omits critic.json references. Two-tier fallback applies.

### Full Path

Echo: `"Spawning {N} experts + critic + plan-writer"`

Proceed to Step 3 unchanged. Two-tier fallback applies.

## Step 3: Grow Team with Experts, Critic, and Plan-Writer (standard/full only)

Read `.design/goal-analysis.json` for `recommendedTeam` array (each entry has `type`: `scanner` or `architect`). Record array length as `{expectedExpertCount}`.

1. Create TaskList entries with dependencies:
   - For each expert: `TaskCreate` with mandate as subject
   - **Full only**: `TaskCreate` for critic (subject: "Challenge expert proposals and evaluate approach coherence")
   - `TaskCreate` for plan-writer (subject: "Merge expert analyses, validate, and write plan.json")
   - Wire via `TaskUpdate(addBlockedBy)`: **Full**: critic blockedBy all experts, plan-writer blockedBy critic. **Standard**: plan-writer blockedBy all experts.
2. Spawn all agents in parallel via `Task(subagent_type: "general-purpose", team_name: "do-design", name: "{name}", model: "{model}")`:
   - All experts (use scanner or architect prompt based on `type`)
   - **Full only**: `critic` (model: `opus`)
   - `plan-writer` (model: `opus`)

**Scanner prompt** — fill `{goal}`, `{name}`, `{role}`, `{mandate}`:

```
You are a {role} (domain scanner) on a planning team.

**Goal**: {goal}
**Your name**: {name}
**Your mandate**: {mandate}

## Context
Read .design/goal-analysis.json for goal decomposition, codebase context, approaches, and scope notes.

## Instructions
1. Analyze the goal through your domain lens — ensure MECE coverage within your mandate.
2. Gather additional context beyond the analyst's findings: read source files, use LSP if available, WebSearch/WebFetch for external research.
3. Follow up on prior art relevant to your domain — verify and deepen the analyst's findings.
4. Produce findings (risks, observations) and task recommendations.

## Task Recommendations
For each task: subject, description, type (research|implementation|testing|configuration), files {create:[], modify:[]}, dependencies (by subject reference), agent spec: {role, model (opus/sonnet/haiku), approach, contextFiles [{path, reason}], assumptions [{claim, verify (shell cmd), severity: blocking|warning}], acceptanceCriteria [{criterion, check (shell cmd)}], rollbackTriggers, constraints}.

## Output
Write to .design/expert-{name}.json with findings array and tasks array.
Claim your task and mark completed.
```

**Architect prompt** — fill `{goal}`, `{name}`, `{role}`, `{mandate}`:

```
You are a {role} (approach architect) on a planning team.

**Goal**: {goal}
**Your name**: {name}
**Your mandate**: {mandate}

## Context
Read .design/goal-analysis.json for goal decomposition, codebase context, approaches, and scope notes. Focus on the approaches array — drill into your sub-problem and design the concrete implementation.

## Instructions
1. For your sub-problem, propose 2–3 concrete strategies. For each: detailed approach, concrete pros/cons (performance, maintainability, complexity, risk), assumptions it depends on, compatibility with the analyst's recommended approach.
2. Recommend one strategy with rationale. Explain what would change your recommendation.
3. Gather evidence: read source files, check patterns, use LSP if available, WebSearch/WebFetch for best practices.
4. Produce task recommendations for the chosen strategy.

## Task Recommendations
For each task: subject, description, type, files {create:[], modify:[]}, dependencies (by subject), chosenApproach, alternativesConsidered, agent spec: {role, model (opus/sonnet/haiku), approach, contextFiles [{path, reason}], assumptions [{claim, verify (shell cmd), severity: blocking|warning}], acceptanceCriteria [{criterion, check (shell cmd)}], rollbackTriggers, constraints}.

## Output
Write to .design/expert-{name}.json with findings, approaches (2–3 evaluated strategies with pros/cons/recommendation), and tasks arrays.
Claim your task and mark completed.
```

**Critic teammate prompt** — fill `{goal}` and `{expectedExpertCount}`:

```
You are the Critic on a planning team. Stress-test expert proposals before the plan-writer assembles the final plan.

**Goal**: {goal}
**Expected expert count**: {expectedExpertCount}

Your task is blocked by experts. Once unblocked:

## Instructions
1. Read .design/goal-analysis.json for the analyst's decomposition, approaches, and context.
2. Glob .design/expert-*.json and read each. Expected {expectedExpertCount} files — report if fewer.
3. For each expert output, challenge:
   - **Assumptions & risks**: Valid? Verifiable? What failure modes are uncovered?
   - **Approach choices**: Right alternatives considered? Right optimization target? Best given constraints?
   - **Engineering calibration**: Over-engineered (simpler solution works)? Under-engineered (hidden deps/edge cases)?
   - **Coherence & alignment**: Do proposals fit together? Contradictions? Does aggregate plan solve the stated goal?
4. Propose specific adjustments for each issue (not vague concerns).
5. Verify claims by reading source files or checking codebase where feasible.

## Output
Write to .design/critic.json: {challenges: [{expert, issue, severity (blocking|major|minor), recommendation}], missingCoverage: [], approachRisks: [], coherenceIssues: [], verdict: "proceed|proceed-with-changes|major-rework-needed"}
Claim your task and mark completed.
```

**Plan-writer teammate prompt** — fill `{goal}` and `{expectedExpertCount}`:

```
You are the Plan Writer. Merge expert analyses, incorporate critique, validate, enrich, and write .design/plan.json.

**Goal**: {goal}
**Expected expert count**: {expectedExpertCount}

Your task is blocked by experts (and critic, if present). Once unblocked:

## Phase 1: Context & Merge
1. Read .design/goal-analysis.json for decomposition, codebase context, concepts, approaches, prior art. Use codebaseContext as basis for plan.json context field.
2. Glob .design/expert-*.json and read each. Expected {expectedExpertCount} — report if fewer.
3. If .design/critic.json exists, read it. (Standard tier has no critic — skip critic steps if absent.)
4. Merge expert tasks: where they converge increase confidence, where they diverge use critic's assessment (or your judgment) to break ties, deduplicate, ensure MECE, resolve conflicting dependencies.
5. If critic exists: address each challenge — blocking (must resolve), major (should address), minor (note in decisions). Record each decision in progress.decisions.

## Phase 2: Validate & Enrich
For each task, verify all required fields and fill gaps:
- Task: subject, description (WHY + connection to dependents), activeForm, status (pending), result (null), attempts (0), blockedBy
- Metadata: type (research|implementation|testing|configuration), files {create:[], modify:[]}, reads
- Agent: role, model, approach, contextFiles [{path, reason, lines?}], assumptions [{claim, verify (shell cmd), severity: blocking|warning}], acceptanceCriteria [{criterion, check (shell cmd)}], rollbackTriggers ["If X, STOP and return BLOCKED: reason"], constraints
- Non-code goals: acceptance criteria may use content checks (grep), rollback triggers reference content expectations
- Design artifacts: add .design/goal-analysis.json to every task's contextFiles (reason: "design phase codebase analysis and approach decisions"). For expert-originated tasks, add .design/expert-{name}.json.

## Phase 3: Auto-generate Safety
- File existence: for each modify path, add blocking assumption `test -f {path}`
- Cross-task deps: if task B modifies/creates files overlapping task A (in blockedBy closure), add blocking assumption
- Convert every blocking assumption to a rollback trigger

## Phase 4: Validate (7 checks)
1. Tasks >= 1. 2. No concurrent file conflicts (create/modify). 3. No read/write overlaps between concurrent tasks. 4. All blockedBy valid, no cycles. 5. Every task has >= 1 assumption and >= 1 rollback trigger. 6. Total tasks <= 12. 7. Critical path <= 4 (restructure for parallelism if exceeded).
Self-repair: fix and re-validate. After 2 attempts, include in validationIssues and proceed.

## Phase 5: Assemble Worker Prompts

For each task, concatenate sections S1-S9. Include conditional sections only when referenced field is non-empty.

**S1: Role** [always] `You are a {agent.role}` + ` with expertise in {agent.expertise}` [if exists]

**S2: Pre-flight** [always] `## Pre-flight` / `Verify before starting. If BLOCKING check fails, return BLOCKED: followed by the reason.` + agent.assumptions as checklist: `- [ ] [{severity}] {claim}: \`{verify}\``

**S3: Context** [always] `## Context` / `Read before implementing:` + agent.contextFiles as `- {path} — {reason}` + `Project: {context.stack}. Conventions: {context.conventions}.` + `Test: {context.testCommand}` [if exists] + `Use LSP (goToDefinition, findReferences, hover) over Grep for {context.lsp.available}.` [if exists] + `Use WebSearch/WebFetch for current information. Prefer web tools over assumptions when external facts are needed.` [if metadata.type = research]

**S4: Task** [always] `## Task: {task.subject}` / `{task.description}` / `Files to create: {metadata.files.create or "(none)"}` / `Files to modify: {metadata.files.modify or "(none)"}` + agent.constraints as bullets under `Constraints:`

**S5: Strategy** [if any exists] `Approach: {agent.approach}` [if exists] / `Apply: {agent.priorArt}` [if exists] / `Fallback: {agent.fallback}` [if exists]

**S6: Dependency placeholder** [if task.blockedBy non-empty] Emit: `[Dependency results — deferred: lead appends actual results at spawn time]`

**S7: Rollback** [always] `Rollback triggers — STOP immediately if any occur:` + agent.rollbackTriggers as bullets

**S8: Acceptance** [always] `## After implementing` / `1. Verify acceptance criteria:` + agent.acceptanceCriteria as `- [ ] {criterion}: \`{check}\`` + `   Fix failures before proceeding.` / `2. Do NOT stage or commit — the lead handles git after the batch completes.`

**S9: Output format** [always] Emit verbatim (substitute {planIndex}):
   ## After implementing (continued)
   3. Write your full work log (reasoning, commands run, decisions made, issues encountered) to `.design/worker-{planIndex}.log` using the Write tool. This log is consumed by the result processor — include enough detail for verification.

   ## Output format
   The FINAL line of your output MUST be one of:
   - COMPLETED: {one-line summary}
   - FAILED: {one-line reason}
   - BLOCKED: {reason}

   Return ONLY the status line as your final output. All detailed work output goes in the log file above.

   Example valid outputs:
   ...writing log.\nCOMPLETED: Added user authentication middleware with JWT
   ...writing log.\nBLOCKED: Required package pg not installed

Store the assembled prompt string in each task's `prompt` field.

## Phase 6: Compute File Overlap Matrix

Build a global concurrency-aware file overlap matrix. Two tasks can run concurrently if neither transitively depends on the other through blockedBy chains.

For each pair of tasks that can run concurrently, build a set of all file paths from each task's metadata.files.create and metadata.files.modify. Check for intersections between the two tasks' file sets. Record which task indices conflict.

The result is a mapping from each planIndex to an array of other planIndices that have file conflicts AND can run concurrently with it. Store in each task's `fileOverlaps` field (array of planIndex integers; empty array if no conflicts).

## Phase 7: Write .design/plan.json
Schema (schemaVersion 3): {schemaVersion: 3, goal, context: {stack, conventions, testCommand, buildCommand, lsp}, progress: {completedTasks: [], surprises: [], decisions: []}, tasks: [...]}
Each task uses the schema from Phase 2 plus: `prompt` (assembled worker prompt from Phase 5), `fileOverlaps` (array of conflicting planIndex integers from Phase 6). Tasks ordered (index = ID, 0-based), blockedBy references indices, status: pending|in_progress|completed|failed|blocked|skipped. Note: execute will strip `prompt` from completed tasks during progressive trimming to reduce plan size.

## Output
Claim your task and mark completed. Read ~/.claude/teams/do-design/config.json for the lead's name, then:

    SendMessage(type: "message", recipient: {lead-name}, content: <FINAL-line JSON below>, summary: "Plan written")

FINAL-line JSON: {"taskCount": N, "maxDepth": N, "gapsFilled": N, "critiqueResolutions": N, "validationIssues": [], "depthSummary": {"1": ["Task 0: subject"], ...}}
Depth: 1 for empty blockedBy, else 1 + max(depth of blockedBy tasks). On unresolvable error, send {error: "...", validationIssues: []} instead.
```

**Lead wait pattern**: After spawning all agents, wait. The plan-writer's `SendMessage` is delivered automatically. Parse JSON from message content.

**Do NOT poll**: Teammate messages are auto-delivered — never use `sleep`, `ls`, or Bash loops to check for agent output files. Simply wait; the next message you receive will be from a teammate or the system.

After receiving the plan-writer's message: `SendMessage(type: "shutdown_request")` to each teammate, wait for confirmations, `TeamDelete(team_name: "do-design")`.

**Two-tier fallback** (standard/full only) — triggered when the team fails to produce `.design/plan.json`:

- **Tier 1**: Shut down team. Spawn single plan-writer Task subagent (not teammate) with the prompt above, reading `.design/expert-*.json` and `.design/critic.json` (full only).
- **Tier 2**: If retry fails, merge inline with context minimization — process one expert file at a time, extract tasks arrays, merge incrementally. Read critic for blocking issues only (full). Execute Phases 2–5 with reduced scope.

## Step 4: Cleanup & Summary

1. **Verify**: `python3 -c "import json; p=json.load(open('.design/plan.json')); assert p.get('schemaVersion') == 3, 'schemaVersion must be 3'"`. Use stored `taskCount`/`maxDepth` from plan-writer's SendMessage.
2. **Clean up TaskList**: Delete all tasks created during planning so `/do:execute` starts clean.
3. **Output summary** using stored plan-writer data:

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
