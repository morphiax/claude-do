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

1. Validate: `python3 $PLAN_CLI status .design/plan.json`. On failure: `not_found` = "No plan found. Run `/do:design <goal>` first." and stop; `bad_schema` = unsupported schema, stop; `empty_tasks` = no tasks, stop.
2. Resume detection: `python3 $PLAN_CLI status .design/plan.json`. If `isResume`: run `python3 $PLAN_CLI resume-reset .design/plan.json`, then for each `resetTasks` entry: `git checkout -- {filesToRevert}` and `rm -f {filesToDelete}`. If `noWorkRemaining`: "All tasks already resolved." and stop.
3. Create team: `TeamDelete(team_name: "do-execute")` (ignore errors), then `TeamCreate(team_name: "do-execute")`. If TeamCreate fails, tell user Agent Teams is required and stop.
4. Create TaskList: `python3 $PLAN_CLI tasklist-data .design/plan.json`. For each task: `TaskCreate` with subject `"Task {planIndex}: {subject}"`, record returned ID in `taskIdMapping`. Wire `blockedBy` via `TaskUpdate(addBlockedBy)`. If resuming, mark completed tasks. Add overlap constraints: `python3 $PLAN_CLI overlap-matrix .design/plan.json` — for each pair `(i, j)` where `j > i`, files overlap, and no existing dependency: `TaskUpdate(taskId: taskIdMapping[j], addBlockedBy: [taskIdMapping[i]])`.
5. **Worker Selection**: Analyze the tasks and determine what workers you need. Trust your judgment.

   Common worker types:
   - **frontend-developer** — UI components, CSS, HTML, client-side logic
   - **backend-developer** — APIs, databases, server-side logic
   - **core-developer** — business logic, state management, utilities
   - **qa-engineer** — testing, validation, quality checks
   - **devops** — build, deploy, infrastructure

   The list is not exhaustive. If a task involves CSS, it's frontend work. If a task involves API design, it's backend work. Group tasks by inferred worker type. Spawn one persistent worker per type. For simple plans, a single worker may suffice.

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

Spawn workers as teammates using the Task tool. Write prompts appropriate to the tasks they'll handle. Tell them what they need to know — don't follow a template.

**CRITICAL: Always use agent teams.** You MUST include `team_name` and `name` parameters:
```
Task(subagent_type: "general-purpose", team_name: "do-execute", name: "{worker-name}", prompt: <appropriate prompt>)
```

Workers should know:
- Where to find their tasks (TaskList, plan.json)
- How to report progress and completion
- How to handle errors

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
1. `python3 $PLAN_CLI status .design/plan.json`
2. No pending tasks and all workers idle: shut down workers, go to Final Verification
3. Pending tasks exist but all workers idle (deadlock): report deadlock, shut down, go to Final Verification

**On peer issues**: Workers handle these directly. The lead does not intervene unless asked.

### 4. Final Verification

Build a Bash script that for each completed task: checks created files exist (`test -f`), checks modified files in git log. Output JSON array with per-task results.

For verification failures with attempts < 3: update plan.json to failed, spawn a retry worker to try again. For non-retryable: leave as failed.

### 5. Goal Review

Workers execute tasks mechanically — none of them hold the full picture. The lead does. Before checking mechanical correctness, the lead steps back and evaluates whether the completed work actually achieves the original goal.

Review against the goal from `plan.json`:
1. **Completeness** — Does the sum of completed tasks deliver the goal end-to-end? Or did tasks get done but leave a gap? (e.g., API built but no route registered, component created but never rendered, migration written but no seed data)
2. **Coherence** — Do the pieces fit together as a whole? Are naming conventions consistent across tasks? Do data models from one task match what another task consumes?
3. **User intent** — Would a user looking at the result say "this is what I asked for"? Or did the plan drift from the goal during execution?

If gaps are found: spawn a targeted worker to address them (or assign to an idle worker). These are goal-level fixes, not task retries — they may require new work that no task covered.

### 6. Integration Testing

After the goal review, test that the combined work integrates correctly at the mechanical level.

1. Spawn an `integration-tester` worker into the team. Its prompt should include:
   - The full list of completed tasks (subjects + files touched)
   - The project's test command from `plan.json context.testCommand`
   - Instructions to: run the full test suite, attempt a build (`context.buildCommand` if present), check for import/dependency conflicts between files created by different tasks, verify that tasks referencing each other's outputs actually connect (e.g., API endpoint + client call, component + route registration)
2. The integration-tester reports findings: PASS (all clean) or FAIL (list of issues with affected tasks).
3. On FAIL: the lead assigns fix tasks to appropriate idle workers or spawns a targeted fix worker. Re-run integration test after fixes.
4. On PASS or after max 2 fix rounds: proceed to Complete.

**Skip integration testing when**: only 1 task was executed, or all tasks were independent (no shared files, no cross-references).

### 7. Complete

1. Summary: `python3 $PLAN_CLI status .design/plan.json`. Display completed/failed/blocked/skipped counts with subjects. Recommend follow-ups for failures.
2. **Session handoff** — Write `.design/handoff.md` with structured summary for future context:

```markdown
# Session Handoff — {goal}
Date: {ISO timestamp}

## What Was Done
- {completed count} of {total count} tasks completed
- {For each completed task: "Task N: {subject} — {one-line result}"}

## What Failed
- {For each failed task: "Task N: {subject} — {failure reason}"}

## Integration Status
- {PASS/FAIL/SKIPPED + details}

## Key Decisions Made During Execution
- {Any deviations from the plan, retries, workarounds}

## Files Changed
- {Deduplicated list of all files created/modified across tasks}

## Known Gaps and Risks
- {Missing test coverage, TODOs left in code, edge cases deferred}
- {Tasks that were skipped/blocked and why}

## Next Steps
- {Concrete actions: what should happen next if work continues}
```

3. Archive: If all completed, move all artifacts to a timestamped history folder:
   ```bash
   ARCHIVE_DIR=".design/history/$(date -u +%Y%m%dT%H%M%SZ)"
   mkdir -p "$ARCHIVE_DIR"
   find .design -mindepth 1 -maxdepth 1 ! -name history -exec mv {} "$ARCHIVE_DIR/" \;
   ```
   This preserves plan.json, expert files, and handoff.md together for future reference. If partial (failures remain): leave artifacts in `.design/` for resume.
4. Cleanup: `TeamDelete(team_name: "do-execute")`.

**Arguments**: $ARGUMENTS
