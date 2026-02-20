# Shared Lead Protocol — Core

---

## Lead Boundaries

Use only `TeamCreate`, `TeamDelete`, `TaskCreate`, `TaskUpdate`, `TaskList`, `SendMessage`, `Task`, `AskUserQuestion`, and `Bash` (for `python3 $PLAN_CLI`, cleanup, verification). Project metadata (CLAUDE.md, package.json, README) allowed via Bash. **Never use Read, Grep, Glob, Edit, Write, LSP, WebFetch, WebSearch, or MCP tools on project source files.** The lead orchestrates — agents implement.

---

## No Polling

Messages auto-deliver. Never use `sleep`, loops, or Bash waits. When a teammate sends a message, it appears in your next turn.

---

## Guardrails

**Do NOT answer the goal directly. Your FIRST action after reading the goal MUST be the pre-flight check. Follow the Flow step-by-step.**

**Do NOT use `EnterPlanMode`** — this skill IS the plan.

---

## Script Setup

Resolve plugin root (containing `.claude-plugin/`). All script calls: `python3 $PLAN_CLI <command> [args]` via Bash. JSON output: `{"ok": true/false, ...}`.

```bash
PLAN_CLI={plugin_root}/skills/{skill}/scripts/plan.py
TEAM_NAME=$(python3 $PLAN_CLI team-name {skill} | python3 -c "import sys,json;print(json.load(sys.stdin)['teamName'])")
SESSION_ID=$TEAM_NAME
```

---

## Trace Emission

Emit lifecycle events via `python3 $PLAN_CLI trace-add` (failures are non-blocking — append `|| true`).

**Always include `--payload` with structured context** — empty payloads waste the trace infrastructure. Payloads enable cross-run analysis (step coverage, timing, skip patterns).

| Event | Required | When | Payload |
|-------|----------|------|---------|
| `skill-start` | mandatory | start of every run | `{"roleCount":N,"stepsSkipped":["..."],"isResume":bool}` |
| `skill-complete` | mandatory | end of every run | `{"outcome":"...","rolesCompleted":N,"rolesFailed":N,"retries":N,"auxiliariesRun":["..."],"auxiliariesSkipped":["..."]}` |
| `failure` | mandatory | any agent or role fails | `{"reason":"...","attempt":N,"model":"..."}` |
| `respawn` | mandatory | re-spawning a timed-out or failed agent | `{"attempt":N,"escalatedModel":"...","reason":"..."}` |
| `spawn` | optional | team-based skills only | `{"model":"...","memoriesInjected":N}` |
| `completion` | optional | team-based skills only | `{"acPassed":N,"acTotal":N,"filesChanged":N,"firstAttempt":bool}` |

---

## Memory Injection

```bash
python3 $PLAN_CLI memory-search .design/memory.jsonl --goal "{goal}" --stack "{stack}" [--keywords "{extra terms}"]
```

If `ok: false` or no memories → proceed without injection. Otherwise inject **top 3-5** into agent prompts. **Show user**: "Memory: injecting {count} past learnings — {keyword summaries}."

### Reflection Prepend

When `plan-health-summary` returns `unresolvedImprovements` (non-empty), the lead MUST inject matching items into each agent's spawn prompt. This is not optional — agents that don't receive past lessons repeat past mistakes.

**Procedure** (at agent spawn time, after memory injection):
1. Take the `unresolvedImprovements` list from the `plan-health-summary` output stored during Lifecycle Context.
2. For each agent being spawned, filter items where the item's `text` contains the agent's role name, goal keywords, or scope directory names. Also include all items where `failureClass` matches a pattern relevant to this agent type (e.g., `incorrect-verification` for workers, `spec-disobey` for any agent).
3. If matches found (even 1), prepend to the agent's prompt: "Lessons from prior runs — you MUST apply these:\n{bullet list of matching fix texts}"
4. **Show user**: "Reflection prepend: {agent-name} ← {count} lessons from prior runs."

If `unresolvedImprovements` is empty, skip silently. Memories provide general knowledge; reflection prepend provides specific corrections from recent failures.

---

## Lifecycle Context

Run at skill start (Step 1 of pre-flight), before trace emit:

```bash
python3 $PLAN_CLI plan-health-summary .design
```

Display to user: "Recent runs: {reflection summaries}. {plan status}." If `unresolvedImprovements` is non-empty, also display: "Unresolved from prior runs: {count} items" and list the top 3 (these are concrete prompt fixes or doNextTime items that keep recurring). Skip if all fields empty.

Then emit skill-start trace (with payload per Trace Emission table):
```bash
python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event skill-start --skill {skill} --payload '{"roleCount":N,"stepsSkipped":["..."],"isResume":false}' || true
```

---

## Phase Announcements

Announce each major phase to user for visibility. Minimum: pre-flight, agent spawning, synthesis/execution, completion. Format: brief one-liner stating what's happening next.

---

## INSIGHT Handling

When an agent sends a message prefixed with `INSIGHT:`, display it to the user immediately: "Insight from {agent}: {finding}". Do NOT count INSIGHT messages as completion signals — continue waiting for the full report or artifact. An INSIGHT message is a partial update, not a completion report.

---

## Self-Monitoring

Every skill MUST call `reflection-add` at end of each run. **Purpose: produce data that directly improves SKILL.md prompts.** Generic observations ("worked well", "was useful") are worthless — record only what would change the prompt text.

### Reflection Procedure (mandatory — follow these steps in order)

**Step A — Collect AC gradients** (execute only): During the monitor loop, maintain a session-scoped `acGradients` list. Every time a lead-side AC check exits non-zero, append `{"role": "...", "criterion": "...", "check": "the shell command", "exitCode": N, "stderr": "actual error output"}`. This list feeds Step C.

**Step B — Lamarckian reverse-engineering** (mandatory for every failure or suboptimal outcome): For each failed or retried role, write two things before deriving any prompt fix:
1. `idealOutcome`: "The agent should have produced: {describe the correct output/behavior in one sentence}"
2. `promptFix`: "To get that outcome, change SKILL.md at {section}: {concrete text change}"

Do NOT skip Step 1. The ideal outcome forces specificity — without it, fixes drift into vague advice. If you cannot describe the ideal outcome, the failure is not understood well enough to fix.

**Step C — Lead-side workarounds** (all skills, even on full success): Review any plan.json mutations the lead made during the run — AC check fixes from challenger findings, constraint injections from scout, pre-validation workarounds, nested quoting fixes. For each, write a `promptFix` targeting the *upstream* skill (usually design) to prevent the issue from recurring. Example: if the lead fixed a broken AC check command before spawning workers, the promptFix targets design's Step 5 (AC authoring) to prevent that class of check from being generated.

**Step D — High-value instructions** (all skills): Review which SKILL.md instructions demonstrably drove good outcomes this run. Record these in `highValueInstructions` — an array of `{"instruction": "brief description of what the instruction says", "section": "SKILL.md section", "evidence": "what happened that proves it worked"}`. Purpose: protect these instructions from future simplification. If a `/do:simplify` run targets these files, the simplification analyst will see which instructions have proven impact and avoid removing them.

**Step E — Build reflection JSON**: Assemble the fields below and pipe to `reflection-add`:

```bash
echo '{"promptFixes":[...],"acGradients":[...],"stepsSkipped":[...],"instructionsIgnored":[...],"whatWorked":[...],"whatFailed":[...]}' \
  | python3 $PLAN_CLI reflection-add .design/reflection.jsonl \
    --skill {skill} --goal "<goal>" --outcome "<completed|partial|failed|aborted>" --goal-achieved <true|false>
```

### Reflection Fields

All arrays. Each skill adds skill-specific fields in its SKILL.md.

**`promptFixes`** (PRIMARY — captures both failure-driven fixes AND lead-side workarounds from successful runs):

Each entry MUST have all 5 fields:
- `section` — which SKILL.md section (e.g., "Step 3", "Worker Protocol")
- `problem` — what went wrong
- `idealOutcome` — what the agent should have produced instead (from Step B)
- `fix` — concrete text change to make to get that outcome
- `failureClass` — one of:

| Class | Meaning |
|-------|---------|
| `spec-disobey` | Agent ignored task/role specification |
| `step-repetition` | Agent repeated same step without progress |
| `context-loss` | Agent lost conversation history or prior context |
| `termination-unaware` | Agent didn't know when to stop |
| `ignored-peer-input` | Agent had relevant peer data but didn't use it |
| `task-derailment` | Agent pursued wrong subtask |
| `premature-termination` | Agent stopped before completing all work |
| `incorrect-verification` | Superficial checks passed, substantive failures missed |
| `no-verification` | Agent skipped verification entirely |
| `reasoning-action-mismatch` | Agent stated correct plan but executed differently |

**`acMutations`** (execute only — from Step C): Lead-side plan.json modifications made before workers spawn. Each entry: `{"source": "challenger|pre-validation|scout", "role": "affected role", "category": "issue type", "before": "original", "after": "modified or null", "reason": "why"}`. Feeds back to `/do:design` to improve AC authoring quality. This field captures the gap between what design produced and what execute needed — the exact signal design needs to stop generating the same anti-patterns.

**`acGradients`** (execute only — from Step A): The raw `(check, exitCode, stderr)` triples that make prompt fixes evidence-based rather than speculative.

**`stepsSkipped`** — protocol steps that were skipped and why (e.g., `"Step 2.3: AC pre-validation skipped — plan had no check commands"`)

**`instructionsIgnored`** — SKILL.md instructions that agents didn't follow despite being told (e.g., `"Workers didn't use CoVe verification — reported completion without running checks"`)

**`highValueInstructions`** — instructions that demonstrably drove good outcomes (from Step D). Each entry: `{"instruction": "...", "section": "...", "evidence": "..."}`. Protects proven instructions from future simplification.

**`auxiliaryEffectiveness`** — per-auxiliary outcome tracking for cross-run ROI analysis. Each entry: `{"auxiliary": "challenger|scout|integration-verifier|memory-curator", "ran": true|false, "findings": N, "blockingFindings": N, "prevented": "description of what would have gone wrong without this auxiliary, or 'unknown' if unclear"}`. When an auxiliary finds nothing actionable across 3+ consecutive runs, `plan-health-summary` flags it so the lead can consider skipping it (token savings). When an auxiliary consistently prevents failures, it's evidence for keeping it even if it seems expensive.

**`whatWorked`** / **`whatFailed`** — kept for backward compatibility but secondary to promptFixes.

### Lifecycle Feedback

`plan-health-summary` surfaces `unresolvedImprovements` (deduplicated promptFixes from last 5 runs, sorted failures-first). Skills display these at startup so the lead can act on recurring issues.

Ordering rules: `reflection-add` before `trace-add skill-complete`. Non-fatal: if reflection-add fails, proceed.
