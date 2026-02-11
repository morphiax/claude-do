---
name: execute
description: "Execute a plan from /design with validation, dependency-graph scheduling, and single-file state tracking."
argument-hint: ""
---

# Execute

Execute a `.design/plan.json` using dependency-graph scheduling with worker teammates. The lead (main conversation) computes ready-sets dynamically from `blockedBy` dependencies, spawning each batch of ready tasks as worker teammates in a round. Workers report results via `SendMessage` and are shut down after each round.

**Workflow guard**: Execute the Orchestration Flow (Steps 1-4) as written. Do NOT use `EnterPlanMode` — this skill IS the execution plan. Proceed directly to Step 1: Setup.

- **Signaling**: Workers signal completion via `SendMessage(type: "message")` to the lead. The lead parses JSON from message content.

**Lead responsibilities**:

- Plan reading, validation, and TaskList creation (inline — no subagent)
- `TeamCreate` / `TeamDelete` for team lifecycle
- Spawn worker teammates and collect results via `SendMessage`
- Verify results (spot-checks + acceptance criteria via batched Bash)
- Update `.design/plan.json` (status, trimming, cascading failures)
- `git add` + `git commit`
- `AskUserQuestion` (user interaction)
- Circuit breaker evaluation
- Compute ready-sets and manage round progression
- Assemble retry prompts for failed tasks
- Shutdown workers after each round via `SendMessage(type: "shutdown_request")`

**MANDATORY: The lead's ONLY tools are: `TeamCreate`, `TeamDelete`, `TaskCreate`, `TaskUpdate`, `TaskList`, `SendMessage`, `Task` (spawn worker teammates), `AskUserQuestion`, and `Bash` (`python3 $PLAN_CLI` invocations, verification scripts, `git add`/`git commit`, file cleanup). No other tools — no MCP tools, no `Grep`, no `Glob`, no `LSP`, no source file reads. If you are tempted to execute a task directly — STOP. Spawn a worker.**

**Do NOT poll**: Teammate messages are auto-delivered — never use `sleep`, `ls`, or Bash loops to check for worker output. Simply wait; the next message you receive will be from a teammate or the system.

### Conventions

- **Silent execution**: Do NOT narrate worker progress. No per-worker status updates, no "waiting for tasks", no "Task X completed". The ONLY user-facing output is the round summary at Step 3h. Between spawning workers and the round summary, output nothing.

### Script Setup

Resolve the plugin root directory (the directory containing `.claude-plugin/` and `skills/`). Set `PLAN_CLI` to the skill-local plan helper script:

```
PLAN_CLI = {plugin_root}/skills/execute/scripts/plan.py
```

All deterministic operations use: `python3 $PLAN_CLI <command> [args]` via Bash. Parse JSON output. Every command outputs `{"ok": true/false, ...}` to stdout.

---

## Orchestration Flow

### Step 1: Setup (Inline)

Read and validate `.design/plan.json`, run batch validation, create team and TaskList. This is mechanical — no subagent needed.

#### 1a. Read and Validate Plan

Run: `python3 $PLAN_CLI validate .design/plan.json` via Bash. Parse JSON output.

- If `ok` is false:
  - `error` is `not_found`: tell user "No plan found. Run `/design <goal>` first." and stop.
  - `error` is `bad_schema`: tell user the plan uses an unsupported schema version and v3 is required, then stop.
  - `error` is `empty_tasks`: tell user the plan contains no tasks and to re-run `/design`, then stop.

#### 1b. Resume Detection

Run: `python3 $PLAN_CLI status-counts .design/plan.json` via Bash. Parse JSON output. Set `isResume` from the output's `isResume` field.

If `isResume` is true:

Run: `python3 $PLAN_CLI resume-reset .design/plan.json` via Bash. Parse JSON output. For each entry in `resetTasks`: revert uncommitted changes via `git checkout -- {filesToRevert}` and delete partial files via `rm -f {filesToDelete}`.

**Resume-nothing-to-do check**: If `noWorkRemaining` is true, tell user "All tasks are already resolved — nothing to do." and stop.

#### 1c. Create Team

1. `TeamDelete(team_name: "do-execute")` (ignore errors — cleanup of stale team)
2. `TeamCreate(team_name: "do-execute")`. If it fails, tell user: "Agent Teams is required for /do:execute. Ensure your Claude Code version supports Agent Teams and retry." Then STOP.

#### 1d. Extract File Overlap Matrix

Run: `python3 $PLAN_CLI overlap-matrix .design/plan.json` via Bash. Parse JSON output. Store the `matrix` field as `fileOverlapMatrix`: a mapping from planIndex to array of conflicting planIndices.

#### 1e. Batch Validation

Build a single Bash script that:

1. Runs `git status --porcelain` and captures output
2. For each task with `agent.assumptions` where severity is `blocking`: runs the `verify` command and captures exit code + output
3. For each `agent.contextFiles` entry: tests path existence with `test -e`
4. Outputs a single JSON object to stdout: `{"gitClean": bool, "gitStatus": "...", "blockingChecks": [{"taskIndex": N, "claim": "...", "passed": bool, "output": "..."}], "contextFilesValid": bool, "missingContextFiles": ["..."]}`

Run this script in one Bash call and parse the JSON output. Store as `validation`.

#### 1f. Create TaskList

The TaskList is a derived view for user-facing visibility. `.design/plan.json` is authoritative. The TaskList uses only valid statuses (`pending` | `in_progress` | `completed`). Detailed status (`failed` | `blocked` | `skipped`) is tracked exclusively in `.design/plan.json`.

Run: `python3 $PLAN_CLI tasklist-data .design/plan.json` via Bash. Parse JSON output. For each entry in the `tasks` array:

1. `TaskCreate` with `subject`, `description`, `activeForm`
2. Record the returned ID in `taskIdMapping` (planIndex → taskId)

After creating all tasks, wire dependencies:

- For each entry with non-empty `blockedBy`: `TaskUpdate(taskId, addBlockedBy: [taskIdMapping[dep] for dep in blockedBy])`

If resuming: mark entries with `status` of `completed` via `TaskUpdate(status: "completed")`.

#### 1g. Compute Summary

Run: `python3 $PLAN_CLI summary .design/plan.json` via Bash. Parse JSON output. Store `goal`, `taskCount`, `maxDepth`, `depthSummary`, and `modelDistribution` from the output.

Store all computed data (`goal`, `isResume`, `validation`, `taskIdMapping`, `fileOverlapMatrix`, `taskCount`, `maxDepth`, `depthSummary`) as **setup data** — referenced by later steps.

### Step 2: Report Validation

Using the setup data's `validation` field, display to the user:

```
Executing: {goal}
Tasks: {taskCount} (max dependency depth: {maxDepth})
Validation: {pass_count}/{total_count} blocking checks passed
```

If `validation.gitClean` is false, warn about uncommitted changes.

If any blocking checks failed, show them and use `AskUserQuestion` to let the user fix or proceed anyway.

If `isResume` is true, report: "Resuming execution."

### Step 3: Execute by Ready-Set Rounds

Initialize `roundNumber` to 1. Maintain a `completedResults` map (planIndex → result string) across all rounds. Track `activeWorkers` (list of worker names spawned in current round).

**Main loop**: While there are tasks with `pending` status in the setup data's `taskIdMapping`:

#### 3a. Compute Ready Set

Run: `python3 $PLAN_CLI ready-set .design/plan.json` via Bash. Parse JSON output.

**Deadlock detection**: If `isDeadlock` is true, abort with: "Deadlock detected: {pendingCount} tasks remain but none are ready. Remaining tasks depend on failed or blocked predecessors." Proceed to Step 4.

Use the `ready` array for this round's tasks. Use setup data for task metadata (taskIdMapping, fileOverlapMatrix). Reset `activeWorkers` to empty.

#### 3b. Spawn Worker Teammates

**Pre-extract worker tasks**: For each task in the ready set, run: `python3 $PLAN_CLI extract-task {planIndex} .design/plan.json` via Bash. This writes `.design/worker-task-{planIndex}.json` containing the task data and plan-level context.

For each task in the ready set:

1. Mark as in progress: `TaskUpdate(taskId: {ID}, status: "in_progress")`
2. **Assemble dependency results**: If the task has `blockedBy` entries, build a dependency results block from the `completedResults` map:

   ```
   Dependency results (from prior tasks):
   - Task {index}: {result from the completedResults map for that task}
   ```

3. Spawn a worker teammate with a bootstrap prompt — workers read their instructions from a pre-extracted task file:

```
Task:
  subagent_type: "general-purpose"
  team_name: "do-execute"
  name: "worker-{planIndex}"
  model: {task model from ready-set output}
  prompt: <WORKER_PROMPT assembled from template below, with {planIndex} and {taskSubject} filled, dependency results appended if present>
```

4. Add `"worker-{planIndex}"` to `activeWorkers`.

**Parallel safety**: Check the setup data's `fileOverlapMatrix`. If any tasks in this ready set have file overlaps with each other, spawn those conflicting tasks sequentially (wait for one to complete before spawning the next). Spawn all non-conflicting tasks in parallel in a single response.

#### 3c. Collect Results

**Wait** for `SendMessage` from each worker in `activeWorkers`. Each worker sends a JSON message with `planIndex`, `status` (COMPLETED|FAILED|BLOCKED), and `result`.

Track received count vs expected count. Once all workers have reported, proceed to verification.

#### 3d. Verify Results

After all batch workers report, parse each worker's `SendMessage` content as JSON.

**Spot-check and acceptance in one batched Bash script**: Build a single Bash script that, for each task in the batch:

1. If COMPLETED: spot-check created files (`test -f {path}` for each `metadata.files.create`), check modified files appear in `git diff --name-only`, run each `acceptanceCriteria[].check` command
2. Output one JSON object per task: `{"planIndex": N, "status": "completed|failed|blocked", "result": "...", "spotCheckPassed": bool, "acceptancePassed": bool, "failures": ["..."]}`

Wrap all per-task objects in a JSON array and output to stdout. Run this script in one Bash call.

**Interpret results**: For each task:
- COMPLETED + all checks passed → completed
- COMPLETED + spot-check or acceptance failed → override to failed (use failure details as reason)
- FAILED → failed (use status line reason)
- BLOCKED → blocked

#### 3e. Update Plan State

Build a JSON array of results from 3d: `[{"planIndex": N, "status": "completed|failed|blocked", "result": "..."}]`.

Run: `echo '<results JSON>' | python3 $PLAN_CLI update-status .design/plan.json` via Bash. Parse JSON output.

The script handles status updates, progressive trimming (strips verbose fields from completed tasks), cascading failures (tasks depending on failed/blocked tasks are set to `skipped`), and writes the updated plan.

Record any `cascaded` entries (skipped planIndices and reasons) for the round summary.

#### 3f. Handle Retries

Run: `python3 $PLAN_CLI retry-candidates .design/plan.json` via Bash. Parse JSON output.

For each entry in the `retryable` array:

1. Clean up partial work: `git checkout -- {metadata.files.modify}` and `rm -f {metadata.files.create}` (extract file paths from plan.json metadata for the task at `planIndex`)
2. Assemble retry prompt from the **RETRY_WORKER_PROMPT** template below with `{planIndex}`, `{taskSubject}`, `{attempts}`, `{failureReason}`, and `{fallbackStrategy}` filled
3. Spawn retry worker teammate:

```
Task:
  subagent_type: "general-purpose"
  team_name: "do-execute"
  name: "retry-{planIndex}"
  model: {same model as original task}
  prompt: <RETRY_WORKER_PROMPT filled>
```

4. Add `"retry-{planIndex}"` to `activeWorkers`
5. After retry worker reports via `SendMessage`, repeat verification (3d) and plan update (3e) for just that task

Repeat until no retryable tasks remain or all have reached 3 attempts.

#### 3g. Shutdown Round Workers

For each worker name in `activeWorkers`: `SendMessage(type: "shutdown_request", recipient: "{worker_name}")`. Wait for confirmations.

#### 3h. Round Summary

Display: `Round {roundNumber}: {completed}/{total_in_batch} tasks ({total_completed_overall}/{taskCount} overall)` + per-task status.

Update `completedResults` map with completed task results. Mark completed tasks in TaskList via `TaskUpdate(status: "completed")`. Mark skipped tasks as completed in TaskList. Remove completed and skipped from pending set.

#### 3i. Git Commit

Run: `python3 $PLAN_CLI collect-files .design/plan.json --indices {comma-separated planIndices of completed tasks in this round}` via Bash. Parse JSON output.

If `allFiles` is not empty: `git add {allFiles} && git commit -m "{round summary}"`. Skip if empty (research-only tasks).

**Clean up worker task files**: Run `rm -f .design/worker-task-*.json` via Bash to remove ephemeral pre-extracted task files from this round.

#### 3j. Circuit Breaker

Run: `python3 $PLAN_CLI circuit-breaker .design/plan.json` via Bash. Parse JSON output.

If `shouldAbort` is true, display `reason` and proceed to Step 4.

Increment `roundNumber` and continue the main loop.

### Step 4: Complete

After all rounds (or after circuit breaker abort or deadlock):

1. `TaskList` to confirm final statuses
2. Run: `python3 $PLAN_CLI status-counts .design/plan.json` via Bash. Parse JSON output to get per-status counts. Display summary:
   - Completed: {counts.completed}
   - Failed: {counts.failed} — {subjects}
   - Blocked: {counts.blocked} — {subjects}
   - Skipped: {counts.skipped} — {subjects}
   - Follow-up recommendations if any failures

3. If fully successful (all tasks completed): archive completed plan to history: `mkdir -p .design/history && mv .design/plan.json ".design/history/$(date -u +%Y%m%dT%H%M%SZ)-plan.json"`. Return "All {count} tasks completed."
4. If partial: leave `.design/plan.json` for resume. Return "Execution incomplete. {done}/{total} completed."
5. `TeamDelete(team_name: "do-execute")` (ignore errors — cleanup)

---

## Worker Prompt Templates

### WORKER_PROMPT

```
You are a worker on an execution team. Read your task instructions and execute them. Report results via SendMessage.

## Bootstrap — Self-Read Instructions

1. Read `.design/worker-task-{planIndex}.json`. If this file does not exist, fall back to reading `.design/plan.json` and extract `tasks[{planIndex}]` (the element at 0-based array index {planIndex}).
2. **Verify**: the task's `subject` must contain "{taskSubject}". If it does not, STOP and report BLOCKED via SendMessage below with result "Bootstrap mismatch — expected '{taskSubject}' at tasks[{planIndex}]".
3. Your full task instructions are in the `prompt` field of that task (at `task.prompt` in the worker-task file, or `tasks[{planIndex}].prompt` in plan.json).
4. If dependency results appear below, find the placeholder line `[Dependency results — deferred: lead appends actual results at spawn time]` in the prompt and replace it with the dependency results section below.
5. Execute the task instructions from the prompt field.

## Reporting

When done, read ~/.claude/teams/do-execute/config.json for the lead's name, then report your result:

    SendMessage(type: "message", recipient: {lead-name}, content: '{"planIndex": {planIndex}, "status": "COMPLETED|FAILED|BLOCKED", "result": "brief description of what was done or why it failed"}', summary: "Task {planIndex}: done")

Use exactly one of: COMPLETED (task succeeded), FAILED (task attempted but failed), BLOCKED (task cannot proceed due to external issue).
```

### RETRY_WORKER_PROMPT

```
You are a worker on an execution team, retrying a previously failed task. Read your task instructions and execute them with the retry context below. Report results via SendMessage.

## Bootstrap — Self-Read Instructions

1. Read `.design/worker-task-{planIndex}.json`. If this file does not exist, fall back to reading `.design/plan.json` and extract `tasks[{planIndex}]` (the element at 0-based array index {planIndex}).
2. **Verify**: the task's `subject` must contain "{taskSubject}". If it does not, STOP and report BLOCKED via SendMessage below with result "Bootstrap mismatch — expected '{taskSubject}' at tasks[{planIndex}]".
3. Your full task instructions are in the `prompt` field of that task (at `task.prompt` in the worker-task file, or `tasks[{planIndex}].prompt` in plan.json).
4. If dependency results appear below, find the placeholder line `[Dependency results — deferred: lead appends actual results at spawn time]` in the prompt and replace it with the dependency results section below.
5. Execute the task instructions from the prompt field, applying the retry context.

## Retry Context

- **Attempt**: {attempts} of 3
- **Previous failure**: {failureReason}
- **Fallback strategy**: {fallbackStrategy}

IMPORTANT: The previous attempt failed. Review the failure reason carefully. If a fallback strategy is provided, use it instead of the primary approach. Avoid repeating the same approach that failed.

## Reporting

When done, read ~/.claude/teams/do-execute/config.json for the lead's name, then report your result:

    SendMessage(type: "message", recipient: {lead-name}, content: '{"planIndex": {planIndex}, "status": "COMPLETED|FAILED|BLOCKED", "result": "brief description of what was done or why it failed"}', summary: "Task {planIndex}: done")

Use exactly one of: COMPLETED (task succeeded), FAILED (task attempted but failed), BLOCKED (task cannot proceed due to external issue).
```

**Arguments**: $ARGUMENTS
