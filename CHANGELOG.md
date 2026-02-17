# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.10.1] - 2026-02-17

### Fixed

- CLAUDE.md command count corrected to 25 (was 18)

## [2.10.0] - 2026-02-17

### Added

- `validate-checks` command in plan.py — extracts Python from `python3 -c` acceptance criteria checks and validates syntax with `ast.compile()`
- Validate-checks gate in design SKILL.md Step 4 — catches check syntax errors at design time (non-blocking)
- Scout-to-plan feedback loop in execute — lead injects high-impact scout discrepancies as role constraints before worker spawning
- Lead-side acceptance criteria verification in execute — trust-but-verify step before marking roles complete
- `self-test` command in plan.py — 27 automated smoke tests exercising every command against synthetic fixtures

### Changed

- Deduplicated worker protocol in execute SKILL.md — extracted shared worker preamble to reduce per-spawn prompt bloat
- Strengthened acceptance criteria guidance across all 4 SKILL.md files — replaced grep-only examples with functional verification commands
- `_is_grep_only` renamed to `_is_surface_only` with expanded detection (piped grep, `test -f`, `[ -f ]`, `[[ -f ]]`)

### Fixed

- Pyright diagnostics in plan.py: None guards in `cmd_memory_add`, `_ = args` for unused parameters, removed redundant imports
- `plan-health-summary` used consistently in improve and reflect skills (was using different commands)

## [2.9.0] - 2026-02-17

### Added

- Adaptive model escalation on retry (haiku -> sonnet -> opus)
- Worker-to-worker handoff context (keyDecisions, contextForDependents)
- Simplified liveness pipeline (3-turn timeout, down from 5+7)
- Procedural memory category for learned execution patterns
- Dynamic importance tracking via --boost/--decay flags on memory-add
- Lifecycle context via `plan-health-summary` command at skill start
- Comprehensive visibility and observability across all 4 skills
- State validation, health-check, and plan-diff commands in plan.py
- Schema validation (`expert-validate`, `reflection-validate`) and memory visibility (`memory-review`, `memory-summary`) commands
- Behavioral trait instructions for experts and auxiliaries
- Structured tables for worker instructions
- Compressed quality rubric (1/3/5 anchors only)

### Changed

- Harmonized and compressed shared protocols across all 4 skills
- Optimized prompts with behavioral traits and structured tables

## [2.8.4] - 2026-02-17

### Added

- Expert liveness pipeline and consistency improvements to improve skill
- 7 design skill enhancements (draft plan review, phase announcements, etc.)
- Error handling and constraint consistency to reflect SKILL.md
- `archive` command in plan.py (replaces raw shell archiving)
- TeamCreate health check, memory-search fallback in execute skill

### Changed

- Extracted verification specs protocol to CLAUDE.md (shared documentation)
- Compressed execute skill Section 7 (25 lines saved)

## [2.8.2] - 2026-02-16

### Added

- Expert liveness pipeline to design skill (turn-based timeout, re-spawn ceiling)
- Worker liveness pipeline and imperative cascade handling to execute
- Structured completion reports and worker tool boundaries
- Verification spec layer to improve skill

### Changed

- Compressed /do:design skill (68 lines saved)
- Compressed /do:improve skill (46 lines saved)
- Restructured expert spawn instruction in /do:design

### Fixed

- Cross-review enforcement rules in improve skill
- Hardened /do:improve protocol coordination

## [2.6.0] - 2026-02-15

### Added

- `/do:improve` skill for scientific skill analysis across 7 quality dimensions
- `/do:reflect` skill for evidence-based improvement from execution reflections
- Project-unique team names to prevent cross-terminal contamination
- Verification spec layer with SHA256 tamper detection for design-execute pipeline

### Fixed

- Cross-review enforcement and expert artifact protection
- Experts required to save artifact files before proceeding

## [2.4.1] - 2026-02-15

### Added

- Structured interface negotiation and perspective reconciliation in design cross-review
- Challenger and integration-verifier always run as auxiliaries
- Hardened auxiliary agents and acceptance criteria verification

### Fixed

- Auxiliaries made standalone Task calls (not team members)
- Memory-search CLI flags aligned with SKILL.md invocations
- Quality gates added to memory curator
- memory.jsonl preserved during design archive
- Runnable shell commands required for acceptance criteria checks

## [2.2.0] - 2026-02-14

### Added

- Memory injection and memory-curator to execute skill
- memory-search and memory-add commands to plan.py
- Memory injection and diverse debate to design skill
- Importance scoring for memory-search and memory-add
- Worker verification (CoVe-style), reflexion on retries, and progress reporting to execute

### Changed

- Strengthened design skill protocol and debate mechanisms

### Fixed

- Memory-curator reads all roles including failed/skipped
- Duplicate memory command argparse registrations removed
- Command categorization corrected in CLAUDE.md

## [2.0.0] - 2026-02-14

### Added

- Schema v4 with role briefs, auxiliary agents, and worker autonomy
- Goal review, integration testing, session handoff, and adversarial design review

### Changed

- Rewrote design and execute SKILL.md for density and effectiveness
- Deduplicated CLAUDE.md, added agent schema docs

### Fixed

- Cascading failures, worker-pool, status exit code, overlap optimization
- Finalize schema expectations documented with validate-only mode

## [1.9.0] - 2026-02-14

### Changed

- Simplified design and execute skills
- Organic research-driven design and trust-the-plan execute

### Fixed

- Use status command instead of non-existent status-counts

## [1.5.2] - 2026-02-11

### Added

- Persistent self-organizing workers with natural team flow

### Changed

- Simplified design and execute skills

## [1.4.1] - 2026-02-11

### Added

- Dedicated team lead architecture for both skills

### Fixed

- Removed middleman lead agent — main conversation is team lead

## [1.3.1] - 2026-02-10

### Changed

- Consolidated plan.py to root with symlinks from each skill

## [1.2.5] - 2026-02-10

### Added

- `scripts/plan.py` with deterministic plan.json operations
- Per-skill scripts for design and execute
- Pre-commit checklist for doc sync and version bumps

### Changed

- Replaced scanner/architect with architect/researcher expert types
- Eliminated batch finalizer — lead verifies results inline
- Removed worker log files — workers return status lines directly

## [1.2.0] - 2026-02-10

### Changed

- Moved prompt assembly from execute to design, eliminated tasks.json

### Fixed

- Suppressed per-worker status chatter during execution

## [1.1.0] - 2026-02-10

### Added

- Complexity tier branching to design skill (trivial/standard/complex/high-stakes)
- TeamCreate error handling
- Timestamped plan history archive and selective cleanup
- Sequential thinking as Step 1 for goal understanding
- Dynamic team growth with goal analyst as first teammate

### Changed

- Replaced wave-based scheduling with dependency-graph execution
- Streamlined design pipeline from 6 steps to 4
- Bumped schemaVersion from 2 to 3

### Fixed

- Anti-polling instruction (explicit instead of vague timeout hint)
- Prompt quality fixes and schema version correction

## [1.0.0] - 2026-02-08

### Added

- Initial release of the `do` plugin for Claude Code
- `/do:design` skill for structured goal decomposition with enriched agent specifications
- `/do:execute` skill for dependency-graph execution with parallel agents and safety features
- Marketplace support via `.claude-plugin/marketplace.json`
- Full documentation (README, CONTRIBUTING, LICENSE)
