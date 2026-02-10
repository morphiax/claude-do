---
name: execute
description: "Execute a plan from /design with validation, dependency-graph scheduling, and single-file state tracking."
argument-hint: ""
---

# Execute

Execute a `.design/plan.json` using dependency-graph scheduling with Task subagents. The lead computes ready-sets dynamically from `blockedBy` dependencies, spawning each batch of ready tasks as a round. The lead is a thin orchestrator: it delegates mechanical work to three specialized subagents (setup, batch processor, plan updater) and retains only user interaction, worker spawning, git commits, and abort decisions.

**Workflow guard**: Execute the Orchestration Flow (Steps 1-4) as written. Do NOT use `EnterPlanMode` — this skill IS the execution plan. Proceed directly to Step 1: Setup.

**Lead responsibilities** (never delegated):

- Spawn task agents and collect return values
- `git add` + `git commit` (user-visible side effects)
- `AskUserQuestion` (user interaction)
- Circuit breaker evaluation (orchestration judgment)
- Compute ready-sets and manage round progression
- Display progress to user

**Delegated to subagents** (lead never reads raw `.design/plan.json`, except during fallback recovery):

- Plan reading, validation, TaskList creation → Setup Subagent
- Result parsing (from worker log files), spot-checks, acceptance checks, retry prompt assembly, plan mutation, progress tracking, cascading failures, progressive trimming → Batch Finalizer Subagent

**Fallback rule**: If any delegation subagent fails (non-zero exit, malformed JSON output, or missing required fields), the lead performs that step's scoped minimal-mode fallback inline. Each step (Setup, Finalizer) defines its own fallback with reduced scope — see the **Fallback (minimal mode)** block at each step. Never abort execution due to a subagent infrastructure failure.

### Conventions

- **FINAL-line**: Every subagent's last line of output is its structured return value (JSON object, no markdown fencing). The lead parses only this line.

---

## Subagent Definitions

### A. Setup Subagent (Plan Bootstrap)

Replaces plan reading, validation, and task list creation. Spawn once at the start. Model: sonnet.

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

### B. Batch Finalizer Subagent (Result Processor + State Updater)

Processes worker results and updates plan state after each batch. Combines result parsing, verification, retry assembly, plan mutation, progressive trimming, and cascading failure computation into a single subagent. Model: sonnet. Spawn once per processing pass (initial + each retry pass).

```
Task:
  subagent_type: "general-purpose"
  model: sonnet
  prompt: <assembled from template below>
```

**Batch finalizer prompt template** — assemble by concatenating these sections:

1. **Role and mission**:

   ```
   You are a batch finalizer. You process worker results and update plan state in a single pass. Responsibilities: (1) read task status lines and detailed output from worker log files (.design/worker-{planIndex}.log), (2) parse results, verify file artifacts, run acceptance criteria, (3) determine retries and assemble retry prompts, (4) apply results to .design/plan.json, (5) perform progressive trimming on completed tasks, (6) compute cascading failures and circuit breaker. You read task metadata from .design/plan.json and are the ONLY agent that writes to .design/plan.json.
   ```

2. **Input data section** — the lead assembles this from task status lines and round metadata:

   ```
   ## Input
   Round: {round_number}, Total tasks: {taskCount}, Small plan (<=3 tasks): {true/false}
   Plan file: .design/plan.json
   Read .design/plan.json for task metadata (prompts, acceptance criteria, fallback strategies).

   ### Task Results
   - planIndex: {planIndex}, statusLine: {FINAL status line}, attempts: {attempts}
   ```

   Append one line per task. If surprises/decisions exist, append `### Surprises/Decisions` with bullets.

The finalizer reads task metadata from plan.json and detailed output from `.design/worker-{planIndex}.log` (fallback to status line if missing).

3. **Processing instructions**:

   ```
   ## Phase 1: Process Results

   For each task:

   1. Parse status line. Match `^(COMPLETED|FAILED|BLOCKED): .+`. If no match, treat as FAILED. Read `.design/worker-{planIndex}.log` for failure details (if missing, use "No status line returned and no log file found").

   2. Spot-check files: For creates, run `test -f {path}`. For modifies, verify in `git diff --name-only`. Flag unexpected diffs as warnings. If spot-check fails but agent reported COMPLETED: override to FAILED.

   3. If COMPLETED and spot-check passed: run acceptance criteria checks. Override to FAILED if any fail (include command and output).

   4. If BLOCKED: record as blocked — no retry, no cleanup.

   5. If FAILED and attempts < 3: Read worker log for context. Clean up: `git checkout -- {modifies}` and `rm -f {creates}`. Delete stale log: `rm -f .design/worker-{planIndex}.log`. Assemble retry prompt: (a) original prompt from the task's `prompt` field in plan.json, (b) retry context block with attempt number and failure reason, (c) fallback strategy if exists: "IMPORTANT: The primary approach failed. Use this strategy instead: {fallback}", (d) acceptance failures if relevant: "The following acceptance checks failed — ensure they pass before reporting COMPLETED: {failures}".

   6. If FAILED and attempts >= 3: record as failed — no retry.

   7. If COMPLETED and all checks passed: record as completed.
   ```

4. **Plan update instructions**:

   ```
   ## Phase 2: Update Plan State

   1. Read .design/plan.json.

   2. For each task from Phase 1: set status, result, attempts. Append completed tasks to progress.completedTasks. Append surprises and decisions.

   3. Progressive trimming: for completed tasks, keep ONLY: subject, status, result, metadata.files, blockedBy, agent.role, agent.model. Strip prompt, fileOverlaps, and all other fields.

   4. Compute cascading failures: tasks whose blockedBy chain includes failed/blocked tasks → set to skipped with dependency message.

   5. Write .design/plan.json.

   6. Circuit breaker: count pending tasks, count how many would be skipped by cascading failures. shouldAbort: true if totalTasks > 3 AND wouldBeSkipped >= 50% of pending.
   ```

5. **Output format**:

   ```
   ## Output
   FINAL line: JSON object (no fencing). Schema: {"retryTasks": [{"planIndex": 1, "retryPrompt": "...", "model": "opus", "attempt": 2}], "completedFiles": {"create": [...], "modify": [...]}, "summary": "...", "updated": true, "skipList": [...], "circuitBreaker": {"totalTasks": N, "pendingCount": N, "wouldBeSkipped": N, "shouldAbort": bool}, "planSizeAfterTrim": "..."}
   ```

---

## Orchestration Flow

### Step 1: Setup

Spawn the Setup Subagent using the prompt template from Section A.

Parse the final line of the subagent's return value as JSON.

**Fallback (minimal mode)**: Read `.design/plan.json`, validate schemaVersion is 3, create TaskList entries with dependencies. Extract `fileOverlaps` from each task to build `fileOverlapMatrix`. Return a setup JSON. Log: "Setup subagent failed — executing inline (minimal mode)."

**Error handling from setup output**:

- If error is `no_plan`: tell user "No plan found. Run `/design <goal>` first." and stop.
- If error is `schema_version`: tell user the plan uses an unsupported schema version and v3 is required, then stop.
- If error is `empty_tasks`: tell user the plan contains no tasks and to re-run `/design`, then stop.

Store setup output. The lead never reads `.design/plan.json` directly — all plan data comes through setup/finalizer responses. Worker prompts live in `.design/plan.json` — workers self-read via bootstrap.

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

**Main loop**: While there are tasks with `pending` status in the setup output's `taskIdMapping`:

#### 3a. Compute Ready Set

Compute the ready set: tasks that are `pending` AND all tasks in their `blockedBy` are `completed` (check against the `completedResults` map and prior updater `skipList` responses).

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

#### 3c. Process Results and Update Plan

After all batch workers return, extract the FINAL status line from each worker's return value. The FINAL line is the last line of output and must match the format `COMPLETED:|FAILED:|BLOCKED:`. Discard all preceding output — only the FINAL status line is retained for processing.

Spawn the Batch Finalizer Subagent using the prompt template from Section B.

Assemble finalizer input: round number, total task count, plan file path (`.design/plan.json`), and for each task: planIndex, status line (FINAL line only), attempts count, surprises/decisions. The lead does NOT embed raw output — finalizer reads from worker log files.

Parse the final line of the finalizer's return value as JSON. The finalizer processes results and updates plan state in a single pass.

**Fallback (minimal mode)**: Parse worker status lines against `^(COMPLETED|FAILED|BLOCKED): .+`. For COMPLETED tasks, verify primary output files exist (`test -f` for creates, `git diff --name-only` for modifies). Skip acceptance criteria checks. For FAILED tasks with attempts < 3, read original prompt from the task's `prompt` field in `.design/plan.json`, append retry context, assemble retry prompt. Update status/result/attempts fields in `.design/plan.json`. Skip progressive trimming and cascading failure computation. Write plan. Return `{"retryTasks": [...], "completedFiles": {...}, "updated": true, "skipList": [], "circuitBreaker": {"shouldAbort": false}}`. Log: "Finalizer subagent failed — executing inline (minimal mode)."

#### 3d. Handle Retries

If finalizer output contains `retryTasks`: spawn new Task subagents with finalizer-provided `retryPrompt` and `model`. After all retry agents return, spawn Batch Finalizer again with retry results. Include plan file path for further retry assembly. Repeat until no `retryTasks` remain or all failed tasks reach 3 attempts.

#### 3e. Display Round Progress

Using final finalizer output (after retries): display `Round {roundNumber}: {completed}/{total_in_batch} tasks ({total_completed_overall}/{taskCount} overall)` + task statuses.

#### 3f. Update Tracking State

Update `completedResults` map with completed task results. Mark skipped tasks (from `skipList`) as completed in TaskList. Remove completed and skipped from pending set.

#### 3g. Git Commit

Stage and commit completed files: `git add {completedFiles} && git commit -m "{round summary}"`. Use finalizer's `completedFiles` field. Skip if no files (research-only tasks).

#### 3h. Circuit Breaker

If finalizer's `circuitBreaker.shouldAbort` is true, ABORT. Display: "Circuit breaker triggered: {wouldBeSkipped}/{pendingCount} pending tasks would be skipped due to cascading failures." Proceed to Step 4. Ignore circuit breaker for plans with ≤3 tasks.

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

3. Clean up intermediate artifacts: `rm -f .design/worker-*.log`
4. If fully successful: archive completed plan to history: `mkdir -p .design/history && mv .design/plan.json ".design/history/$(date -u +%Y%m%dT%H%M%SZ)-plan.json"`. Return "All {count} tasks completed."
5. If partial: leave `.design/plan.json` for resume. Return "Execution incomplete. {done}/{total} completed."

**Arguments**: $ARGUMENTS
