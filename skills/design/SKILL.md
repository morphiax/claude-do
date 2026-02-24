---
name: design
description: Reconcile spec with product, decompose a goal into expert-analyzed role-based execution plan, author behavioral contracts.
argument-hint: "[goal] — omit to run full reconciliation"
allowed-tools: Read,Write,Edit,Glob,Grep,Bash,Task,AskUserQuestion,mcp__sequential-thinking__sequentialthinking
model: claude-opus-4-6
satisfies:
  [
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


# PHASE 1 — LOAD STATE [IE-8, IE-9]

Deterministic. Execute ALL before any synthesis.

1. Read `.do/conventions.md` if exists [XC-14]
2. Read `.do/aesthetics.md` if exists [DS-1]
3. `python3 $DO spec list --root .do` — current contract statuses
4. `python3 $DO spec preflight --root .do` — re-verify satisfied contracts; revoke regressions [SL-30]
5. `python3 $DO spec divergence --root .do --spec-doc spec.md` — detect unregistered/orphaned IDs [SL-29]
6. `python3 $DO memory search --root .do --keyword <goal-keywords>` — prior learnings [XC-21]
7. `python3 $DO reflection list --root .do --urgency immediate` — unresolved immediate findings
8. `python3 $DO reflection list --root .do --lens product --urgency deferred` — pending spec tightenings [XC-28]
9. `python3 $DO research search --root .do --keyword <goal-keywords>` — prior research [DC-16]
10. `python3 $DO trace add --root .do --json '{"event":"design_start","goal":"<goal>"}'`

If preflight revokes any contracts: note them — they become pending work.
If divergence finds unregistered IDs: flag for registration during spec authoring.
If divergence finds orphaned IDs: flag for cleanup.

---

# PHASE 2 — RECONCILIATION [DC-9, DC-10, DC-11, DC-12, DC-13]

Compare spec contracts against product state. Classify every gap:

- **Spec-only** (pending contracts): behavior in spec, not yet in product. Pending work.
- **Product-only** (undocumented): behavior in product, no spec contract.
  - Ask user via AskUserQuestion: "Codify as pre-satisfied contract, or flag for removal?" [DC-10]
- **Mismatches** (drift): both exist, disagree.
  - Ask user per gap: "Update spec to match product, or product to match spec?" [DC-11]

When user chooses to codify existing behavior [DC-12]:

- Author contract in trigger-obligation form: `WHEN <trigger>, system SHALL <outcome>` [SL-18]
- Mark pre-satisfied (exception to TDD rule — behavior already exists)
- `python3 $DO spec register --root .do --id <ID> --type execute --json '{"command":"<cmd>"}'`

Goal scoping [DC-1]:

- Goal provided: narrow to contracts the goal addresses
- No goal: treat ALL gaps as work scope

---

# PHASE 3 — SPEC AUTHORING [DC-2, DC-13, DC-15, SL-12 through SL-40]

Author NEW contracts for behavior not yet implemented. TDD: specs MUST FAIL against current codebase [XC-9].

Per-contract requirements:

- Technology-agnostic description — no tool names, file paths, API fields [SL-12]
- Knowledge-agnostic — describe outcomes, not named frameworks [SL-32]
- Trigger-obligation form: `WHEN <observable trigger>, system SHALL <observable outcome>` [SL-18]
- Stable ID assigned at authorship — never changes [SL-7]
- Every SHALL/MUST obligation gets an ID [SL-40]
- Portability test: "Still valid if reimplemented in another language?" [SL-37]
- Freshness test: "Does this prevent adopting better approaches?" [SL-38]

Document form checks [DC-15, SL-15, SL-16, SL-17, SL-19, SL-20, SL-21, SL-22, SL-23]:

- All IDs unique, all cross-references resolve
- Top-down: purpose -> capabilities -> contracts -> cross-cutting -> operational [SL-16]
- Each section opens with context paragraph before contracts [SL-17]
- Positive contracts separated from prohibitions [SL-20]
- Grouped by concern with shared ID prefix [SL-19]
- Rebuild test: spec alone sufficient to reconstruct system [SL-21]
- Recreation test: system can produce equivalent-quality specs [SL-22]
- Single document with inline contract IDs [SL-23]
- Implementation choices called out explicitly [SL-39]

Register each new contract — THIS IS MANDATORY, not optional [DC-20]:

```
python3 $DO spec register --root .do --id <ID> --type execute --json '{"command":"<cmd>"}'
python3 $DO spec register --root .do --id <ID> --type review --json '{"question":"<q>","artifact":"<path>","evidence_commands":[]}'
```

Every contract ID that will appear in a plan's `contract_ids` MUST be registered here. Execute validates that all plan contract_ids exist in the registry [EC-4a] and halts if any are missing. Unregistered contract IDs break the satisfaction chain and leave the regression gate inert.

Bidirectional traceability [SL-31]: every contract ID must be findable via text search in both spec and implementation.

---

# PHASE 4 — AESTHETICS ESTABLISHMENT [DS-1 through DS-14]

TRIGGER: goal produces user-facing interfaces AND `.do/aesthetics.md` does not exist.
SKIP if trigger not met.

Apply established design methodology from foundational knowledge [DS-4, XC-18]:

1. **Direction** [DS-3, DS-5]: analyze purpose, audience, tone. Commit to a DISTINCTIVE direction — not generic/safe. Document alternatives considered and rationale.
2. **Visual identity**: aesthetic direction, visual language, spatial principles, color, typography
3. **Mental models** [DS-9]: what users believe the system does, likely misconceptions, what interface must reinforce or correct
4. **Information architecture** [DS-10]: enumerate all user-facing concepts, classify as primary/secondary/progressive
5. **State design** [DS-11]: for each interface element define empty/loading/success/error/partial states — what user sees, understands, can do next
6. **Cognitive load** [DS-12]: identify decision/uncertainty/wait moments, document simplification strategies
7. **Flow integrity** [DS-13]: where could first-time users get lost? what must be explicit vs implied?

Write `.do/aesthetics.md`.

---

# PHASE 5 — EXPERT ANALYSIS [DC-3, DC-4, DC-8, DC-17]

MANDATORY for goals with 3+ roles [DC-8]. For simpler goals, use judgment.

Spawn >=2 experts via Task tool with contrasting priorities [DC-3]:

- **Expert A**: correctness, safety, long-term maintainability
- **Expert B**: delivery speed, simplicity, minimal surface area
- **Expert C** (when UI present) [DS-7]: visual/interaction design evaluation

Each expert receives: goal, relevant spec contracts, conventions, aesthetics, prior research, memory findings.
Each expert returns: role structure proposal, scope boundaries, dependency graph, risks.

When experts disagree [DC-4]:

- Use `mcp__sequential-thinking__sequentialthinking` for structured conflict resolution [IE-10]
- Document reasoning for each decision
- State conditions under which chosen direction would be wrong [IE-21]

When knowledge gaps exist [DC-17]:

- `python3 $DO research search --root .do --keyword <gap-topic>`
- If no prior research covers the gap: invoke do-research via Skill tool (uses `context: fork` — runs in isolated subagent for context economy)
- Do NOT guess when you can know

---

# PHASE 5b — CONVENTIONS BOOTSTRAP [XC-14a, XC-14, XC-20]

TRIGGER: `.do/conventions.md` does not exist (checked in Phase 1 step 1).
SKIP if conventions already exist.

**Step 1 — Research the stack** [DC-17]:

For each technology in the project (language, frameworks, libraries, storage, tooling):

- Check prior research: `python3 $DO research search --root .do --keyword <technology>`
- WHEN no prior research covers the technology: invoke do-research via Skill tool with topic scoped to that technology's idiomatic patterns, community best practices, common failure modes, documented anti-patterns, and production-readiness concerns. do-research uses `context: fork` — runs in isolated subagent for context economy.
- do-research performs comprehensive external investigation (WebSearch, WebFetch, source analysis) — not internal codebase search
- Wait for research artifacts before proceeding to Step 2

**Step 2 — Write `.do/conventions.md`** capturing:

1. **Technology choices** [XC-20]: runtime, storage, module system, dependencies — with rationale, alternatives considered, constraints that drove decisions
2. **Idiomatic patterns**: how the ecosystem expects this stack to be used — naming, structure, error handling, concurrency, testing idioms
3. **Best practices**: community-established standards — linting, formatting, type checking, dependency management, CI patterns
4. **Anti-patterns and failure modes**: documented pitfalls — what NOT to do and why, common mistakes, performance traps, security gotchas
5. **Coding standards**: style rules, import ordering, documentation expectations
6. **Platform patterns**: file organization, test structure, build commands
7. **Project-specific idioms**: patterns established by this project that workers must follow

Conventions must exist BEFORE plan assembly so `[XC-15]` can inject them into role constraints.

---

# PHASE 6 — PLAN ASSEMBLY [XC-1 through XC-5, XC-15, XC-17, XC-19, DC-6, DC-14, DC-18]

Build plan JSON at `.do/plans/current.json`. Schema version 2.

Every role MUST have ALL required fields [XC-4]:

| Field               | Content                                                        |
| ------------------- | -------------------------------------------------------------- |
| `name`              | Unique imperative noun (for example, "auth-module") [PV-2]     |
| `goal`              | What to achieve                                                |
| `contract_ids`      | Spec IDs this role satisfies [XC-1]                            |
| `scope`             | Directories the worker may touch                               |
| `expected_outputs`  | Exact file paths to create/modify                              |
| `context`           | Domain knowledge: conventions, patterns, algorithms, prior art |
| `constraints`       | Hard rules: satisfied specs, scope rules, invariants           |
| `verification`      | Shell commands that exit 0 when role complete [EC-5]           |
| `assumptions`       | Preconditions that must be true                                |
| `rollback_triggers` | When to abandon and signal failure                             |
| `fallback`          | Alternative approach if primary fails                          |
| `model_tier`        | `high` / `standard` / `efficient` per complexity [EM-15]       |
| `dependencies`      | Names of prerequisite roles [XC-5]                             |

Context vs constraints [XC-17]:

- **context** = domain knowledge (guidance) — inject conventions [DC-14], expert findings, aesthetics [DS-6, DS-14], foundational knowledge [XC-19], research findings [DC-16]
- **constraints** = enforceable rules — inject satisfied specs [DC-6], scope rules, invariants

Plan integrity rules:

- 1-8 roles [PV-1]
- No circular dependencies [PV-3]
- Self-contained: worker reading only the plan has everything needed [XC-2]
- Scope tracing [DC-18]: trace transitive dependencies (imports, shared types) outside initial scope. Include in scope or add dependency role.
- When plan includes UI roles: inject aesthetics into context [DS-6, DS-14]
- Verification commands SHALL reference the project command surface [XC-31] rather than raw tool invocations

Command surface [XC-30, XC-31]:

- Read the project's command surface (tool recorded in conventions)
- WHEN new operations are introduced by this plan: add entries to the command surface before finalization
- WHEN no command surface exists: create one, recording the tool choice in conventions
- Role verification fields reference command surface entries (`just test` not `cd /path && python -m pytest ...`)

Write plan to `.do/plans/current.json`.

---

# PHASE 7 — VALIDATE AND PERSIST [IE-8, IE-9, PV-1 through PV-8]

Deterministic. Execute in order.

## 7a. Finalize plan

```
python3 $DO plan finalize-file .do/plans/current.json
```

Validates: role count [PV-1], unique names [PV-2], no cycles [PV-3], all required fields [PV-4], schema version [PV-6].
On rejection [PV-5]: fix structural issues, retry. Do NOT proceed with an invalid plan.

## 7b. Post-authoring divergence check [DC-20]

```
python3 $DO spec divergence --root .do --spec-doc spec.md
```

Resolve any unregistered or orphaned IDs before proceeding. This is a HARD GATE — do NOT proceed to trace/reflect if unregistered IDs exist. Register them first.

Additionally, verify all plan contract_ids are registered:

```
python3 $DO spec list --root .do
```

Cross-check: every contract_id in `.do/plans/current.json` roles must appear in the spec list. If any are missing, register them before proceeding. Execute will halt on missing contract_ids [EC-4a].

## 7c. Trace

Record design_complete event. JSON fields: event, roles (count), contracts_authored (count).

    python3 $DO trace add --root .do --json TRACE_JSON

## 7d. Reflection

Self-assessment is prohibited [XC-23]. Record a deferred process reflection.
Required fields: type, outcome, lens=process, urgency=deferred, failures=[], fix_proposals=[].

    python3 $DO reflection add --root .do --json REFLECTION_JSON

## 7e. Memory

Record significant learnings [XC-21].
Required fields: category=design, keywords (list), content, source=do-design, importance (3-10).

    python3 $DO memory add --root .do --json MEMORY_JSON

## 7f. Propose updates [XC-16, DS-8]

- **Conventions**: note patterns discovered that should be standardized
- **Aesthetics**: note interaction patterns discovered during design

Present proposals to user. Do NOT write directly — propose for review.

## 7g. Invoke reflect [LC-8, XC-23]

MANDATORY. Invoke do-reflect via Skill tool. Reflect uses `context: fork` [FC-6] — automatically runs in an isolated subagent that reads artifacts from disk, not from this conversation. No manual Task spawning needed.

Present reflect's immediate findings to user [LC-3]. User resolves each finding before design is considered complete.

---

# PHASE 8 — VERSION CONTROL [VC-2, VC-3, VC-5]

Commit all changes produced by this design run. Working tree must be clean afterward.

1. Check working tree status: `git status --porcelain`
2. Resolve untracked files:
   - Legitimate project artifacts (specs, plans, conventions, aesthetics, `.do/` state files) → `git add`
   - Generated/environment-specific files → add to `.gitignore`, then `git add .gitignore`
   - Scratch output that should not persist → delete
3. Stage all changes: `git add` relevant files
4. Commit: message summarizing design output (goal, contracts authored/registered, plan roles)
5. Verify clean: `git status --porcelain` — must produce no output

If no changes were produced [VC-4]: skip commit.

---

# PROHIBITIONS

- **[DC-7]** MUST NOT execute any part of the plan. Design only designs.
- **[DC-8]** MUST NOT skip expert analysis for goals with 3+ roles.
- **[XC-7]** MUST NOT delegate spec authorship. Design is the sole spec author.
- **[EM-16]** MUST NOT read project source files directly. Delegate to subagents.
- **[EM-17]** MUST NOT write implementation artifacts that workers should produce.
