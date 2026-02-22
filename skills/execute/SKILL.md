---
name: execute
description: "Execute a plan from /design with standalone Task() workers."
argument-hint: ""
---

# Execute

Execute `.design/plan.json` with standalone Task() workers. Design produced the plan with role briefs — now workers read the codebase and achieve their goals. **This skill only executes — it does NOT design.**

Before starting the Flow, Read `lead-protocol-core.md`. It defines the canonical lead protocol (boundaries, trace emission, memory injection, phase announcements). Substitute: {skill}=execute, {agents}=workers. Task() blocks until done — no polling logic is needed.

> **Execute Lead Boundaries override**: Bash also includes `git` (for partial-work cleanup on retry and git status checks).

**Progress reporting**: After the initial summary, output brief progress updates for significant events. Keep updates to one line each. Suppress intermediate worker tool calls and chatter.

---

## Flow

### 1. Setup

1. **Lifecycle context**: Run Lifecycle Context protocol (see lead-protocol-core.md).
2. Validate: `python3 $PLAN_CLI status .design/plan.json`. On failure: `not_found` = "No plan found. Run `/do:design <goal>` first." and stop; `bad_schema` = unsupported schema, stop; `empty_roles` = no roles, stop.
3. Resume detection: If `isResume`: run `python3 $PLAN_CLI resume-reset .design/plan.json`. If `noWorkRemaining`: "All roles already resolved." and stop.
4. **Worker pool**: Run `python3 $PLAN_CLI worker-pool .design/plan.json` to get workers (one per role).
5. Summary: `python3 $PLAN_CLI summary .design/plan.json`. Store `goal`, `roleCount`, `maxDepth`.
6. Pre-flight: Build a Bash script that checks `git status --porcelain` and runs any blocking checks.

### 2. Pre-Execution Checks

Check `auxiliaryRoles[]` in plan.json for `type: "pre-execution"` roles. If none exist (the default — `/do:reflect` handles plan verification between design and execute), skip directly to AC Pre-Validation below.

If pre-execution auxiliaries ARE present (legacy plans or `/do:simplify` output), run them as standalone Task() calls. The Task() call returns their result directly.

**AC Pre-Validation**: Before spawning workers, run each acceptance criterion check command from plan.json against the current codebase to catch always-pass and broken criteria early. For each role in `roles[]`, for each criterion in `acceptanceCriteria[]`, run the `check` command via Bash. Flag:
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
            issues.append('ALWAYS-PASS [{}]: {!r} — exits 0 before any work'.format(role['name'], ac['criterion']))
print('\n'.join(issues) if issues else 'No always-pass criteria detected')
"
```

**Show user**: "AC pre-validation: {count} always-pass criteria flagged, {broken} broken checks detected." For each flagged criterion, display role name and criterion text. Always-pass criteria are warnings (proceed); broken checks are blocking (fix before proceeding).

**CLI signature verification**: Before spawning workers, scan role constraints for `python3 $PLAN_CLI` command references. For each referenced subcommand (e.g., `spec-add`, `reflection-add`), run `python3 $PLAN_CLI {subcommand} --help 2>&1` to verify the command exists and accepts the flags mentioned in constraints. If a constraint references a flag that doesn't exist (e.g., `--type` on a command that has no `--type` flag), fix the constraint in plan.json before spawning the worker. Record any fixes as acMutations.

**AC mutation recording** (MANDATORY): When an always-pass or broken check is found during AC pre-validation (or CLI signature verification), and the lead fixes the check command before spawning workers, record each mutation to reflection immediately. This is MANDATORY — skipping this recording is a protocol violation. For each mutated criterion:

```bash
echo '{"acMutations":[{"role":"{role.name}","criterion":"{criterion text}","originalCheck":"{original check}","issue":"always-pass|surface-only|syntax-error|wrong-boundary","fixedCheck":"{fixed check}","reasoning":"{why it was wrong and what the fix verifies}"}],"whatWorked":[],"whatFailed":["AC mutations detected during pre-validation"],"promptFixes":[{"section":"plan.json acceptanceCriteria","problem":"{issue description}","idealOutcome":"check command verifies actual behavior","fix":"{fixedCheck}","failureClass":"spec-disobey"}]}' | python3 $PLAN_CLI reflection-add .design/reflection.jsonl \
  --skill execute \
  --goal "$GOAL" \
  --outcome partial \
  --goal-achieved false
```

Record one entry per pre-validation pass (batch all mutations in one `acMutations` array via piped JSON). The JSON is read from stdin by reflection-add as the evaluation object. This feeds the "Learn from past AC mutations" block in the next design run and enables the post-execution spec curation step to exclude mutated criteria from promotion.

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
If `ok: false` or no memories → proceed without injection. Otherwise take top 3-5. **Show user**: "Memory: {role.name} ← {count} learnings ({keyword summaries})."

**Execution order**: For sequential roles (depth > 1), spawn Task() calls in order — wait for each to return before spawning the next. For parallel roles (same depth level with no dependencies), spawn multiple Task() calls in the same response.

**Dependency cascade**: The lead tracks which roles completed or failed. For parallel roles with dependencies, if a dependency failed, skip the dependent role entirely (do not spawn it). Output progress update "⊘ Skipped: {role.name} (dependency failed)".

Spawn workers as standalone Task() calls. Each worker prompt MUST include:

**Role-specific context** (customize per worker):

1. **Identity**: "You are a specialist: {role.name}. Your goal: {role.goal}"
2. **Brief location**: "Read your full role brief from `.design/plan.json` at `roles[{roleIndex}]`."
3. **Expert context**: "Read these expert artifacts for context: {expertContext entries with artifact paths and relevance notes}." If a scout report exists: "Also read `.design/scout-report.json` for codebase reality check."
4. **Past learnings** (if memories found): "Relevant past learnings: {bullet list of memories with format: '- {category}: {summary} (from {created})'}"
5. **Process**: "Explore your scope directories ({scope.directories}). Plan your own approach based on what you find in the actual codebase. Implement, test, verify against your acceptance criteria."
6. **Constraints**: "Constraints from role brief — read them from plan.json roles[{roleIndex}].constraints."
7. **Done when**: "Done when — read acceptance criteria from plan.json roles[{roleIndex}].acceptanceCriteria."
8. **Fallback**: If role has a fallback: "If your primary approach fails: {fallback}"
9. **Dependency context** (if this role depends on others): Inject `keyDecisions` and `contextForDependents` from completed dependency roles. Include: "Dependency completed: {role.name}. Key decisions: {keyDecisions}. Context: {contextForDependents}. Files changed: {filesChanged}."
10. **Working protocol** (inline):

**Pre-Completion Verification (MANDATORY)**: Before reporting done, run EVERY acceptance criterion's `check` command as separate shell invocation. For each: (a) run exact shell command from `check` field, (b) capture exit code and output, (c) record pass/fail with evidence. If ANY fails, fix and re-run ALL checks. Don't report completion until every check exits 0. If plan.json verificationSpecs[] has entry for your role, run spec via its runCommand AFTER all acceptance criteria pass. Spec files in `.design/specs/` are IMMUTABLE — fix code, never modify specs. Spec failures are blocking.

**Universal Worker Rules**: Tool boundaries: You may use Read, Grep, Glob, Edit, Write, Bash (for tests/build/git), LSP. Do NOT use WebFetch, WebSearch, MCP tools, or Task (no sub-spawning). | Failure handling: If cannot complete, return a structured failure summary with: role name, what failed, why, what you tried, suggested alternative. If rollback triggers fire, stop immediately and report. | Scope boundaries: Stay within your scope directories. Don't modify files outside scope unless absolutely necessary for integration. | **Minimal edits**: Only change what is necessary. Do not reformat, re-indent, or reorder surrounding code/YAML. Formatting churn inflates diffs and obscures real changes. | **INSIGHT**: If you discover a surprising finding during your work (unexpected constraint, contradicts assumption, high-impact decision), include it prominently in your completion summary. Maximum one insight — choose the most surprising.

**Completion format**: Return a structured text summary with these fields:
```
COMPLETION REPORT:
role: {name}
achieved: true|false
filesChanged: [list of files]
acceptanceCriteria:
- criterion: "..." | passed: true|false | evidence: "..."
keyDecisions: [list]
contextForDependents: "summary for dependent roles"
```

**Before spawning each worker**, set the role to in_progress so the state machine allows the completed transition after return:
```
python3 -c "import subprocess,json; subprocess.run(['python3','$PLAN_CLI','update-status','.design/plan.json'], input=json.dumps([{'roleIndex':N,'status':'in_progress'}]), text=True)"
python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event spawn --skill execute --agent "{worker-name}" --payload '{"model":"{model}","memoriesInjected":N}' || true
Task(subagent_type: "general-purpose", model: "{model}", prompt: <role-specific prompt with all above>)
```

### 4. Process Results

Process worker results as each Task() call returns.

**On role completion**: Worker returns structured text summary with achieved, filesChanged, acceptanceCriteria, keyDecisions, contextForDependents.
1. **Completion report validation**: Parse worker return value and validate structure. Required fields: role, achieved, filesChanged (list), acceptanceCriteria (list of criterion/passed/evidence), keyDecisions (list), contextForDependents (string). If any required field is missing, spawn a replacement Task() with instructions to re-run and return complete structured output. On second failure, escalate to user for manual review.
2. **Lead-side verification** (trust but verify): For each criterion in `plan.json roles[N].acceptanceCriteria`, run the `check` command via Bash independently. **Before rejecting, verify the actual file state** — run `git diff --name-only HEAD` and `ls -la {relevant files}` to confirm the worker's changes are actually present on disk. Stale diagnostics from cached state or previous runs can produce false rejections. Only reject if the check fails AND the file state confirms the work is genuinely absent. If any check exits non-zero after confirming actual file state, spawn a retry Task() with explicit fix instructions (see retry handling below).
3. Update plan.json — use `python3 -c` with subprocess to avoid pipe-to-script fragility (piping stdin directly to `python3 $PLAN_CLI` fails when the working directory is a Python package): `python3 -c "import subprocess,json; subprocess.run(['python3','$PLAN_CLI','update-status','.design/plan.json'], input=json.dumps([{'roleIndex':N,'status':'completed','result':'...'}]), text=True)"`. Then: `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event completion --skill execute --agent "{worker-name}" --payload '{"acPassed":N,"acTotal":N,"filesChanged":N,"firstAttempt":true|false}' || true`
4. Store `keyDecisions` and `contextForDependents` from the completion report. Inject this context into dependent role prompts when spawning them.
5. **Progress update**: Output "Completed: {role.name} — {one-line summary}"
6. **Post-worker CLI validation** (for SKILL.md-modifying roles only): If the completed role's filesChanged includes any SKILL.md file, scan the modified SKILL.md for `python3 $PLAN_CLI` references. For each referenced subcommand, run `python3 $PLAN_CLI {subcommand} --help 2>&1` to verify it exists. If a reference points to a non-existent command, fix the SKILL.md instruction before proceeding.

**On role failure**: Worker returns a failure summary.
1. Update plan.json: `echo '[{"roleIndex": N, "status": "failed", "result": "..."}]' | python3 $PLAN_CLI update-status .design/plan.json`. Then: `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event failure --skill execute --agent "{worker-name}" --payload '{"reason":"...","attempt":N,"model":"..."}' || true`
2. **Progress update**: Output "Failed: {role.name} — {failure reason}"
3. Circuit breaker: `python3 $PLAN_CLI circuit-breaker .design/plan.json`. If `shouldAbort`: go to Post-Execution.
4. Retries: `python3 $PLAN_CLI retry-candidates .design/plan.json`. If retryable (attempts < 3):
   a. **Reflexion step**: Before retry, generate a 2-3 sentence reflection analyzing what went wrong. Ask: What was the root cause? What assumptions were incorrect? What should be done differently? Update plan.json to append reflection to role.result: `echo '[{"roleIndex": N, "status": "failed", "result": "{existing_result}\n\n--- Retry {attempt+1} Reflexion ---\n{reflection_text}\n--- End Reflexion ---"}]' | python3 $PLAN_CLI update-status .design/plan.json`.
   b. Clean up partial work: `git checkout` + `rm` any artifacts from failed attempt.
   c. **Adaptive model escalation**: On retry, escalate the worker's model to the next tier: haiku → sonnet → opus. If already on opus, keep opus.
   d. Spawn retry Task() with structured context: Include in prompt "Retry {attempt+1}/3 for {role.name}. Previous attempt failed: {result}. Reflection: {generated reflection}. What to try differently: {suggested alternative or fallback}. Re-read acceptance criteria and verify each independently before reporting. **Fix constraint: modify existing files only — no new file creation allowed during retry.** If new files seem necessary, report it as a blocker instead." Use escalated model: `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event respawn --skill execute --agent "{worker-name}" --payload '{"attempt":N,"escalatedModel":"...","reason":"..."}' || true`
   e. **Progress update**: Output "Retry {attempt+1}/3: {role.name} (escalated to {new_model})"

### 5. Post-Execution Auxiliaries

Check `auxiliaryRoles[]` for `type: "post-execution"` roles. **Progress update** for each auxiliary: "Running {auxiliary.name}..."

Post-execution auxiliaries are standalone Task() calls.

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

**After integration-verifier completes**: Validate artifact via `python3 $PLAN_CLI validate-auxiliary-report --type integration-verifier .design/integration-verifier-report.json`. On validation failure: bypass Task() and perform integration verification directly via Bash: run `{testCommand}` from plan.json context if available, manually check that all worker-reported filesChanged exist via `ls -l {files}`, grep acceptance criteria for common issues. Save minimal report: `echo '{"status":"PASS","acceptanceCriteria":[],"crossRoleIssues":[],"testResults":{"command":"manual","exitCode":0,"output":"Bash bypass"},"endToEndVerification":{"tested":false,"result":"skipped","details":"Bash bypass fallback"},"summary":"Bash bypass — manual checks passed"}' > .design/integration-verifier-report.json`.

On FAIL: spawn targeted fix workers for specific issues. Re-run verifier after fixes (max 2 fix rounds). **Progress update** after verifier runs: "Integration verification: {PASS|FAIL}"

**Skip when**: only 1 role was executed, or all roles were independent (no shared directories, no cross-references), or all roles were fully sequential (maxDepth == roleCount) and all lead-side AC checks passed (lead already verified integration at each step).

**Spec curator** (MANDATORY — runs after integration-verifier, regardless of outcome): Spawn a standalone Task() spec-curator agent to promote durable behavioral contracts from this run's acceptance criteria into `.design/spec.json`. This step is MANDATORY — do not skip even if you believe no entries qualify. Bootstrap runs are NOT an exception — spawn spec-curator even if zero promotions are expected. The code path validation is the value. If integration-verifier FAILED, the spec-curator still runs but must exclude criteria that failed verification.

```
Task(subagent_type: "general-purpose", model: "sonnet", prompt: <spec-curator prompt below>)
```

Spec-curator prompt MUST include:
- "You are a spec-curator. Your job: identify acceptance criteria from this execution run that represent durable behavioral contracts — properties the system must preserve across all future implementations — and promote them to `.design/spec.json`."
- "Read `.design/plan.json` (all completed roles and their `acceptanceCriteria[]`). Read `.design/integration-verifier-report.json` if it exists. Read `.design/reflection.jsonl` (last entry — look for `acMutations` array to identify criteria that were mutated before spawning and must NOT be promoted)."
- "Read `.design/spec.json` if it exists to get existing entries. If spec.json does not exist, start with an empty entries array."
- "Apply ALL 5 promotion gates — a criterion must pass every gate to be promoted:"
  - "(1) Behavioral check: the criterion's `check` command verifies a WHEN→SHALL system response (trigger → observable behavior), not just file presence, pattern matching, or form. Run the check command against the current codebase — if it exits 0 before any new work would be needed, it is always-passing and must be excluded."
  - "(2) Durable invariant: the behavior is expected to hold for ALL future implementations of this system, not just the current one. Ask: if the system is completely reimplemented from scratch, should this property still hold?"
  - "(3) Not role-setup-specific: the check verifies persistent system behavior, not that the worker's environment was correctly configured for this specific role's work."
  - "(4) Not semantically duplicated: the behavioral boundary is not already covered by an existing spec.json entry (check for semantic overlap, not exact text match)."
  - "(5) Importance >= 5: core system functions and boundary enforcement score 8-10; secondary behavioral contracts score 5-7; entries below 5 are not worth persisting."
- "Exclusion patterns — automatically exclude criteria that match any of these: always-passing checks (exit 0 before work), implementation-naming checks (grep for function/class/variable names), documentation consistency checks (grep CLAUDE.md/README.md), test infrastructure checks (verifying the test suite itself), line-count or file-size checks, role-setup verification checks (file exists, server running, dependencies installed). Also exclude any criterion listed in `acMutations` from reflection.jsonl — mutated criteria were broken checks and must not enter the spec."
- "For each criterion that passes all 5 gates: call `python3 $PLAN_CLI spec-add .design/spec.json --entry '{\"ears\":\"WHEN [trigger], THE system SHALL [observable response]\",\"check\":\"{criterion.check}\",\"category\":\"behavioral-invariant|boundary-contract\",\"source\":\"{role.name}\",\"importance\":{score},\"reasoning\":\"{why this is a durable invariant}\"}'`. Do NOT write spec.json directly — use spec-add to ensure schema validation and sha256 computation."
- "After processing all criteria: return a summary: 'Spec curation complete. Promoted {count} entries, rejected {count} (with reasons), existing entries preserved {count}.'"

Wait for spec-curator completion. **Show user**: "Spec curator: {promoted} criteria promoted to spec.json."

**If 0 entries promoted**: This must be explicitly recorded. Record skip-justification in reflection immediately:

```bash
python3 $PLAN_CLI reflection-add .design/reflection.jsonl \
  --session-id $SESSION_ID \
  --skill execute \
  --goal "$GOAL" \
  --outcome partial \
  --goal-achieved false \
  --steps-skipped '["spec-curator-promotion"]' \
  --what-failed "Spec curator ran but promoted 0 entries. Justification: {curator summary of why all criteria were rejected — e.g., all surface-only, all role-setup-specific, all semantically duplicated}"
```

**Post-step verification**: After spec-curator completes, confirm that EITHER `.design/spec.json` was touched (entry count increased) OR reflection.jsonl contains a skip-justification entry for this session. If neither is true, the step did not complete — re-run the spec-curator or record the gap manually.

On spec-curator failure: proceed (spec curation does not block archive), but record the failure reason in reflection.

### 6. Goal Review

Before declaring completion, evaluate whether the work achieves the original goal.

Review against the goal from `plan.json`:
1. **Completeness** — Does the sum of completed roles deliver the goal end-to-end?
2. **Coherence** — Do the pieces fit together? Naming conventions consistent? Data models match across roles?
3. **User intent** — Would a user looking at the result say "this is what I asked for"?

If gaps are found: spawn a targeted worker to address them.

4. **Deployment state** — Run `git status --porcelain`. If changes exist and the project uses GitOps or CI/CD (check CLAUDE.md, context.stack, or project conventions), the goal is NOT achieved until changes are committed and in the deployment pipeline. Report as "partial" and prompt the user to commit/push, or offer to do so.

### 7. Complete

1. Summary: `python3 $PLAN_CLI status .design/plan.json`. Display a rich end-of-run summary:

```
Execution Complete: {goal}
Result: {goal achieved? yes/partial/no}

Roles: {completed}/{total} completed, {failed} failed, {skipped} skipped
{for each completed role: "  Completed: {name} — {one-line result}"}
{for each failed role: "  Failed: {name} — {failure reason}"}

Files Changed:
{deduplicated list from worker reports, grouped by role — use bullet list}

Acceptance Results:
{use markdown table format for clarity:}
| Criterion | Result |
|-----------|--------|
| {criterion text} | pass/fail |

Integration: {PASS|FAIL|SKIPPED — with details}

{if any worker returned an INSIGHT: display "INSIGHT: {finding}" — these are the surprising discoveries worth highlighting}

{if failures: "Recommended: /do:execute to retry failed roles, or /do:design to redesign."}
{if all passed: "All roles complete."}

{if goal involves external system (API, website, database, third-party service):
"Manual Validation Required:
  {specific command to run against live system, e.g. 'cd scraper && npm run scrape -- --headed --max-resorts 1'}
  Automated tests used fixture/mock data. Verify against the live system before relying on this in production."}
```
2. **Trace** — Emit completion trace:

   ```bash
   python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event skill-complete --skill execute --payload '{"outcome":"<completed|partial|failed|aborted>","rolesCompleted":N,"rolesFailed":N,"retries":N,"auxiliariesRun":["..."],"auxiliariesSkipped":["..."]}' || true
   ```

3. **Memory curation** — Spawn memory-curator via `Task(subagent_type: "general-purpose")`:

Prompt includes:
- "Reject aggressively — only store what a future engineer would find surprising and useful. If in doubt, reject. Prioritize unexpected findings over routine successes. Two high-quality entries are worth more than ten mediocre ones."
- "Read all artifacts: `.design/plan.json` (all roles including completed, failed, skipped, in_progress, pending — read result field for each), `.design/reflection.jsonl` (most recent entry — the self-evaluation for this run), `.design/challenger-report.json` (if exists), `.design/scout-report.json` (if exists), `.design/integration-verifier-report.json` (if exists)."
- "Read existing memories: `.design/memory.jsonl` (if exists). Note what is already recorded to avoid duplicates."
- "The reflection entry contains the lead's honest self-evaluation of what worked and what didn't. Use it as a primary signal for what to record — reflections that identify surprising failures or unexpected successes are high-value memory candidates."

**Quality gates** (all must pass before storing):

- TRANSFERABILITY TEST: Useful in new session? (reject: test counts, metrics, file lists, timings, exit codes)
- CATEGORY TEST: Fits convention|pattern|mistake|approach|failure|procedure? (reject: uncategorizable)
- SURPRISE TEST: Unexpected/contradicts assumptions? Score 7-10. Routine success? Score 1-3.
- DEDUPLICATION TEST: Not already in memory.jsonl? (reject: duplicates)
- SPECIFICITY TEST: Contains concrete reference (path|command|error|pattern|tool)? (reject: vague)

**Format:**
- "For each memory that passes all gates: call `python3 $PLAN_CLI memory-add .design/memory.jsonl --category <cat> --keywords <csv> --content <text> --importance <1-10>`"
- "Keywords: include technology names, directory paths, error types, tool names — terms a future goal description would contain."
- "Content: <200 words. State what you learned AND why it matters. Not what happened."
- "For failed/skipped roles: always create a `failure` or `mistake` memory with root cause analysis."
- "For Known Gaps that describe persistent architectural limitations (not one-off session artifacts): create a `procedure` memory. Example: reflection says 'Keyword scoring is basic (tokenized overlap)' — this recurs across runs and should be stored as procedure memory with importance 7+ so future sessions are aware of the limitation."
- "Return a summary when complete: 'Memory curation complete. Added {count} memories ({breakdown by category}). Rejected {rejected_count} candidates (not transferable or duplicates).'."

```
Task(subagent_type: "general-purpose", model: "haiku", prompt: <above>)
```

Wait for curator completion. **Show user**: "Memory curation: {count} learnings stored, {rejected} rejected." On failure: proceed (memory curation is optional).

   **Memory feedback** — Close the feedback loop on injected memories. For each role that had memories injected (tracked during spawn in Step 3), build a JSON array and pipe to memory-feedback:

   ```bash
   echo '[{"memoryIds":["id1","id2"],"roleSucceeded":true,"firstAttempt":true},{"memoryIds":["id3"],"roleSucceeded":false,"firstAttempt":false}]' | python3 $PLAN_CLI memory-feedback .design/memory.jsonl
   ```

   This boosts memories that correlated with first-attempt success (+1 importance) and decays memories that correlated with failure (-1 importance). Ambiguous cases (succeeded on retry) are left unchanged. All entries get `usage_count` incremented. On failure: proceed (non-blocking).

4. **Next action** — Always include `/do:reflect` first, then the situation-specific follow-up:
   - All roles passed: "Next: `/do:reflect`" then "review the output" or `/do:simplify {target}` if significant code was added.
   - Partial/failed: "Next: `/do:reflect`" then `/do:execute` to retry, or `/do:design {goal}` if failures are structural.

5. Archive: If all completed, move artifacts to history:
   ```bash
   python3 $PLAN_CLI archive .design
   ```
   If partial (failures remain): leave artifacts in `.design/` for resume.

**Arguments**: $ARGUMENTS
