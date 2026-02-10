---
name: execute
description: "Execute a plan from /design with validation, dependency-graph scheduling, and single-file state tracking."
argument-hint: ""
---

# Execute

Execute a `.design/plan.json` using dependency-graph scheduling with Task subagents. The lead computes ready-sets dynamically from `blockedBy` dependencies, spawning each batch of ready tasks as a round. The lead is a thin orchestrator — it delegates plan bootstrap to a setup subagent and performs verification, plan updates, and retries inline.

**Workflow guard**: Execute the Orchestration Flow (Steps 1-4) as written. Do NOT use `EnterPlanMode` — this skill IS the execution plan. Proceed directly to Step 1: Setup.

**Lead responsibilities**:

- Spawn task subagents and collect return values
- Verify results (spot-checks + acceptance criteria via batched Bash)
- Update `.design/plan.json` (status, trimming, cascading failures)
- `git add` + `git commit`
- `AskUserQuestion` (user interaction)
- Circuit breaker evaluation
- Compute ready-sets and manage round progression
- Assemble retry prompts for failed tasks

**Delegated to setup subagent only**:

- Plan reading, validation, TaskList creation → Setup Subagent

### Conventions

- **FINAL-line**: Every subagent's last line of output is its structured return value (JSON object or status line, no markdown fencing). The lead parses only this line.

---

## Setup Subagent (Plan Bootstrap)

Reads and validates plan, creates TaskList. Spawn once at the start. Model: sonnet.

```
Task:
  subagent_type: "general-purpose"
  model: sonnet
  prompt: <assembled from template below>
```

**Setup subagent prompt template** — assemble by concatenating these sections in order:

1. **Role and mission**:

   ```
   You are a plan bootstrap agent. Your job is to read .design/plan.json, validate it, and create the TaskList for progress tracking. You produce structured JSON output — you do NOT execute any tasks.
   ```

2. **Plan reading instructions**:

   ```
   ## Step 1: Read Plan

   Read `.design/plan.json` from the project root.

   - If not found: return JSON with error field set to no_plan
   - If found: parse JSON.
     - If schemaVersion is not 3: return JSON with error field set to schema_version and version set to the actual version number
     - If tasks array is empty: return JSON with error field set to empty_tasks
     - Resume detection: if any task has status other than pending (e.g., completed, failed, blocked, skipped, in_progress), this is a resume. Reset any tasks with status in_progress back to pending (increment their attempts count). For each in_progress task being reset, clean up partial artifacts: revert uncommitted changes to metadata.files.modify files via git checkout -- {files} and delete partially created metadata.files.create files via rm -f {files}. For each completed task on resume, verify its metadata.files.create entries exist and its metadata.files.modify entries are committed. If verification fails, reset to pending. Write the updated plan back to .design/plan.json.
     - Extract file overlap matrix: for each task, read its `fileOverlaps` array (populated by design). Build a mapping from planIndex to array of conflicting planIndices.
   ```

3. **Validation instructions**:

   ```
   ## Step 2: Batch Validation

   Build a single Bash script that performs all validation in one invocation. The script:

   1. Runs `git status --porcelain` and captures output
   2. For each task with agent.assumptions where severity is blocking: runs the verify command and captures exit code + output
   3. For each agent.contextFiles entry: tests path existence with `test -e`
   4. Outputs a single JSON object to stdout with the combined results:
      {"gitClean": bool, "gitStatus": "...", "blockingChecks": [{"taskIndex": N, "claim": "...", "passed": bool, "output": "..."}], "contextFilesValid": bool, "missingContextFiles": ["..."]}

   Run this script in one Bash call and parse the JSON output.
   ```

4. **TaskList creation instructions**:

   ```
   ## Step 3: Create Task List

   The TaskList is a derived view for user-facing visibility. .design/plan.json is authoritative.

   The TaskList uses only valid statuses (pending | in_progress | completed). Detailed status (failed | blocked | skipped) is tracked exclusively in .design/plan.json.

   For each task in .design/plan.json, create a tracked task:

   id = TaskCreate:
     subject: {task.subject}
     description: {task.description}
     activeForm: {task.activeForm}

   Build an explicit planIndex-to-taskId mapping from the returned IDs.

   After creating all tasks, wire dependencies:

   TaskUpdate:
     taskId: {planIndex-to-taskId map[task index]}
     addBlockedBy: [planIndex-to-taskId map[dep] for dep in task.blockedBy]

   If resuming: mark already-completed tasks as completed via TaskUpdate.
   ```

5. **Output format instructions**:

   ```
   ## Output

   The FINAL line of your output MUST be a single JSON object (no markdown fencing). All fields required:

   {
     "goal": "Add user authentication",
     "contextSummary": "Next.js + Prisma | ESLint + Prettier | test: npm test",
     "isResume": false,
     "validation": {
       "gitClean": true,
       "gitStatus": "",
       "blockingChecks": [{"claim": "Node >= 18", "passed": true, "output": "v20.11.0"}],
       "contextFilesValid": true,
       "missingContextFiles": []
     },
     "taskIdMapping": {"0": "task-abc", "1": "task-def"},
     "fileOverlapMatrix": {"0": [1]},
     "taskCount": 5,
     "maxDepth": 3,
     "depthSummary": {"1": [0, 1], "2": [2, 3], "3": [4]}
   }

   fileOverlapMatrix is extracted from each task's `fileOverlaps` array in plan.json (populated by design).

   depthSummary groups planIndices by dependency depth for display purposes (depth = 1 for tasks with empty blockedBy, otherwise 1 + max(depth of blockedBy tasks)). This is informational only — it does not determine execution order.
   ```

---

## Orchestration Flow

### Step 1: Setup

Spawn the Setup Subagent using the prompt template above.

Parse the final line of the subagent's return value as JSON.

**Fallback (minimal mode)**: Read `.design/plan.json`, validate schemaVersion is 3, create TaskList entries with dependencies. Extract `fileOverlaps` from each task to build `fileOverlapMatrix`. Return a setup JSON. Log: "Setup subagent failed — executing inline (minimal mode)."

**Error handling from setup output**:

- If error is `no_plan`: tell user "No plan found. Run `/design <goal>` first." and stop.
- If error is `schema_version`: tell user the plan uses an unsupported schema version and v3 is required, then stop.
- If error is `empty_tasks`: tell user the plan contains no tasks and to re-run `/design`, then stop.

Store setup output. Worker prompts live in `.design/plan.json` — workers self-read via bootstrap.

**Resume-nothing-to-do check**: If resuming and no pending tasks remain, tell user "All tasks are already resolved — nothing to do." and stop.

### Step 2: Report Validation

Using the setup output's `validation` field, display to the user:

```
Executing: {goal}
Tasks: {taskCount} (max dependency depth: {maxDepth})
Validation: {pass_count}/{total_count} blocking checks passed
```

If `validation.gitClean` is false, warn about uncommitted changes.

If any blocking checks failed, show them and use `AskUserQuestion` to let the user fix or proceed anyway.

If `isResume` is true, report: "Resuming execution."

### Step 3: Execute by Ready-Set Rounds

Initialize `roundNumber` to 1. Maintain a `completedResults` map (planIndex → result string) across all rounds.

**Silent execution**: Do NOT narrate worker progress. No per-worker status updates, no "waiting for tasks", no "Task X completed". The ONLY user-facing output is the round summary at Step 3e. Between spawning workers and the round summary, output nothing.

**Main loop**: While there are tasks with `pending` status in the setup output's `taskIdMapping`:

#### 3a. Compute Ready Set

Compute the ready set: tasks that are `pending` AND all tasks in their `blockedBy` are `completed` (check against the `completedResults` map and prior `skipList`).

**Deadlock detection**: If ready set is empty but pending tasks remain, abort with: "Deadlock detected: {pendingCount} tasks remain but none are ready. Remaining tasks depend on failed or blocked predecessors." Proceed to Step 4.

Use setup output for task metadata (taskIdMapping, fileOverlapMatrix). Workers self-read prompts from plan.json via bootstrap.

#### 3b. Spawn Task Subagents

For each task in the ready set:

1. Mark as in progress: `TaskUpdate(taskId: {ID}, status: "in_progress")`
2. **Assemble dependency results**: If the task has `blockedBy` entries, build a dependency results block from the `completedResults` map:

   ```
   Dependency results (from prior tasks):
   - Task {index}: {result from the completedResults map for that task}
   ```

3. Spawn a Task subagent with a bootstrap prompt — workers self-read their full instructions from plan.json:

```
Task:
  subagent_type: "general-purpose"
  model: {task.agent.model from plan.json}
  prompt: <bootstrap prompt assembled from template below>
```

**Worker bootstrap template** — substitute `{planIndex}`, then append dependency results if present:

```
## Bootstrap — Self-Read Instructions

1. Read `.design/plan.json` and extract the task at index {planIndex} from the `tasks` array.
2. Your full task instructions are in the `prompt` field of that task.
3. If dependency results appear below, find the placeholder line `[Dependency results — deferred: lead appends actual results at spawn time]` in the prompt and replace it with the dependency results section below.
4. Execute the task instructions from the prompt field.
```

If the task has dependency results (from point 2 above), append them directly after the bootstrap template.

**Parallel safety**: Check the setup output's `fileOverlapMatrix`. If any tasks in this ready set have file overlaps with each other, run those conflicting tasks sequentially. Spawn all non-conflicting tasks in parallel in a single response.

#### 3c. Verify Results

After all batch workers return, extract the FINAL status line from each worker's return value. The FINAL line is the last line of output and must match the format `COMPLETED:|FAILED:|BLOCKED:`. Discard all preceding output.

**Parse each status line**: Match `^(COMPLETED|FAILED|BLOCKED): .+`. If no match, treat as FAILED with reason "No valid status line returned".

**Spot-check and acceptance in one batched Bash script**: Build a single Bash script that, for each task in the batch:

1. If COMPLETED: spot-check created files (`test -f {path}` for each `metadata.files.create`), check modified files appear in `git diff --name-only`, run each `acceptanceCriteria[].check` command
2. Output one JSON object per task: `{"planIndex": N, "status": "completed|failed|blocked", "result": "...", "spotCheckPassed": bool, "acceptancePassed": bool, "failures": ["..."]}`

Wrap all per-task objects in a JSON array and output to stdout. Run this script in one Bash call.

**Interpret results**: For each task:
- COMPLETED + all checks passed → completed
- COMPLETED + spot-check or acceptance failed → override to failed (use failure details as reason)
- FAILED → failed (use status line reason)
- BLOCKED → blocked

#### 3d. Update Plan State

Read `.design/plan.json`. For each task from 3c:

1. Set `status`, `result`, `attempts` on the task
2. Append completed tasks to `progress.completedTasks`
3. **Progressive trimming**: for completed tasks, keep ONLY: `subject`, `status`, `result`, `metadata.files`, `blockedBy`, `agent.role`, `agent.model`. Strip `prompt`, `fileOverlaps`, and all other fields.
4. **Cascading failures**: tasks whose `blockedBy` chain includes any failed or blocked task → set to `skipped` with dependency message. Record skipped planIndices.
5. Write `.design/plan.json`.

#### 3e. Handle Retries

For each failed task where `attempts < 3`:

1. Clean up partial work: `git checkout -- {modifies}` and `rm -f {creates}`
2. Read the task's `prompt` field from plan.json (loaded in 3d)
3. Assemble retry prompt: original prompt + retry context block with attempt number and failure reason + fallback strategy if exists (`"IMPORTANT: The primary approach failed. Use this strategy instead: {fallback}"`) + acceptance failures if relevant
4. Spawn retry worker with the assembled prompt and same model
5. After retry worker returns, repeat verification (3c) and plan update (3d) for just that task

Repeat until no retryable tasks remain or all have reached 3 attempts.

#### 3f. Round Summary

Display: `Round {roundNumber}: {completed}/{total_in_batch} tasks ({total_completed_overall}/{taskCount} overall)` + per-task status.

Update `completedResults` map with completed task results. Mark completed tasks in TaskList via `TaskUpdate(status: "completed")`. Mark skipped tasks as completed in TaskList. Remove completed and skipped from pending set.

#### 3g. Git Commit

Collect all created and modified files from completed tasks in this round. Stage and commit: `git add {files} && git commit -m "{round summary}"`. Skip if no files (research-only tasks).

#### 3h. Circuit Breaker

Count pending tasks and how many would be skipped by cascading failures. If `totalTasks > 3 AND wouldBeSkipped >= 50% of pending`, ABORT. Display: "Circuit breaker triggered: {wouldBeSkipped}/{pendingCount} pending tasks would be skipped due to cascading failures." Proceed to Step 4.

Increment `roundNumber` and continue the main loop.

### Step 4: Complete

After all rounds (or after circuit breaker abort or deadlock):

1. `TaskList` to confirm final statuses
2. Summary:
   - Completed: {count}
   - Failed: {count} — {subjects}
   - Blocked: {count} — {subjects}
   - Skipped: {count} — {subjects}
   - Follow-up recommendations if any failures

3. If fully successful: archive completed plan to history: `mkdir -p .design/history && mv .design/plan.json ".design/history/$(date -u +%Y%m%dT%H%M%SZ)-plan.json"`. Return "All {count} tasks completed."
4. If partial: leave `.design/plan.json` for resume. Return "Execution incomplete. {done}/{total} completed."

**Arguments**: $ARGUMENTS
