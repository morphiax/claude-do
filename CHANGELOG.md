# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.1] - 2026-02-21

### Changed

- **Reflect: marketplace path guidance**: Added note to always edit marketplace copy of SKILL.md files, not the cache copy which is regenerated.
- **Research: user context check**: Added mandatory pre-spawn check to clarify user situation before researching. Prevents broad landscape surveys when the user has a specific use case.
- **Research: adaptive researcher composition**: Researcher roles are now tailored to the topic instead of fixed 3-role template.
- **Research: audience-targeted recommendations**: Recommendations now lead with the audience matching the clarified user context.

## [3.0.0] - 2026-02-21

### Changed

- **BREAKING: Replace Agent Teams with standalone Task() subagents**: Design, execute, and simplify no longer use TeamCreate/TeamDelete/SendMessage. All agent coordination now uses standalone `Task()` calls that block until completion. Removes team setup, liveness pipelines, and polling logic.
- **Remove lead-protocol-teams.md**: Deleted symlinks from design, execute, and simplify. Team patterns consolidated into individual SKILL.md files or removed entirely.
- **Simplify lead-protocol-core.md**: Removed Self-Monitoring section (now in `/do:reflect`), simplified Lead Boundaries (removed team tools), updated No Polling and INSIGHT Handling for Task()-based model, removed Lifecycle Feedback section.
- **Design uses Task() subagents**: Experts spawned as parallel standalone Task() calls instead of team members. Cross-review uses follow-up Task() calls. No team creation or liveness tracking.
- **Execute and simplify updated**: Adjusted for Task()-based agent model.

## [2.29.0] - 2026-02-20

### Changed

- **Design ambiguity check**: Pre-flight now uses sequential-thinking to assess goal ambiguity and scope assumptions before proceeding. Added scope change gate for when existing solutions would alter what gets built.
- **Reflect skill expanded**: Significant expansion of reflect SKILL.md with deeper adversarial review and fix-skill capabilities.
- **Minor refinements**: Execute, research, and simplify SKILL.md adjustments for consistency with reflect extraction.

## [2.28.1] - 2026-02-20

### Changed

- **Remove runtime reflection prepend**: Replaced Reflection Prepend (runtime prompt patching) with a note directing to `/do:reflect fix-skill` for permanent SKILL.md improvements. Simplified lifecycle feedback display.

## [2.28.0] - 2026-02-20

### Added

- **`/do:reflect` skill**: New standalone reflection skill that runs self-monitoring as a separate step rather than inline at the end of each skill. Supports all existing reflection fields (promptFixes, acGradients, acMutations, highValueInstructions, etc.).

### Changed

- **Self-reflection extracted from skills**: Design, execute, research, and simplify no longer run inline `reflection-add`. Instead, next-action suggestions route through `/do:reflect` first. Trace emission remains in each skill.
- **Next action routing**: All skills now suggest `/do:reflect` as the first next step, followed by the skill-specific follow-up.

## [2.27.0] - 2026-02-20

### Added

- **Next action suggestions**: All four skills now suggest the logical next `/do:` command at the end of each run with a comprehensive, copy-pasteable prompt derived from the current goal. Research routes to `/do:design` using recommendation `designGoal` fields (up to 3 options). Design and simplify route to `/do:execute`. Execute suggests retry, redesign, or simplification based on outcome. Shared protocol defined in `lead-protocol-core.md`, skill-specific behavior in each SKILL.md Complete section.

## [2.26.4] - 2026-02-20

### Changed

- **Step numbering fixed**: Eliminated `2b.` sub-step in design Step 5 (renumbered to sequential 1-10). Fixed stale "Step 1.8" → "Step 1.9" reference in execute. Fixed stale "Step 4.5" → "Step 6" reference in CLAUDE.md.
- **Dead schema fields removed**: Removed `interfaceContracts` and `complexityTier` from design Contracts (no downstream consumer). Removed prose-only lines across all SKILL.md files (explanatory asides, preambles, purpose clauses that don't change lead behavior).
- **Liveness tracking deduplication**: Removed inline liveness tracking instructions from design and simplify — both already reference lead-protocol-teams.md which defines the canonical procedure.
- **AC anti-pattern deduplication**: Simplified simplify's AC anti-pattern list to reference-only (canonical list in design Step 5).
- **CLAUDE.md validation commands**: Added `validate-auxiliary-report` and `worker-completion-validate` to documented runtime-invoked validation commands.
- **Empty section removed**: Removed vacuous "Worker Protocol (Inline)" section from execute SKILL.md.

## [2.26.3] - 2026-02-20

### Added

- **Design consumes AC mutations**: Design Step 5 now reads `acMutations` from `plan-health-summary` before authoring acceptance criteria. Common anti-patterns (wrong test data, fragile position checks, trivially-passing comparisons) are documented with the `after` field as a template for better checks.
- **Simplify protects proven instructions**: Analyst prompts include a 6th mandatory constraint: check `highValueInstructions` in reflection.jsonl before recommending removal. Instructions with recorded evidence are flagged `provenValue: true`.
- **Auxiliary effectiveness tracking**: New `auxiliaryEffectiveness` reflection field records per-auxiliary ROI (ran, findings, blockingFindings, prevented). `plan-health-summary` aggregates across last 5 runs and flags `lowROI` auxiliaries with 3+ consecutive zero-finding runs.

## [2.26.2] - 2026-02-20

### Added

- **AC mutation tracking**: New `acMutations` reflection field captures every plan.json modification the lead makes before workers spawn — challenger AC fixes, scout constraint injections, pre-validation broken-check repairs, always-pass classifications. Each entry has `source`, `role`, `category`, `before`, `after`, `reason`. Surfaced via `plan-health-summary` so `/do:design` sees the gap between what it produced and what `/do:execute` needed, closing the AC quality feedback loop.
- **High-value instruction tracking**: New `highValueInstructions` reflection field records which SKILL.md instructions demonstrably drove good outcomes. Each entry has `instruction`, `section`, and `evidence`. Surfaced via `plan-health-summary` so `/do:simplify` can see proven-impact instructions before removing them.
- **Lead-side workaround capture**: New Step C in Reflection Procedure captures plan.json mutations the lead made during execution. Generates `promptFixes` targeting upstream design skill even on fully successful runs.

### Fixed

- **CLAUDE.md mutation count**: Corrected "6 mutation" → "7 mutation" commands (trace-add was uncounted). Total 35 commands unchanged (17+7+9+1+1).

## [2.26.1] - 2026-02-20

### Changed

- **CLAUDE.md trimmed**: Removed ~150 lines of runtime-duplicate content from CLAUDE.md. Eliminated per-skill Execution Model bullets (those were restatements of SKILL.md workflows), removed Verification Specs Protocol section (developers should read SKILL.md Step 4.5), trimmed verbose Data Contracts prose to developer-facing schema references only, removed stale /do:improve references, and condensed 10 never-invoked plan.py inspection tool descriptions into a single summary line. Architecture section now focuses on structural facts (file layout, symlinks, data contracts) rather than runtime sequences.
- **Step numbering unified**: Fixed step numbering in design/SKILL.md (3.5→4, 4→5, 4.5→6, 5→7, 6→8) and simplify/SKILL.md (3.5→4, 4→5, 5→6). All internal cross-references and protocol headers updated. AC anti-patterns consolidated into canonical location (design Step 5).
- **Soft protocol references hardened**: Strengthened all soft protocol references (e.g., "Per Self-Monitoring protocol") to hard directives (e.g., "You MUST follow the Self-Monitoring procedure...") across all 4 SKILL.md files. Applies to Self-Monitoring, Reflection Prepend, Memory Injection show-user steps, and Liveness Pipeline (design/execute/simplify). Improves protocol enforcement.
- **Reflection validation tightened**: `reflection-add` now rejects (exit 1 with error) when `whatFailed` is non-empty but `promptFixes` is empty. This prevents vague failure records that lack actionable improvement guidance. All self-tests pass (121/121).

## [2.26.0] - 2026-02-19

### Added

- **MAST failure taxonomy**: `promptFixes` entries now include a `failureClass` field drawn from the MAST multi-agent failure taxonomy (spec-disobey, premature-termination, incorrect-verification, etc.). `reflection-validate` enforces valid values via `VALID_FAILURE_CLASSES` constant. Enables cross-run aggregation by failure type.
- **AC gradient capture**: During lead-side verification in execute, failed AC checks are recorded as structured `(role, criterion, check, exitCode, stderr)` triples into a session-scoped `acGradients` list (initialized Step 1.9, populated Step 4, consumed Step 7). Based on ProTeGi textual gradient approach.
- **Reflection prepend into agent prompts**: Unresolved improvements from past runs are injected directly into agent prompts at spawn time via a 4-step structural procedure in lead-protocol-core.md. All 4 skills reference it. Based on Reflexion (Shinn et al.) finding that explicit instructions outperform narrative feedback.
- **OPRO ascending sort**: `_extract_unresolved_improvements` sorts failures-first (items from failed runs before successful), making the improvement direction visible. Based on OPRO (Yang et al.).
- **Lamarckian prompt fix derivation**: Mandatory Step B in the Reflection Procedure — must write `idealOutcome` before deriving `fix`. `reflection-validate` warns when `idealOutcome` is missing. Based on PromptBreeder's Lamarckian mutation operator.

### Changed

- **Self-Monitoring rewritten as Reflection Procedure**: Advisory paragraph replaced with mandatory 3-step procedure (A: collect AC gradients, B: Lamarckian reverse-engineering, C: build reflection JSON). Each step is structural — has named inputs, outputs, and validation.
- **Reflection Prepend elevated to structural protocol**: From one-liner "apply per core" to 4-step procedure with matching rules, MUST language, and show-user gate.
- **`reflection-validate` strengthened**: Now validates `promptFixes` subfields (`section`, `problem`, `idealOutcome`, `fix`, `failureClass`), validates `failureClass` against MAST taxonomy, and accepts `acGradients` array. Returns warnings for missing fields.
- **SKILL.md reflection templates deduplicated**: All 4 skills now reference lead-protocol-core.md for base schema, only listing skill-specific fields.

## [2.25.0] - 2026-02-19

### Added

- **Prompt-improvement reflections**: Reflection schema reframed to produce data that directly improves SKILL.md prompts. New required fields: `promptFixes` (specific SKILL.md section + problem + fix), `stepsSkipped` (protocol steps skipped and why), `instructionsIgnored` (instructions agents didn't follow). Replaces generic `doNextTime` as primary improvement signal.
- **Memory feedback loop**: New `memory-feedback` command in plan.py closes the feedback loop on injected memories. Boosts memories correlated with first-attempt role success (+1 importance, cap 10), decays memories correlated with failure (-1 importance, floor 1), increments `usage_count` on all. Execute/SKILL.md wired to call after memory curation.
- **Unresolved improvements surfacing**: `plan-health-summary` now extracts and deduplicates `promptFixes` + `doNextTime` items from last 5 reflections. Lifecycle Context displays top 3 unresolved items at skill startup so the lead can act on recurring issues.

### Changed

- **Trace payloads**: All trace-add calls across all 4 SKILL.md files now include structured `--payload` with context (model, memories injected, AC results, outcomes, skipped steps). Previously all payloads were empty `{}`. Enables cross-run analysis of step coverage, timing, skip patterns, and retry behavior.
- **lead-protocol-core.md**: Trace Emission table now includes a Payload column documenting required payload fields per event type. Added guidance: "Always include `--payload` with structured context — empty payloads waste the trace infrastructure."
- **lead-protocol-core.md streamlined** (via /do:execute): Trace Emission compressed to table, execute-specific git override moved to execute/SKILL.md, Protocol Requirement + Do Not Use EnterPlanMode merged into single Guardrails section, INSIGHT handling separated from Phase Announcements, fixed redundant "auto-deliver automatically" wording.
- **Deduplication**: Removed inline Lifecycle Context restatements from all 4 SKILL.md files (replaced with references to lead-protocol-core.md). Removed duplicate Script Setup and Trace Emission sections from execute/SKILL.md.

## [2.23.0] - 2026-02-19

### Removed

- **`/do:reflect` skill**: Removed entire skill directory and command entry. The separate reflection analysis skill is no longer needed since all skills now self-monitor continuously via the Self-Monitoring protocol.
- `/do:reflect` from plugin.json description
- `/do:reflect` execution model section from CLAUDE.md
- `/do:reflect` example from README.md usage block
- `skills/reflect/SKILL.md` — skill file
- `skills/reflect/scripts/plan.py` — symlink

### Added

- **Self-Monitoring protocol** in `shared/lead-protocol-core.md`: Lightweight observation recording mechanism. All four surviving skills (design, execute, research, simplify) now record structured observations at the moment they occur — no separate reflection analysis step needed. Observations are appended to `.design/reflection.jsonl` alongside end-of-run reflections.
- Self-monitoring references added to design, execute, research, and simplify SKILL.md files to emit observations at key decision points (AC quality, challenger outcome, verifier outcome, worker violations in execute; similar expansion points in other skills as needed).

## [2.22.0] - 2026-02-19

### Changed

- **Lead protocol split**: `shared/lead-protocol.md` split into `shared/lead-protocol-core.md` (boundaries, no-polling, trace, memory, phase announcements, INSIGHT handling) and `shared/lead-protocol-teams.md` (TeamCreate enforcement, liveness pipeline, team patterns). All symlinks updated in skill directories.
- **Research topology**: Research skill converted from TeamCreate with team-member researchers to parallel standalone Task() subagents. Researchers report via artifact files instead of SendMessage. Simplified team lifecycle overhead, research consumes only lead-protocol-core.md.
- **Complexity-proportional auxiliaries**: Execute, design, and simplify now gate auxiliary selection by complexity tier. Plans with roleCount ≤ 2 skip challenger and scout auxiliaries. Reduces token overhead for trivial goals while maintaining safety for complex ones.
- **INSIGHT surfacing**: Lead protocol (core) now documents how to handle INSIGHT: messages from agents for immediate intermediate findings. Agent prompts in design, execute, research, and simplify updated to emit INSIGHT: prefixed messages during research/analysis phases. Improves real-time user feedback.
- **Peer-to-peer worker handoff**: Execute workers can now send context directly to dependent workers via SendMessage (notifyOnComplete). Lead still controls task unblocking. Enables faster context delivery for dependent roles.

## [2.21.0] - 2026-02-19

### Added

- Shared lead protocol extracted into `shared/lead-protocol.md` as canonical source of truth for 4 team-based skills (design, execute, research, simplify). Reduces drift and improves maintainability.
- Each team-based skill now reads `shared/lead-protocol.md` at startup, substituting skill-specific values (agent types: experts/researchers/analysts/workers).
- `shared/` directory consolidates common assets (`plan.py` helper script + `lead-protocol.md` protocol) at root level, replacing previous `scripts/` and `skills/shared/` layout.

### Fixed

- **Bug 1**: TEAM_NAME parsing now uses proper JSON extraction (`python3 -c` with json.load) instead of shell field accessor. Fixes design and execute skills.
- **Bug 2**: Research liveness pipeline table restored to 4 rows (was missing "Turn timeout" ping text and "Never write artifacts yourself" row).
- **Bug 3**: Design liveness timeout standardized to 3 turns (was incorrectly 2 turns; execute/research/simplify all use 3).
- **Bug 4**: Trace emission `--payload` option now documented in research SKILL.md (was missing payload mention).

### Changed

- Memory injection standardized to "top 3-5" across all skills (execute was inconsistently using "top 2-3").
- Design, execute, research, simplify SKILL.md files refactored to reference shared protocol instead of inline duplication.
- Reflect SKILL.md left unchanged (fully inline, no team, does not consume shared protocol).

## [2.20.0] - 2026-02-19

### Changed

- **BREAKING**: `/do:improve` retired — `/do:simplify` now handles both code and text targets, subsuming improve's functionality with cascade thinking applied to prompts, constraints, and protocol text
- `/do:simplify` generalized: target type detection (code/text/mixed) drives analyst variant selection. Text targets get token weight, dead rules, and redundancy analysis. SKILL.md exclusion removed
- Anti-pattern guards from improve merged into simplify: token budget tracking, circular simplification detection, regression safety
- Text-specific worked example added (Liveness Protocol Unification — 5 separate pipeline descriptions → 1 shared protocol table)
- Plugin description and docs updated to reflect five-skill plugin (design, execute, research, simplify, reflect)

### Removed

- `skills/improve/` directory — SKILL.md and scripts/plan.py symlink
- All `/do:improve` references from CLAUDE.md, README.md, plan.py help strings, and plugin.json
- "improve" from valid skill lists in plan.py (reflection-add, trace-add, sync-check, _load_skill_paths)

## [2.19.0] - 2026-02-19

### Added

- Memory curator now accepts `procedure` category for persistent architectural limitations (was missing from CATEGORY TEST)
- Worked example in curator prompt for Known Gaps → procedure memory conversion

### Changed

- `plan-health-summary` now returns structured `recentRuns` (goal, doNextTime, whatFailed) from last 3 reflections instead of reading handoff.md
- All 6 SKILL.md lifecycle context displays simplified: "Recent runs: {reflection summaries}" (removed "Previous session: {handoff summary}")
- improve/SKILL.md historical evidence check uses `tail -5` for most recent entries

### Removed

- **handoff.md retired** — session handoff file removed from persistence layer. All unique value (Known Gaps, Next Steps) now flows through reflection.jsonl → memory-curator → memory.jsonl
- `_read_handoff_summary()` function from plan.py
- Session handoff write step from execute SKILL.md (was Step 7.2)
- handoff.md from persistent file set in archive command
- handoff.md reads from reflect and improve SKILL.md
- handoff.md from memory-curator artifact read list in execute SKILL.md

## [2.18.1] - 2026-02-18

### Changed

- Extracted `_read_jsonl(path, filter_fn)` shared utility — 5 JSONL reading sites unified
- Unified duplicate memory loaders (`_load_memories` + `_load_memory_entries`) into single `_load_memory_entries`
- Unified duplicate memory scorers (`_score_memory` + inline closure) into single `_score_memory` with proper tokenization (fixes naive substring scoring bug)
- Replaced `_get_shared_block_patterns` (~105 lines of normalize closures) with `_SHARED_BLOCK_PATTERNS` constant + `_normalize_block` function (19 lines)
- Extracted shared `_compute_overlaps` utility — both `cmd_overlap_matrix` and `_compute_directory_overlaps` now call it
- CLAUDE.md command count corrected from 32 to 35

### Fixed

- Added 'simplify' to `_VALID_TRACE_SKILLS` — `trace-add --skill simplify` now works correctly

### Removed

- 7 `skip_test_` methods and 5 inline commented test bodies (~140 lines dead code)
- `_compute_intervention_score` function and its test (unused)

## [2.18.0] - 2026-02-18

### Added

- Concept dependency graph (`conceptDependencyGraph[]`) in research prerequisites section — ordered learning paths ("understand A before B before C")
- Evolution paths (`evolutionPaths[]`) in research usage patterns section — captures pattern progression at scale ("start with X, refactor to Y as you scale")
- Team adoption factors (`teamAdoption`) in research production readiness section — learning timeline, documentation quality, community support assessment
- Decision framework (`bestFit[]`, `wrongFit[]`) in research recommendations — explicit fit/anti-fit scenarios for adoption planning
- Minimum research thresholds enforced during synthesis — >=3 production post-mortems, >=5 beginner mistakes, quantitative performance claims required
- Second calibration example for external-researcher (prerequisite documentation quality)
- Paradigm-level cascade worked example (immutability) in simplify pattern-recognizer prompt — expands analytical search space beyond component unification

### Changed

- Elevated "Everything is a special case of..." as primary lens in simplify pattern-recognizer prompt (before symptom table)
- Research DO/DON'T guardrail table expanded with quantitative performance and intended-vs-actual-use rules
- External-researcher prompt explicitly seeks "intended use case vs how people actually use it" gaps

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
