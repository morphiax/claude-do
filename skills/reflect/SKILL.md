---
name: reflect
description: Adversarial review producing classified observations (product/process, immediate/deferred). Observer only — surfaces findings, does not prescribe action.
argument-hint: "[--root PATH]"
context: fork
agent: general-purpose
allowed-tools: Read,Glob,Grep,Bash,Task,mcp__sequential-thinking__sequentialthinking
model: claude-opus-4-6
satisfies:
  [
    FC-1,
    FC-2,
    FC-3,
    FC-4,
    FC-5,
    FC-6,
    FC-7,
    FC-8,
    FC-9,
    FC-10,
    FC-11,
    XC-12,
    XC-18,
    XC-23,
    XC-26,
    XC-27,
    XC-28,
    XC-29,
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


# do-reflect

Adversarial reviewer. Surface findings; lead and user decide action [FC-9].

## CONTEXT ISOLATION [FC-6, FC-7]

This skill uses `context: fork` — when invoked, it automatically runs in an isolated subagent [FC-6]. The reviewing agent reads from disk only, not the conversation that produced the artifacts. No manual Task spawning needed.

**Manual** (user-invoked directly): MAY run in current context via `context: fork` override. Reduced objectivity accepted [FC-7].

## PHASE 1 — LOAD [IE-8, IE-9]

Deterministic reads. Complete all before analysis.

```bash
python3 $DO spec list --root .do
python3 $DO memory search --root .do --keyword "reflect"
python3 $DO reflection list --root .do --urgency immediate
python3 $DO trace add --root .do --json '{"event":"reflect_start","skill":"do-reflect"}'
```

- Read `.do/plans/current.json` — extract roles, expected_outputs, contract_ids, verification commands
- Read `.do/conventions.md` (if exists)
- Read `.do/aesthetics.md` (if exists)
- Read all `expected_outputs` files from plan roles — build intended-vs-actual map
- Glob each role's `scope` directories — identify filesystem reality

## PHASE 2 — ADVERSARIAL REVIEW [FC-1, XC-18]

Use `mcp__sequential-thinking__sequentialthinking` for structured multi-step reasoning. Apply best available adversarial frameworks from foundational knowledge — select for effectiveness, not convention [SL-32].

**Mandatory dimensions — all five required:**

### A. Intended vs Actual

- What did each role declare? (expected_outputs, goal, contract_ids)
- What exists on disk? (glob within declared scope)
- Per gap: product defect, spec gap, or acceptable deviation?

### B. Skipped Steps

- Enumerate verification commands per role — did they pass?
- Scope compliance: files created outside declared scope?
- Unexpected outputs: files not in expected_outputs?
- Contract coverage: all contract_ids addressed?

### C. Counter-Evidence and Latent Assumptions

- Assumptions embedded in plan structure (role count, scope divisions, dependency ordering)
- Evidence contradicting the plan's approach
- What must be true for dependent role work to fail despite own verification passing?

### D. Prospective Failure

- Most likely failure modes in subsequent use
- Edge cases implementations don't handle
- Latent defects no verification command catches

### E. Lifecycle Integrity [FC-11]

Verify the execution lifecycle was sound:

1. **Registry health**: Was the spec registry non-empty when the plan referenced contract_ids? Run:
   ```
   python3 $DO spec list --root .do
   ```
   Cross-reference against plan's contract_ids. WHEN plan references contract_ids but registry is empty or missing referenced IDs: process + immediate observation.

2. **Satisfaction completeness**: Were all completed roles' contract_ids satisfied? Check trace for satisfaction events. WHEN a completed role's contracts were not satisfied: process + immediate observation.

3. **Regression gate non-vacuity**: Did the regression gate test at least one spec? Check trace for preflight results. WHEN regression gate was vacuous (zero specs tested): process + immediate observation.

4. **Coverage gate**: Did execute check which contracts were already satisfied and only work on pending ones? WHEN execute re-satisfied already-satisfied contracts or worked on roles with no pending contracts: process + immediate observation.

**Aesthetics review** [FC-10]: If aesthetics doc exists and artifacts include user-facing interfaces — evaluate against aesthetic identity. Vague or gap-revealing aesthetics doc -> propose aesthetics updates as product+deferred observations.

## PHASE 3 — OBSERVATIONS [FC-2, FC-3, FC-8, FC-10]

Every observation requires both classifications [XC-26]:

| Lens    | Scope                                           |
| ------- | ----------------------------------------------- |
| product | Is the artifact correct? Output matches intent? |
| process | Was the method sound? Approach improvable?      |

| Urgency   | Action                             | Consumer            |
| --------- | ---------------------------------- | ------------------- |
| immediate | Evaluate before proceeding         | Lead/user           |
| deferred  | Accumulates for future improvement | Design (next cycle) |

**Severity**: critical | high | medium | low

### Product gaps [FC-2] — lens:product, urgency:immediate

- File path + line range
- Current content (verbatim)
- Proposed change (exact replacement)
- Rationale

### Spec gaps [FC-3] — lens:product, urgency:deferred

- Which contract ID is underspecified or missing
- Unaddressed observable behavior
- Proposed tightening in trigger-obligation form
- Reflect does NOT write specs [FC-5]

### Aesthetics gaps [FC-10] — lens:product, urgency:deferred

- Aesthetic gap revealed by artifacts
- Proposed addition/change to aesthetics doc

### Process weaknesses [FC-8] — lens:process, urgency:immediate|deferred

- Missing/weak step with evidence from this run
- Pattern or recurrence indicator
- Concrete improvement proposal

## PHASE 4 — VALIDATE OBSERVATIONS [XC-26]

Before persisting, every observation must have:

- `lens` (product|process)
- `urgency` (immediate|deferred)
- `severity` (critical|high|medium|low)
- `evidence` — specific file paths, line numbers, command outputs (not assertions)
- `proposal` — actionable, not vague
- If `failures` non-empty -> `fix_proposals` must be non-empty [XC-12]

Discard vague entries without actionable fixes. Quality over volume.

## PHASE 5 — PERSIST [FC-4, IE-8, IE-9]

```bash
# Each observation -> structured reflection entry
python3 $DO reflection add --root .do --json '{
  "type": "product_gap|spec_gap|aesthetics_gap|process_weakness|lifecycle_integrity",
  "outcome": "<one-sentence summary>",
  "lens": "product|process",
  "urgency": "immediate|deferred",
  "severity": "critical|high|medium|low",
  "failures": ["<specific finding with evidence>"],
  "fix_proposals": ["<concrete actionable proposal>"]
}'

# Trace completion
python3 $DO trace add --root .do --json '{
  "event": "reflect_complete",
  "skill": "do-reflect",
  "observations": <count>,
  "immediate": <count>,
  "deferred": <count>
}'

# Memory: persist high-value learnings (importance >= 6)
python3 $DO memory add --root .do --json '{
  "category": "reflect_finding",
  "keywords": ["<topic>"],
  "content": "<learning worth carrying forward>",
  "source": "do-reflect",
  "importance": 7
}'
```

## PHASE 6 — SURFACE IMMEDIATE FINDINGS [XC-27]

Report to lead after persisting:

```
REFLECT COMPLETE

Immediate findings requiring evaluation:
  [PRODUCT/severity] <finding> — <file:line> — Proposed: <patch summary>
  [PROCESS/severity] <finding> — <evidence> — Proposed: <improvement>
  [LIFECYCLE/severity] <finding> — <evidence> — Proposed: <fix>

Deferred findings (stored, no action required now):
  <N> spec gaps [XC-28]
  <N> aesthetics gaps
  <N> process observations [XC-29]

Next: lead presents immediate findings to user per [LC-3].
Unresolved immediate findings block transition to refine [LC-4].
```

## VERSION CONTROL [VC-2, VC-3, VC-5]

Commit all changes produced by this reflect run. Working tree must be clean afterward.

1. Check working tree status: `git status --porcelain`
2. Resolve untracked files:
   - Reflection entries, trace entries, `.do/` state files → `git add`
   - Generated/environment-specific files → add to `.gitignore`, then `git add .gitignore`
   - Scratch output that should not persist → delete
3. Stage all changes: `git add` relevant files
4. Commit: message summarizing reflect output (observation count, immediate/deferred split)
5. Verify clean: `git status --porcelain` — must produce no output

If no changes were produced [VC-4]: skip commit.

## PROHIBITIONS

- MUST NOT modify behavioral specs [FC-5]
- MUST NOT override lead judgment [FC-9] — observations, not directives
- MUST NOT produce observations without lens + urgency [XC-26]
- MUST NOT write reflections with non-empty failures and empty fix_proposals [XC-12]
