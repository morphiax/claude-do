# Decisions

## Unified single skill (v7.0.0)

**Context:** The plugin had three separate skills — shape (dialogue), build (planning + execution), and two analysis commands (audit, challenge). Users had to know which to invoke. Mode selection was a user burden that didn't need to exist.

**Alternative:** Keep separate skills with clear triggers.

**Decision:** Merge everything into `/do:work` with automatic mode routing. The skill reads context and picks the right mode. Modes transition fluidly within a session.

**Tipping point:** Mode transitions happen naturally in real work — you discover a gap during execution and need dialogue, you resolve a question in dialogue and want to plan. Separate skills made these transitions jarring (exit one skill, invoke another, re-establish context).

## Six project files instead of two (v7.0.0)

**Context:** v6 had two files: spec.md (behaviors) and context.md (everything else). Context.md became a dumping ground — technology choices, debugging insights, decision rationale, and external system models all mixed together.

**Alternative:** Keep two files but with stricter internal structure (sections within context.md).

**Decision:** Split into six files with distinct routing: spec, reference, stack, design, decisions, pitfalls. Each answers one question. The routing heuristic makes placement unambiguous.

**Tipping point:** A future session reading context.md couldn't quickly find what it needed. Six files with clear names are self-indexing — you know where to look without reading the whole thing.

## No status file (v7.0.0)

**Context:** Earlier versions maintained a status.md that tracked what was done, what was in progress, and what was next.

**Alternative:** Keep status tracking in a project file.

**Decision:** Reconstruct state from project files and git diffs each session. No status file.

**Tipping point:** Status files go stale immediately. Git history is the ground truth for what changed. Project files are the ground truth for what should exist. A status file is a third source that contradicts the other two.

## Bidirectional sync invariant (v7.1.0)

**Context:** Implementation could change behavior without updating the spec. The layout redesign problem: code was updated to remove a sidebar and add a card grid, but spec.md and design.md still described the old sidebar layout.

**Alternative:** Rely on the developer to remember to update specs after implementation.

**Decision:** Make it a protocol step and a rule. After execution, the skill diffs what was built against project files and proposes updates. The spec and code are two representations of the same truth — neither changes without the other.

**Tipping point:** The failure was silent. Nobody noticed the spec was wrong until someone asked "did you update the spec?" That's the most dangerous kind of bug — the one that doesn't look like a bug.

## Task list as execution interface (v7.1.0)

**Context:** The protocol started each session with `TaskCreate subject: "Work"` — a single generic task that sat in_progress for the entire session. In practice this looked wrong: the task list showed a permanent "Work" spinner alongside no other tasks. It was ceremony without information.

**Alternative:** Remove task tracking entirely from the skill.

**Decision:** Replace the generic "Work" task with real plan tasks. After plan approval, each plan task becomes a TaskCreate with a specific subject and activeForm. During execution, tasks move through pending → in_progress → completed as subagents work. The task list becomes a live progress dashboard. No tasks created for dialogue or short exchanges.

**Tipping point:** The task list is the most visible UI element in Claude Code during long operations. A single "Work" task wastes that real estate. Real tasks with real progress give the user an at-a-glance understanding of where execution stands — which is exactly what the task list was designed for.

## Quick fix execution path (v7.2.0)

**Context:** The skill required full plan mode (EnterPlanMode → approval → execution) for all implementation work. When investigation revealed a small, obvious fix (e.g., a month default mismatch causing an empty state), the model would skip the ceremony entirely — implementing directly in main context without task tools or subagents — because the full pipeline felt disproportionate to a 3-file fix.

**Alternative:** Enforce full planning for everything regardless of size.

**Decision:** Add a quick-fix execution path: skip plan approval but still require task tools and subagent dispatch. The threshold is clarity (no ambiguity about approach), not size. Quick fix is explicitly not a shortcut to skip subagents or task tracking — it's a shortcut to skip the plan approval ceremony.

**Tipping point:** The failure mode was observed in practice: the model read implementation files and made edits directly in main context, used no task tools, and skipped project file sync — all because the full pipeline felt like too much ceremony for a small fix. The right fix isn't "allow main context implementation" — it's providing a lighter path that still enforces the invariants that matter (subagents for implementation, task tracking for visibility, project file sync for knowledge capture).

## Sync gate over sync step (v7.3.0)

**Context:** Protocol step 5 said "Sync project files — diff what was built against project files, propose updates for any drift." In practice, after a successful fix with passing tests, the model skipped this step entirely — reporting success without checking if the spec reflected the new behavior. The instruction was aspirational ("propose updates for drift") and competed with strong momentum to ship.

**Alternative:** Add more emphatic language ("don't forget to sync!" / "this is mandatory!").

**Decision:** Replace the aspirational step with a mechanical gate that requires specific output. The sync gate demands: enumerate each behavior changed, confirm spec coverage for each, and either propose updates or state "Sync gate: all changes reflected in project files." The explicit statement makes skipping visible.

**Tipping point:** Aspirational instructions ("remember to X") fail under momentum pressure because omitting them produces no visible gap — the response just doesn't have a sync section, and that's easy to not notice. A required output format ("state X or propose Y") fails visibly — the response skeleton has a mandatory section that's either filled or conspicuously absent.

## Stop-and-wait in quick fix sequence (v7.3.0)

**Context:** The quick fix sequence said "state the fix and get human agreement." In practice, the model stated the fix and dispatched the implementation in the same message — never waiting for agreement. The human had no chance to redirect.

**Alternative:** Rely on the existing instruction being clear enough.

**Decision:** Make the stop explicit with bold formatting: "**Stop and wait for the human's response.**" Also add the rationale inline — "they may have context that changes the approach" — so the instruction isn't just a rule but explains why pausing matters.

**Tipping point:** "Get human agreement" is ambiguous — it could mean "state it and proceed unless they object" (which is how the model interpreted it). "Stop and wait for the human's response" is unambiguous — it requires a message boundary.
