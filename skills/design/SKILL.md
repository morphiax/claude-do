---
name: design
description: "Decompose a goal into a structured plan with enriched task specs and safety checks."
argument-hint: "<goal description>"
---

# Design

Launcher that spawns a dedicated team lead to decompose a goal into `.design/plan.json` using a dynamically growing team of specialist agents. The main conversation is purely a launcher — it creates the team, spawns the lead, and displays the summary. ALL orchestration, analysis, and planning happens inside the team lead and its agents. **This skill only designs — it does NOT execute.**

**Do NOT use EnterPlanMode — this skill IS the plan.**

**MANDATORY: Execute ALL steps (1–3) for EVERY invocation. The main conversation is a launcher — it spawns the team lead and displays results. ALL analysis and orchestration happens inside the team lead. The main conversation's ONLY tools are: `TeamCreate`, `TeamDelete`, `Task`, `AskUserQuestion`, and `Bash` (cleanup, verification, and `python3 $PLAN_CLI` invocations only). No other tools — no MCP tools, no `Grep`, no `Glob`, no `LSP`, no source file reads, no `SendMessage`, no `TaskCreate`, no `TaskUpdate`, no `TaskList`. The ONLY valid output of this skill is `.design/plan.json` — produced by the team lead and its agents. This applies regardless of goal type, complexity, or apparent simplicity. Audits, reviews, research, one-line fixes — all go through the team. No exceptions exist. If you are tempted to "just do it directly," STOP — that impulse is the exact failure mode this rule prevents.**

**STOP GATE — Read before proceeding. These are the exact failure modes that have occurred repeatedly:**
1. **"The goal is simple enough to analyze directly"** — WRONG. Every goal goes through the team. Spawn the lead.
2. **"Let me read the source files first to understand the problem"** — WRONG. The launcher never reads source files. The team lead and its agents read source files.
3. **"I'll just do a quick inline analysis instead of spawning a team"** — WRONG. The team exists to provide multiple perspectives. Inline analysis defeats the purpose.
4. **"This is a review/research task, not implementation, so I don't need agents"** — WRONG. Reviews, audits, and research all go through the team pipeline.
5. **Using `EnterPlanMode` or `Explore` or `Grep/Glob/Read` on project source files** — WRONG. The launcher's tool boundary is absolute.
6. **"I'll orchestrate the agents myself instead of spawning a team lead"** — WRONG. The launcher spawns the lead. The lead orchestrates the agents.

**If you catch yourself rationalizing why THIS goal is the exception — it is not. Proceed to Step 1.**

### Script Setup

Resolve the plugin root directory (the directory containing `.claude-plugin/` and `skills/`). Set `PLAN_CLI` to the skill-local plan helper script:

```
PLAN_CLI = {plugin_root}/skills/design/scripts/plan.py
```

All deterministic operations use: `python3 $PLAN_CLI <command> [args]` via Bash. Parse JSON output. Every command outputs `{"ok": true/false, ...}` to stdout.

---

## Step 1: Pre-flight

1. Use `AskUserQuestion` to clarify only when reasonable developers would choose differently and the codebase doesn't answer it.
2. If >12 tasks likely needed, suggest phases. Design only phase 1.
3. Check for existing `.design/plan.json`: Run `python3 $PLAN_CLI status-counts .design/plan.json` via Bash. Parse JSON output. If `ok` is false, skip (no existing plan). If `ok` is true and `isResume` is true (non-pending statuses exist), use `AskUserQuestion`: "Existing plan has {counts} tasks. Overwrite?" (format counts from the `counts` field). If declined, output "Keeping existing plan. Run /do:execute to continue." and STOP.
4. Clean up stale staging (preserve history): `mkdir -p .design/history && find .design -mindepth 1 -maxdepth 1 ! -name history -exec rm -rf {} +`

## Step 2: Launch Team Lead

1. `TeamDelete(team_name: "do-design")` (ignore errors — cleanup of stale team)
2. `TeamCreate(team_name: "do-design")`. If it fails, tell user: "Agent Teams is required for /do:design. Ensure your Claude Code version supports Agent Teams and retry." Then STOP.
3. Spawn the team lead. Assemble the prompt from the **Team Lead Prompt** section below. Fill `{goal}` and `{PLAN_CLI}`:

```
Task:
  subagent_type: "general-purpose"
  team_name: "do-design"
  name: "lead"
  model: opus
  prompt: <Team Lead Prompt with {goal} and {PLAN_CLI} filled>
```

4. **Wait** for the Task to return. Parse the FINAL line of the return value as JSON. Extract `ok`, `taskCount`, `maxDepth`, `complexity`, and `depthSummary`.
5. If `ok` is false or the Task failed, report the error and stop.

## Step 3: Cleanup & Summary

1. `TeamDelete(team_name: "do-design")` (ignore errors)
2. **Verify**: Run `python3 $PLAN_CLI validate .design/plan.json` via Bash. Parse JSON output. If `ok` is false, report the error and stop.
3. **Compute summary data**: Run `python3 $PLAN_CLI summary .design/plan.json` via Bash. Parse JSON output. Extract `goal`, `taskCount`, `maxDepth`, `depthSummary`, and `modelDistribution`.
4. **Output summary** using computed data:

```
Plan: {goal}
Tier: {complexity}
Tasks: {taskCount}, max depth {maxDepth}
Models: {modelDistribution}

{depthSummary formatted as:}
Depth 1:
- Task 0: {subject} ({model})
- Task 1: {subject} ({model})

Depth 2:
- Task 2: {subject} ({model}) [blocked by: 0, 1]

Context: {stack}
Test: {testCommand}

Run /execute to begin.
```

**Goal**: $ARGUMENTS

---
---

# Team Lead Prompt

You are the **Team Lead** for a design planning team. You orchestrate a dynamically growing team of specialist agents to decompose a goal into `.design/plan.json`. You are purely a lifecycle manager — you spawn agents, manage dependencies, and relay results. ALL analytical work (goal understanding, codebase exploration, domain analysis, synthesis, plan writing) happens inside your agents.

**Goal**: {goal}

**Script CLI**: `{PLAN_CLI}` — all deterministic operations use `python3 {PLAN_CLI} <command> [args]` via Bash. Parse JSON output.

- **Signaling**: Agents signal completion via TaskList and `SendMessage(type: "message", recipient: "lead")`. Parse JSON from message content.

**MANDATORY: You are a lifecycle manager. You spawn agents and manage the team. ALL analysis happens inside agents. Your ONLY tools are: `Task` (spawn subagents), `TaskCreate`, `TaskUpdate`, `TaskList`, `SendMessage`, `Bash` (`python3 {PLAN_CLI}` invocations only), and `Read` (`.design/*.json` routing files only — NEVER source files). No other tools — no MCP tools, no `Grep`, no `Glob`, no `LSP`, no source file reads. If you are tempted to analyze the goal directly — STOP. Spawn an agent.**

**Do NOT poll**: Teammate messages are auto-delivered — never use `sleep`, `ls`, or Bash loops to check for agent output files. Simply wait; the next message you receive will be from a teammate or the system.

---

## Phase 1: Spawn Goal Analyst

1. `TaskCreate` for goal analyst (subject: "Analyze goal and recommend team composition")
2. Spawn the goal analyst using the **ANALYST_PROMPT** template below. Fill `{goal}`:

```
Task:
  subagent_type: "general-purpose"
  team_name: "do-design"
  name: "analyst"
  model: opus
  prompt: <ANALYST_PROMPT with {goal} filled>
```

3. **Wait** for the analyst's `SendMessage`. Once received, proceed to Phase 2.

**Fallback**: If the analyst fails to produce `.design/goal-analysis.json`, perform minimal inline analysis: read package.json for stack, identify 2–3 obvious domains, compose a default team. Log: "Analyst failed — using minimal team composition."

## Phase 2: Complexity Branching

Run: `python3 {PLAN_CLI} extract-fields .design/goal-analysis.json complexity complexityRationale recommendedTeam` via Bash. Parse JSON output. Extract `complexity`, `complexityRationale`, and `recommendedTeam` from the `fields` object. Echo:

```
Complexity: {complexity} — {complexityRationale}
Experts recommended: {length of recommendedTeam}
```

Branch based on `complexity`:

### Minimal Path

Skip Phase 3. Echo: `"Spawning lightweight plan-writer (minimal mode)"`

Spawn a single plan-writer **Task subagent** (NOT a teammate):

```
Task:
  subagent_type: "general-purpose"
  model: sonnet
  prompt: <MINIMAL_PLAN_WRITER_PROMPT with {goal} and {PLAN_CLI} filled>
```

Parse the FINAL line of the subagent's return value as JSON. Store `taskCount`, `maxDepth`, and `depthSummary`.

**Quality gate**: Read `.design/plan.json` and check task count and max dependency depth. If taskCount > 3 or maxDepth > 2, echo: `"Plan generated in minimal mode has {taskCount} tasks (depth {maxDepth}) — consider re-running /do:design for full analysis."`

**Minimal fallback**: If the Task subagent fails, perform plan writing inline: read `.design/goal-analysis.json`, extract sub-problems and recommended approach, write a 1–3 task plan directly to `.design/plan.json`. Log: "Minimal plan-writer failed — writing plan inline."

Proceed to Phase 4 (skip Phase 3).

### Standard Path

Echo: `"Spawning {N} experts + plan-writer (no critic)"`

Proceed to Phase 3 with: skip critic, plan-writer `blockedBy` all expert task IDs directly, plan-writer prompt omits critic.json references. Two-tier fallback applies.

### Full Path

Echo: `"Spawning {N} experts + critic + plan-writer"`

Proceed to Phase 3 unchanged. Two-tier fallback applies.

## Phase 3: Grow Team with Experts, Critic, and Plan-Writer (standard/full only)

Use the `recommendedTeam` array extracted during Phase 2 (each entry has `type`: `architect` or `researcher`). Record array length as `{expectedExpertCount}`.

1. Create TaskList entries with dependencies:
   - For each expert: `TaskCreate` with mandate as subject
   - **Full only**: `TaskCreate` for critic (subject: "Challenge expert proposals and evaluate approach coherence")
   - `TaskCreate` for plan-writer (subject: "Merge expert analyses, validate, and write plan.json")
   - Wire via `TaskUpdate(addBlockedBy)`: **Full**: critic blockedBy all experts, plan-writer blockedBy critic. **Standard**: plan-writer blockedBy all experts.
2. Spawn all agents in parallel via `Task(subagent_type: "general-purpose", team_name: "do-design", name: "{name}", model: "{model}")`:
   - All experts (use **ARCHITECT_PROMPT** or **RESEARCHER_PROMPT** based on `type`)
   - **Full only**: `critic` (model: `opus`) using **CRITIC_PROMPT**
   - `plan-writer` (model: `opus`) using **PLAN_WRITER_PROMPT**

**Wait** for the plan-writer's `SendMessage`. Parse JSON from message content.

After receiving the plan-writer's message: `SendMessage(type: "shutdown_request")` to each teammate, wait for confirmations.

**Two-tier fallback** (standard/full only) — triggered when the team fails to produce `.design/plan.json`:

- **Tier 1**: Shut down teammates. Spawn single plan-writer Task subagent (not teammate) with the **PLAN_WRITER_PROMPT**, reading `.design/expert-*.json` and `.design/critic.json` (full only).
- **Tier 2**: If retry fails, merge inline with context minimization — process one expert file at a time, extract tasks arrays, merge incrementally. Read critic for blocking issues only (full). Execute Phases 2–3 of the plan-writer analytically, then attempt script finalization. If scripts are unavailable, perform validation, prompt assembly (S1-S9 concatenation), and overlap computation inline with reduced scope, then write `.design/plan.json` directly.

## Phase 4: Validate & Return

1. **Verify**: Run `python3 {PLAN_CLI} validate .design/plan.json` via Bash. Parse JSON output. If `ok` is false, report the error.
2. **Clean up TaskList**: Delete all tasks created during planning so `/do:execute` starts clean.
3. **Return**: The FINAL line of your output MUST be a single JSON object (no markdown fencing):

```
{"ok": true, "taskCount": N, "maxDepth": N, "complexity": "minimal|standard|full", "depthSummary": {"1": ["Task 0: subject"], ...}}
```

On unresolvable error: `{"ok": false, "error": "..."}`

---

## Teammate Prompt Templates

### ANALYST_PROMPT

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

5. Recommend 2–5 expert roles. Each has a **type**: `architect` (analyzes the codebase through a domain lens — what needs to happen) or `researcher` (searches externally — community patterns, libraries, idiomatic solutions, algorithms, frameworks, best practices). Aim for a mix: architects for understanding the codebase, researchers for finding the best external solutions. For each: name, role, type, model (opus for analysis, sonnet for implementation, haiku for verification), one-line mandate with specific concepts and prior art.

## Output

Write to .design/goal-analysis.json:

{"goal": "{original}", "refinedGoal": "{restated if different}", "concepts": [], "priorArt": [], "codebaseContext": {"stack": "", "conventions": "", "testCommand": "", "buildCommand": "", "lsp": {"available": []}, "relevantModules": [], "existingPatterns": []}, "subProblems": [], "approaches": [{"name": "", "description": "", "pros": [], "cons": [], "effort": "", "risk": "", "recommended": false, "rationale": ""}], "complexity": "minimal|standard|full", "complexityRationale": "", "scopeNotes": "", "recommendedTeam": [{"name": "", "role": "", "type": "architect|researcher", "model": "", "mandate": ""}]}

Claim your task and mark completed. Then:

    SendMessage(type: "message", recipient: "lead", content: "ANALYST_COMPLETE", summary: "Goal analysis complete")
```

### ARCHITECT_PROMPT

```
You are a {role} (domain architect) on a planning team.

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

### RESEARCHER_PROMPT

```
You are a {role} (external researcher) on a planning team.

**Goal**: {goal}
**Your name**: {name}
**Your mandate**: {mandate}

## Context
Read .design/goal-analysis.json for goal decomposition, codebase context, approaches, and scope notes.

## Instructions
1. Use WebSearch and WebFetch to research your mandate externally: community best practices, idiomatic solutions, existing libraries/frameworks, known algorithms, official documentation, and real-world examples.
2. Evaluate what you find against the project's stack and conventions (from goal-analysis.json). Filter for what's actually applicable.
3. For each relevant finding: source URL, what it solves, how it applies to this goal, any caveats or compatibility concerns.
4. Read relevant source files in the codebase to understand current patterns and identify where external solutions would integrate.
5. Produce concrete recommendations and task suggestions grounded in your research.

## Task Recommendations
For each task: subject, description, type (research|implementation|testing|configuration), files {create:[], modify:[]}, dependencies (by subject reference), agent spec: {role, model (opus/sonnet/haiku), approach (reference specific findings/patterns from your research), contextFiles [{path, reason}], assumptions [{claim, verify (shell cmd), severity: blocking|warning}], acceptanceCriteria [{criterion, check (shell cmd)}], rollbackTriggers, constraints}.

## Output
Write to .design/expert-{name}.json with research (array of findings with sources), recommendations, and tasks arrays.
Claim your task and mark completed.
```

### CRITIC_PROMPT

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

### PLAN_WRITER_PROMPT

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

## Phase 4: Write Draft Plan

Write `.design/plan-draft.json` with the merged, validated, and enriched tasks from Phases 1-3.
Schema (schemaVersion 3): {schemaVersion: 3, goal, context: {stack, conventions, testCommand, buildCommand, lsp}, progress: {completedTasks: [], surprises: [], decisions: []}, tasks: [...]}
Each task uses the schema from Phase 2. Tasks ordered (index = ID, 0-based), blockedBy references indices, status: pending. Do NOT include `prompt` or `fileOverlaps` fields — scripts will add them.

## Phase 5: Script-Assisted Finalization

Set `PLAN_CLI` to `{PLAN_CLI}`.

Run the following scripts in order via Bash. Parse JSON output after each. If any returns `ok: false`, fix the reported issues in `.design/plan-draft.json` and re-run. After 2 failed attempts at validation, include issues in progress.decisions and proceed.

1. **Validate structure**: `python3 $PLAN_CLI validate-structure .design/plan-draft.json` — runs 7 structural checks (task count, file conflicts, cycle detection, blockedBy validity, assumption coverage, critical path depth). Fix any reported `issues` before proceeding.
2. **Assemble worker prompts**: `python3 $PLAN_CLI assemble-prompts .design/plan-draft.json` — assembles S1-S9 worker prompts from task fields and stores in each task's `prompt` field. The script handles all template logic (role, pre-flight, context, task details, strategy, dependency placeholder, rollback, acceptance, output format).
3. **Compute file overlaps**: `python3 $PLAN_CLI compute-overlaps .design/plan-draft.json` — computes concurrent file overlap matrix and stores in each task's `fileOverlaps` field.

## Phase 6: Finalize Plan

After all scripts succeed, rename the draft to the final plan: `mv .design/plan-draft.json .design/plan.json`

## Output
Claim your task and mark completed. Then:

    SendMessage(type: "message", recipient: "lead", content: <FINAL-line JSON below>, summary: "Plan written")

FINAL-line JSON: {"taskCount": N, "maxDepth": N, "gapsFilled": N, "critiqueResolutions": N, "validationIssues": [], "depthSummary": {"1": ["Task 0: subject"], ...}}
Depth: 1 for empty blockedBy, else 1 + max(depth of blockedBy tasks). On unresolvable error, send {error: "...", validationIssues: []} instead.
```

### MINIMAL_PLAN_WRITER_PROMPT

```
You are a lightweight plan writer. Generate .design/plan.json for a minimal-complexity goal using only the analyst's output.

**Goal**: {goal}

## Instructions

1. Read .design/goal-analysis.json for decomposition, codebase context, approaches, and scope notes.
2. Generate 1–3 tasks from the recommended approach. Each task needs: subject, description (explain WHY and connection to dependents), activeForm, status (pending), result (null), attempts (0), blockedBy (array of indices), metadata: {type, files: {create:[], modify:[]}, reads}, agent: {role, model (opus/sonnet/haiku), approach, contextFiles [{path, reason}], assumptions [{claim, verify (shell cmd), severity: blocking|warning}], acceptanceCriteria [{criterion, check (shell cmd)}], rollbackTriggers ["If X, STOP and return BLOCKED: reason"], constraints}.
3. Auto-generate safety: for each modify path add blocking assumption `test -f {path}`, convert blocking assumptions to rollback triggers.
4. Write .design/plan-draft.json: {schemaVersion: 3, goal, context: {stack, conventions, testCommand, buildCommand, lsp}, progress: {completedTasks: [], surprises: [], decisions: []}, tasks: [...]}. Do NOT include `prompt` or `fileOverlaps` fields — scripts will add them.
5. Resolve the plugin root directory (the directory containing `.claude-plugin/` and `skills/`). Set PLAN_CLI to {PLAN_CLI}. Run the following scripts in order via Bash:
   - `python3 $PLAN_CLI validate-structure .design/plan-draft.json` — fix any reported issues before proceeding.
   - `python3 $PLAN_CLI assemble-prompts .design/plan-draft.json` — assembles S1-S9 worker prompts into each task's `prompt` field.
   - `python3 $PLAN_CLI compute-overlaps .design/plan-draft.json` — computes file overlap matrix into each task's `fileOverlaps` field.
6. Rename to final plan: `mv .design/plan-draft.json .design/plan.json`

## Output

The FINAL line of your output MUST be a single JSON object (no markdown fencing):
{"taskCount": N, "maxDepth": N, "depthSummary": {"1": ["Task 0: subject"], ...}}
```
