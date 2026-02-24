---
name: execute
description: Execute a finalized plan — spawn workers per role, verify outputs, handle failures, satisfy specs.
argument-hint: "[plan-path] — defaults to .do/plans/current.json"
allowed-tools: Read,Write,Edit,Glob,Grep,Bash,Task,AskUserQuestion
model: claude-opus-4-6
satisfies:
  [
    EC-1,
    EC-2,
    EC-3,
    EC-4,
    EC-4a,
    EC-4b,
    EC-4c,
    EC-5,
    EC-6,
    EC-7,
    EC-8,
    EC-9,
    EC-10,
    EM-1,
    EM-2,
    EM-3,
    EM-4,
    EM-10,
    EM-13,
    EM-14,
    EM-15,
    EM-16,
    EM-17,
    EM-18,
    XC-1,
    XC-2,
    XC-3,
    XC-5,
    XC-6,
    XC-7,
    XC-8,
    XC-9,
    XC-41,
    IE-8,
    IE-9,
    IE-13,
    IE-15,
    IE-16,
    EC-11,
    EC-12,
    EC-13,
    LC-2,
    LC-3,
    LC-7,
    LC-15,
    SL-46,
    VC-1,
    VC-2,
    VC-3,
    VC-4,
    VC-5,
  ]
---

## CLI Setup

Resolve the helper script path at skill start. `scripts/do.py` is a symlink that resolves to `shared/do.py` in the plugin root.

Use the Glob tool to find `scripts/do.py` relative to this SKILL.md, then resolve its absolute path:

```bash
DO=$(python3 -c "import os; print(os.path.realpath('<absolute-path-to-scripts/do.py>'))" )
```

All commands: `python3 $DO <domain> <command> --root .do`


# LOAD STATE [IE-8, IE-9, LC-15] — deterministic

Execute all loads before any work:

1. Read plan file (default `.do/plans/current.json`). If not finalized:

   ```
   python3 $DO plan finalize-file .do/plans/current.json
   ```

   Parse result. On error: halt — plan must be valid before execution.

2. Spec preflight — re-verify all satisfied contracts and establish regression baseline [EC-4, EC-4c]:

   ```
   python3 $DO spec preflight --root .do
   ```

   Record `preflight_baseline`: total, passed, failed, revoked. Preflight re-runs all satisfied contracts — some may have regressed and been revoked to pending.

3. Contract coverage gate [EC-4a, EC-4c, SL-46] — verify plan contracts are registered AND determine work scope:

   First, get the spec registry:

   ```
   python3 $DO spec list --root .do
   ```

   Extract the `contracts` array from the result. Then run coverage:

   ```
   python3 $DO plan coverage --plan-json '<plan-json>' --spec-json '<spec-contracts-json>'
   ```

   The coverage command returns:
   - `missing`: contract_ids not in registry → HALT, design failed to register
   - `pending`: registered but unsatisfied → these need work
   - `satisfied`: registered and still satisfied after preflight → skip
   - `roles_to_execute`: roles with at least one pending contract
   - `roles_to_skip`: roles whose contracts are all satisfied
   - `has_work`: false when nothing is pending → HALT, nothing to do

   **Gates**:
   - WHEN `missing` is non-empty: halt and report — design failed to register contracts
   - WHEN `has_work` is false: halt — all contracts already satisfied, no work needed
   - Record `pending_contract_ids` — only these will be satisfied after execution

4. Execution order:

   ```
   python3 $DO plan order-file .do/plans/current.json
   ```

   Returns topologically sorted role indices. Filter against `roles_to_execute` — skip roles not in the execute list.

5. Read `.do/conventions.md` if exists — workers inherit project conventions [XC-14].
6. Read `.do/aesthetics.md` if exists — workers with UI scope inherit aesthetics [DS-6].
7. `python3 $DO memory search --root .do --keyword execution` — prior execution learnings.
8. `python3 $DO trace add --root .do --json '{"event":"execute_start","plan":"<plan-path>"}'`

---

# TEST GENERATION [EC-11, EC-12, EC-13] — creative

Before spawning implementation workers, generate tests from behavioral contracts for all pending roles.

For each role in `roles_to_execute`:

1. **Extract contracts**: get the role's `contract_ids` list filtered to `pending_contract_ids`.

2. **Spawn test-generation worker** via Task tool:

   Worker receives ONLY:
   - The role's contract_ids and their spec content (behavioral descriptions)
   - The role's scope, expected_outputs, and verification commands
   - Project conventions from `.do/conventions.md`
   - **NOT** implementation code — test authors must not see implementation [EC-11]

   Worker instructions:
   - Write test files that assert the behavioral contracts as executable tests
   - Tests go in the role's scope (typically `tests/` directory)
   - Each contract should have at least one test asserting its expected behavior
   - Use pytest conventions, tmp_path fixtures for isolation
   - Report: test files created, test count per contract

3. **Red check** [EC-12] — verify all new tests FAIL against current codebase:

   ```
   python3 -m pytest <test-files> -x 2>&1
   ```

   - Tests that FAIL: correct — behavior not yet implemented
   - Tests that PASS: investigate — either behavior already exists (contract should not be pending) or test is vacuous
   - If all tests pass: halt role — contracts may already be satisfied, re-check with preflight

4. **Trace**:

   ```
   python3 $DO trace add --root .do --json '{"event":"tests_generated","role":"<name>","test_count":<N>,"all_failing":true}'
   ```

WHEN test generation is complete for all roles, proceed to the execution loop. Workers will implement until these tests pass.

---

# EXECUTION LOOP [EM-3, EM-14, EM-15, EM-18, XC-2] — creative

Process roles in topological order from step 4, but ONLY roles in `roles_to_execute`.

For roles in `roles_to_skip` (all contracts already satisfied): transition directly to `completed` without spawning a worker.

For each role at index `i` in `roles_to_execute`:

1. **Dependency gate**: all roles in `dep_indices` must be `completed`. If any dependency is `failed` or `skipped`: skip this role via cascade (handled automatically by failure path).

2. **Snapshot scope** [EC-7] — record files before execution:

   ```
   python3 $DO plan snapshot-scope --json '<plan-json>' --role-index <i>
   ```

   Record `before_files` for delta comparison after worker completes.

3. **Transition to in_progress** and trace:

   ```
   python3 $DO plan transition --file .do/plans/current.json --role-index <i> --new-status in_progress
   ```

   ```
   python3 $DO trace add --root .do --json '{"event":"role_start","role":"<name>","role_index":<i>}'
   ```

4. **Spawn worker** via Task tool [EM-3]:

   Worker receives the role object directly from the plan — name, goal, context, constraints, verification, scope, expected_outputs, assumptions, rollback_triggers, fallback [EM-18, XC-2].

   Worker instructions:
   - Implement ONLY what the role specifies
   - Respect scope boundaries — do not create/modify files outside `scope` directories [EC-8, EC-9]
   - Contract tests were pre-generated in the TEST GENERATION phase — implementation must make those tests pass [EC-13]
   - Run all `verification` commands — every command must exit 0 [EC-5]
   - Report back: files created/modified, verification results, any issues
   - On rollback trigger: stop and report failure with reason

   Model from role's `model` field [EM-15]:
   - `opus` = complex judgment tasks
   - `sonnet` = typical implementation
   - `haiku` = straightforward/mechanical tasks

5. **Parallel execution** [EM-4]: roles with no mutual dependencies MAY run concurrently. Roles with overlapping scope (from plan `overlaps`) MUST be serialized.

---

# PER-WORKER VERIFICATION [EC-5, EC-6, EC-7, EC-9, EC-10] — deterministic

After each worker completes:

1. **Scope check** — every file the worker touched [EC-9]:

   ```
   python3 $DO plan scope-check --json '<plan-json>' --role-index <i> --file <touched-file>
   ```

   Any out-of-scope file is a violation. Worker must undo or the role fails.

2. **File delta** [EC-7] — compare against pre-execution snapshot:

   ```
   python3 $DO plan snapshot-scope --json '<plan-json>' --role-index <i>
   ```

   Then compute delta:

   ```
   python3 $DO plan file-delta --before <before-files-csv> --after <after-files-csv>
   ```

   New files in delta absent from `expected_outputs` are unexpected output violations.

3. **Unexpected outputs** [EC-10]:

   ```
   python3 $DO plan unexpected-outputs --json '<plan-json>' --role-index <i> --files <file1>,<file2>,...
   ```

   Files present but not in `expected_outputs` are flagged. Undeclared new files (from delta) are violations — role fails.

4. **Verification commands** [EC-5]:

   Run each command in the role's `verification` list. ALL must exit 0. On any failure: the role fails.

5. **Status transition** and trace:
   - Success:
     ```
     python3 $DO plan transition --file .do/plans/current.json --role-index <i> --new-status completed
     python3 $DO trace add --root .do --json '{"event":"role_completed","role":"<name>","role_index":<i>}'
     ```
   - Failure:
     ```
     python3 $DO plan transition --file .do/plans/current.json --role-index <i> --new-status failed
     python3 $DO trace add --root .do --json '{"event":"role_failed","role":"<name>","role_index":<i>,"reason":"<reason>"}'
     ```

---

# FAILURE HANDLING [EC-2, EC-3, EM-7, EM-10] — deterministic

WHEN a role fails:

1. **Cascade** [EC-2, EC-3]:

   ```
   python3 $DO plan cascade --file .do/plans/current.json --role-index <i>
   ```

   Returns: `skipped` (list of role names), `pending_before` (count), `abort` (bool).
   Transitively dependent pending roles are marked `skipped` [EM-7].

2. **Abort check** [EM-10]:

   If `abort` is true (>50% of pending roles would be skipped): halt entire execution.
   Log abort reason. Do NOT continue with remaining roles.

3. **Continue**: if not aborting, proceed to next role in execution order. Already-skipped roles are skipped automatically by the dependency gate.

   (Role failure is already traced in PER-WORKER VERIFICATION step 5.)

---

# REGRESSION GATE [EC-4, SL-30] — deterministic

After ALL roles complete (or execution halts):

1. **Spec preflight** — re-verify all previously satisfied specs:

   ```
   python3 $DO spec preflight --root .do
   ```

2. Compare against `preflight_baseline` from load phase. Any newly failing spec is a regression.

3. WHEN the regression gate has zero specs to verify: report as **vacuous**, not passing.

4. On regression: report which specs regressed, which roles likely caused them (by scope overlap with spec artifacts). Execution is NOT successful if regressions exist.

---

# SPEC SATISFACTION [XC-6, XC-8, XC-9, EC-4b, EC-4c] — deterministic

Only satisfy contracts that were PENDING at execution start (recorded in `pending_contract_ids` from load step 3).

For each COMPLETED role:

1. Get the role's `contract_ids` list.
2. For each contract ID that is in `pending_contract_ids`, satisfy via CLI [XC-6]:

   ```
   python3 $DO spec satisfy --root .do --id <contract-id> --json '{"role":"<name>","verification":"passed"}'
   ```

3. Skip contract_ids that were already satisfied at execution start — do not re-satisfy.
4. Only satisfy contracts whose verification commands passed [XC-8]. Never satisfy contracts for failed/skipped roles.
5. Design is the sole spec author [XC-7] — execute never registers or modifies specs [EC-9].

6. **Satisfaction completeness report** [EC-4b]: after all satisfaction attempts, report:
   - Which contract_ids were satisfied (newly)
   - Which contract_ids were already satisfied (skipped)
   - Which contract_ids remain unsatisfied and why (role failed, verification failed, etc.)
   - WHEN any contract_id from a completed role remains unsatisfied: report as a gap

---

# PERSIST [IE-8, IE-9] — deterministic

1. **Trace** — record execution_complete with summary:

   ```
   python3 $DO trace add --root .do --json TRACE_JSON
   ```

   TRACE_JSON keys: event=execute_complete, completed=N, failed=N, skipped=N, contracts_satisfied=N, contracts_already_satisfied=N.

2. **Reflection** — record execution outcome [LC-2]. Required fields: type, outcome, lens=process, urgency=deferred, failures=[], fix_proposals=[]:

   ```
   python3 $DO reflection add --root .do --json REFLECTION_JSON
   ```

   REFLECTION_JSON keys: type=execution, outcome=summary, lens=process, urgency=deferred, failures=[], fix_proposals=[].
   If failures occurred: populate failures list with role names and reasons. Populate fix_proposals with actionable improvements.

3. **Memory** — record significant execution learnings. Required fields: category=execution, keywords, content, source=do-execute, importance (3–10):

   ```
   python3 $DO memory add --root .do --json MEMORY_JSON
   ```

   MEMORY_JSON keys: category=execution, keywords=[...], content=learning, source=do-execute, importance=5.

4. **Propose updates** [XC-16, DS-8]:
   - Conventions: note patterns discovered during execution
   - Aesthetics: note interaction patterns from UI-producing roles

5. **Report to user** [LC-1] — present execution summary (completed/failed/skipped roles, regression gate result, satisfaction completeness). Wait for user acknowledgment before proceeding.

6. **Invoke reflect** [LC-2, LC-8, XC-23] — MANDATORY. Execute without reflect is an incomplete cycle.
   Invoke do-reflect via Skill tool. do-reflect uses `context: fork` — automatically runs in an isolated subagent.
   After reflect completes, present immediate findings to user [LC-3].
   User resolves each immediate finding before proceeding.

7. **Invoke refine** [LC-7] — MANDATORY. Every execution cycle produces artifacts that benefit from a consistency and clarity pass.
   Invoke do-refine via Skill tool (uses `context: fork` — automatically runs in an isolated subagent).
   Trace the invocation:
   ```
   python3 $DO trace add --root .do --json '{"event":"refine_start"}'
   ```
   After refine completes:
   ```
   python3 $DO trace add --root .do --json '{"event":"refine_complete"}'
   ```

8. **Archive** [LC-5, XC-41] — after cycle complete (execute + reflect + refine, all immediate findings resolved):
   ```
   python3 $DO archive --root .do
   ```
   Verify archive post-conditions are met (no ephemeral dirs remain, persistent files intact, history contains archived artifacts).

---

# VERSION CONTROL [VC-2, VC-3, VC-5]

Commit all changes produced by this execution cycle. Working tree must be clean afterward.

1. Check working tree status: `git status --porcelain`
2. Resolve untracked files:
   - Implementation artifacts, tests, config produced by workers → `git add`
   - Generated/environment-specific files (caches, build output) → add to `.gitignore`, then `git add .gitignore`
   - Scratch output that should not persist → delete
3. Stage all changes: `git add` relevant files
4. Commit: message summarizing execution output (roles completed/failed/skipped, contracts satisfied, regressions)
5. Verify clean: `git status --porcelain` — must produce no output

If no changes were produced [VC-4]: skip commit.

Run this AFTER archive (step 8) — the commit captures the final post-archive state of the cycle.

---

# PROHIBITIONS

- `[EC-8]` MUST NOT modify the plan structure — only transition role statuses
- `[EC-9]` MUST NOT author or modify spec contracts — design is the sole author
- `[EC-10]` MUST NOT allow workers to modify files outside their declared scope
- `[EM-16]` MUST NOT read project source files directly — delegate to workers
- `[EM-17]` MUST NOT write implementation artifacts — workers produce all outputs
