---
name: execute
description: "Execute a plan from /design with persistent workers and self-organizing task claiming."
argument-hint: ""
---

# Execute

Execute `.design/plan.json` with persistent, self-organizing workers. Design produced the plan with role briefs — now workers read the codebase and achieve their goals. **This skill only executes — it does NOT design.**

**Do NOT use `EnterPlanMode`** — this skill IS the plan.

**CRITICAL: Always use agent teams.** When spawning any worker via Task tool, you MUST include `team_name: $TEAM_NAME` and `name: "{role}"` parameters. Without these, workers are standalone and cannot coordinate.

**Lead boundaries**: Use only `TeamCreate`, `TeamDelete`, `TaskCreate`, `TaskUpdate`, `TaskList`, `SendMessage`, `Task`, `AskUserQuestion`, and `Bash` (only for `python3 $PLAN_CLI`, `git`, verification scripts, and cleanup). Never read source files, use MCP tools, `Grep`, `Glob`, or `LSP`. Never execute tasks directly — spawn a worker.

**Progress reporting**: After the initial summary, output brief progress updates for significant events. Keep updates to one line each. Suppress intermediate worker tool calls and chatter.

**No polling**: Messages auto-deliver automatically. Never use `sleep`, loops, or Bash waits. When a teammate sends a message, it appears in your next turn.

### Script Setup

```
PLAN_CLI = {plugin_root}/skills/execute/scripts/plan.py
```

All script calls: `python3 $PLAN_CLI <command> [args]` via Bash. Output: JSON with `{"ok": true/false, ...}`.

**Team name** (project-unique, avoids cross-contamination between terminals):
```
TEAM_NAME = $(python3 $PLAN_CLI team-name execute).teamName
```

---

## Flow

### 1. Setup

1. Validate: `python3 $PLAN_CLI status .design/plan.json`. On failure: `not_found` = "No plan found. Run `/do:design <goal>` first." and stop; `bad_schema` = unsupported schema, stop; `empty_roles` = no roles, stop.
2. Resume detection: If `isResume`: run `python3 $PLAN_CLI resume-reset .design/plan.json`. If `noWorkRemaining`: "All roles already resolved." and stop.
3. Create team: `TeamDelete(team_name: $TEAM_NAME)` (ignore errors), then `TeamCreate(team_name: $TEAM_NAME)`. If TeamCreate fails, tell user Agent Teams is required and stop.
4. Create TaskList: `python3 $PLAN_CLI tasklist-data .design/plan.json`. For each role: `TaskCreate` with subject `"Role {roleIndex}: {name} — {goal}"`, record returned ID in `roleIdMapping`. Wire `blockedBy` via `TaskUpdate(addBlockedBy)`. If resuming, mark completed roles. Add overlap constraints: `python3 $PLAN_CLI overlap-matrix .design/plan.json` — for each pair `(i, j)` where `j > i` and directories overlap: `TaskUpdate(taskId: roleIdMapping[j], addBlockedBy: [roleIdMapping[i]])`.
5. **Worker pool**: Run `python3 $PLAN_CLI worker-pool .design/plan.json` to get workers (one per role).
6. Summary: `python3 $PLAN_CLI summary .design/plan.json`. Store `goal`, `roleCount`, `maxDepth`.
7. Pre-flight: Build a Bash script that checks `git status --porcelain` and runs any blocking checks.

### 2. Pre-Execution Auxiliaries

Check `auxiliaryRoles[]` in plan.json for `type: "pre-execution"` roles. Run them sequentially before execution workers. **Progress update** for each auxiliary: "Running {auxiliary.name}..."

Auxiliaries are standalone Task tool calls (no `team_name`) — they don't need team coordination. The Task tool returns their result directly. Do not use `SendMessage` or `TaskOutput` for auxiliaries.

**Challenger**: Spawn via `Task(subagent_type: "general-purpose")`. Prompt includes: "Read `.design/plan.json` and all `.design/expert-*.json` artifacts. Challenge assumptions, find gaps, identify risks. Save findings to `.design/challenger-report.json` with this structure: `{\"issues\": [{\"category\": \"scope-gap|overlap|invalid-assumption|missing-dependency|criteria-gap|constraint-conflict\", \"severity\": \"blocking|high-risk|low-risk\", \"description\": \"...\", \"affectedRoles\": [...], \"recommendation\": \"...\"}], \"summary\": \"...\"}`. Return a summary with count of blocking/high-risk/low-risk issues found." **Blocking issues are mandatory gates**: for each blocking issue, the lead MUST either (a) modify plan.json to address it (update acceptance criteria, add constraints, adjust scope), or (b) ask the user whether to accept the risk. Do not proceed to worker spawning with unresolved blocking issues. High-risk issues should be noted as additional constraints on affected roles.

**Scout**: Spawn via `Task(subagent_type: "general-purpose")`. Prompt includes: "Read actual codebase in scope directories from plan.json roles. Map patterns, conventions, integration points. **Verify that referenced dependencies actually resolve**: check that HTML classes have corresponding CSS definitions, imports point to existing modules, type references exist, API endpoints match route definitions, etc. Flag any orphaned references (classes, imports, types used but never defined) as discrepancies — especially layout-critical ones (display, positioning, sizing, visibility). Flag discrepancies with expert assumptions. Save report to `.design/scout-report.json` with this structure: `{\"scopeAreas\": [{\"directory\": \"...\", \"affectedRoles\": [...], \"actualStructure\": {\"files\": [...], \"patterns\": [...], \"conventions\": [...]}, \"expertAssumptions\": [{\"expert\": \"...\", \"assumption\": \"...\", \"verified\": true|false, \"actualReality\": \"...\"}], \"integrationPoints\": [{\"type\": \"import|export|shared-type\", \"description\": \"...\"}]}], \"discrepancies\": [{\"area\": \"...\", \"expected\": \"...\", \"actual\": \"...\", \"impact\": \"high|medium|low\", \"recommendation\": \"...\"}], \"summary\": \"...\"}`. Return a summary with count of discrepancies found." If discrepancies found, update role briefs in plan.json or note for workers.

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
9. **Pre-completion verification (MANDATORY)**: "Before reporting done, you MUST run every acceptance criterion's `check` command as a separate shell invocation. This is non-negotiable — do not skip any check, do not assume one passing check implies another passes. For EACH criterion: (a) run the exact shell command from the `check` field, (b) capture its exit code and output, (c) record pass/fail with the actual output as evidence. If ANY check fails, you are NOT done — fix the issue and re-run ALL checks. Do not report completion until every check command exits 0. Common mistake: assuming 'tests pass' means 'build succeeds' — these are independent checks."
10. **Committing**: "git add specific files + git commit with conventional commit message (feat:/fix:/refactor: etc). Never git add -A."
11. **Completion reporting**: "When done, SendMessage to lead with: role name, what you achieved, files changed, acceptance criteria results (pass/fail each with evidence)."
12. **Failure handling**: "If you cannot complete your goal, SendMessage to lead with: role name, what failed, why, what you tried, suggested alternative. If rollback triggers fire ({rollbackTriggers}), stop immediately and report."
13. **Fallback**: If role has a fallback: "If your primary approach fails: {fallback}"
14. **Scope boundaries**: "Stay within your scope directories. Do not modify files outside your scope unless absolutely necessary for integration."

```
Task(subagent_type: "general-purpose", team_name: $TEAM_NAME, name: "{worker-name}", model: "{model}", prompt: <role-specific prompt with all above>)
```

### 4. Monitor

Event-driven loop — process worker messages as they arrive.

**On role completion**: Worker reports what they achieved and acceptance criteria results.
1. Update plan.json: `echo '[{"roleIndex": N, "status": "completed", "result": "..."}]' | python3 $PLAN_CLI update-status .design/plan.json`
2. Handle any `cascaded` entries by marking them in TaskList.
3. Wake idle workers — tell them to check for new tasks.
4. **Progress update**: Output "✓ Completed: {role.name} — {one-line summary}"

**On role failure**: Worker reports what failed and why.
1. Update plan.json: `echo '[{"roleIndex": N, "status": "failed", "result": "..."}]' | python3 $PLAN_CLI update-status .design/plan.json`
2. Handle cascaded entries in TaskList. For each skipped role: **Progress update** "⊘ Skipped: {role.name} (dependency failed)"
3. **Progress update**: Output "✗ Failed: {role.name} — {failure reason}"
4. Circuit breaker: `python3 $PLAN_CLI circuit-breaker .design/plan.json`. If `shouldAbort`: shut down all workers, go to Post-Execution.
5. Retries: `python3 $PLAN_CLI retry-candidates .design/plan.json`. If retryable (attempts < 3):
   a. **Reflexion step**: Before retry, generate a 2-3 sentence reflection analyzing what went wrong. Ask: What was the root cause? What assumptions were incorrect? What should be done differently? Store reflection in role.result field as "Reflection for retry {attempt+1}: {reflection text}".
   b. Clean up partial work: `git checkout` + `rm` any artifacts from failed attempt.
   c. Reset in TaskList: `TaskUpdate(taskId, status: pending)`.
   d. Tell the worker to retry via SendMessage with structured context: "Retry {attempt+1}/3 for {role.name}. Previous attempt failed: {result}. Reflection: {generated reflection}. What to try differently: {suggested alternative or fallback}. Re-read acceptance criteria and verify each independently before reporting."
   e. **Progress update**: Output "↻ Retry {attempt+1}/3: {role.name}"

**On idle**: Worker reports no tasks available. Track idle workers. Check completion.

**Completion check** (after each idle/completion):
1. `python3 $PLAN_CLI status .design/plan.json`
2. No pending roles and all workers idle: shut down workers, go to Post-Execution.
3. Pending roles exist but all workers idle (deadlock): report deadlock, shut down, go to Post-Execution.

**On peer issues**: Workers handle these directly. The lead does not intervene unless asked.

### 5. Post-Execution Auxiliaries

Check `auxiliaryRoles[]` for `type: "post-execution"` roles. **Progress update** for each auxiliary: "Running {auxiliary.name}..."

Post-execution auxiliaries are standalone Task tool calls (no `team_name`), same as pre-execution auxiliaries.

**Integration Verifier**: Spawn via `Task(subagent_type: "general-purpose")`. Prompt includes:
- "Verify all completed roles' work integrates correctly."
- Completed roles: subjects, files changed (from worker reports)
- Test command from `plan.json context.testCommand`
- All `acceptanceCriteria` from all completed roles
- "Run the full test suite. Check for import/dependency conflicts. Verify cross-role connections. Test the goal end-to-end."
- "**Only report results for checks you actually performed.** If a check requires capabilities you don't have (e.g., visual rendering, browser access), report it as `\"result\": \"skipped\"` with `\"details\": \"requires browser rendering\"`. Never infer visual or behavioral results from grep/file-reading alone — a CSS rule existing in a file does not mean it takes effect on the page."
- "Save findings to `.design/integration-verifier-report.json` with this structure: `{\"status\": \"PASS|FAIL\", \"acceptanceCriteria\": [{\"role\": \"...\", \"criterion\": \"...\", \"result\": \"pass|fail|skipped\", \"details\": \"...\"}], \"crossRoleIssues\": [{\"issue\": \"...\", \"affectedRoles\": [...], \"severity\": \"blocking|high|medium|low\", \"suggestedFix\": \"...\"}], \"testResults\": {\"command\": \"...\", \"exitCode\": 0, \"output\": \"...\"}, \"endToEndVerification\": {\"tested\": true|false, \"result\": \"pass|fail|skipped\", \"details\": \"...\"}, \"summary\": \"...\"}`. Return PASS or FAIL with summary."

On FAIL: spawn targeted fix workers for specific issues. Re-run verifier after fixes (max 2 fix rounds). **Progress update** after verifier runs: "Integration verification: {PASS|FAIL}"

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

3. **Self-reflection** — Evaluate this run against the goal. Write a structured reflection entry:

   Assess: (a) Did completed roles deliver the goal end-to-end? (b) What worked well? (c) What failed or was suboptimal? (d) What should be done differently next time?

   ```bash
   echo '{"roleQuality":"<N of M roles completed first attempt>","whatWorked":["<item>"],"whatFailed":["<item>"],"doNextTime":["<item>"],"coordinationNotes":"<any team/worker observations>"}' | \
     python3 $PLAN_CLI reflection-add .design/reflection.jsonl \
       --skill execute \
       --goal "<the goal from plan.json>" \
       --outcome "<completed|partial|failed|aborted>" \
       --goal-achieved <true|false>
   ```

   The evaluation JSON is piped via stdin. Be honest — this reflection feeds future runs via memory curation. On failure: proceed (reflection is valuable but not blocking).

4. **Memory curation** — Spawn memory-curator via `Task(subagent_type: "general-purpose")`:

Prompt includes:
- "Read all artifacts: `.design/handoff.md`, `.design/plan.json` (all roles including completed, failed, skipped, in_progress, pending — read result field for each), `.design/reflection.jsonl` (most recent entry — the self-evaluation for this run), `.design/challenger-report.json` (if exists), `.design/scout-report.json` (if exists), `.design/integration-verifier-report.json` (if exists)."
- "Read existing memories: `.design/memory.jsonl` (if exists). Note what is already recorded to avoid duplicates."
- "The reflection entry contains the lead's honest self-evaluation of what worked and what didn't. Use it as a primary signal for what to record — reflections that identify surprising failures or unexpected successes are high-value memory candidates."

**Quality gates — apply BEFORE storing each candidate memory:**

- "TRANSFERABILITY TEST: Ask 'Would this be useful in a NEW session on a SIMILAR goal?' If no, discard. Session-specific data — test counts, bundle sizes, line counts, exit codes, specific file lists, timing — is never transferable."
- "CATEGORY TEST: Each memory must be exactly one of: `convention` (codebase/domain facts: 'this repo uses Bun not Node'), `pattern` (reusable procedures: 'to deploy, run A then B'), `mistake` (failed approaches with root cause: 'approach X fails because Y, use Z'), `approach` (how a class of problem was solved: 'for rate limiting in Express, middleware pattern works because...'), `failure` (why a role/task failed — always record these). If it doesn't fit a category, it's not a memory."
- "SURPRISE TEST: Routine successes on well-understood tasks are LOW value (importance 1-3). Record high importance (7-10) only for: unexpected failures, contradictions with prior assumptions, novel patterns not previously documented, or discovered conventions that differ from defaults."
- "DEDUPLICATION: If an existing memory already covers this learning, skip it. If new evidence refines an existing memory, note the refinement rather than creating a duplicate."
- "SPECIFICITY TEST: Each memory must contain at least one concrete reference — a file path, command, error message, code pattern, or tool name. 'Tests pass after changes' is not a memory. 'Bun test requires --run flag for CI (no watch mode)' is."

**Format:**
- "For each memory that passes all gates: call `python3 $PLAN_CLI memory-add .design/memory.jsonl --category <cat> --keywords <csv> --content <text> --importance <1-10>`"
- "Keywords: include technology names, directory paths, error types, tool names — terms a future goal description would contain."
- "Content: <200 words. State what you learned AND why it matters. Not what happened."
- "For failed/skipped roles: always create a `failure` or `mistake` memory with root cause analysis."
- "SendMessage to lead when complete: 'Memory curation complete. Added {count} memories ({breakdown by category}). Rejected {rejected_count} candidates (not transferable or duplicates).'."

```
Task(subagent_type: "general-purpose", team_name: $TEAM_NAME, name: "memory-curator", model: "haiku", prompt: <above>)
```

Wait for curator completion. On failure: proceed (memory curation is optional).

5. Archive: If all completed, move artifacts to history:
   ```bash
   ARCHIVE_DIR=".design/history/$(date -u +%Y%m%dT%H%M%SZ)"
   mkdir -p "$ARCHIVE_DIR"
   find .design -mindepth 1 -maxdepth 1 ! -name history ! -name memory.jsonl ! -name reflection.jsonl ! -name handoff.md -exec mv {} "$ARCHIVE_DIR/" \;
   ```
   If partial (failures remain): leave artifacts in `.design/` for resume.
6. Cleanup: `TeamDelete(team_name: $TEAM_NAME)`.

**Arguments**: $ARGUMENTS
