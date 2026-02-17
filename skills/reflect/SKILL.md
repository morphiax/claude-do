---
name: reflect
description: "Analyze execution reflections to improve skill effectiveness based on real outcomes."
argument-hint: "[skill-filter] [--min-runs N]"
---

# Reflect

Analyze `.design/reflection.jsonl` to identify what's actually working and what isn't across runs, then produce `.design/plan.json` with evidence-based improvements. Unlike `/do:improve` (which analyzes prompt quality statically), this skill uses **execution outcomes** as the optimization signal.

**PROTOCOL REQUIREMENT: Your FIRST action MUST be the pre-flight check. Follow the Flow step-by-step.**

**Do NOT use `EnterPlanMode`** — this skill IS the plan.

**Lead boundaries**: Use only `TaskCreate`, `TaskUpdate`, `TaskList`, `Task`, `AskUserQuestion`, and `Bash` (for `python3 $PLAN_CLI`, cleanup, verification). Project metadata (CLAUDE.md, package.json, README) allowed via Bash. **Never use Read, Grep, Glob, Edit, Write, LSP, WebFetch, WebSearch, or MCP tools on project source files.** The lead orchestrates — agents think.

**No polling**: Messages auto-deliver. Never use sleep, loops, or Bash waits.

**Output contract**: Reflect ALWAYS produces `.design/plan.json` (schemaVersion 4) for `/do:execute`. Reflect never writes skill source files directly.

---

## What This Skill Optimizes

| Signal | Source | What it reveals |
|---|---|---|
| Goal achievement rate | `goalAchieved` field | Are skills producing results that match intent? |
| Recurring failures | `whatFailed` across runs | Systematic issues vs one-off problems |
| Unaddressed feedback | `doNextTime` items | Improvement opportunities that were identified but never acted on |
| Coordination patterns | `coordinationNotes` | Team/worker issues that recur |
| Outcome trends | `outcome` over time | Getting better or worse? |

---

## Clarification Protocol

| ASK (`AskUserQuestion`) when | SKIP when |
|---|---|
| No reflection.jsonl exists or has <2 entries | Sufficient data exists |
| Skill filter ambiguous | Filter is clear or omitted |
| Multiple conflicting patterns with equal evidence | Clear priority exists |

### Script Setup

Resolve the plugin root directory (containing `.claude-plugin/` and `skills/`). Set:

```
PLAN_CLI = {plugin_root}/skills/reflect/scripts/plan.py
```

All script calls: `python3 $PLAN_CLI <command> [args]` via Bash. Output is JSON with `{"ok": true/false, ...}`.

---

## Flow

### 1. Pre-flight

1. **Lifecycle context**: Run `python3 $PLAN_CLI plan-health-summary .design` and display to user: "Previous session: {handoff summary}. Recent runs: {reflection summaries}. {plan status}." Skip if all fields empty.
2. **Parse arguments**: Extract optional `[skill-filter]` (design|execute|improve) and `[--min-runs N]` (default 2).
3. **Load reflections**:
   ```bash
   python3 $PLAN_CLI reflection-search .design/reflection.jsonl --skill {filter} --limit 20
   ```
   If fewer than `min-runs` entries exist, tell user: "Need at least {min-runs} reflections to identify patterns. Run more design/execute cycles first." Stop.
4. **Check existing plan**: `python3 $PLAN_CLI status .design/plan.json`. If `ok` and `isResume`: ask user "Existing plan found. Overwrite?" If declined, stop.
5. **Archive stale artifacts**: `python3 $PLAN_CLI archive .design`
6. **Memory injection**: Run `python3 $PLAN_CLI memory-search .design/memory.jsonl --goal "reflect on skill performance" --keywords "failure,pattern,improvement"`. If `ok: false` or no memories → proceed without injection. Otherwise inject top 3-5 into analyst prompt. **Show user**: "Memory: injecting {count} past learnings — {keyword summaries}."

### 2. Pattern Analysis

**Announce to user**: "Analyzing {count} reflections{skill filter if any}. Spawning analyst."

Spawn a single analyst via `Task(subagent_type: "general-purpose")`:

**Analyst prompt** includes:

- "Read `.design/reflection.jsonl` — each line is a JSON object with: `skill`, `goal`, `outcome`, `goalAchieved`, `evaluation` (containing `whatWorked`, `whatFailed`, `doNextTime`, and skill-specific fields), `timestamp`."
- "Read `.design/memory.jsonl` (if exists) — cross-reference with existing learnings to avoid duplicate findings."
- "Read the SKILL.md files for the relevant skills: `skills/design/SKILL.md`, `skills/execute/SKILL.md`, `skills/improve/SKILL.md`. Understand what each skill is supposed to do."
- If `handoff.md` exists: "Read `.design/handoff.md` for additional context from the most recent run."

**Analysis tasks** (structured output required):

1. **Goal achievement**: What percentage of runs achieved their goal? Break down by skill.
2. **Recurring failures**: Group `whatFailed` items across runs. Items appearing in >=2 runs are patterns, not incidents. For each pattern: which skill, what fails, how often, severity.
3. **Unaddressed feedback**: Compare `doNextTime` items against subsequent reflections. Did the improvement happen? Flag items that appear in `doNextTime` but recur in later `whatFailed`.
4. **Trend analysis**: Are outcomes improving or degrading over time? Any skill getting worse?
5. **Root cause mapping**: For each recurring failure pattern, trace to the specific SKILL.md section that governs that behavior. Quote the relevant instruction. Explain why the current instruction produces the observed failure.
6. **Improvement hypotheses**: For each root cause, propose a specific change to the SKILL.md with:
   - `skillFile`: which SKILL.md to modify
   - `section`: which section/step to change
   - `currentBehavior`: what the instruction currently produces (from reflection evidence)
   - `proposedChange`: what to change and why
   - `predictedEffect`: what should improve (be specific and testable)
   - `evidence`: which reflection entries support this (by ID or timestamp)
   - `confidence`: high (>=3 reflections show pattern) | medium (2 reflections) | low (1 reflection but strong signal)

"Save findings to `.design/expert-reflection-analyst.json` with structure:
```json
{
  "reflectionsAnalyzed": N,
  "skillFilter": "all|design|execute|improve",
  "goalAchievementRate": {"overall": 0.X, "bySkill": {"design": 0.X, ...}},
  "recurringFailures": [{"pattern": "...", "skill": "...", "occurrences": N, "severity": "high|medium|low", "reflectionIds": ["..."]}],
  "unaddressedFeedback": [{"item": "...", "firstSeen": "timestamp", "stillRecurring": true}],
  "trends": {"overall": "improving|stable|degrading", "bySkill": {}},
  "hypotheses": [{"skillFile": "...", "section": "...", "currentBehavior": "...", "proposedChange": "...", "predictedEffect": "...", "evidence": ["..."], "confidence": "high|medium|low"}],
  "summary": "..."
}
```
Return a summary."

### 3. Synthesize into Improvement Plan

After the analyst reports:

1. **Verify artifact**: `ls .design/expert-reflection-analyst.json`. If missing, retry Task once with the same prompt. If still missing after retry, abort with clear error message to user: "Analyst failed to produce findings after retry. Cannot proceed."
2. Read the analyst's findings.
3. **Prioritize hypotheses**: Rank by `confidence * severity`. High-confidence, high-severity patterns first.
4. Present top findings to user:

```
Reflection Analysis ({N} runs analyzed):
- Goal achievement: {X}% overall ({bySkill breakdown})
- Recurring failures: {count} patterns identified
- Unaddressed feedback: {count} items still recurring
- Trend: {overall trend}

Top improvement hypotheses:
1. [{confidence}] {skill}: {proposedChange} — evidence from {N} runs
2. [{confidence}] {skill}: {proposedChange} — evidence from {N} runs
...
```

5. Ask user: "Which improvements should I include in the plan?" (options: All, Top N, Let me choose)
6. **Build roles**: For each approved improvement, create a role:
   - `goal`: The hypothesis — what to change, why (citing reflection evidence), predicted effect
   - `scope.directories/patterns`: The skill file(s) to modify
   - `constraints`: Must preserve YAML frontmatter, must not break plan.json contract, must not regress other skills
   - `acceptanceCriteria`: Checks that verify the change was made correctly. Include at least one functional check beyond grep. For SKILL.md changes: verify finalize still validates (`python3 $PLAN_CLI finalize`), verify YAML frontmatter parses (`python3 -c "import yaml; ..."`), verify referenced plan.py commands exist (`python3 $PLAN_CLI <command> --help`), verify behavioral change took effect. **Anti-patterns to avoid**: `grep -q "text"` alone, `wc -l` counts, `test -f` existence checks, `cmd || echo` fallbacks.
   - `expertContext`: Reference to the analyst artifact with specific hypothesis
   - `assumptions`, `rollbackTriggers`, `fallback` as appropriate
7. If improvements touch multiple skills, add a `docs-updater` role to sync CLAUDE.md and README.md.
8. Write `.design/plan.json` with:
   - `schemaVersion: 4`
   - `goal`: "Reflect: {summary of improvements based on {N} run reflections}"
   - `context.stack`: "Claude Code plugin, SKILL.md prompt engineering"
   - `expertArtifacts[]`: Reference to analyst artifact
   - `roles[]`: Improvement roles
   - `auxiliaryRoles[]`: challenger (pre-execution), regression-checker (post-execution), integration-verifier (post-execution), memory-curator (post-execution)
9. Run `python3 $PLAN_CLI finalize .design/plan.json` to validate.

### 4. Auxiliary Roles

Add to `auxiliaryRoles[]`. Challenger always runs. Regression-checker and integration-verifier always run post-execution.

```json
[
  {
    "name": "challenger",
    "type": "pre-execution",
    "goal": "Review improvement plan. Challenge: Is the evidence strong enough? Could changes cause regression in other skills? Are the reflection patterns genuine or coincidental?",
    "model": "sonnet",
    "trigger": "before-execution"
  },
  {
    "name": "regression-checker",
    "type": "post-execution",
    "goal": "Verify: YAML frontmatter intact, SKILL.md internal references valid, CLAUDE.md matches changed skills, script symlinks resolve. Compare against skill files before changes.",
    "model": "sonnet",
    "trigger": "after-all-roles-complete"
  },
  {
    "name": "integration-verifier",
    "type": "post-execution",
    "goal": "Verify all three skills (design, execute, improve) still reference correct plan.py commands. Run finalize to confirm script works. Check cross-skill consistency.",
    "model": "sonnet",
    "trigger": "after-all-roles-complete"
  },
  {
    "name": "memory-curator",
    "type": "post-execution",
    "goal": "Distill what reflection-based improvements were made, which hypotheses were acted on, what evidence strength was required. Store as patterns for future reflect runs.",
    "model": "haiku",
    "trigger": "after-all-roles-complete"
  }
]
```

### 5. Complete

1. Validate: `python3 $PLAN_CLI status .design/plan.json`. Stop if `ok: false`.
2. Clean up TaskList (delete analysis tasks so `/do:execute` starts clean).
3. Summary: `python3 $PLAN_CLI summary .design/plan.json`. Display a rich end-of-run summary:

```
Reflection Plan: {goal}
Evidence: {N} reflections analyzed ({time span}), {M} patterns found

Achievement trend: {overall trend indicator, e.g., "improving: 60% → 80% over last 5 runs"}
Recurring failures: {count} patterns ({top pattern names})
Unaddressed feedback: {count} items still recurring

Improvements ({roleCount} roles):
- Role 0: {name} — {hypothesis summary} [{confidence}]
- Role 1: {name} — {hypothesis summary} [{confidence}]

Auxiliary: {auxiliaryRoles}
Memories applied: {count or "none"}

Run /do:execute to apply improvements.
```

4. **Self-reflection** — Evaluate this reflect run:

   ```bash
   echo '{"reflectionsAnalyzed":N,"patternsFound":N,"hypothesesGenerated":N,"hypothesesApproved":N,"whatWorked":["<item>"],"whatFailed":["<item>"],"doNextTime":["<item>"]}' | \
     python3 $PLAN_CLI reflection-add .design/reflection.jsonl \
       --skill reflect \
       --goal "<the analysis goal>" \
       --outcome "<completed|partial|failed|aborted>" \
       --goal-achieved <true|false>
   ```

**Fallback** (if finalize fails):
1. Fix validation errors and re-run finalize.
2. If structure is fundamentally broken: rebuild from analyst findings, one role at a time.

---

## Contracts

### plan.json (schemaVersion 4)

Reflect produces plan.json in the same format as design/improve — fully compatible with `/do:execute`. See CLAUDE.md "Data Contract" for full schema.

Reflect-specific conventions:
- `goal` describes improvements citing reflection evidence
- `expertArtifacts[]` references the reflection analyst artifact
- Role `goal` fields include the testable hypothesis with evidence references
- Role `constraints` always include "must not regress other skills"

### Reflect-Specific Artifacts

- `expert-reflection-analyst.json` — structured analysis of reflection patterns, hypotheses with evidence

### Evidence Requirements

| Confidence | Min reflections | Action |
|---|---|---|
| **High** | >=3 showing same pattern | Include by default |
| **Medium** | 2 showing same pattern | Include with note |
| **Low** | 1 strong signal | Ask user before including |

Single-run observations are noted but not acted on unless the signal is unambiguous (e.g., a skill step that consistently produces the wrong output format).

**Arguments**: $ARGUMENTS
