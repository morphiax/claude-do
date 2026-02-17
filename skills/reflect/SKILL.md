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

**Announce to user**: "Analyzing {count} reflections{skill filter if any}. Running direct analysis."

Perform analysis directly via Bash commands — no Task agent. This eliminates hallucination risk from agents that may fail to read files.

#### 2a. Gather data

1. **Reflections** (already loaded in Step 1.3):
   ```bash
   python3 $PLAN_CLI reflection-search .design/reflection.jsonl --skill {filter} --limit 20
   ```
   Store the JSON output as `$REFLECTIONS`.

2. **Existing memories** (already loaded in Step 1.6):
   Use the memory-search output from pre-flight. Store as `$MEMORIES`.

3. **Handoff context** (if exists):
   ```bash
   test -f .design/handoff.md && cat .design/handoff.md
   ```

#### 2b. Compute analysis metrics

Run a single `python3 -c` script via Bash that reads the reflection-search JSON output and computes all analysis metrics. Pass `$REFLECTIONS` via stdin or as a file argument. Also reads `$MEMORIES` (from Step 1.6) to cross-reference resolution records.

```bash
python3 -c "
import json, sys, collections

reflections = json.loads('''$REFLECTIONS''')['entries']
memories = json.loads('''$MEMORIES''').get('memories', []) if '''$MEMORIES''' and '''$MEMORIES''' != 'null' else []
N = len(reflections)

# 1. Goal achievement by skill
by_skill = collections.defaultdict(lambda: {'total':0,'achieved':0})
for r in reflections:
    s = r.get('skill','unknown')
    by_skill[s]['total'] += 1
    if r.get('goalAchieved'): by_skill[s]['achieved'] += 1
overall = sum(v['achieved'] for v in by_skill.values()) / max(N,1)
achievement = {s: v['achieved']/max(v['total'],1) for s,v in by_skill.items()}

# 2. Recurring failures (items in whatFailed appearing >=2 times) with temporal resolution
fail_counts = collections.Counter()
fail_skills = collections.defaultdict(set)
fail_ids = collections.defaultdict(list)
fail_timestamps = collections.defaultdict(list)
for r in reflections:
    ev = r.get('evaluation',{})
    ts = r.get('timestamp', 0)
    for item in ev.get('whatFailed',[]):
        fail_counts[item] += 1
        fail_skills[item].add(r.get('skill','unknown'))
        fail_ids[item].append(r.get('id',''))
        fail_timestamps[item].append(ts)

# Temporal resolution: classify patterns by recency (most recent 3 runs)
recent_window = 3
recurring = []
for p, c in fail_counts.items():
    if c < 2:
        continue
    # Sort timestamps for this pattern (most recent last)
    sorted_ts = sorted(fail_timestamps[p])
    # Check if pattern appears in most recent 3 runs
    most_recent_runs = sorted([r.get('timestamp',0) for r in reflections])[-recent_window:]
    in_recent = any(ts in most_recent_runs for ts in sorted_ts[-recent_window:])

    resolution_status = 'active' if in_recent else 'likely_resolved'

    # Cross-reference memory.jsonl for resolution records (category: procedure)
    # Check if any memory documents a fix for this pattern
    memory_match = False
    for m in memories:
        if m.get('category') == 'procedure':
            # Simple keyword matching: if pattern keywords appear in memory content
            pattern_lower = p.lower()
            content_lower = m.get('content', '').lower()
            # Check for resolution indicators and pattern match
            if any(kw in content_lower for kw in ['fix', 'resolve', 'solution', 'prevent']) and \
               any(word in content_lower for word in pattern_lower.split()[:3]):
                memory_match = True
                break

    if memory_match and not in_recent:
        resolution_status = 'confirmed_resolved'

    recurring.append({
        'pattern': p,
        'skill': list(fail_skills[p]),
        'occurrences': c,
        'reflectionIds': fail_ids[p],
        'resolutionStatus': resolution_status,
        'lastSeen': max(sorted_ts) if sorted_ts else 0
    })

# 3. Unaddressed feedback (doNextTime items that recur in later whatFailed)
all_do = set()
all_fail = set()
for r in reflections:
    ev = r.get('evaluation',{})
    all_do.update(ev.get('doNextTime',[]))
    all_fail.update(ev.get('whatFailed',[]))
unaddressed = [{'item':d,'stillRecurring':True} for d in all_do if d in all_fail]

# 4. Trend (compare first half vs second half goal achievement)
half = N // 2
first = reflections[:half] if half > 0 else []
second = reflections[half:] if half > 0 else reflections
r1 = sum(1 for r in first if r.get('goalAchieved')) / max(len(first),1)
r2 = sum(1 for r in second if r.get('goalAchieved')) / max(len(second),1)
trend = 'improving' if r2 > r1 + 0.1 else ('degrading' if r1 > r2 + 0.1 else 'stable')

result = {
    'reflectionsAnalyzed': N,
    'goalAchievementRate': {'overall': round(overall,2), 'bySkill': {s:round(v,2) for s,v in achievement.items()}},
    'recurringFailures': recurring,
    'unaddressedFeedback': unaddressed,
    'trends': {'overall': trend, 'bySkill': {s: 'stable' for s in achievement}},
}
json.dump(result, sys.stdout, indent=2)
"
```

Store the output as `$METRICS`.

#### 2c. Generate hypotheses

For each recurring failure pattern in `$METRICS`, the lead formulates improvement hypotheses. This is the lead's analytical work — use the recurring failures, unaddressed feedback, and trends to identify root causes and propose changes.

**Temporal resolution guidance**: Only generate hypotheses for patterns with `resolutionStatus: 'active'`. Skip patterns marked `'likely_resolved'` or `'confirmed_resolved'` unless there's strong evidence of regression (pattern was absent, then reappeared).

For each active recurring failure, determine:
- `skillFile`: which SKILL.md likely governs the behavior (map skill name to `skills/{skill}/SKILL.md`)
- `section`: which section/step to change (infer from the failure pattern description)
- `currentBehavior`: what the instruction currently produces (from reflection evidence)
- `proposedChange`: what to change and why
- `predictedEffect`: what should improve (be specific and testable)
- `evidence`: which reflection entry IDs support this
- `confidence`: high (>=3 reflections show pattern) | medium (2 reflections) | low (1 strong signal)

#### 2d. Write analyst artifact

Write the complete analysis to `.design/expert-reflection-analyst.json` via Bash (`python3 -c` or `cat > file`):

```bash
python3 -c "
import json
metrics = json.loads('''$METRICS''')
hypotheses = [...]  # constructed by lead from analysis above
metrics['hypotheses'] = hypotheses
metrics['summary'] = '...'
metrics['skillFilter'] = '{filter or all}'
with open('.design/expert-reflection-analyst.json', 'w') as f:
    json.dump(metrics, f, indent=2)
print(json.dumps({'ok': True}))
"
```

Verify the artifact was created: `ls .design/expert-reflection-analyst.json`. If missing, re-run the write command. If still missing after retry, abort with clear error to user.

### 3. Synthesize into Improvement Plan

After Step 2 completes:

1. **Verify artifact**: `ls .design/expert-reflection-analyst.json`. If missing, the write in Step 2d failed — re-run it. If still missing after retry, abort with clear error to user: "Analysis artifact missing after retry. Cannot proceed."
2. Read the analyst's findings (already in `$METRICS` + hypotheses from Step 2c-2d).
3. **Prioritize hypotheses**: Rank by `confidence * severity`. High-confidence, high-severity patterns first.
4. Present top findings to user:

```
Reflection Analysis ({N} runs analyzed):
- Goal achievement: {X}% overall ({bySkill breakdown})
- Recurring failures: {count} patterns ({count_active} active, {count_resolved} likely/confirmed resolved)
- Unaddressed feedback: {count} items still recurring
- Trend: {overall trend}

Top improvement hypotheses (active patterns only):
1. [{confidence}] {skill}: {proposedChange} — evidence from {N} runs
2. [{confidence}] {skill}: {proposedChange} — evidence from {N} runs
...

Resolved patterns (not addressed):
- {pattern} — last seen {timestamp}, {resolution_status}
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
