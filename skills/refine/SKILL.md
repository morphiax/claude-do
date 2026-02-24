---
name: refine
description: Improve accepted artifacts — enhance clarity, consistency, maintainability while preserving all functionality. Runs after reflect's immediate findings are resolved.
argument-hint: "[--root PATH]"
context: fork
agent: general-purpose
allowed-tools: Read,Write,Edit,Glob,Grep,Bash,Task
model: claude-sonnet-4-6
satisfies:
  [
    RN-1,
    RN-2,
    RN-3,
    RN-4,
    RN-5,
    RN-6,
    RN-7,
    RN-8,
    RN-9,
    RN-10,
    RN-11,
    LC-4,
    LC-5,
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


# do-refine

Improve accepted artifacts. Preserve functionality; enhance clarity, consistency, maintainability. Execute makes things work. Reflect verifies correctness. Refine makes them clean [RN-5].

## CONTEXT ISOLATION [RN-1, RN-2]

This skill uses `context: fork` — when invoked, it automatically runs in an isolated subagent [RN-1]. The refining agent reads from filesystem only, not the conversation that produced the artifacts. The agent that wrote the code has sunk-cost bias; a fresh agent sees unnecessary complexity. No manual Task spawning needed.

**Manual** (user-invoked directly): MAY run in current context via `context: fork` override [RN-2].

## PHASE 1 — LOAD [IE-8, IE-9]

Deterministic reads. Complete all before any changes.

```bash
# Regression baseline — MUST pass before any refinement [RN-6]
python3 $DO spec preflight --root .do
# Record: total, passed, failed. If ANY fail -> STOP. Do not refine broken artifacts.

python3 $DO memory search --root .do --keyword "refine"
python3 $DO memory search --root .do --keyword "convention"
python3 $DO trace add --root .do --json '{"event":"refine_start","skill":"do-refine"}'
```

- Read `.do/plans/current.json` — extract completed roles, expected_outputs, scope
- Read `.do/conventions.md` (if exists) — defines "better" for this project [RN-4]
- Read `.do/aesthetics.md` (if exists) — defines "better" for user-facing work [RN-11]

**Preflight gate**: ANY preflight failure -> STOP and report to lead. Do not refine on a broken baseline.

## PHASE 2 — SCOPE IDENTIFICATION [RN-3]

Default: artifacts from **most recent execution only**. Surgical — improve what was just touched.

From plan's completed roles, collect:

- All `expected_outputs` from completed roles
- Verify each path exists on disk

**In scope**: files appearing in completed roles' expected_outputs that exist on disk.

**Out of scope** — do NOT touch:

- Files from prior execution cycles
- Persistent state: memory.jsonl, reflections.jsonl, traces.jsonl
- Specs, research artifacts, conventions, aesthetics
- Files outside plan's declared scopes

**Exception**: User explicitly directs broader scope -> honor that direction.

Read each in-scope file completely before editing. Full picture before assessment.

## PHASE 3 — IMPROVEMENT [RN-7, RN-8]

Every change must preserve functionality [RN-5]. Apply in order:

### Complexity Reduction

- Remove unnecessary nesting (early returns over deep if/else)
- Eliminate dead code (unreachable branches, unused imports, commented blocks)
- Split multi-concern functions — name each concern
- Replace clever constructs with explicit ones when clarity improves

### Redundancy Elimination

- Consolidate repeated logic into shared functions (DRY where it adds clarity)
- Remove comments restating what code already says
- Deduplicate data structures expressing same concept

### Naming and Readability

- Rename to express intent, not implementation (`get_data` -> `fetch_user_records`)
- Replace single-letter names except universal idioms (i, k/v)
- Align naming with conventions doc patterns
- Add docstrings to public functions lacking them (follow conventions format)

### Logic Consolidation

- Group related operations; separate unrelated concerns
- Consolidate related conditionals sharing common patterns
- Apply established project patterns from conventions doc

### Conventions Application [RN-4]

- For each convention: scan in-scope files for violations
- Apply mechanically, one at a time
- Document each applied convention in report

### Aesthetics Application [RN-11]

- If aesthetics doc exists and in-scope files include user-facing interfaces:
  - Evaluate against visual identity and interaction design foundations
  - Apply aesthetic consistency improvements
  - Improve information presentation per documented principles

**Balance constraint** [RN-8] — avoid:

- Over-simplification hiding necessary complexity
- Combining concerns to reduce line count when separation aids understanding
- Removing abstractions that exist for testability/extensibility
- Prioritizing fewer lines over readability

**Test for any change**: Does this make code easier to understand and extend? Yes -> apply. Unclear -> leave it.

## PHASE 4 — REGRESSION GATE [RN-6]

```bash
python3 $DO spec preflight --root .do
```

Compare to Phase 1 baseline:

- All contracts that passed before MUST still pass
- Any newly failed contract = refinement introduced regression

**If regression detected**:

1. Identify which change broke the contract (bisect if necessary)
2. Revert that specific change
3. Re-run preflight — confirm regression resolved
4. Document attempted change and why it regressed

Do NOT proceed to Phase 5 until baseline is restored.

## PHASE 5 — PERSIST [IE-8, IE-9]

```bash
# Trace completion
python3 $DO trace add --root .do --json '{
  "event": "refine_complete",
  "skill": "do-refine",
  "files_modified": <count>,
  "specs_passed": <count>,
  "regressions_found": <count>,
  "regressions_resolved": <count>
}'

# Reflection: session summary
python3 $DO reflection add --root .do --json '{
  "type": "refine_session",
  "outcome": "<what improved, conventions applied>",
  "lens": "process",
  "urgency": "deferred",
  "failures": [],
  "fix_proposals": []
}'

# Memory: persist high-value patterns (importance >= 6)
python3 $DO memory add --root .do --json '{
  "category": "refine_pattern",
  "keywords": ["refine", "<topic>"],
  "content": "<pattern that improved clarity or caught convention violation>",
  "source": "do-refine",
  "importance": 6
}'
```

**Propose conventions/aesthetics updates**: If refine revealed a reusable pattern not yet documented, propose update to lead [XC-16].

## REPORT FORMAT

```
REFINE COMPLETE

Scope: <N> files from <M> completed roles
Preflight baseline: <N> satisfied (all passed)
Post-refine preflight: <N> satisfied (all passed | N regressions found and resolved)

Files modified:
  <path>: <one-line improvement description>

Conventions applied:
  - <convention>: <files affected>

Regressions encountered: <N> (all resolved | N unresolved)

Convention/aesthetics proposals: <N>
  - <proposal summary>
```

## VERSION CONTROL [VC-2, VC-3, VC-5]

Commit all changes produced by this refine run. Working tree must be clean afterward.

1. Check working tree status: `git status --porcelain`
2. Resolve untracked files:
   - Refined source files, trace entries, `.do/` state files → `git add`
   - Generated/environment-specific files → add to `.gitignore`, then `git add .gitignore`
   - Scratch output that should not persist → delete
3. Stage all changes: `git add` relevant files
4. Commit: message summarizing refine output (files modified, conventions applied, regressions resolved)
5. Verify clean: `git status --porcelain` — must produce no output

If no changes were produced [VC-4]: skip commit.

## PROHIBITIONS

- MUST NOT change what artifacts do — only how [RN-5]
- MUST NOT add new functionality, features, or behaviors [RN-9]
- MUST NOT author new behavioral specs [RN-10]
- MUST NOT refine files outside declared scope [RN-3]
- MUST NOT proceed past Phase 4 with unresolved spec regressions [RN-6]
