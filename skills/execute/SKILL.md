---
name: execute
description: "Execute a plan from /design with persistent workers and self-organizing task claiming."
argument-hint: ""
---

# Execute

Execute `.design/plan.json` with persistent, self-organizing workers. Design produced the plan with role briefs — now workers read the codebase and achieve their goals. **This skill only executes — it does NOT design.**

**Do NOT use `EnterPlanMode`** — this skill IS the plan.

**CRITICAL: Always use agent teams.** When spawning any worker via Task tool, you MUST include `team_name: "do-execute"` and `name: "{role}"` parameters. Without these, workers are standalone and cannot coordinate.

**Lead boundaries**: Use only `TeamCreate`, `TeamDelete`, `TaskCreate`, `TaskUpdate`, `TaskList`, `SendMessage`, `Task`, `AskUserQuestion`, and `Bash` (only for `python3 $PLAN_CLI`, `git`, verification scripts, and cleanup). Never read source files, use MCP tools, `Grep`, `Glob`, or `LSP`. Never execute tasks directly — spawn a worker.

**Silent execution**: Output nothing between the initial summary and the final summary.

**No polling**: Messages auto-deliver automatically. Never use `sleep`, loops, or Bash waits. When a teammate sends a message, it appears in your next turn.

### Script Setup

```
PLAN_CLI = {plugin_root}/skills/execute/scripts/plan.py
```

All script calls: `python3 $PLAN_CLI <command> [args]` via Bash. Output: JSON with `{"ok": true/false, ...}`.

---

## Flow

### 1. Setup

1. Validate: `python3 $PLAN_CLI status .design/plan.json`. On failure: `not_found` = "No plan found. Run `/do:design <goal>` first." and stop; `bad_schema` = unsupported schema, stop; `empty_roles` = no roles, stop.
2. Resume detection: If `isResume`: run `python3 $PLAN_CLI resume-reset .design/plan.json`. If `noWorkRemaining`: "All roles already resolved." and stop.
3. Create team: `TeamDelete(team_name: "do-execute")` (ignore errors), then `TeamCreate(team_name: "do-execute")`. If TeamCreate fails, tell user Agent Teams is required and stop.
4. Create TaskList: `python3 $PLAN_CLI tasklist-data .design/plan.json`. For each role: `TaskCreate` with subject `"Role {roleIndex}: {name} — {goal}"`, record returned ID in `roleIdMapping`. Wire `blockedBy` via `TaskUpdate(addBlockedBy)`. If resuming, mark completed roles. Add overlap constraints: `python3 $PLAN_CLI overlap-matrix .design/plan.json` — for each pair `(i, j)` where `j > i` and directories overlap: `TaskUpdate(taskId: roleIdMapping[j], addBlockedBy: [roleIdMapping[i]])`.
5. **Worker pool**: Run `python3 $PLAN_CLI worker-pool .design/plan.json` to get workers (one per role).
6. Summary: `python3 $PLAN_CLI summary .design/plan.json`. Store `goal`, `roleCount`, `maxDepth`.
7. Pre-flight: Build a Bash script that checks `git status --porcelain` and runs any blocking checks.

### 2. Pre-Execution Auxiliaries

Check `auxiliaryRoles[]` in plan.json for `type: "pre-execution"` roles. Spawn them sequentially before execution workers.

**Challenger**: Spawn as a teammate. Prompt includes: "Read `.design/plan.json` and all `.design/expert-*.json` artifacts. Challenge assumptions, find gaps, identify risks. Report findings via SendMessage." Wait for report. If critical issues found, adjust plan (update plan.json) or ask user. If no critical issues, proceed.

**Scout**: Spawn as a teammate. Prompt includes: "Read actual codebase in scope directories from plan.json roles. Map patterns, conventions, integration points. Flag discrepancies with expert assumptions. Save report to `.design/scout-report.json` and SendMessage summary." Wait for report. If discrepancies found, update role briefs in plan.json or note for workers.

### 3. Report and Spawn Workers

Report to user:
```
Executing: {goal}
Roles: {roleCount} (depth: {maxDepth})
Workers: {totalWorkers} ({names})
Auxiliaries: {pre-execution auxiliaries run, post-execution pending}
```
Warn if git is dirty. If resuming: "Resuming execution."

**Memory injection** — For each role, retrieve relevant memories:
```bash
python3 $PLAN_CLI memory-search .design/memory.jsonl --goal "{role.goal}" --stack "{context.stack}" --keywords "{role.scope.directories + role.name}"
```
Parse JSON output. Take top 2-3 `memories[]` per role.

Spawn workers as teammates using the Task tool. Each worker prompt MUST include:

1. **Identity**: "You are a specialist: {role.name}. Your goal: {role.goal}"
2. **Brief location**: "Read your full role brief from `.design/plan.json` at `roles[{roleIndex}]`."
3. **Expert context**: "Read these expert artifacts for context: {expertContext entries with artifact paths and relevance notes}." If a scout report exists: "Also read `.design/scout-report.json` for codebase reality check."
4. **Past learnings** (if memories found): "Relevant past learnings: {bullet list of memories with format: '- {category}: {summary} (from {created})'}"
5. **Process**: "Explore your scope directories ({scope.directories}). Plan your own approach based on what you find in the actual codebase. Implement, test, verify against your acceptance criteria."
6. **Task discovery**: "Check TaskList for your pending unblocked task. Claim by setting status to in_progress."
7. **Constraints**: "{constraints from role brief}"
8. **Done when**: "{acceptanceCriteria from role brief}"
9. **Committing**: "git add specific files + git commit with conventional commit message (feat:/fix:/refactor: etc). Never git add -A."
10. **Completion reporting**: "When done, SendMessage to lead with: role name, what you achieved, files changed, acceptance criteria results (pass/fail each)."
11. **Failure handling**: "If you cannot complete your goal, SendMessage to lead with: role name, what failed, why, what you tried, suggested alternative. If rollback triggers fire ({rollbackTriggers}), stop immediately and report."
12. **Fallback**: If role has a fallback: "If your primary approach fails: {fallback}"
13. **Scope boundaries**: "Stay within your scope directories. Do not modify files outside your scope unless absolutely necessary for integration."

```
Task(subagent_type: "general-purpose", team_name: "do-execute", name: "{worker-name}", model: "{model}", prompt: <role-specific prompt with all above>)
```

### 4. Monitor

Event-driven loop — process worker messages as they arrive.

**On role completion**: Worker reports what they achieved and acceptance criteria results.
1. Update plan.json: `echo '[{"roleIndex": N, "status": "completed", "result": "..."}]' | python3 $PLAN_CLI update-status .design/plan.json`
2. Handle any `cascaded` entries by marking them in TaskList.
3. Wake idle workers — tell them to check for new tasks.

**On role failure**: Worker reports what failed and why.
1. Update plan.json: `echo '[{"roleIndex": N, "status": "failed", "result": "..."}]' | python3 $PLAN_CLI update-status .design/plan.json`
2. Handle cascaded entries in TaskList.
3. Circuit breaker: `python3 $PLAN_CLI circuit-breaker .design/plan.json`. If `shouldAbort`: shut down all workers, go to Post-Execution.
4. Retries: `python3 $PLAN_CLI retry-candidates .design/plan.json`. If retryable (attempts < 3): clean up partial work (`git checkout` + `rm`), reset in TaskList, tell the worker to retry with context: what failed, why, suggested alternative approach, fallback strategy.

**On idle**: Worker reports no tasks available. Track idle workers. Check completion.

**Completion check** (after each idle/completion):
1. `python3 $PLAN_CLI status .design/plan.json`
2. No pending roles and all workers idle: shut down workers, go to Post-Execution.
3. Pending roles exist but all workers idle (deadlock): report deadlock, shut down, go to Post-Execution.

**On peer issues**: Workers handle these directly. The lead does not intervene unless asked.

### 5. Post-Execution Auxiliaries

Check `auxiliaryRoles[]` for `type: "post-execution"` roles.

**Integration Verifier**: Spawn as a teammate. Prompt includes:
- "Verify all completed roles' work integrates correctly."
- Completed roles: subjects, files changed (from worker reports)
- Test command from `plan.json context.testCommand`
- All `acceptanceCriteria` from all completed roles
- "Run the full test suite. Check for import/dependency conflicts. Verify cross-role connections. Test the goal end-to-end."
- "Report: PASS (all criteria met) or FAIL (list specific failures with suggested fixes)."

On FAIL: spawn targeted fix workers for specific issues. Re-run verifier after fixes (max 2 fix rounds).

**Skip when**: only 1 role was executed, or all roles were independent (no shared directories, no cross-references).

### 6. Goal Review

Before declaring completion, evaluate whether the work achieves the original goal.

Review against the goal from `plan.json`:
1. **Completeness** — Does the sum of completed roles deliver the goal end-to-end?
2. **Coherence** — Do the pieces fit together? Naming conventions consistent? Data models match across roles?
3. **User intent** — Would a user looking at the result say "this is what I asked for"?

If gaps are found: spawn a targeted worker to address them.

### 7. Complete

1. Summary: `python3 $PLAN_CLI status .design/plan.json`. Display completed/failed/blocked/skipped counts with names. Recommend follow-ups for failures.
2. **Session handoff** — Write `.design/handoff.md`:

```markdown
# Session Handoff — {goal}
Date: {ISO timestamp}

## Completed
{For each: "Role: {name} — {one-line result}"}

## Failed
{For each: "Role: {name} — {failure reason}"}

## Integration: {PASS/FAIL/SKIPPED}

## Decisions
{Deviations from plan, retries, workarounds}

## Files Changed
{Deduplicated list of all files created/modified}

## Known Gaps
{Missing coverage, TODOs, skipped roles and why}

## Next Steps
{Concrete actions if work continues}
```

3. **Memory curation** — Spawn memory-curator auxiliary agent:

Prompt includes:
- "Read `.design/handoff.md` and `.design/plan.json` all roles (completed, failed, skipped)."
- "Extract actionable patterns: successful approaches, failed approaches, discovered conventions, blockers overcome, mistakes to avoid."
- "For failed roles: read `result` field for failure reasons. Extract mistake/failure category memories."
- "For each pattern: determine category (pattern|mistake|convention|approach|failure), generate keywords, write concise body (<200 words)."
- "Call `python3 $PLAN_CLI memory-add .design/memory.jsonl --category <cat> --keywords <csv> --body <text>` for each entry."
- "Focus on: specific file/pattern/tool references (actionable), not vague lessons. Reference role names and file paths."
- "Skip generic insights. Only record learnings that would help future similar goals."

```
Task(subagent_type: "general-purpose", team_name: "do-execute", name: "memory-curator", model: "haiku", prompt: <above>)
```

Wait for curator completion. On failure: proceed (memory curation is optional).

4. Archive: If all completed, move artifacts to history:
   ```bash
   ARCHIVE_DIR=".design/history/$(date -u +%Y%m%dT%H%M%SZ)"
   mkdir -p "$ARCHIVE_DIR"
   find .design -mindepth 1 -maxdepth 1 ! -name history ! -name memory.jsonl -exec mv {} "$ARCHIVE_DIR/" \;
   ```
   If partial (failures remain): leave artifacts in `.design/` for resume.
5. Cleanup: `TeamDelete(team_name: "do-execute")`.

**Arguments**: $ARGUMENTS
