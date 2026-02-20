# Shared Lead Protocol — Core

---

## Lead Boundaries

Use only `Task`, `AskUserQuestion`, and `Bash` (for `python3 $PLAN_CLI`, cleanup, verification). Project metadata (CLAUDE.md, package.json, README) allowed via Bash. **Never use Read, Grep, Glob, Edit, Write, LSP, WebFetch, WebSearch, or MCP tools on project source files.** The lead orchestrates — agents implement.

---

## No Polling

Task() blocks until the agent returns. Never use `sleep`, loops, or Bash waits.

---

## Guardrails

**Do NOT answer the goal directly. Your FIRST action after reading the goal MUST be the pre-flight check. Follow the Flow step-by-step.**

**Do NOT use `EnterPlanMode`** — this skill IS the plan.

---

## Script Setup

Resolve plugin root (containing `.claude-plugin/`). All script calls: `python3 $PLAN_CLI <command> [args]` via Bash. JSON output: `{"ok": true/false, ...}`.

```bash
PLAN_CLI={plugin_root}/skills/{skill}/scripts/plan.py
SESSION_ID=$(python3 $PLAN_CLI team-name {skill} | python3 -c "import sys,json;print(json.load(sys.stdin)['teamName'])")
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
| `spawn` | optional | when spawning agents | `{"model":"...","memoriesInjected":N}` |
| `completion` | optional | when an agent completes | `{"acPassed":N,"acTotal":N,"filesChanged":N,"firstAttempt":bool}` |

---

## Memory Injection

```bash
python3 $PLAN_CLI memory-search .design/memory.jsonl --goal "{goal}" --stack "{stack}" [--keywords "{extra terms}"]
```

If `ok: false` or no memories → proceed without injection. Otherwise inject **top 3-5** into agent prompts. **Show user**: "Memory: injecting {count} past learnings — {keyword summaries}."

> **Note**: Runtime lesson injection (formerly "Reflection Prepend") has been removed. Recurring issues are resolved by improving SKILL.md instructions permanently via `/do:reflect fix-skill`, not by patching agent prompts at runtime. Memory injection provides domain knowledge; SKILL.md improvements provide process corrections.

---

## Lifecycle Context

Run at skill start (Step 1 of pre-flight), before trace emit:

```bash
python3 $PLAN_CLI plan-health-summary .design
```

Display to user: "Recent runs: {reflection summaries}. {plan status}." Skip if all fields empty.

Then emit skill-start trace (with payload per Trace Emission table):
```bash
python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event skill-start --skill {skill} --payload '{"roleCount":N,"stepsSkipped":["..."],"isResume":false}' || true
```

---

## Phase Announcements

Announce each major phase to user for visibility. Minimum: pre-flight, agent spawning, synthesis/execution, completion. Format: brief one-liner stating what's happening next.

---

## INSIGHT Handling

When an agent returns output prefixed with `INSIGHT:`, display it to the user immediately: "Insight from {agent}: {finding}". An INSIGHT is informational — it does not change the completion status of the Task() call.

---

## Next Action Suggestion

After the completion summary (and after trace), suggest the logical next skill invocation. The suggestion MUST include a complete, copy-pasteable prompt with the user's goal contextualized from the current run.

**Format** (display as the final output of the skill):

```
Next: /do:{skill} {comprehensive goal description derived from this run}
```

**Routing by skill**:
- **research** → `/do:design` using the top `adopt`/`adapt` recommendation's `designGoal` field. If multiple recommendations, show up to 3 as numbered options.
- **design** → `/do:execute` (no arguments needed, reads plan.json).
- **execute** (all passed) → Suggest reviewing the output OR `/do:simplify {target}` if the codebase grew significantly.
- **execute** (partial/failed) → `/do:execute` to retry failed roles, or `/do:design {goal}` to redesign if failures are structural.
- **simplify** → `/do:execute` (no arguments needed, reads plan.json).

The goal description must be specific and comprehensive — not a generic label but a sentence capturing what the user is building, the key technologies, and the target outcome. Derive this from `plan.json`'s goal, context.stack, and role names.
