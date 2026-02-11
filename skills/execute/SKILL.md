---
name: execute
description: "Execute a plan from /design with persistent workers, self-organizing task claiming, and deferred verification."
argument-hint: ""
---

# Execute

Execute `.design/plan.json` with persistent, self-organizing workers. Design did the heavy lifting — every task has a role, model, approach, file lists, acceptance criteria, and assembled prompt. **This skill only executes — it does NOT design.**

**Do NOT use `EnterPlanMode`** — this skill IS the plan.

**Lead boundaries**: Use only `TeamCreate`, `TeamDelete`, `TaskCreate`, `TaskUpdate`, `TaskList`, `SendMessage`, `Task`, `AskUserQuestion`, and `Bash` (only for `python3 $PLAN_CLI`, `git`, verification scripts, and cleanup). Never read source files, use MCP tools, `Grep`, `Glob`, or `LSP`. Never execute tasks directly — spawn a worker.

**Silent execution**: Output nothing between the initial summary and the final summary.

**No polling**: Messages auto-deliver to your conversation automatically. Never use `sleep`, `for i in {1..N}`, or Bash loops to wait. Simply proceed with your work — when a teammate sends a message, it appears in your next turn. The system handles all delivery.

### Script Setup

```
PLAN_CLI = {plugin_root}/skills/execute/scripts/plan.py
```

All script calls: `python3 $PLAN_CLI <command> [args]` via Bash. Output: JSON with `{"ok": true/false, ...}`.

---

## Flow

### 1. Setup

Mechanical setup — no subagent needed.

1. Validate: `python3 $PLAN_CLI status .design/plan.json`. On failure: `not_found` = "No plan found. Run `/design <goal>` first." and stop; `bad_schema` = unsupported schema, stop; `empty_tasks` = no tasks, stop.
2. Resume detection: `python3 $PLAN_CLI status-counts .design/plan.json`. If `isResume`: run `python3 $PLAN_CLI resume-reset .design/plan.json`, then for each `resetTasks` entry: `git checkout -- {filesToRevert}` and `rm -f {filesToDelete}`. If `noWorkRemaining`: "All tasks already resolved." and stop.
3. Create team: `TeamDelete(team_name: "do-execute")` (ignore errors), then `TeamCreate(team_name: "do-execute")`. If TeamCreate fails, tell user Agent Teams is required and stop.
4. Create TaskList: `python3 $PLAN_CLI tasklist-data .design/plan.json`. For each task: `TaskCreate` with subject `"Task {planIndex}: {subject}"`, record returned ID in `taskIdMapping`. Wire `blockedBy` via `TaskUpdate(addBlockedBy)`. If resuming, mark completed tasks. Add overlap constraints: `python3 $PLAN_CLI overlap-matrix .design/plan.json` — for each pair `(i, j)` where `j > i`, files overlap, and no existing dependency: `TaskUpdate(taskId: taskIdMapping[j], addBlockedBy: [taskIdMapping[i]])`.
5. Read worker team: `python3 $PLAN_CLI worker-pool .design/plan.json` — derives the team from the plan's `agent.role` and `agent.model` fields. One persistent worker per unique role, model chosen by majority among that role's tasks.
6. Summary: `python3 $PLAN_CLI summary .design/plan.json`. Store `goal`, `taskCount`, `maxDepth`.
7. Pre-flight: Build a Bash script that checks `git status --porcelain`, runs each blocking assumption's `verify` command, and tests `contextFiles` existence.

### 2. Report and Spawn

Report to user:
```
Executing: {goal}
Tasks: {taskCount} (depth: {maxDepth})
Workers: {totalWorkers} ({names})
Validation: {pass}/{total} blocking checks passed
```
Warn if git is dirty. If blocking checks failed: `AskUserQuestion` to fix or proceed. If resuming: "Resuming execution."

Spawn workers — the plan dictates the team. For each worker from the pool:
```
Task(subagent_type: "general-purpose", team_name: "do-execute", name: "{worker.name}", model: "{worker.model}", prompt: <WORKER_PROMPT>)
```

### 3. Monitor

Event-driven loop — process worker messages as they arrive.

**On task completion**: Worker tells you which task they finished and what they did.
1. Update plan.json: `echo '[{"planIndex": N, "status": "completed", "result": "..."}]' | python3 $PLAN_CLI update-status .design/plan.json`
2. Handle any `cascaded` entries by marking them in TaskList
3. Wake idle workers — tell them to check for new tasks

**On task failure**: Worker tells you which task failed and why.
1. Update plan.json: `echo '[{"planIndex": N, "status": "failed", "result": "..."}]' | python3 $PLAN_CLI update-status .design/plan.json`
2. Handle cascaded entries in TaskList
3. Circuit breaker: `python3 $PLAN_CLI circuit-breaker .design/plan.json`. If `shouldAbort`: shut down all workers, go to Final Verification.
4. Retries: `python3 $PLAN_CLI retry-candidates .design/plan.json`. If retryable (attempts < 3): clean up partial work (`git checkout` + `rm`), reset in TaskList, tell the worker to retry with failure context.

**On idle**: Worker reports no tasks available. Track idle workers. Check completion.

**Completion check** (after each idle/completion):
1. `python3 $PLAN_CLI status-counts .design/plan.json`
2. No pending tasks and all workers idle: shut down workers, go to Final Verification
3. Pending tasks exist but all workers idle (deadlock): report deadlock, shut down, go to Final Verification

**On peer issues**: Workers handle these directly. The lead does not intervene unless asked.

### 4. Final Verification

Build a Bash script that for each completed task: checks created files exist (`test -f`), checks modified files in git log, runs each `acceptanceCriteria[].check`. Output JSON array with per-task results.

For verification failures with attempts < 3: update plan.json to failed, spawn a one-off retry worker with the RETRY_WORKER_PROMPT. For non-retryable: leave as failed.

### 5. Complete

1. Summary: `python3 $PLAN_CLI status-counts .design/plan.json`. Display completed/failed/blocked/skipped counts with subjects. Recommend follow-ups for failures.
2. Archive: If all completed: `mkdir -p .design/history && mv .design/plan.json ".design/history/$(date -u +%Y%m%dT%H%M%SZ)-plan.json"`. If partial: leave plan for resume.
3. Cleanup: `TeamDelete(team_name: "do-execute")`.

---

## Worker Prompts

### WORKER_PROMPT

Fill `{workerName}`, `{role}`:

```
You are {workerName}, a {role} on the do-execute team.

Read ~/.claude/teams/do-execute/config.json for lead name and teammates.

## Work Loop

1. Check TaskList for pending unblocked tasks matching your role
2. If none: report idle. When lead says check, go to step 1
3. Claim task (TaskUpdate in_progress). Extract planIndex from subject
4. Read .design/plan.json tasks[planIndex].prompt
5. Execute. Run BLOCKING assumptions first — if fail, report to lead
6. Verify acceptance criteria
7. Commit: git add {files}, git commit -m "task {N}: {subject}"
8. Mark complete. Report to lead
9. Go to step 1

## Errors

- Cannot complete: revert, reset to pending, report failure
- Bug in another's code: message that worker directly, CC lead
```

### RETRY_WORKER_PROMPT

Fill `{planIndex}`, `{taskSubject}`, `{attempts}`, `{failureReason}`, `{fallbackStrategy}`:

```
Retrying task {planIndex}: {taskSubject} (attempt {attempts}/3)

Previous failure: {failureReason}
Fallback: {fallbackStrategy}

Read .design/plan.json tasks[{planIndex}].prompt. Do not repeat same approach.
Verify acceptance criteria. Commit: git add + git commit -m "task {planIndex}: {taskSubject} (retry {attempts})"

Read ~/.claude/teams/do-execute/config.json for lead name. Report result.
```

**Arguments**: $ARGUMENTS
