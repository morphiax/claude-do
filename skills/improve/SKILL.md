---
name: improve
description: "Analyze and improve Claude Code skills with scientific methodology."
argument-hint: "<skill-path> [focus-area]"
---

# Improve

Analyze a Claude Code skill and produce `.design/plan.json` with improvement roles — testable hypotheses for targeted changes. **This skill only analyzes and plans — it does NOT write source files.**

**PROTOCOL REQUIREMENT: Your FIRST action MUST be the pre-flight check. Follow the Flow step-by-step.**

**Do NOT use `EnterPlanMode`** — this skill IS the plan.

**Lead boundaries**: Use only `TeamCreate`, `TeamDelete`, `TaskCreate`, `TaskUpdate`, `TaskList`, `SendMessage`, `Task`, `AskUserQuestion`, and `Bash` (cleanup, verification, `python3 $PLAN_CLI` only). Project metadata (CLAUDE.md, package.json, README) allowed. Application source code prohibited — experts read source files. The lead orchestrates — agents think.

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

Scoring rubric (per dimension):
- **5**: Exemplary — no gaps, could serve as a reference implementation
- **4**: Strong — minor improvements possible, no behavioral risk
- **3**: Adequate — works but has identifiable gaps or ambiguities
- **2**: Weak — likely to cause agent deviation or failure in some scenarios
- **1**: Missing/broken — dimension not addressed or fundamentally flawed

---

## Clarification Protocol

| ASK (`AskUserQuestion`) when | SKIP when |
|---|---|
| Skill path is ambiguous or doesn't exist | Path resolves to a valid SKILL.md |
| Focus area conflicts with skill's purpose | Focus area is clear or omitted (general analysis) |
| Multiple valid improvement strategies exist | Standard quality analysis applies |

### Script Setup

Resolve the plugin root directory (containing `.claude-plugin/` and `skills/`). Set:

```
PLAN_CLI = {plugin_root}/skills/improve/scripts/plan.py
```

All script calls: `python3 $PLAN_CLI <command> [args]` via Bash. Output is JSON with `{"ok": true/false, ...}`.

---

## Flow

### 1. Pre-flight

1. **Parse arguments**: Extract `<skill-path>` and optional `[focus-area]` from `$ARGUMENTS`.
   - If `skill-path` is a name (e.g., `design`), resolve to `skills/{name}/SKILL.md`.
   - If no path provided, ask user which skill to analyze.
2. **Validate target**: Confirm the SKILL.md file exists via Bash (`test -f {skill-path}`). If not found, report and stop.
3. **Snapshot**: Copy target SKILL.md to `.design/skill-snapshot.md` via Bash. This is the baseline for regression comparison.
4. **Circular improvement detection**: Check `.design/history/` for recent improve runs targeting the same skill:
   ```bash
   ls .design/history/*/skill-snapshot.md 2>/dev/null | head -5
   ```
   If found, warn user: "Previous improvement runs detected. Review history to avoid circular changes."
5. **Check existing plan**: `python3 $PLAN_CLI status .design/plan.json`. If `ok` and `isResume`: ask user "Existing plan found. Overwrite?" If declined, stop.
6. **Archive stale artifacts**:
   ```bash
   mkdir -p .design/history
   if [ "$(find .design -mindepth 1 -maxdepth 1 ! -name history | head -1)" ]; then
     ARCHIVE_DIR=".design/history/$(date -u +%Y%m%dT%H%M%SZ)"
     mkdir -p "$ARCHIVE_DIR"
     find .design -mindepth 1 -maxdepth 1 ! -name history ! -name memory.jsonl ! -name reflection.jsonl ! -name handoff.md -exec mv {} "$ARCHIVE_DIR/" \;
   fi
   ```
7. **Re-snapshot** (archive may have moved it): Copy target SKILL.md to `.design/skill-snapshot.md` again.

### 2. Lead Research

The lead assesses the target skill and determines the analysis approach.

1. Read project metadata (CLAUDE.md) via Bash to understand the plugin architecture.
2. **Determine analysis mode**:

| Mode | Trigger | Team | Experts |
|---|---|---|---|
| **Targeted** | Focus area provided (e.g., "reduce cross-review verbosity") | No team — single Task agent | 1 specialist |
| **General** | No focus area — full quality analysis | Team `do-improve` | 2-3 experts |
| **Cross-skill** | Path is `--all` or multiple paths | Team `do-improve` | 2-3 experts + cross-review |

3. **Memory injection**: Run `python3 $PLAN_CLI memory-search .design/memory.jsonl --goal "improve {skill-name}" --stack "SKILL.md prompt engineering"`. If memories exist, inject top 3-5 into expert prompts.
4. **Historical evidence**: Check for past execution artifacts:
   ```bash
   ls .design/history/*/handoff.md 2>/dev/null | head -5
   ```
   If found, note paths for experts — execution evidence is higher-confidence than behavioral simulation.
5. Report the planned analysis approach and expert composition to the user.

### 3. Analyze Skill

#### Targeted Mode (single Task agent)

Spawn a single analyst via `Task(subagent_type: "general-purpose")`:

Prompt includes:
- "Analyze `.design/skill-snapshot.md` for this specific improvement area: {focus-area}."
- "Read the actual skill at `{skill-path}` and the project architecture in `CLAUDE.md`."
- "Score the relevant quality dimensions (1-5) using the rubric from this protocol."
- If historical evidence exists: "Read past execution artifacts at {paths} for evidence of actual behavior."
- If no historical evidence: "Perform behavioral simulation: trace through 2 representative scenarios step-by-step. Flag where agent behavior might diverge from intent. **Note: this is lower-confidence than execution evidence.**"
- "For each finding, form a **testable hypothesis**: what to change, predicted behavioral impact, and how to verify."
- "Save findings to `.design/expert-analyst.json` with structure: `{\"skillPath\": \"...\", \"focusArea\": \"...\", \"qualityScores\": {\"dimension\": {\"score\": N, \"evidence\": \"...\"}}, \"findings\": [{\"location\": \"section/line\", \"issue\": \"...\", \"severity\": \"high|medium|low\", \"hypothesis\": {\"change\": \"...\", \"predictedEffect\": \"...\", \"verification\": \"...\"}}], \"tokenAnalysis\": {\"totalLines\": N, \"heaviestSections\": [...]}, \"summary\": \"...\"}`. Return a summary."

Proceed directly to Step 4 (Synthesize) after receiving the analyst's report.

#### General/Cross-skill Mode (team-based)

1. `TeamDelete(team_name: "do-improve")` (ignore errors), `TeamCreate(team_name: "do-improve")`. If TeamCreate fails, tell user Agent Teams is required and stop.
2. Spawn experts in parallel as teammates using the Task tool with `team_name: "do-improve"`:

**Protocol Analyst** — evaluates clarity, completeness, flow gaps:
- "Read `.design/skill-snapshot.md`. Score Protocol Clarity, Error Handling, and Verifiability (1-5 each with evidence)."
- "Trace through 2 representative execution scenarios. Identify ambiguous steps, missing error paths, unverifiable outcomes."
- "Save findings to `.design/expert-protocol-analyst.json`. Then SendMessage to lead with summary."

**Prompt Engineer** — evaluates instruction density, constraint enforcement, economy:
- "Read `.design/skill-snapshot.md`. Score Constraint Enforcement, Prompt Economy, and Information Flow (1-5 each with evidence)."
- "Identify prompt bloat (sections that can be compressed without behavioral loss), dead rules (constraints that can never trigger), and missing constraints (behaviors that should be governed but aren't)."
- "Save findings to `.design/expert-prompt-engineer.json`. Then SendMessage to lead with summary."

**Coordination Analyst** (only for skills with multi-agent patterns) — evaluates agent coordination:
- "Read `.design/skill-snapshot.md`. Score Agent Coordination (1-5 with evidence)."
- "Analyze team lifecycle, message patterns, shared state management. Identify race conditions, deadlock risks, information silos."
- "Save findings to `.design/expert-coordination-analyst.json`. Then SendMessage to lead with summary."

Every expert prompt MUST end with: "Save your complete findings to `.design/expert-{name}.json` as structured JSON. Then SendMessage to the lead with a summary." Include past learnings and historical evidence paths if available.

3. After all experts report back, verify artifacts exist: `ls .design/expert-*.json`. If any expert failed to save its artifact, send it a message to save. **Never write an expert artifact yourself.**

#### Cross-Review (General/Cross-skill mode only, >=2 experts)

When >=2 experts analyzed the same skill from different angles, perspective reconciliation is mandatory.

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
4. **Anti-pattern guards** before building roles:
   - **Token budget**: Calculate net token delta for each proposed change. Flag if total would increase skill beyond 500 lines.
   - **Circular improvement**: If `.design/history/` contains a previous improve run, check whether any proposed change reverses a previous improvement. If so, flag for user review.
   - **Regression safety**: No quality dimension may degrade. If a change improves one dimension but risks another, note the trade-off explicitly.
5. **Build roles**: For each approved improvement (or group of related improvements), create a role:
   - `goal`: The testable hypothesis — what to change and predicted behavioral effect
   - `scope.directories/patterns`: The skill file(s) to modify
   - `constraints`: Must preserve YAML frontmatter, must not break plan.json contract, must not exceed token budget, must not regress other dimensions
   - `acceptanceCriteria`: Concrete checks that verify the improvement (e.g., line count checks, structural pattern checks, dimension-specific verification)
   - `expertContext`: References to the analyst artifacts with relevance notes
   - `assumptions`, `rollbackTriggers`, `fallback` as appropriate
6. If improvements require updating CLAUDE.md or README.md to stay in sync (per pre-commit checklist), add a `docs-updater` role.
7. Write `.design/plan.json` with:
   - `schemaVersion: 4`
   - `goal`: "Improve {skill-name}: {summary of improvements}"
   - `context.stack`: "Claude Code plugin, SKILL.md prompt engineering"
   - `expertArtifacts[]`: References to all analyst artifacts
   - `designDecisions[]`: Resolved conflicts from cross-review
   - `roles[]`: Improvement roles
   - `auxiliaryRoles[]`: challenger (pre-execution), integration-verifier (post-execution), regression-checker (post-execution), memory-curator (post-execution)
8. Run `python3 $PLAN_CLI finalize .design/plan.json` to validate structure and compute overlaps.

### 5. Auxiliary Roles

Add to `auxiliaryRoles[]` in plan.json. Challenger always runs. Regression-checker and integration-verifier always run post-execution.

#### Challenger (pre-execution)
Reviews the improvement plan. Questions whether proposed changes could cause behavioral regression.

```json
{
  "name": "challenger",
  "type": "pre-execution",
  "goal": "Review improvement plan. Challenge: Could any proposed change cause behavioral regression? Are hypotheses testable? Are token budget claims accurate? Does any improvement reverse a previous one?",
  "model": "sonnet",
  "trigger": "before-execution"
}
```

#### Regression Checker (post-execution)
Verifies the improved skill is structurally sound and consistent with the rest of the plugin.

```json
{
  "name": "regression-checker",
  "type": "post-execution",
  "goal": "Verify: YAML frontmatter parses correctly, SKILL.md internal references are valid, CLAUDE.md accurately describes the skill, script symlinks resolve, no broken cross-references. Compare improved skill against .design/skill-snapshot.md — verify no unintended removals of constraints or error handling.",
  "model": "sonnet",
  "trigger": "after-all-roles-complete"
}
```

#### Integration Verifier (post-execution)
Checks cross-file consistency after improvements are applied.

```json
{
  "name": "integration-verifier",
  "type": "post-execution",
  "goal": "Verify SKILL.md references correct plan.py commands, CLAUDE.md matches SKILL.md, README.md matches CLAUDE.md. Run all acceptance criteria checks from plan.json.",
  "model": "sonnet",
  "trigger": "after-all-roles-complete"
}
```

#### Memory Curator (post-execution)
Distills improvement learnings into `.design/memory.jsonl`.

```json
{
  "name": "memory-curator",
  "type": "post-execution",
  "goal": "Distill improvement learnings: what dimensions were weakest, which hypotheses were confirmed/rejected, what improvement patterns worked. Apply five quality gates before storing.",
  "model": "haiku",
  "trigger": "after-all-roles-complete"
}
```

### 6. Complete

1. Validate: `python3 $PLAN_CLI status .design/plan.json`. Stop if `ok: false`.
2. If team was created: shut down teammates, `TeamDelete(team_name: "do-improve")`.
3. Clean up TaskList (delete all analysis tasks so `/do:execute` starts clean).
4. Summary: `python3 $PLAN_CLI summary .design/plan.json`. Display:

```
Improvement Plan: {goal}
Target: {skill-path}
Baseline: .design/skill-snapshot.md
Roles: {roleCount}
Quality Scores: {dimension}: {score}/5, ...

Improvements:
- Role 0: {name} — {hypothesis summary}
- Role 1: {name} — {hypothesis summary}

Auxiliary: {auxiliaryRoles}

Run /do:execute to apply improvements.
```

5. **Self-reflection** — Evaluate this improve run:

   ```bash
   echo '{"targetSkill":"<skill-path>","analysisMode":"<general|targeted>","expertCount":N,"qualityScores":{"dimension":N},"findingsCount":N,"rolesProduced":N,"whatWorked":["<item>"],"whatFailed":["<item>"],"doNextTime":["<item>"]}' | \
     python3 $PLAN_CLI reflection-add .design/reflection.jsonl \
       --skill improve \
       --goal "<the improvement goal>" \
       --outcome "<completed|partial|failed|aborted>" \
       --goal-achieved <true|false>
   ```

   On failure: proceed (reflection is valuable but not blocking).

**Fallback** (if finalize fails):
1. Fix validation errors and re-run finalize.
2. If structure is fundamentally broken: rebuild plan from expert findings, one role at a time.

---

## Contracts

### plan.json (schemaVersion 4)

Improve produces plan.json in the same format as design — fully compatible with `/do:execute`.

**Top-level fields**: schemaVersion (4), goal, context {stack, conventions, testCommand, buildCommand, lsp}, expertArtifacts [{name, path, summary}], designDecisions [], roles[], auxiliaryRoles[], progress {completedRoles: []}

**Role fields**: name, goal, model, scope {directories, patterns, dependencies}, expertContext [{expert, artifact, relevance}], constraints [], acceptanceCriteria [{criterion, check}], assumptions [{text, severity}], rollbackTriggers [], fallback

**Status fields** (initialized by finalize): status ("pending"), result (null), attempts (0), directoryOverlaps (computed)

### Improve-Specific Artifacts

Produced by the analysis phase, preserved in `.design/` for execute workers:
- `skill-snapshot.md` — baseline copy of target SKILL.md at analysis time
- `expert-{name}.json` — per-expert analysis findings (structured JSON)
- `cross-review.json` — reconciliation audit trail (if general/cross-skill mode)

### Historical Evidence

When `.design/history/` contains artifacts from past runs (especially `handoff.md`, `plan.json`, `integration-verifier-report.json`), these serve as execution evidence — higher confidence than behavioral simulation for diagnosing issues.

**Goal**: $ARGUMENTS
