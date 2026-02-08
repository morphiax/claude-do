---
name: execute
description: "Execute a plan from /design with validation, wave-by-wave agents, and single-file state tracking."
argument-hint: ""
---

# Execute

Execute a `.design/plan.json` wave-by-wave using Task subagents. The lead is a thin orchestrator: it delegates mechanical work to three specialized subagents (setup, wave processor, plan updater) and retains only user interaction, worker spawning, git commits, and abort decisions.

**Workflow guard**: Execute the Orchestration Flow (Steps 1-4) as written. Do NOT use `EnterPlanMode` — this skill IS the execution plan. Proceed directly to Step 1: Setup.

**Lead responsibilities** (never delegated):

- Spawn task agents and collect return values
- `git add` + `git commit` (user-visible side effects)
- `AskUserQuestion` (user interaction)
- Circuit breaker evaluation (orchestration judgment)
- Display progress to user

**Delegated to subagents** (lead never reads raw `.design/plan.json`, except during fallback recovery):

- Plan reading, validation, TaskList creation, prompt assembly, per-wave file writing → Setup Subagent
- Result parsing (from worker log files), spot-checks, acceptance checks, retry prompt assembly → Wave Processor Subagent
- `.design/plan.json` mutation, progress tracking, cascading failures, trimming → Plan Updater Subagent

**Fallback rule**: If any delegation subagent fails (non-zero exit, malformed JSON output, or missing required fields), the lead performs that step's scoped minimal-mode fallback inline. Each step (Setup, Processor, Updater) defines its own fallback with reduced scope — see the **Fallback (minimal mode)** block at each step. Never abort execution due to a subagent infrastructure failure.

### Conventions

- **Atomic write**: Write to `{path}.tmp`, then rename to `{path}`. All file outputs in this skill use this pattern.
- **FINAL-line**: Every subagent's last line of output is its structured return value (JSON object, no markdown fencing). The lead parses only this line.

---

## Subagent Definitions

### A. Setup Subagent (Plan Bootstrap)

Replaces plan reading, validation, task list creation, and prompt assembly. Spawn once at the start.

```
Task:
  subagent_type: "general-purpose"
  prompt: <assembled from template below>
```

**Setup subagent prompt template** — assemble by concatenating these sections in order:

1. **Role and mission**:

   ```
   You are a plan bootstrap agent. Your job is to read .design/plan.json, validate it, create the TaskList for progress tracking, compute parallel safety metadata, and assemble complete worker prompts. You produce structured JSON output — you do NOT execute any tasks.
   ```

2. **Plan reading instructions**:

   ```
   ## Step 1: Read Plan

   Read `.design/plan.json` from the project root.

   - If not found: return JSON with error field set to no_plan
   - If found: parse JSON.
     - If schemaVersion is not 2: return JSON with error field set to schema_version and version set to the actual version number
     - If tasks array is empty: return JSON with error field set to empty_tasks
     - If progress.currentWave > 0: this is a resume. Reset any tasks with status in_progress back to pending (increment their attempts count). For each in_progress task being reset, clean up partial artifacts: revert uncommitted changes to metadata.files.modify files via git checkout -- {files} and delete partially created metadata.files.create files via rm -f {files}. For each completed task on resume, verify its metadata.files.create entries exist and its metadata.files.modify entries are committed. If verification fails, reset to pending. Write the updated plan back atomically to .design/plan.json.
   ```

3. **Validation instructions**:

   ```
   ## Step 2: Pre-execution Validation

   Run `git status --porcelain` and record whether the working tree is clean.

   For each task with agent.assumptions where severity is blocking:
   - Run the verify command via Bash
   - Record pass/fail and command output

   For each agent.contextFiles entry: verify the path exists.
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

   If resuming (progress.currentWave > 0): mark already-completed tasks as completed via TaskUpdate.
   ```

5. **File overlap computation instructions**:

   ```
   ## Step 4: Compute File Overlap Matrix

   For each wave, build a set of all file paths from each task's metadata.files.create and metadata.files.modify. Check for intersections between any two tasks' file sets within the same wave. Record which task indices conflict.
   ```

6. **Worker prompt assembly instructions** — builds the 9-section worker prompt:

   ```
   ## Step 5: Assemble Worker Prompts

   For each task, concatenate these sections. Include conditional sections only when the referenced field is non-empty. Produce final prompt text — no template markers.

   **S1: Role line** [always]
   `You are a {agent.role}` + ` with expertise in {agent.expertise}` [if agent.expertise]

   **S2: Pre-flight** [always]
   Emit heading: `## Pre-flight` / `Verify before starting. If BLOCKING check fails, return BLOCKED: followed by the reason.`
   + agent.assumptions as checklist: `- [ ] [{severity}] {claim}: \`{verify}\``

   **S3: Context section** [always]
   Emit heading: `## Context` / `Read before implementing:`
   + agent.contextFiles as bullets: `- {path} — {reason}`
   + `Project: {context.stack}. Conventions: {context.conventions}.`
   + `Test: {context.testCommand}` [if exists]
   + `Use LSP (goToDefinition, findReferences, hover) over Grep for {context.lsp.available}.` [if exists]
   + `Use WebSearch/WebFetch for current information. Prefer web tools over assumptions when external facts are needed.` [if metadata.type = research]

   **S4: Task section** [always]
   `## Task: {task.subject}` / `{task.description}`
   `Files to create: {metadata.files.create or "(none)"}` / `Files to modify: {metadata.files.modify or "(none)"}`
   + agent.constraints as bullets under `Constraints:` heading

   **S5: Strategy lines** [if any field exists]
   + `Approach: {agent.approach}` [if exists] / `Apply: {agent.priorArt}` [if exists] / `Fallback: {agent.fallback}` [if exists]

   **S6: Dependency results** [if task.blockedBy non-empty]
   Emit exactly: `[Dependency results — deferred: lead appends actual results at spawn time]`
   Do NOT resolve during assembly — the lead injects actual results at spawn time.

   **S7: Rollback triggers** [always]
   `Rollback triggers — STOP immediately if any occur:` + agent.rollbackTriggers as bullets

   **S8: Post-implementation** [always]
   `## After implementing` / `1. Verify acceptance criteria:`
   + agent.acceptanceCriteria as checklist: `- [ ] {criterion}: \`{check}\``
   + `   Fix failures before proceeding.`
   + `2. Do NOT stage or commit — the lead handles git after the wave completes.`

   **S9: Output format** [always] (substitute {planIndex} with actual plan index)
   Emit verbatim:
      ## After implementing (continued)
      3. Write your full work log (reasoning, commands run, decisions made, issues encountered) to `.design/worker-{planIndex}.log` using the Write tool. This log is consumed by the result processor — include enough detail for verification.

      ## Output format
      The FINAL line of your output MUST be one of:
      - COMPLETED: {one-line summary}
      - FAILED: {one-line reason}
      - BLOCKED: {reason}

      Return ONLY the status line as your final output. All detailed work output goes in the log file above.

      Example valid outputs:
      ...writing log.\nCOMPLETED: Added user authentication middleware with JWT
      ...writing log.\nBLOCKED: Required package pg not installed
   ```

7. **Per-wave file writing instructions**:

   ```
   ## Step 6: Write Per-Wave Prompt Files

   For each wave number N, collect all task objects for that wave and write them to `.design/wave-{N}.json` as a JSON array.

   Each task object in the array:

   [
     {
       "planIndex": 0,
       "taskId": "task-abc",
       "subject": "Setup auth module",
       "prompt": "<complete worker prompt from Step 5>",
       "model": "opus",
       "fileOverlaps": [1],
       "metadata": {"files": {"create": ["src/auth.ts"], "modify": ["src/app.ts"]}},
       "acceptanceCriteria": [{"criterion": "Auth tests pass", "check": "npm test -- auth"}],
       "fallback": "Use session-based auth instead"
     }
   ]

   Write atomically to `.design/wave-{N}.json`.
   ```

8. **Output format instructions**:

   ```
   ## Output

   **Context efficiency**: Minimize text output. Write reasoning to .design/setup.log if needed. Target: under 100 tokens of non-JSON output.

   The FINAL line of your output MUST be a single JSON object (no markdown fencing). All fields required:

   {
     "goal": "Add user authentication",
     "contextSummary": "Next.js + Prisma | ESLint + Prettier | test: npm test",
     "resumeWave": 0,
     "validation": {
       "gitClean": true,
       "gitStatus": "",
       "blockingChecks": [{"claim": "Node >= 18", "passed": true, "output": "v20.11.0"}],
       "contextFilesValid": true,
       "missingContextFiles": []
     },
     "taskIdMapping": {"0": "task-abc", "1": "task-def"},
     "waveSummary": {"1": [{"planIndex": 0, "taskId": "task-abc", "subject": "Setup auth module"}]},
     "fileOverlapMatrix": {"0": [1]},  // plan indices with file conflicts
     "taskCount": 5,
     "waveCount": 2
   }

   Prompts are NOT included in the output — they live in the per-wave files written in Step 6.
   ```

---

### B. Wave Processor Subagent (Result Processor)

Processes worker results (status lines + log files) after each wave or retry batch. Read-only — does NOT mutate `.design/plan.json`. Spawn once per processing pass.

```
Task:
  subagent_type: "general-purpose"
  prompt: <assembled from template below>
```

**Wave processor prompt template** — assemble by concatenating these sections:

1. **Role and mission**:

   ```
   You are a wave result processor. You receive task status lines, read task metadata from the wave file (.design/wave-{N}.json), and read detailed output from worker log files (.design/worker-{planIndex}.log). You parse results, verify file artifacts, run acceptance criteria, determine retries, clean up failed artifacts, and assemble retry prompts. You write detailed per-task results to .design/processor-wave-{N}.json. You are READ-ONLY with respect to .design/plan.json — you never read or write it.
   ```

2. **Input data section** — the lead assembles this from task status lines:

   ```
   ## Input

   Wave: {wave_number}
   Wave prompt file: .design/wave-{wave_number}.json
   Read .design/wave-{wave_number}.json for task metadata (subject, model, files, acceptance criteria, fallback strategy).

   ### Task Results
   ```

   For each task, append one line:

   `- planIndex: {planIndex}, statusLine: {FINAL status line from worker}, attempts: {attempts}`

---

The processor reads task metadata from the wave file and detailed work output from worker log files (`.design/worker-{planIndex}.log`). If a log file is missing, fall back to the status line only.

3. **Processing instructions**:

   ```
   ## Processing Instructions

   For each task:

   1. Parse the status line provided in the input. Match against the regex: ^(COMPLETED|FAILED|BLOCKED): .+
      If no match, treat as FAILED. Read `.design/worker-{planIndex}.log` for failure details — if the log file is missing, use "No status line returned and no log file found" as the failure reason.

   2. Spot-check files:
      - For each path in files to modify: run `git diff --name-only` and verify the path appears
      - For each path in files to create: run `test -f {path}`
      - Unexpected file detection: run `git diff --name-only` for the full wave and flag any modified files not listed in any task's files to create/modify. Include unexpected files in the result summary as warnings.

   3. If spot-check fails but agent reported COMPLETED: override to FAILED with reason describing which file verification failed

   4. If COMPLETED and spot-check passed: run each acceptance criteria check command via Bash. If any fail, override to FAILED with the acceptance failure details (command and output).

   5. If BLOCKED: record status as blocked — no retry, no cleanup.

   6. If FAILED and current attempts < 3:
      - Read `.design/worker-{planIndex}.log` for detailed failure context (if missing, use the status line).
      - Clean up partial artifacts: revert uncommitted changes to files-to-modify via `git checkout -- {files}` and delete partially created files-to-create via `rm -f {files}`.
      - Delete the stale worker log: `rm -f .design/worker-{planIndex}.log`
      - Assemble a retry prompt by concatenating:
        a. The original worker prompt (read from the wave prompt file at the path given in Original prompt source, extracting the entry matching the task's planIndex).
        b. A retry context block:

           ## Retry context
           This is attempt {attempts + 1} of 3. The previous attempt failed.

           Previous failure reason:
           {failure reason or raw output}

        c. If the task has a fallback strategy, append:

           IMPORTANT: The primary approach failed. Use this strategy instead: {fallback strategy}

        d. If the failure was due to acceptance criteria, append:

           The following acceptance checks failed — ensure they pass before reporting COMPLETED:
           {list of failed check commands and their output}

   7. If FAILED and current attempts >= 3: record as failed — no retry.

   8. If COMPLETED and all checks passed: record as completed.
   ```

4. **Output format instructions**:

   ```
   ## Output

   **Context efficiency**: Minimize text output. Write reasoning to .design/processor.log if needed. Target: under 100 tokens of non-JSON output.

   Write detailed per-task results to .design/processor-wave-{wave_number}.json atomically:

   [
     {"planIndex": 0, "status": "completed", "result": "Added auth middleware", "attempts": 1, "acceptancePassed": true},
     {"planIndex": 1, "status": "failed", "result": "Auth test failed", "attempts": 2, "acceptancePassed": false}
   ]

   The FINAL line of your output MUST be a single JSON object (no markdown fencing). Include only what the lead needs — per-task details are in the file above:

   {
     "retryTasks": [
       {"planIndex": 1, "retryPrompt": "<full assembled retry prompt>", "model": "opus", "attempt": 2}
     ],
     "completedFiles": {
       "create": ["src/auth.ts"],
       "modify": ["src/app.ts"]
     },
     "summary": "2 completed, 1 retry pending, 0 blocked"
   }
   ```

---

### C. Plan Updater Subagent (State Updater)

Applies wave results to `.design/plan.json`, handles progressive trimming and cascading failures. Spawn once per wave after all tasks (including retries) are resolved.

```
Task:
  subagent_type: "general-purpose"
  prompt: <assembled from template below>
```

**Plan updater prompt template** — assemble by concatenating these sections:

1. **Role and mission**:

   ```
   You are a plan state updater. You read .design/plan.json, apply wave results, perform progressive trimming on completed tasks, compute cascading failures, and write the updated plan atomically. You are the ONLY agent that writes to .design/plan.json.
   ```

2. **Input data section** — the lead assembles this:

   ```
   ## Input

   Wave: {wave_number}
   Total tasks in plan: {taskCount}
   Tasks with 3 or fewer total: {true/false}
   Read .design/processor-wave-{wave_number}.json for per-task results (planIndex, status, result, attempts).
   ```

   If any surprises or decisions were noted during the wave, append:

   ```
   ### Surprises/Decisions
   - {description}
   ```

3. **Update instructions**:

   ```
   ## Update Instructions

   1. Read .design/plan.json from the project root.

   2. For each task in the wave results:
      - Set task.status to the provided status
      - Set task.result to the provided result string
      - Set task.attempts to the provided attempts count

   3. Update progress.currentWave to {wave_number}.

   4. Append completed tasks to progress.completedTasks as [{index, summary, wave}] for each task with completed status.

   5. Append any surprises to progress.surprises and decisions to progress.decisions.

   6. Apply progressive plan trimming: for every task with completed status, strip verbose agent fields — keep ONLY these fields on the task object:
      - subject
      - status
      - result
      - metadata.files (the full files object with create and modify)
      - wave
      - blockedBy
      - agent.role
      - agent.model
      Remove all other agent subfields (approach, priorArt, fallback, contextFiles, assumptions, acceptanceCriteria, rollbackTriggers, constraints, expertise) and all other task-level fields (description, activeForm, attempts, metadata.type, metadata.reads) from completed tasks. This reduces plan size progressively as execution proceeds.

   7. Compute cascading failure skip list: for tasks in later waves whose blockedBy includes any task with failed or blocked status, set their status to skipped and result to a message indicating which dependency caused the skip.

   8. Write atomically to .design/plan.json.

   9. Compute circuit breaker evaluation:
      - Count all tasks still in pending status
      - Count how many of those pending tasks would be skipped due to cascading failures (their blockedBy chain leads to a failed/blocked task)
      - Determine shouldAbort: true if totalTasks > 3 AND wouldBeSkipped >= 50% of pending tasks
   ```

4. **Output format instructions**:

   ```
   ## Output

   **Context efficiency**: Minimize text output. Write reasoning to .design/updater.log if needed. Target: under 100 tokens of non-JSON output.

   The FINAL line of your output MUST be a single JSON object (no markdown fencing). Use this exact schema:

   {
     "updated": true,
     "skipList": [3, 5, 7],
     "circuitBreaker": {
       "totalTasks": 8,
       "pendingCount": 5,
       "wouldBeSkipped": 3,
       "shouldAbort": true
     },
     "planSizeAfterTrim": "<approximate token count>"
   }
   ```

---

## Orchestration Flow

### Step 1: Setup

Spawn the Setup Subagent using the prompt template from Section A.

Parse the final line of the subagent's return value as JSON.

**Fallback (minimal mode)**: Read `.design/plan.json`, validate schemaVersion is 2, create TaskList entries with dependencies. Write `.design/wave-{N}.json` files with simplified prompts — skip file overlap computation (set `fileOverlaps` to empty arrays). Include in each prompt: role, task context, acceptance criteria, and FINAL-line format. Return a setup JSON with `fileOverlapMatrix` set to `{}`. Log: "Setup subagent failed — executing inline (minimal mode)."

**Error handling from setup output**:

- If error is `no_plan`: tell user "No plan found. Run `/design <goal>` first." and stop.
- If error is `schema_version`: tell user the plan uses an unsupported schema version and v2 is required, then stop.
- If error is `empty_tasks`: tell user the plan contains no tasks and to re-run `/design`, then stop.

Store the setup output for use throughout execution. The lead never reads `.design/plan.json` directly — all plan data comes through the setup output or updater responses. Worker prompts are stored in per-wave files (`.design/wave-{N}.json`), not in the setup output — workers self-read their prompts at execution time via the bootstrap template.

**Resume-nothing-to-do check**: If resuming (`resumeWave > 0`) and the setup output shows no pending tasks remain (all tasks are already completed, failed, blocked, or skipped), tell the user "All tasks are already resolved — nothing to do." and stop.

### Step 2: Report Validation

Using the setup output's `validation` field, display to the user:

```
Executing: {goal}
Tasks: {taskCount} across {waveCount} waves
Validation: {pass_count}/{total_count} blocking checks passed
```

If `validation.gitClean` is false, warn about uncommitted changes.

If any blocking checks failed, show them and use `AskUserQuestion` to let the user fix or proceed anyway.

If `resumeWave` > 0, report: "Resuming from wave {resumeWave}."

### Step 3: Execute Wave-by-Wave

For each wave (starting from `resumeWave + 1` if resuming, otherwise 1):

#### 3a. Collect Wave Tasks

Use `TaskList` to find tasks for this wave that are `pending` and have all `blockedBy` resolved. Read `.design/wave-{N}.json` for task metadata only (planIndex, taskId, subject, model, fileOverlaps) — do NOT read prompt fields into lead context. Workers self-read their prompts.

#### 3b. Spawn Task Subagents

For each task in the wave:

1. Mark as in progress: `TaskUpdate(taskId: {ID}, status: "in_progress")`
2. **Assemble dependency results**: If the task has `blockedBy` entries, build a dependency results block from the lead's completed task results map:

   ```
   Dependency results (from prior tasks):
   - Task {index}: {result from the updater or processor output for that completed task}
   ```

   The lead maintains a map of completed task results from prior waves' processor outputs.

3. Spawn a Task subagent with a bootstrap prompt — workers self-read their full instructions from the wave file:

```
Task:
  subagent_type: "general-purpose"
  model: {task.model from wave file}
  prompt: <bootstrap prompt assembled from template below>
```

**Worker bootstrap template** — substitute `{N}` and `{planIndex}`, then append dependency results if present:

```
## Bootstrap — Self-Read Instructions

1. Read `.design/wave-{N}.json` and extract the entry where `planIndex` equals {planIndex}.
2. Your full task instructions are in the `prompt` field of that entry.
3. If dependency results appear below, find the placeholder line `[Dependency results — deferred: lead appends actual results at spawn time]` in the prompt and replace it with the dependency results section below.
4. Execute the task instructions from the prompt field.

Wave file: `.design/wave-{N}.json`
Plan index: {planIndex}
```

If the task has dependency results (from point 2 above), append them directly after the bootstrap template.

**Parallel safety**: Check the setup output's `fileOverlapMatrix`. If any tasks in this wave have file overlaps, run those conflicting tasks sequentially. Spawn all non-conflicting tasks in parallel in a single response.

#### 3c. Process Results

After all wave workers return, extract the FINAL status line from each worker's return value. The FINAL line is the last line of output and must match the format `COMPLETED:|FAILED:|BLOCKED:`. Discard all preceding output — only the FINAL status line is retained for processing.

Spawn the Wave Processor Subagent using the prompt template from Section B.

Assemble the processor's input data section by inserting:

- The wave number and wave prompt file path (`.design/wave-{N}.json`)
- For each task: its planIndex, the **status line only** (FINAL line from worker return value), and current attempts count
- For retry processing: include the wave prompt file path so the processor can read original prompts

The lead does NOT embed raw return values or full worker output — the processor reads detailed output from worker log files directly.

Parse the final line of the processor's return value as JSON.

**Fallback (minimal mode)**: Parse worker status lines against `^(COMPLETED|FAILED|BLOCKED): .+`. For COMPLETED tasks, verify primary output files exist (`test -f` for creates, `git diff --name-only` for modifies). Skip acceptance criteria checks — retry catches regressions. For FAILED tasks with attempts < 3, read original prompt from `.design/wave-{N}.json` by planIndex, append retry context, assemble retry prompt. Write results to `.design/processor-wave-{N}.json`. Log: "Processor subagent failed — executing inline (minimal mode)."

#### 3d. Handle Retries

If the processor output contains `retryTasks`:

For each retry task, spawn a new Task subagent using the processor-provided `retryPrompt` and `model`. Collect return values.

After all retry agents return, spawn the Wave Processor Subagent again with the retry results (status lines and worker log file paths). Include the wave prompt file path so the processor can read original prompts for further retry assembly if needed.

Repeat until no `retryTasks` remain or all failed tasks have reached 3 attempts. Each retry pass processes only the tasks that were marked for retry in the previous pass.

#### 3e. Display Wave Progress

Using the final processor output (after all retries are resolved), display:

```
Wave {N} complete: {completed}/{total_in_wave} tasks
- Task {planIndex}: {subject} — {status}
```

#### 3f. Update Plan State

Spawn the Plan Updater Subagent using the prompt template from Section C.

Assemble the updater's input data section by inserting:

- Wave number
- Total task count and whether it is 3 or fewer
- Any surprises or decisions noted during the wave

The updater reads per-task results from `.design/processor-wave-{N}.json` -- the lead does not relay them inline.

Parse the final line of the updater's return value as JSON.

**Fallback (minimal mode)**: Read `.design/plan.json` and `.design/processor-wave-{N}.json`. For each task result: update status, result, and attempts fields. Set `progress.currentWave` to the wave number. Write atomically. Skip progressive trimming and cascading failure computation — defer to next wave's updater. Return `{"updated": true, "skipList": [], "circuitBreaker": {"shouldAbort": false}}`. Log: "Updater subagent failed — executing inline (minimal mode)."

#### 3g. Update TaskList for Skipped Tasks

Using the updater's `skipList`, mark skipped tasks as `completed` in the TaskList (the detailed skipped status lives in `.design/plan.json`).

#### 3h. Git Commit

Stage and commit all completed tasks' files from this wave:

```
git add {all metadata.files.create and metadata.files.modify from completed tasks}
git commit -m "{wave summary}"
```

Use the processor's `completedFiles` field to determine which files to stage. Skip git add and commit if no files were created or modified in this wave (possible for research-only tasks).

#### 3i. Circuit Breaker

Using the updater's `circuitBreaker` field: if `shouldAbort` is true, ABORT execution. Display: "Circuit breaker triggered: {wouldBeSkipped}/{pendingCount} pending tasks would be skipped due to cascading failures." The updater has already written the skip statuses to `.design/plan.json`. Proceed to Step 4.

For plans with 3 or fewer total tasks (`circuitBreaker.totalTasks <= 3`), ignore the circuit breaker — cascading failures are managed individually.

### Step 4: Complete

After all waves (or after circuit breaker abort):

1. `TaskList` to confirm final statuses
2. Summary:
   - Completed: {count}
   - Failed: {count} — {subjects}
   - Blocked: {count} — {subjects}
   - Skipped: {count} — {subjects}
   - Follow-up recommendations if any failures

3. Clean up intermediate artifacts: `rm -f .design/wave-*.json .design/worker-*.log .design/processor-wave-*.json`
4. If fully successful: rename `.design/plan.json` to `.design/plan.done.json` for audit trail. Return "All {count} tasks completed."
5. If partial: leave `.design/plan.json` for resume. Return "Execution incomplete. {done}/{total} completed."

**Arguments**: $ARGUMENTS
