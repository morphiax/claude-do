# Shared Lead Protocol — Teams

---

## CRITICAL: Always Use Agent Teams

When spawning any agent via Task tool as a team member, you MUST include `team_name: $TEAM_NAME` and `name: "{agent-name}"` parameters. Without these, agents are standalone and cannot coordinate.

> **Note**: Post-execution auxiliaries (integration-verifier, memory-curator) and one-off Task delegates (spec-writer, synthesis) are standalone `Task()` calls without `team_name` — they don't need coordination. Only primary {agents} spawned into the team require these parameters.

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
| **Turn timeout (3 turns)** | Send: "Status check — artifact expected at `.design/expert-{name}.json`. Report completion or blockers." On re-spawn: `python3 $PLAN_CLI trace-add ... --event respawn ... \|\| true`. Show: "Re-spawning {name} (timeout)." |
| **Re-spawn ceiling** | No completion 1 turn after ping → re-spawn with same prompt (max 2 attempts). |
| **Proceed with available** | After 2 re-spawn attempts → `python3 $PLAN_CLI trace-add ... --event failure ... \|\| true`. Log failure, proceed with responsive agents' artifacts. |
| **Never write artifacts yourself** | Lead interpretation ≠ specialist analysis. |

On completion: `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event completion --skill {skill} --agent "{name}" || true`
