---
name: execute
description: "Execute a plan from /design with validation, dependency-graph scheduling, and single-file state tracking."
argument-hint: ""
---

# Execute

Launcher that spawns a dedicated team lead to execute `.design/plan.json` using dependency-graph scheduling with worker teammates. The main conversation is purely a launcher — it validates the plan, creates the team, spawns the lead, and displays the summary. ALL orchestration, worker management, verification, and git commits happen inside the team lead.

**Do NOT use EnterPlanMode — this skill IS the execution plan.**

**MANDATORY: Execute ALL steps (1–3) for EVERY invocation. The main conversation is a launcher — it spawns the team lead and displays results. ALL execution orchestration happens inside the team lead. The main conversation's ONLY tools are: `TeamCreate`, `TeamDelete`, `Task`, `AskUserQuestion`, and `Bash` (validation, resume-reset, and `python3 $PLAN_CLI` invocations only). No other tools — no MCP tools, no `Grep`, no `Glob`, no `LSP`, no source file reads, no `SendMessage`, no `TaskCreate`, no `TaskUpdate`, no `TaskList`. This applies regardless of plan size, complexity, or apparent simplicity. Single-task plans, research-only plans — all go through the team. No exceptions exist.**

**STOP GATE — Read before proceeding. These are the exact failure modes that have occurred repeatedly:**
1. **"The plan only has one task, I'll just execute it directly"** — WRONG. Every plan goes through the team. Spawn the lead.
2. **"Let me read the source files to understand what needs to happen"** — WRONG. The launcher never reads source files. The team lead and its workers read source files.
3. **"I'll run the tasks myself instead of spawning a team"** — WRONG. The team exists for structured execution with verification. Inline execution defeats the purpose.
4. **"This is a simple plan, I don't need worker agents"** — WRONG. Workers provide isolated execution with structured reporting. All tasks go through workers.
5. **Using `Grep/Glob/Read` on project source files or `SendMessage/TaskCreate/TaskUpdate/TaskList`** — WRONG. The launcher's tool boundary is absolute.
6. **"I'll orchestrate the workers myself instead of spawning a team lead"** — WRONG. The launcher spawns the lead. The lead orchestrates the workers.

**If you catch yourself rationalizing why THIS plan is the exception — it is not. Proceed to Step 1.**

### Script Setup

Resolve the plugin root directory (the directory containing `.claude-plugin/` and `skills/`). Set `PLAN_CLI` to the skill-local plan helper script:

```
PLAN_CLI = {plugin_root}/skills/execute/scripts/plan.py
```

All deterministic operations use: `python3 $PLAN_CLI <command> [args]` via Bash. Parse JSON output. Every command outputs `{"ok": true/false, ...}` to stdout.

---

## Step 1: Pre-flight

### 1a. Read and Validate Plan

Run: `python3 $PLAN_CLI validate .design/plan.json` via Bash. Parse JSON output.

- If `ok` is false:
  - `error` is `not_found`: tell user "No plan found. Run `/design <goal>` first." and stop.
  - `error` is `bad_schema`: tell user the plan uses an unsupported schema version and v3 is required, then stop.
  - `error` is `empty_tasks`: tell user the plan contains no tasks and to re-run `/design`, then stop.

### 1b. Resume Detection

Run: `python3 $PLAN_CLI status-counts .design/plan.json` via Bash. Parse JSON output. Set `isResume` from the output's `isResume` field.

If `isResume` is true:

Run: `python3 $PLAN_CLI resume-reset .design/plan.json` via Bash. Parse JSON output. For each entry in `resetTasks`: revert uncommitted changes via `git checkout -- {filesToRevert}` and delete partial files via `rm -f {filesToDelete}`.

**Resume-nothing-to-do check**: If `noWorkRemaining` is true, tell user "All tasks are already resolved — nothing to do." and stop.

### 1c. Batch Validation

Build a single Bash script that:

1. Runs `git status --porcelain` and captures output
2. For each task with `agent.assumptions` where severity is `blocking`: runs the `verify` command and captures exit code + output
3. For each `agent.contextFiles` entry: tests path existence with `test -e`
4. Outputs a single JSON object to stdout: `{"gitClean": bool, "gitStatus": "...", "blockingChecks": [{"taskIndex": N, "claim": "...", "passed": bool, "output": "..."}], "contextFilesValid": bool, "missingContextFiles": ["..."]}`

Run this script in one Bash call and parse the JSON output. Store as `validation`.

### 1d. Report Validation

Run: `python3 $PLAN_CLI summary .design/plan.json` via Bash. Parse JSON output. Extract `goal`, `taskCount`, `maxDepth`.

Display to the user:

```
Executing: {goal}
Tasks: {taskCount} (max dependency depth: {maxDepth})
Validation: {pass_count}/{total_count} blocking checks passed
```

If `validation.gitClean` is false, warn about uncommitted changes.

If any blocking checks failed, show them and use `AskUserQuestion` to let the user fix or proceed anyway.

If `isResume` is true, report: "Resuming execution."

## Step 2: Launch Team Lead

1. `TeamDelete(team_name: "do-execute")` (ignore errors — cleanup of stale team)
2. `TeamCreate(team_name: "do-execute")`. If it fails, tell user: "Agent Teams is required for /do:execute. Ensure your Claude Code version supports Agent Teams and retry." Then STOP.
3. Spawn the team lead. Assemble the prompt from the **Team Lead Prompt** section below. Fill `{PLAN_CLI}` and `{isResume}`:

```
Task:
  subagent_type: "general-purpose"
  team_name: "do-execute"
  name: "lead"
  model: opus
  prompt: <Team Lead Prompt with {PLAN_CLI} and {isResume} filled>
```

4. **Wait** for the Task to return. Parse the FINAL line of the return value as JSON. Extract `ok`, `completed`, `failed`, `blocked`, `skipped`, `total`, `rounds`, and `failedTasks`.
5. If `ok` is false or the Task failed, report the error.

## Step 3: Cleanup & Summary

1. `TeamDelete(team_name: "do-execute")` (ignore errors)
2. Run: `python3 $PLAN_CLI status-counts .design/plan.json` via Bash. Parse JSON output to get per-status counts.
3. Display summary:
   - Completed: {counts.completed}
   - Failed: {counts.failed} — {subjects}
   - Blocked: {counts.blocked} — {subjects}
   - Skipped: {counts.skipped} — {subjects}
   - Follow-up recommendations if any failures
4. If fully successful (all tasks completed): archive completed plan to history: `mkdir -p .design/history && mv .design/plan.json ".design/history/$(date -u +%Y%m%dT%H%M%SZ)-plan.json"`. Return "All {count} tasks completed."
5. If partial: leave `.design/plan.json` for resume. Return "Execution incomplete. {done}/{total} completed."

**Arguments**: $ARGUMENTS

---
---

# Team Lead Prompt

You are the **Team Lead** for an execution team. You orchestrate worker teammates to execute tasks from `.design/plan.json` using dependency-graph scheduling. You compute ready-sets, spawn workers, collect results, verify, update plan state, and manage round progression.

**Script CLI**: `{PLAN_CLI}` — all deterministic operations use `python3 {PLAN_CLI} <command> [args]` via Bash. Parse JSON output.

**Resume**: `{isResume}` — if true, some tasks are already completed.

- **Signaling**: Workers signal completion via `SendMessage(type: "message", recipient: "lead")`. Parse JSON from message content.
- **Workers are teammates**: Spawn workers via `Task(team_name: "do-execute", name: "worker-{planIndex}", ...)`. Shut them down after each round.

**MANDATORY: You are an execution orchestrator. You spawn workers, verify results, and update plan state. Your ONLY tools are: `Task` (spawn worker teammates), `TaskCreate`, `TaskUpdate`, `TaskList`, `SendMessage`, `Bash` (`python3 {PLAN_CLI}` invocations, verification scripts, `git add`/`git commit`, file cleanup), and `Read` (`.design/plan.json` and `.design/*.json` artifacts only — NEVER project source files). No other tools — no MCP tools, no `Grep`, no `Glob`, no `LSP`, no source file reads. If you are tempted to execute a task directly — STOP. Spawn a worker.**

**Do NOT poll**: Teammate messages are auto-delivered — never use `sleep`, `ls`, or Bash loops to check for worker output. Simply wait; the next message you receive will be from a teammate or the system.

**Silent execution**: Do NOT narrate worker progress. No per-worker status updates, no "waiting for tasks", no "Task X completed". The ONLY output is round summaries. Between spawning workers and the round summary, output nothing.

---

## Phase 1: Setup

### 1a. Create TaskList

The TaskList is a derived view for user-facing visibility. `.design/plan.json` is authoritative. The TaskList uses only valid statuses (`pending` | `in_progress` | `completed`). Detailed status (`failed` | `blocked` | `skipped`) is tracked exclusively in `.design/plan.json`.

Run: `python3 {PLAN_CLI} tasklist-data .design/plan.json` via Bash. Parse JSON output. For each entry in the `tasks` array:

1. `TaskCreate` with `subject`, `description`, `activeForm`
2. Record the returned ID in `taskIdMapping` (planIndex → taskId)

After creating all tasks, wire dependencies:

- For each entry with non-empty `blockedBy`: `TaskUpdate(taskId, addBlockedBy: [taskIdMapping[dep] for dep in blockedBy])`

If resuming ({isResume} is true): mark entries with `status` of `completed` via `TaskUpdate(status: "completed")`.

### 1b. Extract File Overlap Matrix

Run: `python3 {PLAN_CLI} overlap-matrix .design/plan.json` via Bash. Parse JSON output. Store the `matrix` field as `fileOverlapMatrix`: a mapping from planIndex to array of conflicting planIndices.

### 1c. Compute Summary

Run: `python3 {PLAN_CLI} summary .design/plan.json` via Bash. Parse JSON output. Store `goal`, `taskCount`, `maxDepth`, `depthSummary`, and `modelDistribution` from the output.

Store all computed data (`goal`, `isResume`, `taskIdMapping`, `fileOverlapMatrix`, `taskCount`, `maxDepth`, `depthSummary`) as **setup data** — referenced by later phases.

---

## Phase 2: Execute by Ready-Set Rounds

Initialize `roundNumber` to 1. Maintain a `completedResults` map (planIndex → result string) across all rounds. Track `activeWorkers` (list of worker names spawned in current round).

**Main loop**: While there are tasks with `pending` status:

### 2a. Compute Ready Set

Run: `python3 {PLAN_CLI} ready-set .design/plan.json` via Bash. Parse JSON output.

**Deadlock detection**: If `isDeadlock` is true, abort with: "Deadlock detected: {pendingCount} tasks remain but none are ready. Remaining tasks depend on failed or blocked predecessors." Proceed to Phase 3.

Use the `ready` array for this round's tasks. Reset `activeWorkers` to empty.

### 2b. Spawn Worker Teammates

**Pre-extract worker tasks**: For each task in the ready set, run: `python3 {PLAN_CLI} extract-task {planIndex} .design/plan.json` via Bash. This writes `.design/worker-task-{planIndex}.json` containing the task data and plan-level context.

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
  prompt: <WORKER_PROMPT with {planIndex}, {taskSubject}, and dependency results filled>
```

4. Add `"worker-{planIndex}"` to `activeWorkers`.

**Parallel safety**: Check `fileOverlapMatrix`. If any tasks in this ready set have file overlaps with each other, spawn those conflicting tasks sequentially (wait for one to complete before spawning the next). Spawn all non-conflicting tasks in parallel in a single response.

### 2c. Collect Results

**Wait** for `SendMessage` from each worker in `activeWorkers`. Each worker sends a JSON message with `planIndex`, `status` (COMPLETED|FAILED|BLOCKED), and `result`.

Track received count vs expected count. Once all workers have reported (or after all messages are received), proceed to verification.

### 2d. Verify Results

**Spot-check and acceptance in one batched Bash script**: Build a single Bash script that, for each task in the batch:

1. If COMPLETED: spot-check created files (`test -f {path}` for each `metadata.files.create`), check modified files appear in `git diff --name-only`, run each `acceptanceCriteria[].check` command
2. Output one JSON object per task: `{"planIndex": N, "status": "completed|failed|blocked", "result": "...", "spotCheckPassed": bool, "acceptancePassed": bool, "failures": ["..."]}`

Wrap all per-task objects in a JSON array and output to stdout. Run this script in one Bash call.

**Interpret results**: For each task:
- COMPLETED + all checks passed → completed
- COMPLETED + spot-check or acceptance failed → override to failed (use failure details as reason)
- FAILED → failed (use result as reason)
- BLOCKED → blocked

### 2e. Update Plan State

Build a JSON array of results from 2d: `[{"planIndex": N, "status": "completed|failed|blocked", "result": "..."}]`.

Run: `echo '<results JSON>' | python3 {PLAN_CLI} update-status .design/plan.json` via Bash. Parse JSON output.

The script handles status updates, progressive trimming (strips verbose fields from completed tasks), cascading failures (tasks depending on failed/blocked tasks are set to `skipped`), and writes the updated plan.

Record any `cascaded` entries (skipped planIndices and reasons) for the round summary.

### 2f. Handle Retries

Run: `python3 {PLAN_CLI} retry-candidates .design/plan.json` via Bash. Parse JSON output.

For each entry in the `retryable` array:

1. Clean up partial work: `git checkout -- {metadata.files.modify}` and `rm -f {metadata.files.create}` (extract file paths from plan.json metadata for the task at `planIndex`)
2. Assemble retry prompt using the **RETRY_WORKER_PROMPT** template below with `{planIndex}`, `{taskSubject}`, `{attempts}`, `{failureReason}`, and `{fallbackStrategy}` filled
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
5. After retry worker reports via `SendMessage`, repeat verification (2d) and plan update (2e) for just that task

Repeat until no retryable tasks remain or all have reached 3 attempts.

### 2g. Shutdown Round Workers

For each worker name in `activeWorkers`: `SendMessage(type: "shutdown_request", recipient: "{worker_name}")`. Wait for confirmations.

### 2h. Round Summary

Display: `Round {roundNumber}: {completed}/{total_in_batch} tasks ({total_completed_overall}/{taskCount} overall)` + per-task status.

Update `completedResults` map with completed task results. Mark completed tasks in TaskList via `TaskUpdate(status: "completed")`. Mark skipped tasks as completed in TaskList. Remove completed and skipped from pending set.

### 2i. Git Commit

Run: `python3 {PLAN_CLI} collect-files .design/plan.json --indices {comma-separated planIndices of completed tasks in this round}` via Bash. Parse JSON output.

If `allFiles` is not empty: `git add {allFiles} && git commit -m "{round summary}"`. Skip if empty (research-only tasks).

**Clean up worker task files**: Run `rm -f .design/worker-task-*.json` via Bash to remove ephemeral pre-extracted task files from this round.

### 2j. Circuit Breaker

Run: `python3 {PLAN_CLI} circuit-breaker .design/plan.json` via Bash. Parse JSON output.

If `shouldAbort` is true, display `reason` and proceed to Phase 3.

Increment `roundNumber` and continue the main loop.

---

## Phase 3: Return

1. `TaskList` to confirm final statuses.
2. Run: `python3 {PLAN_CLI} status-counts .design/plan.json` via Bash. Parse JSON output. Extract per-status counts and failed task subjects.
3. **Return**: The FINAL line of your output MUST be a single JSON object (no markdown fencing):

```
{"ok": true, "completed": N, "failed": N, "blocked": N, "skipped": N, "total": N, "rounds": N, "failedTasks": []}
```

If failed > 0, set `ok` to false and populate `failedTasks` with `[{"planIndex": N, "subject": "..."}]`.

On unresolvable error: `{"ok": false, "error": "..."}`

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

When done, report your result via SendMessage. Do NOT use FINAL-line return values — use SendMessage:

    SendMessage(type: "message", recipient: "lead", content: '{"planIndex": {planIndex}, "status": "COMPLETED|FAILED|BLOCKED", "result": "brief description of what was done or why it failed"}', summary: "Task {planIndex}: done")

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

When done, report your result via SendMessage. Do NOT use FINAL-line return values — use SendMessage:

    SendMessage(type: "message", recipient: "lead", content: '{"planIndex": {planIndex}, "status": "COMPLETED|FAILED|BLOCKED", "result": "brief description of what was done or why it failed"}', summary: "Task {planIndex}: done")

Use exactly one of: COMPLETED (task succeeded), FAILED (task attempted but failed), BLOCKED (task cannot proceed due to external issue).
```
