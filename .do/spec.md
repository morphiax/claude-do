# do

A Claude Code plugin for collaborative sensemaking. One skill (`/do:work`) and one command (`/do:release`).

## Problem

AI coding assistants lose context between sessions. Project understanding lives in conversation history that gets compacted or discarded. Decisions, constraints, and hard-won debugging insights vanish. Each session starts from scratch, re-discovering what the last session already knew.

## Principle

Intentionality — every output reflects a deliberate choice, not a default. Before acting in any mode, identify what matters most right now. In dialogue: what's the one question that would most narrow the problem space? In planning: what's the riskiest assumption to resolve first? In execution: what's the failure mode this implementation must prevent? In analysis: what's the finding that would cascade improvements?

Intentionality must survive the handoff. Process insight that stays in conversation history is lost. The same insight crystallized into a spec entry, a plan task, or a pitfall persists — and any future session or subagent benefits from it regardless of their capability. "Returns search results" lets a lesser AI build mediocre search. "Returns search results sorted by relevance, grouped by resort, with the single best value badged" lets the same AI build good search. The quality bars below exist to force this crystallization.

## Behaviors

### Work on a project

Takes an optional argument describing what to work on. Without an argument, reads project state and continues where the last session left off.

Routes to one of four modes based on context:

**Dialogue** — Conversation about the project. Listens, reflects back with structure, surfaces constraints and process chains. Proposes updates to project files with human agreement.

When starting from existing code with no spec, the code is evidence, not the spec. Surveys the domain, pivots to the human: what problem were you solving? Uses code details as probes to surface intent. Writes the spec from answers, not code structure.

Quality bar: each exchange makes understanding more specific. Questions narrow the problem space — if the answer wouldn't change the approach, the question isn't worth asking. Constraints are actively surfaced ("what would make this unacceptable?"). Process chains are traced ("when X happens, what else does the system do?"). Information routes to the right file on the first attempt.

**Planning** — Enters read-only plan mode. Explores the codebase, decomposes work into tasks. Each task is self-sufficient: an agent with zero prior context can execute it from the task description alone. Every task specifies a test and an implementation goal. Submits the plan for human approval. After approval, creates the task list — each plan task becomes a tracked task item with dependencies.

Quality bar: every task is executable from its description alone — includes file paths, existing patterns to follow, the test to write, and any task-specific constraints. "Implement login" fails this test. "Test: POST /api/login with valid credentials returns 200 and Set-Cookie header. Implementation: Hono route in src/server/routes/auth.ts, validate against env vars" passes it. Every ambiguity is resolved during planning, not deferred to execution. The plan's preamble specifies the dispatch mechanism: each task runs in its own subagent with a clean context window (preamble + task description only), so no task is polluted by prior tasks' implementation details. Each task specifies its model tier (haiku/sonnet/opus) — model selection is a planning decision, made when the task's complexity is understood, not deferred to execution.

**Execution** — Two paths based on scope. Main context handles orchestration only — implementation always runs in subagents regardless of task size.

*Full execution* requires an approved plan. The task list is the progress interface — tasks move through pending → in_progress → completed as subagents work. TDD workflow: failing test, minimum implementation, green. After all tasks complete, verifies bidirectionally: code satisfies spec AND spec reflects what was built.

*Quick fix* (1–3 tasks, obvious fix after investigation) skips plan approval but still uses task tools and subagents. Sequence: (1) state the diagnosis and proposed fix, then **stop and wait for human response** — they may have context that changes the approach, (2) after agreement, create tasks via TaskCreate — even for single-task fixes, since the task list is the user's progress dashboard, (3) dispatch to subagents, (4) mark completed, (5) complete the sync gate. The threshold is clarity, not size — any ambiguity about approach requires full planning. Quick fix is not a shortcut to skip subagents or task tracking; it's a shortcut to skip the plan approval ceremony when the fix is self-evident.

Quality bar: tests assert behaviors, not implementation details. Only the code the test demands gets written. After completion, approach verification as a bug hunt — the first implementation is almost never complete. When execution surfaces new insights, capture them in the relevant project file.

**Analysis** — Explicitly invoked ("audit" or "challenge"). Audit examines technical choices against current best practices. Challenge examines product assumptions from a PM lens.

Quality bar: every finding is specific (names files, counts instances, quantifies impact), evidence-backed (grounded in research, not vibes), and actionable (includes what to do and effort estimate). Findings are prioritized — high-impact low-effort wins first. Good choices get genuine praise.

Modes transition fluidly. Discovering a gap during execution pauses into dialogue. Resolving a question in dialogue can advance into planning.

**Context management** — Main context handles dialogue, project files, planning, and orchestration only. All implementation file reads, code exploration, and code edits go to subagents — no exceptions, even for quick fixes. Only `.do/` file reads and git commands belong in main context. When an investigation subagent returns incomplete results, dispatch a targeted follow-up — don't fall back to main-context reads.

**Design thinking** — Before implementing any visual interface, commits to an aesthetic direction by thinking across five dimensions: typography, color, motion, spatial composition, and atmosphere. Reads design.md and reference images first. Matches implementation complexity to the aesthetic vision. Each project's interface should feel genuinely designed for its context — never converging on the same look across projects.

**Session sequence** — Every invocation follows this order:

1. Read all existing `.do/` files to reconstruct project understanding.
2. Check what changed since the last relevant commit — diff code, dependencies, and `.do/` files. Surface gaps between project files and reality. Skip when no version control.
3. Determine mode from the request context. Bug reports start as dialogue with investigation in a subagent — never main context. Transition to execution when root cause and fix can be stated in one sentence.
4. Execute in the determined mode. Modes can transition mid-session.
5. Sync gate — mandatory after any execution. Read spec.md (and design.md/stack.md if relevant), enumerate each behavior added/modified/removed, confirm each is reflected or propose an update. If nothing drifted, state explicitly: "Sync gate: all changes reflected in project files." The explicit statement prevents silent skipping. Skip only for dialogue or analysis with no implementation changes.
6. Produce concrete next steps (mandatory unless project is fully complete).

### Maintain project files

Six files under `.do/`, each answering a specific question:

| File | Question |
|------|----------|
| spec.md | What should it do? |
| reference.md | How does the target system work? |
| stack.md | What are we building with? |
| design.md | What should it look like? |
| decisions.md | Why did we choose this? |
| pitfalls.md | What breaks and how to avoid it? |

Information routes to files by signal type. Behaviors go to spec. External system facts go to reference. Technology choices go to stack. Aesthetic direction goes to design. Choice rationale goes to decisions. Debugging insights go to pitfalls.

Each file type has a quality bar enforced during writing — both what to include and what to avoid:
- **spec.md**: Behaviors are testable and include quality expectations. Sequences captured as behavior. Constraints probed. Data formats precise. The rebuild test: could someone rebuild from this spec alone? Avoid: capabilities without quality bars, specs that require reading code to understand, implicit sequencing, implementation details (those go in stack.md).
- **reference.md**: Implementation-grade detail. Edge cases documented. Gotchas surfaced. Freshness signals noted. Avoid: high-level overviews that don't help implementation, omitting the non-obvious behaviors that cause bugs.
- **stack.md**: Conventions specific enough to write new code without reading existing code. Project structure clear. Build/run recipes included. Avoid: generic technology lists without conventions, missing the "how we use it" part.
- **design.md**: Covers every output surface — visual UI, CLI output, API responses, structured text. Includes tone, information density, and output structure. Avoid: vague aesthetic direction, generic tone descriptions, ignoring non-visual output surfaces, ad-hoc formatting without skeletons.
- **decisions.md**: Context sufficient, alternatives acknowledged, tipping point named, reversal cost noted. Avoid: recording trivial decisions, omitting rationale, listing what without why.
- **pitfalls.md**: Recognizable symptom, specific root cause, actionable fix, pattern class identified. Avoid: vague warnings, missing the symptom, fixes that don't explain the mechanism.

When a project has distinct subprojects, each gets its own folder under `.do/<component>/` with whichever files it needs.

### Release a version

Takes a bump type (patch, minor, major). If omitted, infers from git log since last tag.

Steps: detect all version sources, bump them in sync, update changelog from git log (Keep a Changelog format), sync README prose against the full diff, commit as `release: vX.Y.Z`, tag, push (with confirmation).

Scope: version, changelog, docs, commit, tag, push. Does not build, publish to registries, or create GitHub releases.

### Self-target

When explicitly directed to work on itself, reads and evolves the plugin's own `.do/` files instead of the project's.

## Invariants

- **Human agreement required for project file updates.** Propose changes, get confirmation, then write.
- **Plan is the contract.** Self-sufficient for agents with no prior context. Once approved, follow it. If reality diverges, stop and propose an update.
- **Project files and code stay in sync.** After execution, verify project files reflect what was built. After project file updates, verify implementation matches. Neither drifts without the other.
- **Tests live in the plan.** Each task specifies test and implementation goal. Plan approval is TDD approval.
- **Next steps are mandatory.** Every session ends with concrete actionable items unless the project is fully complete.

## Scope boundaries

### Owns

- Project file creation and maintenance
- Planning and task decomposition
- Execution orchestration via subagents
- Technical audit and product challenge
- Version release workflow
- Quality standards for each project file type

### Does not own

- The Claude Code plugin system itself
- CI/CD pipelines or registry publishing
- Runtime tooling or build systems
- Project-level CLAUDE.md instructions
