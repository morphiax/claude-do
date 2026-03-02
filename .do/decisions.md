# Decisions

## Single unified skill over separate mode-specific skills

**Context:** The system needs to support dialogue, planning, execution, and analysis. These could be separate invocations (e.g., `/do:shape`, `/do:build`, `/do:audit`) or a single entry point that routes internally. The question arose because mode transitions happen naturally during real work — discovering a gap during execution needs dialogue, resolving a question in dialogue leads to planning.

**Alternative:** Separate skills with explicit triggers. The human decides which mode to enter.

**Tipping point:** Mode transitions require re-establishing context. Separate skills mean exiting one, invoking another, and re-reading project state. A unified skill with internal routing preserves context across transitions and removes the burden of mode selection from the human.

**Reversal cost:** Moderate. Splitting back into separate skills would require decomposing the SKILL.md routing logic and duplicating shared protocol steps (orient, sync gate, next steps). The accumulated decision to handle transitions fluidly would be lost — each skill would need its own transition-out logic.

## Seven specialized files over fewer general-purpose files

**Context:** Project understanding must persist across sessions in `.do/` files. Earlier iterations used two files: `spec.md` for behaviors and `context.md` for everything else. As projects grew, context.md became a dumping ground — technology choices, debugging insights, decision rationale, external system models, and aesthetic direction all intermixed.

**Alternative:** Keep two files with stricter internal structure (named sections within context.md). Fewer files means fewer routing decisions and less overhead.

**Tipping point:** A future session reading context.md couldn't quickly find what it needed. Seven files with distinct names are self-indexing — you know where to look without reading the whole thing. The routing heuristic (behaviors -> spec, broke -> pitfalls, chose -> decisions, etc.) makes placement unambiguous. The cost of maintaining seven files is paid once during writing; the benefit of fast lookup is paid every session.

**Reversal cost:** Low for structure, high for accumulated content. Merging files back is mechanical. But the routing discipline — knowing which signal goes where — would degrade. Mixed files invite mixed signals.

## Reconstructed state over persistent status file

**Context:** Sessions need to know what happened since the last session. A status.md file could track progress, or the system could reconstruct state from project files and git diffs each time.

**Alternative:** Maintain a status.md that records what was done, in-progress, and next.

**Tipping point:** Status files go stale immediately. Git history is ground truth for what changed. Project files are ground truth for what should exist. A status file is a third source that contradicts the other two whenever someone forgets to update it — which is every time.

**Reversal cost:** Negligible. Adding a status file back would be additive. The reconstruction logic in orient would still work.

## Mandatory sync gate over aspirational sync step

**Context:** After execution, project files must reflect what was built. The original protocol had a step: "diff what was built against project files, propose updates for any drift." In practice, after successful execution with passing tests, this step was skipped — the momentum to report success outweighed the instruction to verify sync.

**Alternative:** Stronger language in the existing step ("this is mandatory," "don't forget"). Also considered: automated diff tooling that mechanically detects drift.

**Tipping point:** Aspirational instructions ("remember to X") fail under momentum pressure because omitting them produces no visible gap. A required output format — enumerate each behavior changed, confirm spec coverage, or explicitly state "Sync gate: all changes reflected" — fails visibly. The response skeleton has a mandatory section that is either filled or conspicuously absent.

**Reversal cost:** Low. Removing the gate is a SKILL.md edit. But the failure mode it prevents (silent spec drift) returns immediately — the aspirational version was already tried and failed.

## Quick-fix path over full-planning-only execution

**Context:** All implementation required full plan mode (enter plan mode, human approval, task creation, subagent dispatch). When investigation revealed a small, obvious fix, the system bypassed the entire protocol — reading implementation files in main context, editing directly, skipping task tools and sync. The heavyweight path created an all-or-nothing dynamic.

**Alternative:** Enforce full planning for everything regardless of size. Accept that small fixes will carry ceremony overhead.

**Tipping point:** The observed failure mode: the system treated "not worth the ceremony" as permission to skip every structural invariant — not just plan approval, but subagents, task tracking, and sync. The right response is a lighter path that preserves the invariants that matter (subagents for implementation, task tools for visibility, sync gate for knowledge capture) while dropping the one that doesn't (plan approval for self-evident fixes). The threshold is clarity, not size.

**Reversal cost:** Low structurally (remove the quick-fix branch from SKILL.md). But the behavioral regression is immediate — the system will resume bypassing everything when the only option is heavyweight.

## Orchestrator/worker context boundary

**Context:** The main conversation context could handle everything — reading implementation files, making edits, running tests — or it could be restricted to orchestration while subagents handle implementation. The question is whether the separation is worth the overhead of formulating subagent prompts and waiting for results.

**Alternative:** Allow main context to read and edit implementation files directly, using subagents only for parallel work.

**Tipping point:** Main-context implementation reads have unbounded scope creep. "Just one file" becomes seven. Investigation work pollutes the context window, displacing project-level reasoning with implementation details. The context boundary is a forcing function: the orchestrator thinks about what to do, subagents think about how to do it. Mixing the two degrades both.

**Reversal cost:** High. Removing the boundary is easy. Re-establishing the discipline after it erodes is hard — every "just this once" exception trains the system to bypass.

## Pseudocode over prose for mechanisms in spec

**Context:** The spec describes routing logic, validation functions, session sequences, and other mechanisms. These could be expressed in prose ("the system first reads all files, then checks for staleness...") or pseudocode (`files = read_all(path); for file in files: check_staleness(file)`).

**Alternative:** Prose throughout, with pseudocode reserved for architecture.md algorithms only.

**Tipping point:** Prose descriptions of mechanisms are ambiguous about ordering, conditionality, and completeness. "The system checks for staleness and consistency" doesn't say which happens first or whether both always run. Pseudocode makes control flow explicit. The contract-vs-comment rule adds a second benefit: behavioral contracts must be pseudocode statements, preventing important requirements from hiding in comments that look optional.

**Reversal cost:** Moderate. Converting pseudocode back to prose loses precision. Subtle ordering and branching contracts would need to be re-discovered through testing.
