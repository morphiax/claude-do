---
name: execute
description: "Execute a plan from /design with persistent workers and self-organizing task claiming."
argument-hint: ""
---

# Execute

Execute `.design/plan.json` with persistent, self-organizing workers. Design produced the plan — now execute makes it happen. **This skill only executes — it does NOT design.**

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

1. Validate: `python3 $PLAN_CLI status .design/plan.json`. On failure: `not_found` = "No plan found. Run `/do:design <goal>` first." and stop; `bad_schema` = unsupported schema, stop; `empty_tasks` = no tasks, stop.
2. Resume detection: If `isResume`: run `python3 $PLAN_CLI resume-reset .design/plan.json`, then for each `resetTasks` entry: `git checkout -- {filesToRevert}` and `rm -f {filesToDelete}`. If `noWorkRemaining`: "All tasks already resolved." and stop.
3. Create team: `TeamDelete(team_name: "do-execute")` (ignore errors), then `TeamCreate(team_name: "do-execute")`. If TeamCreate fails, tell user Agent Teams is required and stop.
4. Create TaskList: `python3 $PLAN_CLI tasklist-data .design/plan.json`. For each task: `TaskCreate` with subject `"Task {planIndex}: {subject}"`, record returned ID in `taskIdMapping`. Wire `blockedBy` via `TaskUpdate(addBlockedBy)`. If resuming, mark completed tasks. Add overlap constraints: `python3 $PLAN_CLI overlap-matrix .design/plan.json` — for each pair `(i, j)` where `j > i`, files overlap, and no existing dependency: `TaskUpdate(taskId: taskIdMapping[j], addBlockedBy: [taskIdMapping[i]])`.
5. **Role-based worker selection**: Run `python3 $PLAN_CLI worker-pool .design/plan.json` to get unique roles and worker count. Spawn one specialist per unique `agent.role` — workers are experts in their domain, not generic executors.
6. Summary: `python3 $PLAN_CLI summary .design/plan.json`. Store `goal`, `taskCount`, `maxDepth`.
7. Pre-flight: Build a Bash script that checks `git status --porcelain`, runs any blocking checks, and tests context files exist.

### 2. Report and Spawn

Report to user:
```
Executing: {goal}
Tasks: {taskCount} (depth: {maxDepth})
Workers: {totalWorkers} ({names})
```
Warn if git is dirty. If resuming: "Resuming execution."

Spawn workers as teammates using the Task tool. Each worker prompt MUST include these invariants:

1. **Task discovery**: "Check TaskList for pending unblocked tasks matching your role. Claim by setting status to in_progress."
2. **Brief location**: "Read your task brief from `.design/plan.json` at `tasks[{planIndex}].prompt`. The planIndex is the number in the task subject."
3. **Completion reporting**: "When done, SendMessage to lead with: task subject, what you did, files changed."
4. **Committing**: "git add specific files + git commit with conventional commit message (feat:/fix:/refactor: etc). Never git add -A."
5. **Failure handling**: "If you cannot complete a task, SendMessage to lead with: task subject, what failed, why it failed, what you tried, suggested alternative."

Beyond invariants, include: scope boundaries (what NOT to touch), expected output files, success criteria from the plan's `agent.acceptanceCriteria`, and any `agent.contextFiles` to read first.

```
Task(subagent_type: "general-purpose", team_name: "do-execute", name: "{role}", prompt: <role-specific prompt with invariants>)
```

### 3. Monitor

Event-driven loop — process worker messages as they arrive.

**On task completion**: Worker tells you which task they finished and what they did.
1. Update plan.json: `echo '[{"planIndex": N, "status": "completed", "result": "..."}]' | python3 $PLAN_CLI update-status .design/plan.json`
2. Progressive trimming: completed tasks are automatically stripped of verbose agent fields by `update-status`.
3. Handle any `cascaded` entries by marking them in TaskList.
4. Wake idle workers — tell them to check for new tasks.

**On task failure**: Worker tells you which task failed and why.
1. Update plan.json: `echo '[{"planIndex": N, "status": "failed", "result": "..."}]' | python3 $PLAN_CLI update-status .design/plan.json`
2. Handle cascaded entries in TaskList.
3. Circuit breaker: `python3 $PLAN_CLI circuit-breaker .design/plan.json`. If `shouldAbort`: shut down all workers, go to Final Verification.
4. Retries: `python3 $PLAN_CLI retry-candidates .design/plan.json`. If retryable (attempts < 3): clean up partial work (`git checkout` + `rm`), reset in TaskList, tell the worker to retry with context: what failed, why, what was tried, suggested alternative approach.

**On idle**: Worker reports no tasks available. Track idle workers. Check completion.

**Completion check** (after each idle/completion):
1. `python3 $PLAN_CLI status .design/plan.json`
2. No pending tasks and all workers idle: shut down workers, go to Final Verification.
3. Pending tasks exist but all workers idle (deadlock): report deadlock, shut down, go to Final Verification.

**On peer issues**: Workers handle these directly. The lead does not intervene unless asked.

### 4. Final Verification

Build a Bash script that for each completed task: checks created files exist (`test -f`), checks modified files in git log. Output JSON array with per-task results.

For verification failures with attempts < 3: update plan.json to failed, spawn a retry worker to try again. For non-retryable: leave as failed.

### 5. Goal Review

Before checking mechanical correctness, evaluate whether the completed work actually achieves the original goal.

Review against the goal from `plan.json`:
1. **Completeness** — Does the sum of completed tasks deliver the goal end-to-end? (e.g., API built but no route registered, component created but never rendered)
2. **Coherence** — Do the pieces fit together? Naming conventions consistent? Data models match across tasks?
3. **User intent** — Would a user looking at the result say "this is what I asked for"?

If gaps are found: spawn a targeted worker to address them. These are goal-level fixes, not task retries.

### 6. Integration Testing

After the goal review, test that the combined work integrates correctly.

1. Spawn an `integration-tester` worker. Its prompt should include: completed tasks (subjects + files), test command from `plan.json context.testCommand`, instructions to run the full test suite, attempt a build, check for import/dependency conflicts, verify cross-task connections.
2. On FAIL: assign fix tasks to appropriate workers or spawn a targeted fix worker. Re-run after fixes.
3. On PASS or after max 2 fix rounds: proceed to Complete.

**Skip when**: only 1 task was executed, or all tasks were independent (no shared files, no cross-references).

### 7. Complete

1. Summary: `python3 $PLAN_CLI status .design/plan.json`. Display completed/failed/blocked/skipped counts with subjects. Recommend follow-ups for failures.
2. **Session handoff** — Write `.design/handoff.md`:

```markdown
# Session Handoff — {goal}
Date: {ISO timestamp}

## Completed
{For each: "Task N: {subject} — {one-line result}"}

## Failed
{For each: "Task N: {subject} — {failure reason}"}

## Integration: {PASS/FAIL/SKIPPED}

## Decisions
{Deviations from plan, retries, workarounds}

## Files Changed
{Deduplicated list of all files created/modified}

## Known Gaps
{Missing coverage, TODOs, skipped tasks and why}

## Next Steps
{Concrete actions if work continues}
```

3. Archive: If all completed, move artifacts to history:
   ```bash
   ARCHIVE_DIR=".design/history/$(date -u +%Y%m%dT%H%M%SZ)"
   mkdir -p "$ARCHIVE_DIR"
   find .design -mindepth 1 -maxdepth 1 ! -name history -exec mv {} "$ARCHIVE_DIR/" \;
   ```
   If partial (failures remain): leave artifacts in `.design/` for resume.
4. Cleanup: `TeamDelete(team_name: "do-execute")`.

**Arguments**: $ARGUMENTS
