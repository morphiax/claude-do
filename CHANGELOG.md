# Changelog

## [8.1.0] — 2026-03-03

### Added
- EnterPlanMode prohibition — planning happens inline; plan mode's system prompt supersedes skill directives, so it is now a forbidden tool and an invariant
- Numbered next steps menu — "What's next?" header with numbered actions the user selects by entering the number
- Pitfall: "Host platform feature supersedes skill directives" — documents the protocol handoff directive loss pattern

### Changed
- All response skeletons use "### What's next?" with numbered list instead of "### Next steps" with bullets
- spec.md context boundary and invariants updated to reflect plan mode prohibition and menu-style next steps

## [8.0.0] — 2026-03-03

### Added
- Technology-agnostic behavioral spec — spec.md now describes WHAT the system does without tool names or file paths; implementation details moved to context.md
- context.md as implementation mapping — maps spec concepts to Claude Code (Agent tool, TaskCreate, model tiers, git commands, preamble construction, sequentialthinking)
- validate_context_entry — ensures implementation context files have tool permissions, concrete syntax, dispatch patterns, and no behavioral contracts
- Response skeletons for all six modes in SKILL.md — dialogue, planning, execution, quick-fix (diagnosis + confirmation), and analysis
- Per-mode tone and density descriptions inlined in SKILL.md
- Formatting conventions section in SKILL.md
- Pitfall-derived operational rules inlined at point of action (stop-and-wait, routing function, zero-context plan check, preamble contract)

### Changed
- Reduced project files from seven to six — architecture.md removed, algorithm pseudocode folded into spec.md per choose_format routing
- SKILL.md regenerated from spec + context + design + pitfalls (668 lines, up from 473)
- Scope section converted from prose to pseudocode function with explicit refuse
- find_next_constraint simplified — removed rebuild-test measurement mechanism
- design.md, decisions.md, pitfalls.md rewritten with higher information density against their validate_*_entry criteria
- decisions.md adds "pseudocode over prose" and "orchestrator/worker context boundary" as standalone decisions
- pitfalls.md adds "wrong-file routing" and "plan tasks require prior context"

### Removed
- architecture.md and validate_architecture_entry — pseudocode algorithm criteria folded into validate_spec_entry
- EnterPlanMode and sequentialthinking references from SKILL.md (sequentialthinking moved to context.md)
- Rebuild-test measurement from find_next_constraint (meta-process, not runtime behavior)

## [7.5.0] — 2026-03-02

### Added
- "Own everything" rule and invariant — every issue in the project is a project issue regardless of when it appeared; the only valid dispositions are fix or track, never dismiss as "pre-existing"

## [7.4.0] — 2026-03-02

### Added
- architecture.md as seventh project file — captures algorithms as pseudocode, operation counts, assumptions, data flow traces, and boundary conditions
- Pseudocode-first technique — express algorithms, architecture, and debugging hypotheses as pseudo before implementing
- Algorithm validation step in planning — write pseudocode and probe assumptions before decomposing into tasks

### Changed
- Genericized all project-specific examples in SKILL.md quality dimensions (decisions, pitfalls, architecture examples now use placeholder domain terms)
- Quick-fix sequence includes pseudo-process expression for non-obvious fixes
- Sync gate checks architecture.md when algorithms changed
- Project file count updated from six to seven across spec, README, and SKILL.md

## [7.3.0] — 2026-03-01

### Changed
- Sync step replaced with sync gate — requires enumerating changed behaviors and confirming spec coverage (or explicitly stating nothing drifted), preventing silent skipping
- Quick-fix sequence now stops and waits for human response before dispatching — prevents the model from stating a fix and implementing in the same message
- Investigation subagent follow-ups: when a subagent returns incomplete results, dispatch a targeted follow-up instead of falling back to main-context reads

## [7.2.0] — 2026-03-01

### Added
- Quick-fix execution path — skip plan approval ceremony for small, obvious fixes while still using task tools and subagents

### Changed
- Agreement model: direction is established in conversation, project files update as part of execution without re-confirming at write time
- Only gate for project file writes is introducing new direction (new behaviors, scope changes, architectural shifts) without prior conversation

## [7.1.0] — 2026-03-01

### Added
- Bidirectional spec↔code sync invariant — project files and code must always agree at session end
- Protocol step 6 "Sync project files" — after execution, diff what was built against .do/ files and propose updates for any drift
- Spec satisfaction quality dimension is now explicitly bidirectional — verify code matches spec AND spec matches code

## [7.0.0] — 2026-02-28

### Changed
- Unified shape and build into single `/do:work` skill with four modes: dialogue, planning, execution, analysis
- Expanded project files from two (spec, context) to six (spec, reference, stack, design, decisions, pitfalls)
- Absorbed audit and challenge commands as analytical modes within the skill
- Removed status file — state reconstructed from project files and git diffs each session
- Project file updates allowed from any mode with human agreement (previously build couldn't modify spec)

### Removed
- Shape skill (merged into /do:work)
- Build skill (merged into /do:work)
- Audit command (now /do:work analysis mode)
- Challenge command (now /do:work analysis mode)

## [6.6.2]

### Changed
- Added shared skill conventions in context

## [6.6.1]

### Changed
- Shape boundary made explicit — writes only to .do/ spec and context
- Build plan is self-sufficient execution contract
- CLAUDE.md is principle-based

## [6.6.0]

### Changed
- Build two-phase protocol: planning (read-only) then execution (uninterrupted)
- TDD enforced structurally — each plan task specifies test and implementation goal

## [6.5.0]

### Changed
- Component folders replace flat subspecs (.do/<component>/ with their own spec and context)

## [6.4.0]

### Changed
- Build drives to completion — context defines "done"

## [6.3.0]

### Added
- Audit command — technical evaluation against best practices
- Challenge command — product review from PM perspective

## [6.2.0]

### Added
- Release command — version bump, changelog, docs sync, commit, tag, push

## [6.1.0]

### Changed
- Specs capture system-level processes (triggers, cascades, pipelines)

## [6.0.0]

### Changed
- Major restructure — merge shape and frame into one dialogue skill
