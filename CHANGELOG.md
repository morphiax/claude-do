# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.17.0] - 2026-02-18

### Added

- `/do:simplify` skill — analyzes codebases for cascade simplification opportunities (one insight eliminates multiple components) using pattern-recognizer and preservation-guardian analysts. Produces `.design/plan.json` with preservation-focused worker roles for `/do:execute`. Cascade thinking taxonomy covers 5 categories: structural, behavioral, data, cross-cutting, and organizational simplification.
- `skills/simplify/SKILL.md` — complete 6-phase skill protocol with cascade methodology, analyst coordination, and preservation safety constraints
- `skills/simplify/scripts/plan.py` — symlink to shared `scripts/plan.py`

## [2.16.1] - 2026-02-18

### Added

- `designHandoff[]` optional field in research.json schema — array of concrete building blocks extracted from expert artifacts during synthesis, enabling /do:design to read research.json alone without re-reading expert artifacts (token efficiency)
- `_validate_research_design_handoff()` in plan.py — validates designHandoff entries (source enum, required fields, material type)
- `designHandoffCount` in research-validate and research-summary output

### Changed

- Research SKILL.md synthesis step 7: extracts concrete building blocks (patterns, templates, schemas, constraints) from expert findings into designHandoff[]
- Research output display includes design handoff count

## [2.16.0] - 2026-02-18

### Changed

- **BREAKING**: `/do:recon` replaced with `/do:research` — new skill produces structured knowledge across 5 sections (prerequisites, mentalModels, usagePatterns, failurePatterns, productionReadiness) with recommendations array instead of Meadows-ranked interventions
- `.design/recon.json` contract replaced with `.design/research.json` (schemaVersion 1) with recommendations including confidence, effort, and prerequisites for adoption planning
- `recon-validate` and `recon-summary` commands replaced with `research-validate` and `research-summary` in plan.py
- CLAUDE.md updated: Data Contracts section documents new research.json schema; Execution Model `/do:research` section describes new workflow
- README.md updated: skill descriptions and usage examples reflect research output format
- Version bumped to 2.16.0 (minor version bump for feature replacement)

## [2.15.0] - 2026-02-18

### Added

- `trace.jsonl` — append-only event log capturing agent lifecycle events (spawn, completion, failure, respawn, skill-start, skill-complete) with automatic timestamps and session grouping
- `trace-add` command in plan.py — append events to trace.jsonl with graceful degradation on write failure
- `trace-search` command in plan.py — query trace events by session, skill, event type, or agent with AND-logic filtering
- `trace-summary` command in plan.py — format trace data for display with aggregate statistics (session count, event counts, latest session info)
- `trace-validate` command in plan.py — schema validation for trace.jsonl entries with required field checks
- Trace emission instrumentation in all 5 SKILL.md files at lifecycle points with graceful || true degradation
- `trace.jsonl` persisted during archive (treated as cross-session observability data like memory.jsonl and reflection.jsonl)
- Health-check validation for `trace.jsonl` integrity
- Research quality calibration in `/do:recon` — behavioral sharpeners per researcher type, DO/DON'T guardrail table with dual-scan posture, source hierarchy tiers for external-researcher, invisible curriculum elicitation for codebase-analyst and domain-specialist

## [2.14.0] - 2026-02-18

### Added

- `sync-check` command in plan.py — detects drift between shared protocol sections (Script Setup, Liveness Pipeline, Finalize Fallback) across all 5 SKILL.md files using structural fingerprints

### Changed

- Compacted duplicated protocol blocks inline across all 5 SKILL.md files (74 lines saved, 4.5% reduction): Script Setup merged to single code block, Liveness Pipeline converted to table format, Self-Reflection commands compacted
- Inlined worker protocol into `/do:execute` SKILL.md — removed separate `.design/worker-protocol.md` runtime file pattern

## [2.13.0] - 2026-02-17

### Changed

- `/do:recon` always spawns full research team (codebase-analyst, external-researcher, domain-specialist) — removed shallow/deep depth tiers since recon is inherently exploratory and external research is always valuable
- Removed `depthTier` field from recon.json schema and plan.py validation — interventions always capped at 5

## [2.12.0] - 2026-02-17

### Added

- Temporal resolution tracking in `/do:reflect` — 3-tier status (active/likely_resolved/confirmed_resolved) with 3-run recency window and memory.jsonl cross-referencing to prevent flagging already-fixed issues
- Mandatory verification specs for complex goals in `/do:design` Step 4.5 — decision matrix distinguishes mandatory (4+ roles, new skills, API integration) from optional (1-3 roles, docs/config-only)
- Measurable verificationProperties instruction in `/do:design` expert prompts — experts must ground estimates in actual code metrics (file counts, line counts, test coverage)
- Shift-left acceptance criteria anti-pattern warnings in `/do:design` Step 3 expert prompts — prevents grep-only criteria from entering plans
- F-string brace nesting depth tracking in `validate-checks` — detects backslash escapes inside f-string expression braces

### Changed

- `/do:reflect` migrated from Task-based analyst to direct Bash-based analysis (4 substeps: gather data, compute metrics, formulate hypotheses, write artifact) — eliminates hallucination risk from unreliable Task agents
- Strengthened acceptance criteria anti-patterns in `/do:design` Step 4 — added `|| true` variant, expanded examples

### Fixed

- Bidirectional deadlock in overlap matrix — enforced strict j>i ordering in both `cmd_overlap_matrix` and `_compute_directory_overlaps` (finalize)

## [2.11.0] - 2026-02-17

### Added

- `/do:recon` skill — pre-design reconnaissance combining deep research with Meadows-style leverage analysis
- `skills/recon/SKILL.md` — 7-level Meadows framework adapted for software (paradigm/goals/rules/information_flows/feedback_loops/structure/parameters)
- `recon-validate` command in plan.py — schema validation for recon.json with deterministic leverage scoring (tier-weight formula)
- `recon-summary` command in plan.py — format ranked interventions for display with Abson 4-group mapping
- `.design/recon.json` contract (schemaVersion 1) — ranked interventions with designGoal + constraints (not implementation suggestions)
- Depth tiers in recon — shallow mode (max 3 interventions), deep mode (max 5 interventions)
- Contradiction detection in recon — lightweight scan for conflicting findings (TRIZ-style)
- Recon added to valid skills whitelist in reflection-add command

### Changed

- Plugin description updated to include all 5 skills (recon and reflect were missing)
- Command count updated to 27 (14 query, 5 mutation, 6 validation, 1 build, 1 test)

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
