---
name: execute
description: "Execute a plan from /design with persistent workers and self-organizing task claiming."
argument-hint: ""
---

# Execute

Execute `.design/plan.json` with persistent, self-organizing workers. Design produced the plan with role briefs — now workers read the codebase and achieve their goals. **This skill only executes — it does NOT design.**

**Do NOT use `EnterPlanMode`** — this skill IS the plan.

**PROTOCOL REQUIREMENT: Follow the Flow step-by-step.** Begin with pre-flight checks, spawn workers only after auxiliaries complete.

**CRITICAL: Always use agent teams.** When spawning any worker via Task tool, you MUST include `team_name: $TEAM_NAME` and `name: "{role}"` parameters. Without these, workers are standalone and cannot coordinate.

**Lead boundaries**: Use only `TeamCreate`, `TeamDelete`, `TaskCreate`, `TaskUpdate`, `TaskList`, `SendMessage`, `Task`, `AskUserQuestion`, and `Bash` (for `python3 $PLAN_CLI`, cleanup, verification, `git`). Project metadata (CLAUDE.md, package.json, README) allowed via Bash. **Never use Read, Grep, Glob, Edit, Write, LSP, WebFetch, WebSearch, or MCP tools on project source files.** The lead orchestrates — agents think.

**Progress reporting**: After the initial summary, output brief progress updates for significant events. Keep updates to one line each. Suppress intermediate worker tool calls and chatter.

**No polling**: Messages auto-deliver automatically. Never use `sleep`, loops, or Bash waits. When a teammate sends a message, it appears in your next turn.

### Script Setup

Resolve plugin root. All script calls: `python3 $PLAN_CLI <command> [args]` via Bash. JSON output: `{"ok": true/false, ...}`.

```bash
PLAN_CLI={plugin_root}/skills/execute/scripts/plan.py
TEAM_NAME=$(python3 $PLAN_CLI team-name execute).teamName
SESSION_ID=$TEAM_NAME
```

### Trace Emission

After each agent lifecycle event: `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event {event} --skill execute [--agent "{name}"] || true`. Events: skill-start, skill-complete, spawn, completion, failure, respawn. Use `--payload '{"key":"val"}'` for extras. Failures are non-blocking (`|| true`).

---

## Worker Protocol (Inline)

This protocol is included directly in each worker's spawn prompt below (no separate file needed).

---

## Flow

### 1. Setup

1. **Lifecycle context**: Run `python3 $PLAN_CLI plan-health-summary .design` and display to user: "Previous session: {handoff summary}. Recent runs: {reflection summaries}. {plan status}." Skip if all fields empty. Then: `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event skill-start --skill execute || true`
2. Validate: `python3 $PLAN_CLI status .design/plan.json`. On failure: `not_found` = "No plan found. Run `/do:design <goal>` first." and stop; `bad_schema` = unsupported schema, stop; `empty_roles` = no roles, stop.
3. Resume detection: If `isResume`: run `python3 $PLAN_CLI resume-reset .design/plan.json`. If `noWorkRemaining`: "All roles already resolved." and stop.
4. Create team: `TeamDelete(team_name: $TEAM_NAME)` (ignore errors), then `TeamCreate(team_name: $TEAM_NAME)`. If TeamCreate fails, tell user Agent Teams is required and stop. Health check: verify team state via `ls ~/.claude/teams/$TEAM_NAME/config.json`. If missing, delete and retry: `TeamDelete(team_name: $TEAM_NAME)`, `TeamCreate(team_name: $TEAM_NAME)`. If retry fails, abort with error message.
5. Create TaskList: `python3 $PLAN_CLI tasklist-data .design/plan.json`. For each role: `TaskCreate` with subject `"Role {roleIndex}: {name} — {goal}"`, record returned ID in `roleIdMapping`. Wire `blockedBy` via `TaskUpdate(addBlockedBy)`. If resuming, mark completed roles. Add overlap constraints: `python3 $PLAN_CLI overlap-matrix .design/plan.json` — for each pair `(i, j)` where `j > i` and directories overlap: `TaskUpdate(taskId: roleIdMapping[j], addBlockedBy: [roleIdMapping[i]])`.
6. **Worker pool**: Run `python3 $PLAN_CLI worker-pool .design/plan.json` to get workers (one per role).
7. Summary: `python3 $PLAN_CLI summary .design/plan.json`. Store `goal`, `roleCount`, `maxDepth`.
8. Pre-flight: Build a Bash script that checks `git status --porcelain` and runs any blocking checks.

### 2. Pre-Execution Auxiliaries

Check `auxiliaryRoles[]` in plan.json for `type: "pre-execution"` roles. **Run Challenger and Scout concurrently in parallel** — they have no data dependency (both only read plan.json and expert artifacts). **Progress update**: "Running challenger and scout in parallel..."

Auxiliaries are standalone Task tool calls (no `team_name`) — they don't need team coordination. The Task tool returns their result directly. Do not use `SendMessage` or `TaskOutput` for auxiliaries.

**Spawn both in the same turn** (parallel):
- Emit trace for each: `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event spawn --skill execute --agent challenger || true` and `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event spawn --skill execute --agent scout || true`
- Call `Task(subagent_type: "general-purpose", model: "sonnet")` for challenger and `Task(subagent_type: "general-purpose", model: "sonnet")` for scout in the same response.

**Challenger** prompt: "Assume the plan is wrong until proven right. Question every assumption — especially ones that feel obvious. Prioritize finding problems over confirming correctness. Read `.design/plan.json` and all `.design/expert-*.json` artifacts. Challenge assumptions, find gaps, identify risks. Save findings to `.design/challenger-report.json` with this structure: `{\"issues\": [{\"category\": \"scope-gap|overlap|invalid-assumption|missing-dependency|criteria-gap|constraint-conflict\", \"severity\": \"blocking|high-risk|low-risk\", \"description\": \"...\", \"affectedRoles\": [...], \"recommendation\": \"...\"}], \"summary\": \"...\"}`. Return a summary with count of blocking/high-risk/low-risk issues found."

**Scout** prompt: "Verify everything — assume expert assumptions are stale until confirmed by actual code. Focus on what exists in the codebase right now, not what should exist. Read actual codebase in scope directories from plan.json roles. Map patterns, conventions, integration points. **Verify that referenced dependencies actually resolve**: check that HTML classes have corresponding CSS definitions, imports point to existing modules, type references exist, API endpoints match route definitions, etc. Flag any orphaned references (classes, imports, types used but never defined) as discrepancies — especially layout-critical ones (display, positioning, sizing, visibility). Flag discrepancies with expert assumptions. **If plan.json contains verificationSpecs[]**: verify each spec file exists at its path and that the runCommand references valid tools/paths (e.g., 'bun test' requires bun, paths in commands must exist). Check if spec file is executable for shell scripts. Save report to `.design/scout-report.json` with this structure: `{\"scopeAreas\": [{\"directory\": \"...\", \"affectedRoles\": [...], \"actualStructure\": {\"files\": [...], \"patterns\": [...], \"conventions\": [...]}, \"expertAssumptions\": [{\"expert\": \"...\", \"assumption\": \"...\", \"verified\": true|false, \"actualReality\": \"...\"}], \"integrationPoints\": [{\"type\": \"import|export|shared-type\", \"description\": \"...\"}]}], \"verificationSpecs\": [{\"role\": \"...\", \"path\": \"...\", \"exists\": true|false, \"runCommandValid\": true|false, \"issues\": \"...\"}] (if applicable), \"discrepancies\": [{\"area\": \"...\", \"expected\": \"...\", \"actual\": \"...\", \"impact\": \"high|medium|low\", \"recommendation\": \"...\"}], \"summary\": \"...\"}`. Return a summary with count of discrepancies found."

**After both complete** — process results in this order (ordering is mandatory):

**Step 1 — Process Challenger first**: `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event completion --skill execute --agent challenger || true`. Validate artifact via `python3 $PLAN_CLI validate-auxiliary-report --type challenger .design/challenger-report.json`. On validation failure: bypass Task agent and perform challenger analysis directly via Bash: `python3 -c "import json; p=json.load(open('.design/plan.json')); print(json.dumps(p, indent=2))"` to review plan structure, `ls .design/expert-*.json` to list artifacts, grep acceptance criteria for common issues (non-stdlib imports, platform-specific commands, surface-only checks without actual verification). Save minimal report: `echo '{"issues":[],"summary":"Bash bypass — manual review found no blocking issues"}' > .design/challenger-report.json`. **Blocking issues are mandatory gates**: for each blocking issue, the lead MUST either (a) modify plan.json to address it (update acceptance criteria, add constraints, adjust scope), or (b) ask the user whether to accept the risk. Do not proceed to worker spawning with unresolved blocking issues. High-risk issues should be noted as additional constraints on affected roles. **Show user**: "Challenger: {blocking count} blocking, {high-risk count} high-risk, {low-risk count} low-risk issues." Display each blocking issue description.

**Step 2 — Process Scout second** (after challenger modifications to plan.json are applied): `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event completion --skill execute --agent scout || true`. Validate artifact via `python3 $PLAN_CLI validate-auxiliary-report --type scout .design/scout-report.json`. On validation failure: bypass Task agent and perform scout analysis directly via Bash: `find {scope_directories} -type f | head -20` to sample files, `ls -R {scope_directories}` to map structure, grep for common patterns (imports, class names, API routes). Save minimal report: `echo '{"scopeAreas":[],"discrepancies":[],"summary":"Bash bypass — manual scan found no critical discrepancies"}' > .design/scout-report.json`. **Show user**: "Scout: {discrepancy count} discrepancies found." Display high-impact discrepancies. **Then update plan.json constraints** for affected roles with scout findings via Bash: `python3 -c "import json; p=json.load(open('.design/plan.json')); p['roles'][N]['constraints'].append('Scout: {actual}'); json.dump(p, open('.design/plan.json','w'), indent=2)"`.

**Step 3 — AC Pre-Validation**: Before spawning workers, run each acceptance criterion check command from plan.json against the current codebase to catch always-pass and broken criteria early. For each role in `roles[]`, for each criterion in `acceptanceCriteria[]`, run the `check` command via Bash. Flag:
- **Always-pass**: check exits 0 before any worker has run (criterion may not verify actual work — consider tightening)
- **Broken check**: check exits non-zero AND the failure is due to a malformed command (not a missing feature) — fix the check or ask user whether to proceed

```bash
# AC pre-validation example for role N, criterion C:
python3 -c "
import json, subprocess, sys
p = json.load(open('.design/plan.json'))
issues = []
for role in p['roles']:
    for ac in role.get('acceptanceCriteria', []):
        check = ac.get('check', '')
        if not check:
            continue
        r = subprocess.run(check, shell=True, capture_output=True, text=True)
        if r.returncode == 0:
            issues.append(f'ALWAYS-PASS [{role[\"name\"]}]: {ac[\"criterion\"]!r} — exits 0 before any work')
print('\n'.join(issues) if issues else 'No always-pass criteria detected')
"
```

**Show user**: "AC pre-validation: {count} always-pass criteria flagged, {broken} broken checks detected." For each flagged criterion, display role name and criterion text. Always-pass criteria are warnings (proceed); broken checks are blocking (fix before proceeding).

### 3. Report and Spawn Workers

Report to user:
```
Executing: {goal}
Roles: {roleCount} (depth: {maxDepth})
Workers: {totalWorkers} ({names})
Auxiliaries: {pre-execution auxiliaries run, post-execution pending}
```
Warn if git is dirty. If resuming: "Resuming execution."

**Memory injection** — For each role:
```bash
python3 $PLAN_CLI memory-search .design/memory.jsonl --goal "{role.goal}" --stack "{context.stack}" --keywords "{role.scope.directories + role.name}"
```
If `ok: false` or no memories → proceed without injection. Otherwise take top 2-3. **Show user**: "Memory: {role.name} ← {count} learnings ({keyword summaries})."

Spawn workers as teammates using the Task tool. Each worker prompt MUST include:

**Role-specific context** (customize per worker):

1. **Identity**: "You are a specialist: {role.name}. Your goal: {role.goal}"
2. **Brief location**: "Read your full role brief from `.design/plan.json` at `roles[{roleIndex}]`."
3. **Expert context**: "Read these expert artifacts for context: {expertContext entries with artifact paths and relevance notes}." If a scout report exists: "Also read `.design/scout-report.json` for codebase reality check."
4. **Past learnings** (if memories found): "Relevant past learnings: {bullet list of memories with format: '- {category}: {summary} (from {created})'}"
5. **Process**: "Explore your scope directories ({scope.directories}). Plan your own approach based on what you find in the actual codebase. Implement, test, verify against your acceptance criteria."
6. **Constraints**: "Constraints from role brief — read them from plan.json roles[{roleIndex}].constraints."
7. **Done when**: "Done when — read acceptance criteria from plan.json roles[{roleIndex}].acceptanceCriteria."
8. **Fallback**: If role has a fallback: "If your primary approach fails: {fallback}"
9. **Working protocol** (inline):

**Pre-Completion Verification (MANDATORY)**: Before reporting done, run EVERY acceptance criterion's `check` command as separate shell invocation. For each: (a) run exact shell command from `check` field, (b) capture exit code and output, (c) record pass/fail with evidence. If ANY fails, fix and re-run ALL checks. Don't report completion until every check exits 0. If plan.json verificationSpecs[] has entry for your role, run spec via its runCommand AFTER all acceptance criteria pass. Spec files in `.design/specs/` are IMMUTABLE — fix code, never modify specs. Spec failures are blocking.

**Universal Worker Rules**: Task discovery: Check TaskList for pending unblocked task, claim by setting status to in_progress. | Committing: git add specific files + git commit with conventional message (feat:/fix:/refactor:). Never git add -A. | Completion reporting: SendMessage to lead with JSON: `{"role": "{name}", "achieved": true, "filesChanged": ["..."], "acceptanceCriteria": [{"criterion": "...", "passed": true|false, "evidence": "..."}], "keyDecisions": ["..."], "contextForDependents": "..."}`. | **Acknowledgment**: When the lead sends a fix request or retry instruction, you MUST reply within 1 turn — either acknowledging the fix or reporting why you cannot proceed. Do not go silent after receiving instructions. | Tool boundaries: You may use Read, Grep, Glob, Edit, Write, Bash (for tests/build/git), LSP. Do NOT use WebFetch, WebSearch, MCP tools, or Task (no sub-spawning). | Failure handling: If cannot complete, SendMessage to lead with: role name, what failed, why, what you tried, suggested alternative. If rollback triggers fire, stop immediately and report. | Scope boundaries: Stay within your scope directories. Don't modify files outside scope unless absolutely necessary for integration.

```
python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event spawn --skill execute --agent "{worker-name}" || true
Task(subagent_type: "general-purpose", team_name: $TEAM_NAME, name: "{worker-name}", model: "{model}", prompt: <role-specific prompt with all above>)
```

### 4. Monitor

Event-driven loop — process worker messages as they arrive.

**On role completion**: Worker reports what they achieved, acceptance criteria results, and handoff context.
1. **Completion report validation**: Parse worker message as JSON and validate structure via `echo $WORKER_MSG | python3 $PLAN_CLI worker-completion-validate`. If validation fails (`ok: false`), reject with SendMessage: "Completion report malformed. Required fields: role, achieved, filesChanged (array), acceptanceCriteria (array of {criterion, passed, evidence}), keyDecisions (array), contextForDependents (string). Re-submit with correct structure." Do NOT proceed to verification if JSON is invalid. On validation failure, allow ONE re-submission with explicit schema example shown to worker; if second attempt fails, escalate to user for manual review.
2. **Lead-side verification** (trust but verify): For each criterion in `plan.json roles[N].acceptanceCriteria`, run the `check` command via Bash independently. **Before rejecting, verify the actual file state** — run `git diff --name-only HEAD` and `ls -la {relevant files}` to confirm the worker's changes are actually present on disk. Stale diagnostics from cached state or previous runs can produce false rejections. Only reject if the check fails AND the file state confirms the work is genuinely absent. If any check exits non-zero after confirming actual file state, reject completion with SendMessage: "Verification failed for {role.name}: criterion '{criterion}' did not pass. Check output: {output}. Fix and re-report." Do NOT proceed to status update if verification fails.
3. Update plan.json: `echo '[{"roleIndex": N, "status": "completed", "result": "..."}]' | python3 $PLAN_CLI update-status .design/plan.json`. Then: `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event completion --skill execute --agent "{worker-name}" || true`
4. Handle cascaded dependencies: For each roleIndex in the `cascaded[]` array returned by update-status: `TaskUpdate(taskId: roleIdMapping[roleIndex], status: pending)` and output progress update "⊘ Skipped: {role.name} (dependency failed)".
5. **Worker-to-worker handoff**: If the completed role is a dependency for other roles, extract `keyDecisions` and `contextForDependents` from the worker's completion report. When waking dependent workers, inject this context via SendMessage: "Dependency completed: {role.name}. Key decisions: {keyDecisions}. Context: {contextForDependents}. Files changed: {filesChanged}."
6. Wake idle workers — tell them to check for new tasks.
7. **Progress update**: Output "✓ Completed: {role.name} — {one-line summary}"

**On role failure**: Worker reports what failed and why.
1. Update plan.json: `echo '[{"roleIndex": N, "status": "failed", "result": "..."}]' | python3 $PLAN_CLI update-status .design/plan.json`. Then: `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event failure --skill execute --agent "{worker-name}" || true`
2. Handle cascaded dependencies: For each roleIndex in the `cascaded[]` array returned by update-status: `TaskUpdate(taskId: roleIdMapping[roleIndex], status: pending)` and output progress update "⊘ Skipped: {role.name} (dependency failed)".
3. **Progress update**: Output "✗ Failed: {role.name} — {failure reason}"
4. Circuit breaker: `python3 $PLAN_CLI circuit-breaker .design/plan.json`. If `shouldAbort`: shut down all workers, go to Post-Execution.
5. Retries: `python3 $PLAN_CLI retry-candidates .design/plan.json`. If retryable (attempts < 3):
   a. **Reflexion step**: Before retry, generate a 2-3 sentence reflection analyzing what went wrong. Ask: What was the root cause? What assumptions were incorrect? What should be done differently? Update plan.json to append reflection to role.result: `echo '[{"roleIndex": N, "status": "failed", "result": "{existing_result}\n\n--- Retry {attempt+1} Reflexion ---\n{reflection_text}\n--- End Reflexion ---"}]' | python3 $PLAN_CLI update-status .design/plan.json`.
   b. Clean up partial work: `git checkout` + `rm` any artifacts from failed attempt.
   c. Reset in TaskList: `TaskUpdate(taskId, status: pending)`.
   d. **Adaptive model escalation**: On retry, escalate the worker's model to the next tier: haiku → sonnet → opus. If already on opus, keep opus. This gives failing roles more capability without wasting tokens on first attempts.
   e. Tell the worker to retry via SendMessage with structured context: "Retry {attempt+1}/3 for {role.name}. Previous attempt failed: {result}. Reflection: {generated reflection}. What to try differently: {suggested alternative or fallback}. Re-read acceptance criteria and verify each independently before reporting. **Fix constraint: modify existing files only — no new file creation allowed during retry.** If new files seem necessary, report it as a blocker instead." Spawn the retried worker with the escalated model: `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event respawn --skill execute --agent "{worker-name}" || true`
   f. **Progress update**: Output "↻ Retry {attempt+1}/3: {role.name} (escalated to {new_model})"

**On idle**: Worker reports no tasks available. Track idle workers. Check completion.

**Worker liveness check** (3-turn timeout for silent workers):
Track silence per worker (count lead turns where an in_progress worker sends no message).
- After 3 turns of silence: SendMessage to worker: "No updates for 3 turns on {role.name}. Report progress or blockers."
- After 5 total turns of silence (2 more after ping): Mark role as failed with `echo '[{"roleIndex": N, "status": "failed", "result": "worker_timeout: no response after 5 turns"}]' | python3 $PLAN_CLI update-status .design/plan.json`. Re-spawn worker (max 2 attempts per role, then proceed with available progress). Output progress update "✗ Timeout: {role.name} — worker silent for 5 turns".

**Completion check** (after each idle/completion):
1. `python3 $PLAN_CLI status .design/plan.json`
2. No pending roles and all workers idle: shut down workers, go to Post-Execution.
3. Pending roles exist but all workers idle (deadlock): report deadlock, shut down, go to Post-Execution.

**On peer issues**: Workers handle these directly. The lead does not intervene unless asked.

### 5. Post-Execution Auxiliaries

Check `auxiliaryRoles[]` for `type: "post-execution"` roles. **Progress update** for each auxiliary: "Running {auxiliary.name}..."

Post-execution auxiliaries are standalone Task tool calls (no `team_name`), same as pre-execution auxiliaries.

**Integration Verifier** (integration-verifier): Spawn via `Task(subagent_type: "general-purpose", model: "sonnet")`. Prompt includes:
- "Reject assumptions — verify everything by running actual commands. Skip nothing; report only what you can prove with evidence. If you cannot test something, say so explicitly rather than guessing."
- "Verify all completed roles' work integrates correctly."
- Completed roles: subjects, files changed (from worker reports)
- Test command from `plan.json context.testCommand`
- All `acceptanceCriteria` from all completed roles
- "Run the full test suite. Check for import/dependency conflicts. Verify cross-role connections. Test the goal end-to-end."
- "**Verification spec integrity** (if plan.json has verificationSpecs[]): For each spec entry with a sha256 field, compute the current SHA256 of the file at path and compare to the stored value. Use command: `python3 -c \"import hashlib; print(hashlib.sha256(open('{path}', 'rb').read()).hexdigest())\"` or `shasum -a 256 {path} | awk '{print $1}'`. If ANY checksum mismatch is found, report as BLOCKING tamper detection failure — spec files are immutable and must not be modified during execution. Then run each spec via its runCommand and record results."
- "**Only report results for checks you actually performed.** If a check requires capabilities you don't have (e.g., visual rendering, browser access), report it as `\"result\": \"skipped\"` with `\"details\": \"requires browser rendering\"`. Never infer visual or behavioral results from grep/file-reading alone — a CSS rule existing in a file does not mean it takes effect on the page."
- "Save findings to `.design/integration-verifier-report.json` with this structure: `{\"status\": \"PASS|FAIL\", \"verificationSpecs\": [{\"role\": \"...\", \"path\": \"...\", \"checksumValid\": true|false, \"specResult\": \"pass|fail|skipped\", \"details\": \"...\"}] (if applicable), \"acceptanceCriteria\": [{\"role\": \"...\", \"criterion\": \"...\", \"result\": \"pass|fail|skipped\", \"details\": \"...\"}], \"crossRoleIssues\": [{\"issue\": \"...\", \"affectedRoles\": [...], \"severity\": \"blocking|high|medium|low\", \"suggestedFix\": \"...\"}], \"testResults\": {\"command\": \"...\", \"exitCode\": 0, \"output\": \"...\"}, \"endToEndVerification\": {\"tested\": true|false, \"result\": \"pass|fail|skipped\", \"details\": \"...\"}, \"summary\": \"...\"}`. Return PASS or FAIL with summary."

**After integration-verifier completes**: Validate artifact via `python3 $PLAN_CLI validate-auxiliary-report --type integration-verifier .design/integration-verifier-report.json`. On validation failure: bypass Task agent and perform integration verification directly via Bash: run `{testCommand}` from plan.json context if available, manually check that all worker-reported filesChanged exist via `ls -l {files}`, grep acceptance criteria for common issues. Save minimal report: `echo '{"status":"PASS","acceptanceCriteria":[],"crossRoleIssues":[],"testResults":{"command":"manual","exitCode":0,"output":"Bash bypass"},"endToEndVerification":{"tested":false,"result":"skipped","details":"Bash bypass fallback"},"summary":"Bash bypass — manual checks passed"}' > .design/integration-verifier-report.json`.

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

1. Summary: `python3 $PLAN_CLI status .design/plan.json`. Display a rich end-of-run summary:

```
Execution Complete: {goal}
Result: {goal achieved? yes/partial/no}

Roles: {completed}/{total} completed, {failed} failed, {skipped} skipped
{for each completed role: "  ✓ {name} — {one-line result}"}
{for each failed role: "  ✗ {name} — {failure reason}"}

Files Changed: {deduplicated list from worker reports, grouped by role}
Acceptance Results: {per-role: criterion → pass/fail}
Integration: {PASS|FAIL|SKIPPED — with details}

{if failures: "Recommended: /do:execute to retry failed roles, or /do:design to redesign."}
{if all passed: "Run /do:reflect to analyze patterns across runs."}
```
2. **Session handoff** — Write `.design/handoff.md` with sections: goal + date, completed roles (name + one-line result), failed roles (name + reason), integration status (PASS/FAIL/SKIPPED), decisions (deviations/retries/workarounds), files changed (deduplicated list), known gaps (missing coverage/TODOs/skipped roles), next steps (concrete actions).

3. **Self-reflection** — Assess: (a) Roles delivered goal end-to-end? (b) What worked well? (c) What failed/suboptimal? (d) What differently next time?

   ```bash
   echo '{"roleQuality":"<N of M roles completed first attempt>","whatWorked":["<item>"],"whatFailed":["<item>"],"doNextTime":["<item>"],"coordinationNotes":"<any team/worker observations>"}' | python3 $PLAN_CLI reflection-add .design/reflection.jsonl --skill execute --goal "<the goal from plan.json>" --outcome "<completed|partial|failed|aborted>" --goal-achieved <true|false>
   python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event skill-complete --skill execute || true
   ```

   Be honest — this reflection feeds future runs via memory curation. On failure: proceed (not blocking).

4. **Memory curation** — Spawn memory-curator via `Task(subagent_type: "general-purpose")`:

Prompt includes:
- "Reject aggressively — only store what a future engineer would find surprising and useful. If in doubt, reject. Prioritize unexpected findings over routine successes. Two high-quality entries are worth more than ten mediocre ones."
- "Read all artifacts: `.design/handoff.md`, `.design/plan.json` (all roles including completed, failed, skipped, in_progress, pending — read result field for each), `.design/reflection.jsonl` (most recent entry — the self-evaluation for this run), `.design/challenger-report.json` (if exists), `.design/scout-report.json` (if exists), `.design/integration-verifier-report.json` (if exists)."
- "Read existing memories: `.design/memory.jsonl` (if exists). Note what is already recorded to avoid duplicates."
- "The reflection entry contains the lead's honest self-evaluation of what worked and what didn't. Use it as a primary signal for what to record — reflections that identify surprising failures or unexpected successes are high-value memory candidates."

**Quality gates** (all must pass before storing):

- TRANSFERABILITY TEST: Useful in new session? (reject: test counts, metrics, file lists, timings, exit codes)
- CATEGORY TEST: Fits convention|pattern|mistake|approach|failure? (reject: uncategorizable)
- SURPRISE TEST: Unexpected/contradicts assumptions? Score 7-10. Routine success? Score 1-3.
- DEDUPLICATION TEST: Not already in memory.jsonl? (reject: duplicates)
- SPECIFICITY TEST: Contains concrete reference (path|command|error|pattern|tool)? (reject: vague)

**Format:**
- "For each memory that passes all gates: call `python3 $PLAN_CLI memory-add .design/memory.jsonl --category <cat> --keywords <csv> --content <text> --importance <1-10>`"
- "Keywords: include technology names, directory paths, error types, tool names — terms a future goal description would contain."
- "Content: <200 words. State what you learned AND why it matters. Not what happened."
- "For failed/skipped roles: always create a `failure` or `mistake` memory with root cause analysis."
- "SendMessage to lead when complete: 'Memory curation complete. Added {count} memories ({breakdown by category}). Rejected {rejected_count} candidates (not transferable or duplicates).'."

```
Task(subagent_type: "general-purpose", team_name: $TEAM_NAME, name: "memory-curator", model: "haiku", prompt: <above>)
```

Wait for curator completion. **Show user**: "Memory curation: {count} learnings stored, {rejected} rejected." On failure: proceed (memory curation is optional).

5. Archive: If all completed, move artifacts to history:
   ```bash
   python3 $PLAN_CLI archive .design
   ```
   If partial (failures remain): leave artifacts in `.design/` for resume.
6. Cleanup: `TeamDelete(team_name: $TEAM_NAME)`.

**Arguments**: $ARGUMENTS
