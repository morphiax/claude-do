# Shared Lead Protocol — Core
# shared/lead-protocol-core.md
#
# Core lead behavior for all do: skills (design, execute, research, simplify).
# Defines: boundaries, no-polling, trace emission, memory injection, lifecycle context,
# phase announcements, insight handling, and self-monitoring.
#
# Companion file: lead-protocol-teams.md (TeamCreate, liveness pipeline, team patterns).
# Skills that use teams (design, execute, simplify) should read BOTH files.
# Research reads ONLY this file (uses standalone Task subagents, no teams).
#
# Each SKILL.md should Read this file at its upfront instruction block and substitute
# {skill} with its skill name, {agents} with its agent noun (experts/researchers/analysts/workers).

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

Emit lifecycle events via `python3 $PLAN_CLI trace-add` (failures are non-blocking — append `|| true`):

| Event | Required | When |
|-------|----------|------|
| `skill-start` | mandatory | start of every run |
| `skill-complete` | mandatory | end of every run |
| `failure` | mandatory | any agent or role fails |
| `respawn` | mandatory | re-spawning a timed-out or failed agent |
| `spawn` | optional | team-based skills only |
| `completion` | optional | team-based skills only |

---

## Memory Injection

```bash
python3 $PLAN_CLI memory-search .design/memory.jsonl --goal "{goal}" --stack "{stack}" [--keywords "{extra terms}"]
```

If `ok: false` or no memories → proceed without injection. Otherwise inject **top 3-5** into agent prompts. **Show user**: "Memory: injecting {count} past learnings — {keyword summaries}."

---

## Lifecycle Context

Run at skill start (Step 1 of pre-flight), before trace emit:

```bash
python3 $PLAN_CLI plan-health-summary .design
```

Display to user: "Recent runs: {reflection summaries}. {plan status}." Skip if all fields empty.

Then emit skill-start trace:
```bash
python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event skill-start --skill {skill} || true
```

---

## Phase Announcements

Announce each major phase to user for visibility. Minimum: pre-flight, agent spawning, synthesis/execution, completion. Format: brief one-liner stating what's happening next.

---

## INSIGHT Handling

When an agent sends a message prefixed with `INSIGHT:`, display it to the user immediately: "Insight from {agent}: {finding}". Do NOT count INSIGHT messages as completion signals — continue waiting for the full report or artifact. An INSIGHT message is a partial update, not a completion report.

---

## Self-Monitoring

Every skill MUST call `reflection-add` at end of each run. Record what could be improved about *how the skill executed* — only observations that make the next run better. Be specific (names, data, decisions). 79% of failures are specification and coordination issues — weight observations there.

```bash
echo '{"whatWorked":["..."],"whatFailed":["..."],"doNextTime":["..."]}' \
  | python3 $PLAN_CLI reflection-add .design/reflection.jsonl \
    --skill {skill} --goal "<goal>" --outcome "<completed|partial|failed|aborted>" --goal-achieved <true|false>
```

Required base fields: `whatWorked`, `whatFailed`, `doNextTime` (arrays). Each skill adds skill-specific fields in its SKILL.md.

Ordering rules: `reflection-add` before `trace-add skill-complete`. `doNextTime` is the primary improvement signal — memory curator reads it first. Rich evaluations produce high-quality memories. Non-fatal: if reflection-add fails, proceed.
