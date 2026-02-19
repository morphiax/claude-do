# Shared Lead Protocol — Core
# shared/lead-protocol-core.md
#
# Core lead behavior for all do: skills (design, execute, research, simplify).
# Defines: boundaries, no-polling, trace emission, memory injection, lifecycle context,
# phase announcements, and insight handling.
# Reflect does NOT consume this file.
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

> **execute override**: Bash also includes `git` (for partial-work cleanup on retry and git status checks).

---

## No Polling

Messages auto-deliver automatically. Never use `sleep`, loops, or Bash waits. When a teammate sends a message, it appears in your next turn.

---

## Protocol Requirement

**Do NOT answer the goal directly. Your FIRST action after reading the goal MUST be the pre-flight check. Follow the Flow step-by-step.**

---

## Do Not Use EnterPlanMode

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

Emit only the following lifecycle events:

```bash
python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event {event} --skill {skill} [--agent "{name}"] [--payload '{"key":"val"}'] || true
```

Events:
- `skill-start` **(mandatory)** — emit at the start of every run
- `skill-complete` **(mandatory)** — emit at the end of every run
- `failure` **(mandatory)** — emit when any agent or role fails
- `respawn` **(mandatory)** — emit when re-spawning a timed-out or failed agent
- `spawn`, `completion` **(optional)** — emit for team-based skills; omit for single Task() calls

Failures are non-blocking (`|| true`).

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

**Insight surfacing**: When an agent sends a message prefixed with `INSIGHT:`, display it to the user immediately: "Insight from {agent}: {finding}". Do NOT count INSIGHT messages as completion signals — continue waiting for the full report or artifact. An INSIGHT message is a partial update, not a completion report.
