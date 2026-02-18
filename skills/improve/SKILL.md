---
name: improve
description: "Analyze and improve Claude Code skills with scientific methodology."
argument-hint: "<skill-path> [focus-area]"
---

# Improve

Analyze a Claude Code skill and produce `.design/plan.json` with improvement roles — testable hypotheses for targeted changes. **This skill only analyzes and plans — it does NOT write source files.**

**PROTOCOL REQUIREMENT: Your FIRST action MUST be the pre-flight check. Follow the Flow step-by-step.**

**Do NOT use `EnterPlanMode`** — this skill IS the plan.

**Lead boundaries**: Use only `TeamCreate`, `TeamDelete`, `TaskCreate`, `TaskUpdate`, `TaskList`, `SendMessage`, `Task`, `AskUserQuestion`, and `Bash` (for `python3 $PLAN_CLI`, cleanup, verification). Project metadata (CLAUDE.md, package.json, README) allowed via Bash. **Never use Read, Grep, Glob, Edit, Write, LSP, WebFetch, WebSearch, or MCP tools on project source files.** The lead orchestrates — agents think.

**No polling**: Messages auto-deliver automatically. Never use `sleep`, loops, or Bash waits. When a teammate sends a message, it appears in your next turn.

**Output contract**: Improve ALWAYS produces `.design/plan.json` (schemaVersion 4) for `/do:execute`. Even single-file improvements go through execute. Improve never writes skill source files directly.

---

## Quality Dimensions

The 7 dimensions used to evaluate skill quality. Experts score each 1-5 with evidence.

| Dimension | What it measures | Indicators |
|---|---|---|
| **Protocol Clarity** | Unambiguous step-by-step flow. Each step specifies WHAT and WHEN. | Numbered steps, decision matrices, explicit conditionals |
| **Constraint Enforcement** | Mechanisms preventing agent deviation. | CRITICAL/BOLD markers, tool whitelists, negative constraints |
| **Error Handling** | Graceful degradation for failures, timeouts, missing data. | Fallback strategies, retry limits, circuit breakers, resume support |
| **Agent Coordination** | How agents discover each other, share info, avoid conflicts. | Team naming, message-based coordination, shared state patterns |
| **Information Flow** | What information goes where, in what format, when. | Artifact formats, data flow direction, contract schemas |
| **Prompt Economy** | Minimal tokens for maximum behavioral effect. | Tables over prose, structured templates, term reuse |
| **Verifiability** | Can behavior be validated? Are outputs checkable? | Structured outputs, validation commands, audit trails |

Scoring anchors: **5** = exemplary, no gaps, reference-quality | **3** = adequate, works but has identifiable gaps | **1** = missing or broken, causes agent deviation

---

## Clarification Protocol

| ASK (`AskUserQuestion`) when | SKIP when |
|---|---|
| Skill path is ambiguous or doesn't exist | Path resolves to a valid SKILL.md |
| Focus area conflicts with skill's purpose | Focus area is clear or omitted (general analysis) |
| Multiple valid improvement strategies exist | Standard quality analysis applies |

### Script Setup

Resolve plugin root (containing `.claude-plugin/`). All script calls: `python3 $PLAN_CLI <command> [args]` via Bash. JSON output: `{"ok": true/false, ...}`.

```bash
PLAN_CLI={plugin_root}/skills/improve/scripts/plan.py
TEAM_NAME=$(python3 $PLAN_CLI team-name improve).teamName
SESSION_ID=$TEAM_NAME
```

### Trace Emission

After each agent lifecycle event: `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event {event} --skill improve [--agent "{name}"] || true`. Events: skill-start, skill-complete, spawn, completion, failure, respawn. Failures are non-blocking (`|| true`).

---

## Flow

### 1. Pre-flight

1. **Lifecycle context**: Run `python3 $PLAN_CLI plan-health-summary .design` and display to user: "Previous session: {handoff summary}. Recent runs: {reflection summaries}. {plan status}." Skip if all fields empty. Then: `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event skill-start --skill improve || true`
2. **Parse arguments**: Extract `<skill-path>` and optional `[focus-area]` from `$ARGUMENTS`.
   - If `skill-path` is a name (e.g., `design`), resolve to `skills/{name}/SKILL.md`.
   - If no path provided, ask user which skill to analyze.
3. **Validate target**: Confirm the SKILL.md file exists via Bash (`test -f {skill-path}`). If not found, report and stop.
4. **Snapshot**: Copy target SKILL.md to `.design/skill-snapshot.md` via Bash. This is the baseline for regression comparison.
5. **Circular improvement detection**: Check `.design/history/` for recent improve runs targeting the same skill:
   ```bash
   ls .design/history/*/skill-snapshot.md 2>/dev/null | head -5
   ```
   If found, warn user: "Previous improvement runs detected. Review history to avoid circular changes."
6. **Check existing plan**: `python3 $PLAN_CLI status .design/plan.json`. If `ok` and `isResume`: ask user "Existing plan found. Overwrite?" If declined, stop.
7. **Archive stale artifacts**: `python3 $PLAN_CLI archive .design`
8. **Re-snapshot** (archive may have moved it): Copy target SKILL.md to `.design/skill-snapshot.md` again.

### 2. Lead Research

The lead assesses the target skill and determines the analysis approach.

1. Read project metadata (CLAUDE.md) via Bash to understand the plugin architecture.
2. **Determine analysis mode**:

| Mode | Trigger | Team | Experts |
|---|---|---|---|
| **Targeted** | Focus area provided (e.g., "reduce cross-review verbosity") | No team — single Task agent | 1 specialist |
| **General** | No focus area — full quality analysis | Team `$TEAM_NAME` | 2-3 experts |
| **Cross-skill** | Path is `--all` or multiple paths | Team `$TEAM_NAME` | 2-3 experts + cross-review |

3. **Memory injection**: Run `python3 $PLAN_CLI memory-search .design/memory.jsonl --goal "improve {skill-name}" --stack "SKILL.md prompt engineering"`. If `ok: false` or no memories → proceed without injection. Otherwise inject top 3-5 into expert prompts. **Show user**: "Memory: injecting {count} past learnings — {keyword summaries}."
4. **Historical evidence**: Check for past execution artifacts:
   ```bash
   ls .design/history/*/handoff.md 2>/dev/null | head -5
   ```
   If found, note paths for experts — execution evidence is higher-confidence than behavioral simulation.
5. **Announce to user**: "Analyzing {skill-name}: {analysis mode} mode, {N} experts ({names}). {historical evidence status}."

### 3. Analyze Skill

#### Targeted Mode (single Task agent)

Spawn a single analyst via `Task(subagent_type: "general-purpose", model: "sonnet")` (analyst requires Read/Grep for skill files and historical artifacts):

Prompt includes:
- "Analyze `.design/skill-snapshot.md` for this specific improvement area: {focus-area}."
- "Read the actual skill at `{skill-path}` and the project architecture in `CLAUDE.md`."
- "Score the relevant dimensions (1-5) using the scoring anchors from this protocol."
- If historical evidence exists: "Read past execution artifacts at {paths} for evidence of actual behavior."
- If no historical evidence: "Perform behavioral simulation: trace through 2 representative scenarios step-by-step. Flag where agent behavior might diverge from intent. **Note: this is lower-confidence than execution evidence.**"
- "For each finding, form a **testable hypothesis**: what to change, predicted behavioral impact, and how to verify."
- "In your findings JSON, include a `verificationProperties` section: an array of properties that should hold regardless of implementation (behavioral invariants, boundary conditions). Format: `[{\"property\": \"...\", \"category\": \"invariant|boundary|integration\", \"testableVia\": \"how to test this\"}]`."
- "Save findings to `.design/expert-analyst.json` with structure: `{\"skillPath\": \"...\", \"focusArea\": \"...\", \"qualityScores\": {\"dimension\": {\"score\": N, \"evidence\": \"...\"}}, \"findings\": [{\"location\": \"section/line\", \"issue\": \"...\", \"severity\": \"high|medium|low\", \"hypothesis\": {\"change\": \"...\", \"predictedEffect\": \"...\", \"verification\": \"...\"}}], \"verificationProperties\": [...], \"tokenAnalysis\": {\"totalLines\": N, \"heaviestSections\": [...]}, \"summary\": \"...\"}`. Return a summary."

**Artifact verification**: After Task completes, verify artifact exists: `ls .design/expert-analyst.json`. If missing, retry Task once with the same prompt. If still missing, report to user and stop.

Proceed directly to Step 4 (Synthesize) after receiving the analyst's report.

#### General/Cross-skill Mode (team-based)

1. `TeamDelete(team_name: $TEAM_NAME)` (ignore errors), `TeamCreate(team_name: $TEAM_NAME)`. If TeamCreate fails, tell user Agent Teams is required and stop.
2. **Team health check**: After spawning experts, verify team state by checking that all experts are reachable. If any expert is unreachable, delete the team and retry TeamCreate once. If retry fails, abort and tell user Agent Teams is unavailable.
3. Spawn experts in parallel as teammates using the Task tool with `team_name: $TEAM_NAME` and `model: "sonnet"` (experts require Read/Grep for skill files and historical artifacts). Before each Task call: `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event spawn --skill improve --agent "{expert-name}" || true`

**Protocol Analyst** — evaluates clarity, completeness, flow gaps:
- "Question every step that lacks explicit success/failure handling. Assume agents will take the most literal interpretation of ambiguous instructions. Trace through 2 representative execution scenarios looking for where agents could deviate."
- "Read `.design/skill-snapshot.md`. Score Protocol Clarity, Error Handling, and Verifiability (1-5 each with evidence)."
- "Identify ambiguous steps, missing error paths, unverifiable outcomes."

**Prompt Engineer** — evaluates instruction density, constraint enforcement, economy:
- "Reject any instruction that adds tokens without changing behavior. Focus on finding dead rules that can never trigger and constraints that are stated but unenforceable."
- "Read `.design/skill-snapshot.md`. Score Constraint Enforcement, Prompt Economy, and Information Flow (1-5 each with evidence)."
- "Identify prompt bloat, dead rules, and missing constraints."

**Coordination Analyst** (only for skills with multi-agent patterns) — evaluates agent coordination:
- "Assume agents will race, deadlock, or lose messages unless the protocol explicitly prevents it. Verify every coordination point."
- "Read `.design/skill-snapshot.md`. Score Agent Coordination (1-5 with evidence)."
- "Analyze team lifecycle, message patterns, shared state management. Identify race conditions, deadlock risks, information silos."

Every expert prompt MUST end with: "In your findings JSON, include a `verificationProperties` section: an array of properties that should hold regardless of implementation (behavioral invariants, boundary conditions, cross-role contracts). Format: `[{\"property\": \"...\", \"category\": \"invariant|boundary|integration\", \"testableVia\": \"how to test this with concrete commands/endpoints\"}]`. Provide concrete, externally observable properties that can be tested without reading source code. Save your complete findings to `.design/expert-{name}.json` as structured JSON. Then SendMessage to the lead with a summary." Include past learnings and historical evidence paths if available.

4. **Expert liveness pipeline**: Track completion: (a) SendMessage received AND (b) artifact file exists (`ls .design/expert-{name}.json`). **Show user status**: "Expert progress: {name} done ({M}/{N} complete)." On completion: `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event completion --skill improve --agent "{name}" || true`

| Rule | Action |
|---|---|
| Turn timeout (2 turns) | Send: "Status check — artifact expected at `.design/expert-{name}.json`. Report completion or blockers." |
| Re-spawn ceiling | No completion 1 turn after ping → re-spawn with same prompt (max 2 attempts). On re-spawn: `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event respawn --skill improve --agent "{name}" || true` |
| Proceed with available | After 2 re-spawn attempts → `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event failure --skill improve --agent "{name}" || true`. Log failure, proceed with responsive experts' artifacts. |
| Never write artifacts yourself | Lead interpretation ≠ specialist analysis. |
5. **Validate expert artifacts** before cross-review:
   - Verify existence: `ls .design/expert-*.json`
   - Validate JSON structure: For each artifact, parse and confirm it contains required fields: `skillPath`, `dimensions` (or `qualityScores`), `findings`, `summary`
   - If any artifact is missing or malformed, message the expert: "Your artifact at {path} is missing or contains invalid JSON. Please fix and re-save."
   - If the expert is unreachable after retry, re-spawn it with the same prompt. **Never write an expert artifact yourself** — the lead's interpretation is not a substitute for specialist analysis

#### Cross-Review (General/Cross-skill mode only, >=2 experts)

When >=2 experts analyzed the same skill from different angles, perspective reconciliation is mandatory.

**Enforcement**: The lead MUST NOT perform cross-review analysis solo. When >=2 experts analyzed the same skill, perspective reconciliation requires actual `SendMessage` calls to experts and waiting for their responses. Skipping to plan synthesis without expert interaction when reconciliation applies is a protocol violation.

1. Lead identifies overlapping analysis — topics where experts scored the same dimension differently or made conflicting recommendations.
2. Lead messages the relevant experts: "Experts {A} and {B}: you scored {dimension} differently ({A}: {score}, {B}: {score}). Read each other's artifact. Send me: (a) where you agree, (b) where you disagree and why, (c) any synthesis."
3. **Maximum 2 rounds**. If no convergence, lead decides based on evidence quality and documents the trade-off.
4. Save `.design/cross-review.json`:
   ```json
   {
     "phasesRun": ["reconciliation"],
     "reconciliations": {"count": 0, "rounds": 0},
     "skippedPhases": [],
     "resolutions": []
   }
   ```

### 4. Synthesize into Improvement Plan

The lead collects expert findings and builds improvement roles for plan.json.

1. Collect all findings (messages and `.design/expert-*.json` files).
2. **Resolve conflicts** (if cross-review occurred): Document in `designDecisions[]`.
3. **Rank improvements** by: impact (high/medium/low) * (1 / regression risk) * (1 / token cost). Present top findings to user.
4. **Build roles**: For each approved improvement (or group of related improvements), create a role:
   - `goal`: The testable hypothesis — what to change and predicted behavioral effect
   - `scope.directories/patterns`: The skill file(s) to modify
   - `constraints`: Must preserve YAML frontmatter, must not break plan.json contract, must not exceed token budget, must not regress other dimensions
   - `acceptanceCriteria`: Concrete checks that verify the improvement works, not just that it exists. For SKILL.md changes: verify finalize still validates (`python3 $PLAN_CLI finalize .design/test-plan.json`), verify YAML frontmatter parses (`python3 -c "import yaml; yaml.safe_load(open(...))" `), verify behavioral change took effect. **Acceptance criteria anti-patterns to avoid**: `grep -q` (text presence, not function), `wc -l` (size, not behavior), `test -f` alone (file exists, not correct), `cmd || echo` (masks exit code).
   - `expertContext`: References to the analyst artifacts with relevance notes
   - `assumptions`, `rollbackTriggers`, `fallback` as appropriate
5. **CRITICAL: Anti-pattern guards** after building roles (DO NOT proceed to Step 6 if any guard triggers without user approval):
   - **Token budget**: Calculate net token delta for each proposed change. If total would increase skill beyond 500 lines, ask user to approve flagged changes explicitly.
   - **Circular improvement**: If `.design/history/` contains a previous improve run, check whether any proposed change reverses a previous improvement. If found, ask user to review before proceeding.
   - **Regression safety**: No quality dimension may degrade. If a change improves one dimension but risks another, note the trade-off explicitly and ask user to approve.
6. If improvements require updating CLAUDE.md or README.md to stay in sync (per pre-commit checklist), add a `docs-updater` role.
7. Write `.design/plan.json` with:
   - `schemaVersion: 4`
   - `goal`: "Improve {skill-name}: {summary of improvements}"
   - `context.stack`: "Claude Code plugin, SKILL.md prompt engineering"
   - `expertArtifacts[]`: References to all analyst artifacts
   - `designDecisions[]`: Resolved conflicts from cross-review
   - `roles[]`: Improvement roles
   - `auxiliaryRoles[]`: challenger (pre-execution), integration-verifier (post-execution), regression-checker (post-execution), memory-curator (post-execution)
   - Do NOT run finalize yet — that happens after optional verification specs.

#### 4.5. Generate Verification Specs (OPTIONAL)

Verification specs are property-based tests workers must satisfy. They codify expert verificationProperties as executable tests without constraining implementation.

**When to generate**: Goal has 2+ roles with testable properties AND expert artifacts contain verificationProperties AND stack supports tests (context.testCommand/buildCommand exists). Skip for trivial goals or sparse properties.

**Authorship**: Simple goals (1-3 roles) → lead writes from expert verificationProperties. Complex goals (4+ roles) → spawn spec-writer Task agent with `Task(subagent_type: "general-purpose", model: "sonnet")` that reads expert artifacts + actual codebase, writes specs in `.design/specs/{role-name}.{ext}` using project's test framework or shell scripts, returns created paths.

**Spec generation**:
1. Read expert verificationProperties from all `.design/expert-*.json` files
2. For each role, extract relevant properties (filter by scope/goal alignment)
3. `mkdir -p .design/specs`
4. Write spec files: native tests (`.design/specs/spec-{role-name}.test.{ext}` using bun test/pytest/jest/cargo test/etc with property-based frameworks like fast-check/hypothesis/proptest) OR shell scripts (`.design/specs/spec-{role-name}.sh` with exit 0 = pass)
5. For each spec, add to plan.json's `verificationSpecs[]`: `{"role": "{role-name}", "path": ".design/specs/spec-{role}.{ext}", "runCommand": "{e.g., 'bun test .design/specs/spec-api.test.ts'}", "properties": ["brief descriptions"]}`

**Spec content**: Test WHAT (external behavior), not HOW (implementation). Include positive AND negative cases. Use property-based testing where possible. Test cross-role contracts. Specs must be independently runnable.

**Finalization**: `python3 $PLAN_CLI finalize .design/plan.json` validates structure, computes overlaps, computes SHA256 checksums for spec files (tamper detection).

### 5. Auxiliary Roles

Add to `auxiliaryRoles[]` in plan.json. Challenger always runs. Regression-checker and integration-verifier always run post-execution.

| Name | Type | Goal | Model | Trigger |
|---|---|---|---|---|
| challenger | pre-execution | Review improvement plan. Challenge: Could any proposed change cause behavioral regression? Are hypotheses testable? Are token budget claims accurate? Does any improvement reverse a previous one? | sonnet | before-execution |
| regression-checker | post-execution | Verify: YAML frontmatter parses correctly, SKILL.md internal references are valid, CLAUDE.md accurately describes the skill, script symlinks resolve, no broken cross-references. Compare improved skill against .design/skill-snapshot.md — verify no unintended removals of constraints or error handling. | sonnet | after-all-roles-complete |
| integration-verifier | post-execution | Verify SKILL.md references correct plan.py commands, CLAUDE.md matches SKILL.md, README.md matches CLAUDE.md. Run all acceptance criteria checks from plan.json. | sonnet | after-all-roles-complete |
| memory-curator | post-execution | Distill improvement learnings: what dimensions were weakest, which hypotheses were confirmed/rejected, what improvement patterns worked. Apply five quality gates before storing. | haiku | after-all-roles-complete |

### 6. Complete

1. Validate: `python3 $PLAN_CLI status .design/plan.json`. Stop if `ok: false`.
2. If team was created: shut down teammates, `TeamDelete(team_name: $TEAM_NAME)`.
3. Clean up TaskList (delete all analysis tasks so `/do:execute` starts clean).
4. Summary: `python3 $PLAN_CLI summary .design/plan.json`. Display a rich end-of-run summary:

```
Improvement Plan: {goal}
Target: {skill-path}
Baseline: .design/skill-snapshot.md

Quality Scores:
  {dimension}: {score}/5 {delta if previous scores available}
  ...

Improvements ({roleCount} roles):
- Role 0: {name} — {hypothesis summary} [impact: {high/medium/low}]
- Role 1: {name} — {hypothesis summary} [impact: {high/medium/low}]

Evidence: {percentage historical vs simulated}
Regression risks: {any flagged dimensions}
Auxiliary: {auxiliaryRoles}
Memories applied: {count or "none"}

Run /do:execute to apply improvements.
```

5. **Self-reflection** — Evaluate this improve run:

   ```bash
   echo '{"targetSkill":"<skill-path>","analysisMode":"<general|targeted>","expertCount":N,"qualityScores":{"dimension":N},"findingsCount":N,"rolesProduced":N,"whatWorked":["<item>"],"whatFailed":["<item>"],"doNextTime":["<item>"]}' | python3 $PLAN_CLI reflection-add .design/reflection.jsonl --skill improve --goal "<the improvement goal>" --outcome "<completed|partial|failed|aborted>" --goal-achieved <true|false>
   python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event skill-complete --skill improve || true
   ```

   On failure: proceed (not blocking).

**Fallback** (if finalize fails):
1. Read the error message from plan.py output (contains field name and issue)
2. If error is in `roles[]`: edit the failing role brief in plan.json directly, re-run finalize (max 2 retries)
3. If error is in top-level fields (`expertArtifacts`, `designDecisions`): fix the field structure, re-run finalize (max 2 retries)
4. If finalize fails after 2 retries: report to user with error details and ask whether to rebuild from expert findings or abort

---

## Contracts

### plan.json (schemaVersion 4)

Improve produces plan.json in the same format as design — fully compatible with `/do:execute`. See CLAUDE.md for full schema documentation.

### Improve-Specific Artifacts

Produced by the analysis phase, preserved in `.design/` for execute workers:
- `skill-snapshot.md` — baseline copy of target SKILL.md at analysis time
- `expert-{name}.json` — per-expert analysis findings (structured JSON)
- `cross-review.json` — reconciliation audit trail (if general/cross-skill mode)

### Historical Evidence

When `.design/history/` contains artifacts from past runs (especially `handoff.md`, `plan.json`, `integration-verifier-report.json`), these serve as execution evidence — higher confidence than behavioral simulation for diagnosing issues.

**Goal**: $ARGUMENTS
