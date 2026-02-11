---
name: execute
description: "Execute a plan from /design with persistent workers, self-organizing task claiming, and deferred verification."
argument-hint: ""
---

# Execute

Execute `.design/plan.json` with persistent, self-organizing workers. The lead sets up the team and TaskList, spawns workers once, then monitors via event-driven messaging. Workers claim tasks, execute, commit, and claim the next. Verification is deferred to a final pass.

**Do NOT use `EnterPlanMode`** — this skill IS the plan. Proceed to Setup.

**Lead tool boundary**: `TeamCreate`, `TeamDelete`, `TaskCreate`, `TaskUpdate`, `TaskList`, `SendMessage`, `Task`, `AskUserQuestion`, and `Bash` (only for `python3 $PLAN_CLI`, `git`, verification scripts, and cleanup). Never read source files, use MCP tools, `Grep`, `Glob`, or `LSP`. Never execute tasks directly — spawn a worker.

**Silent execution**: Output nothing between the initial summary and the final summary. No per-worker status updates.

**No polling**: Messages auto-deliver. Never use `sleep` or Bash loops to wait.

### Script Setup

Resolve the plugin root directory (containing `.claude-plugin/` and `skills/`). Set:

```
PLAN_CLI = {plugin_root}/skills/execute/scripts/plan.py
```

All script calls: `python3 $PLAN_CLI <command> [args]` via Bash. Output is JSON with `{"ok": true/false, ...}`.

---

## Step 1: Setup

Mechanical setup — no subagent needed.

**1a. Validate**: `python3 $PLAN_CLI validate .design/plan.json`. On failure: `not_found` = "No plan found. Run `/design <goal>` first." and stop; `bad_schema` = unsupported schema, stop; `empty_tasks` = no tasks, stop.

**1b. Resume detection**: `python3 $PLAN_CLI status-counts .design/plan.json`. If `isResume`: run `python3 $PLAN_CLI resume-reset .design/plan.json`, then for each `resetTasks` entry: `git checkout -- {filesToRevert}` and `rm -f {filesToDelete}`. If `noWorkRemaining`: "All tasks already resolved." and stop.

**1c. Create team**: `TeamDelete(team_name: "do-execute")` (ignore errors), then `TeamCreate(team_name: "do-execute")`. If TeamCreate fails, tell user Agent Teams is required and stop.

**1d. Create TaskList**: Run `python3 $PLAN_CLI tasklist-data .design/plan.json`. For each task: `TaskCreate` with subject `"Task {planIndex}: {subject}"`, record returned ID in `taskIdMapping`. Wire `blockedBy` via `TaskUpdate(addBlockedBy)`. If resuming, mark completed tasks.

Add overlap constraints: `python3 $PLAN_CLI overlap-matrix .design/plan.json`. For each pair `(i, j)` where `j > i`, files overlap, and no existing dependency: `TaskUpdate(taskId: taskIdMapping[j], addBlockedBy: [taskIdMapping[i]])`.

**1e. Extract task files**: For each pending task: `python3 $PLAN_CLI extract-task {planIndex} .design/plan.json` (writes `.design/worker-task-{N}.json`).

**1f. Worker pool**: `python3 $PLAN_CLI worker-pool .design/plan.json`. Store `workers` and `totalWorkers`.

**1g. Summary data**: `python3 $PLAN_CLI summary .design/plan.json`. Store `goal`, `taskCount`, `maxDepth`.

**1h. Pre-flight validation**: Build a single Bash script that checks `git status --porcelain`, runs each blocking assumption's `verify` command, and tests `contextFiles` existence. Output JSON: `{"gitClean": bool, "blockingChecks": [...], "contextFilesValid": bool, "missingContextFiles": [...]}`.

---

## Step 2: Report and Spawn

**2a. Report** to user:
```
Executing: {goal}
Tasks: {taskCount} (depth: {maxDepth})
Workers: {totalWorkers} ({names})
Validation: {pass}/{total} blocking checks passed
```
Warn if git is dirty. If blocking checks failed: `AskUserQuestion` to fix or proceed. If resuming: "Resuming execution."

**2b. Spawn workers**: For each worker, spawn a persistent teammate:
```
Task(subagent_type: "general-purpose", team_name: "do-execute", name: "{worker.name}", model: "{worker.model}", prompt: <WORKER_PROMPT>)
```

Track `idleWorkers` (set) and `completedResults` (map).

---

## Step 3: Monitor

Event-driven loop — process worker messages as they arrive.

**On task completion**: Worker reports which task they finished and a brief summary.
1. Update plan.json: `echo '[{"planIndex": N, "status": "completed", "result": "..."}]' | python3 $PLAN_CLI update-status .design/plan.json`
2. Handle any `cascaded` entries by marking them completed in TaskList
3. Wake any idle workers by sending them a message to check for new tasks

**On task failure**: Worker reports which task failed and why.
1. Update plan.json: `echo '[{"planIndex": N, "status": "failed", "result": "..."}]' | python3 $PLAN_CLI update-status .design/plan.json`
2. Handle cascaded entries in TaskList
3. Check circuit breaker: `python3 $PLAN_CLI circuit-breaker .design/plan.json`. If `shouldAbort`: shut down all workers, go to Step 4.
4. Check retries: `python3 $PLAN_CLI retry-candidates .design/plan.json`. If retryable (attempts < 3): clean up partial work (`git checkout` + `rm`), re-extract task file, reset in TaskList, tell the worker to retry with failure context.

**On idle**: Worker reports no tasks available. Add to `idleWorkers`. Check completion.

**Completion check** (after each idle/completion):
1. `python3 $PLAN_CLI status-counts .design/plan.json`
2. If no pending tasks and all workers idle: shut down workers, go to Step 4
3. If pending tasks exist but all workers idle (deadlock): report deadlock, shut down, go to Step 4

**On peer issues**: Workers handle these directly. The lead does not intervene unless asked.

---

## Step 4: Final Verification

Build a single Bash script that for each completed task: checks created files exist (`test -f`), checks modified files in git log, runs each `acceptanceCriteria[].check`. Output JSON array with per-task results.

For verification failures with attempts < 3: update plan.json to failed, re-extract task, spawn a one-off retry worker with the RETRY_WORKER_PROMPT. For non-retryable: leave as failed.

---

## Step 5: Complete

**5a. Summary**: `python3 $PLAN_CLI status-counts .design/plan.json`. Display completed/failed/blocked/skipped counts with subjects. Recommend follow-ups for failures.

**5b. Archive**: If all completed: `mkdir -p .design/history && mv .design/plan.json ".design/history/$(date -u +%Y%m%dT%H%M%SZ)-plan.json"`. If partial: leave plan for resume.

**5c. Cleanup**: `rm -f .design/worker-task-*.json`, `TeamDelete(team_name: "do-execute")`.

---

## WORKER_PROMPT

```
You are {workerName}, a {role} on the do-execute team. You claim tasks, execute them, commit, and move to the next one.

Read ~/.claude/teams/do-execute/config.json to find the lead's name and your teammates.

## Work Loop

1. Check TaskList for pending, unblocked tasks. Prefer tasks matching your role ({role}).
2. If nothing available: tell the lead you're idle and wait. When the lead says to check again, go to step 1.
3. Claim a task (TaskUpdate to in_progress). Extract the planIndex from the subject ("Task N: ...").
4. Read .design/worker-task-<planIndex>.json — the task.prompt field has your instructions.
5. Execute the task. Run any pre-checks marked BLOCKING first — if they fail, report blocked to the lead.
6. Verify acceptance criteria from the prompt. Fix issues before proceeding.
7. Commit: git add <files from task.metadata.files>, git commit -m "task <N>: <subject>". Retry once on git lock errors.
8. Mark completed (TaskUpdate). Tell the lead which task you finished and what you did.
9. Go to step 1.

## If Something Goes Wrong

- Cannot complete a task: revert partial changes (git checkout/rm), reset the task to pending, tell the lead what failed and why.
- The lead may ask you to retry with additional context — follow their instructions.
- Found a bug in another worker's code: message that worker directly to fix it. CC the lead. Continue your work, working around the issue.
- Another worker reports a bug in your code: fix it, commit, and confirm.

## Rules

- Execute silently — no narration.
- One commit per task.
- Always verify acceptance criteria before reporting done.
```

## RETRY_WORKER_PROMPT

```
You are retrying a previously failed task on the do-execute team.

1. Read .design/worker-task-{planIndex}.json (or fall back to .design/plan.json tasks[{planIndex}]).
2. Verify the task subject contains "{taskSubject}". If not, report a mismatch to the lead and stop.
3. Execute the task from the prompt field, applying retry context below.

Attempt {attempts} of 3. Previous failure: {failureReason}. Fallback strategy: {fallbackStrategy}.

The previous attempt failed — do not repeat the same approach. Use the fallback strategy if provided.

4. Verify acceptance criteria, commit (git add + git commit -m "task {planIndex}: {taskSubject} (retry {attempts})").
5. Read ~/.claude/teams/do-execute/config.json for the lead's name. Report result to the lead: what you did, whether it succeeded or failed.
```

**Arguments**: $ARGUMENTS
