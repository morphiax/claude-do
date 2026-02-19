# Shared Lead Protocol
# skills/shared/lead-protocol.md
#
# This file defines the CANONICAL protocol for all team-based do: skills.
# Skills that consume this file: design, execute, research, simplify.
# Reflect does NOT consume this file (it has no team and different tooling).
#
# Each SKILL.md should Read this file at its upfront instruction block and substitute
# {skill} with its skill name, {agents} with its agent noun (experts/researchers/analysts/workers).
# Per-skill overrides are documented in each SKILL.md.

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

## CRITICAL: Always Use Agent Teams

When spawning any agent via Task tool, you MUST include `team_name: $TEAM_NAME` and `name: "{agent-name}"` parameters. Without these, agents are standalone and cannot coordinate.

> **Note**: Post-execution auxiliaries (integration-verifier, memory-curator) and one-off Task delegates (spec-writer, synthesis) are standalone `Task()` calls without `team_name` — they don't need coordination. Only primary {agents} spawned into the team require these parameters.

---

## Script Setup

Resolve plugin root (containing `.claude-plugin/`). All script calls: `python3 $PLAN_CLI <command> [args]` via Bash. JSON output: `{"ok": true/false, ...}`.

```bash
PLAN_CLI={plugin_root}/skills/{skill}/scripts/plan.py
TEAM_NAME=$(python3 $PLAN_CLI team-name {skill} | python3 -c "import sys,json;print(json.load(sys.stdin)['teamName'])")
SESSION_ID=$TEAM_NAME
```

> **Bug fixed**: All skills must use the `python3 -c` JSON parse pattern for `TEAM_NAME`. The `.teamName` field accessor (used in design and execute's original) does not work in shell — the correct form pipes through python3 to parse the JSON and extract `teamName`.

---

## Trace Emission

After each agent lifecycle event:

```bash
python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event {event} --skill {skill} [--agent "{name}"] [--payload '{"key":"val"}'] || true
```

Events: `skill-start`, `skill-complete`, `spawn`, `completion`, `failure`, `respawn`. Use `--payload` for extras (e.g., model escalation on retry). Failures are non-blocking (`|| true`).

---

## TeamCreate Health Check

```bash
# Standard create pattern
TeamDelete(team_name: $TEAM_NAME)  # ignore errors
TeamCreate(team_name: $TEAM_NAME)  # if fails: tell user Agent Teams required, stop

# Health check
ls ~/.claude/teams/$TEAM_NAME/config.json
# If missing: TeamDelete, then retry TeamCreate once
# If retry fails: abort with clear error message
```

---

## Liveness Pipeline

Track completion per agent: (a) SendMessage received AND (b) artifact file exists (`ls .design/expert-{name}.json`). Show user status: "{Agent type} progress: {name} done ({M}/{N} complete)."

| Rule | Action |
|---|---|
| **Turn timeout (3 turns)** | Send: "Status check — artifact expected at `.design/expert-{name}.json`. Report completion or blockers." On re-spawn: `python3 $PLAN_CLI trace-add ... --event respawn ... || true`. Show: "Re-spawning {name} (timeout)." |
| **Re-spawn ceiling** | No completion 1 turn after ping → re-spawn with same prompt (max 2 attempts). |
| **Proceed with available** | After 2 re-spawn attempts → `python3 $PLAN_CLI trace-add ... --event failure ... || true`. Log failure, proceed with responsive agents' artifacts. |
| **Never write artifacts yourself** | Lead interpretation ≠ specialist analysis. |

On completion: `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event completion --skill {skill} --agent "{name}" || true`

> **Bug fixed**: Design originally used a 2-turn timeout; research was missing the "Turn timeout" and "Never write artifacts yourself" rows. Canonical is 4 rows, 3-turn timeout for all skills.

---

## Memory Injection

```bash
python3 $PLAN_CLI memory-search .design/memory.jsonl --goal "{goal}" --stack "{stack}" [--keywords "{extra terms}"]
```

If `ok: false` or no memories → proceed without injection. Otherwise inject **top 3-5** into agent prompts. **Show user**: "Memory: injecting {count} past learnings — {keyword summaries}."

> **Bug fixed**: Execute used "top 2-3" — an arbitrary difference with no rationale. Canonical is "top 3-5" for all skills. Execute's per-role injection loop still applies; the 3-5 cap is per-role.

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
