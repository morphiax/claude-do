# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`claude-do` is a Claude Code plugin providing five skills: `/do:design` (team-based goal decomposition into `.design/plan.json`), `/do:execute` (dependency-graph execution with worker teammates), `/do:research` (comprehensive knowledge research producing actionable research.json with recommendations), `/do:simplify` (cascade simplification for code and text — one insight eliminates multiple components — producing plan.json with preservation-focused worker roles), and `/do:reflect` (evidence-based improvement from execution reflections). It leverages Claude Code's native Agent Teams and Tasks features for multi-agent collaboration. All skills use the main conversation as team lead with teammates for analytical/execution work. Skills are implemented as SKILL.md prompts augmented with python3 helper scripts for deterministic operations.

## Testing

No automated test suite exists. Testing is manual and functional:

```bash
# Load the plugin locally
claude --plugin-dir ~/.claude/plugins/marketplaces/do

# Test the full workflow
/do:design <some goal>
/do:execute
```

All five skills must be tested end-to-end. Changes to design, execute, research, simplify, or reflect may affect the others since they share the `.design/plan.json` contract (or `.design/research.json` for research) and persistent files (`memory.jsonl`, `reflection.jsonl`).

## Architecture

### Plugin Structure

- `.claude-plugin/plugin.json` — Plugin manifest (name, version, metadata)
- `.claude-plugin/marketplace.json` — Marketplace distribution config
- `shared/plan.py` — Shared helper script (35 commands: 17 query, 6 mutation, 9 validation, 1 build, 2 test)
- `shared/lead-protocol-core.md` — Canonical lead protocol core (boundaries, no-polling, trace, memory, phase announcements, INSIGHT handling). Consumed by all team-based skills at startup.
- `shared/lead-protocol-teams.md` — Lead protocol teams patterns (TeamCreate enforcement, liveness pipeline, team patterns). Consumed by design/execute/simplify at startup.
- `skills/design/SKILL.md` — `/do:design` skill definition
- `skills/design/scripts/plan.py` — Symlink → `shared/plan.py`
- `skills/design/lead-protocol-core.md` — Symlink → `shared/lead-protocol-core.md`
- `skills/design/lead-protocol-teams.md` — Symlink → `shared/lead-protocol-teams.md`
- `skills/execute/SKILL.md` — `/do:execute` skill definition
- `skills/execute/scripts/plan.py` — Symlink → `shared/plan.py`
- `skills/execute/lead-protocol-core.md` — Symlink → `shared/lead-protocol-core.md`
- `skills/execute/lead-protocol-teams.md` — Symlink → `shared/lead-protocol-teams.md`
- `skills/research/SKILL.md` — `/do:research` skill definition
- `skills/research/scripts/plan.py` — Symlink → `shared/plan.py`
- `skills/research/lead-protocol-core.md` — Symlink → `shared/lead-protocol-core.md`
- `skills/reflect/SKILL.md` — `/do:reflect` skill definition
- `skills/reflect/scripts/plan.py` — Symlink → `shared/plan.py`
- `skills/simplify/SKILL.md` — `/do:simplify` skill definition
- `skills/simplify/scripts/plan.py` — Symlink → `shared/plan.py`
- `skills/simplify/lead-protocol-core.md` — Symlink → `shared/lead-protocol-core.md`
- `skills/simplify/lead-protocol-teams.md` — Symlink → `shared/lead-protocol-teams.md`

### Skill Files Are the Implementation

The SKILL.md files are imperative prompts that Claude interprets at runtime. Deterministic operations (validation, dependency computation, plan manipulation) are delegated to per-skill python3 helper scripts. Each skill resolves its local `scripts/plan.py` path at runtime and invokes subcommands via `python3 $PLAN_CLI <command> [args]`. All script output follows JSON convention (`{ok: true/false, ...}`).

Each SKILL.md has YAML frontmatter (`name`, `description`, `argument-hint`) that must be preserved.

**Shared Lead Protocol**: Design, execute, research, and simplify share common orchestration patterns through two symlinked files. `shared/lead-protocol-core.md` (consumed by all team-based skills) covers boundaries, no-polling guarantees, trace emission, memory injection, phase announcements, and INSIGHT handling. `shared/lead-protocol-teams.md` (consumed by design/execute/simplify only) covers TeamCreate enforcement, liveness pipeline patterns, and team-member coordination. Research uses standalone Task() subagents and consumes only the core protocol. Reflect is fully inline (no team, no agent spawning) and does not consume the shared protocol.

### Scripts

A single `shared/plan.py` at the repo root provides all deterministic operations. Each skill symlinks to it from `skills/{name}/scripts/plan.py` so SKILL.md can resolve a skill-local path.

- **Query** (17 commands): team-name (generate project-unique team name from skill + cwd), status, summary, overlap-matrix, tasklist-data, worker-pool, retry-candidates, circuit-breaker, memory-search (keyword-based search in .design/memory.jsonl with recency weighting and importance scoring), reflection-search (filter past reflections by skill, sorted by recency), memory-review (list all memories in human-readable format with filtering), health-check (validate .design/ integrity), plan-diff (compare two plan.json files), plan-health-summary (lifecycle context from reflections and plan status), sync-check (detect drift between shared protocol sections across SKILL.md files using structural fingerprints), trace-search (query trace events by session, skill, event type, or agent), trace-summary (format trace data for display with aggregate statistics)
- **Mutation** (6 commands): update-status (atomically modify plan.json via temp file + rename with state machine validation), memory-add (append JSONL entry with UUID, importance 1-10, and dynamic boost/decay), reflection-add (append structured self-evaluation to reflection.jsonl, evaluation JSON via stdin), resume-reset (resets in_progress roles to pending, increments attempts), archive (archives stale .design/ artifacts to .design/history/{timestamp}/), trace-add (append agent lifecycle events to trace.jsonl with automatic ID/timestamp generation)
- **Validation** (7 commands): expert-validate (schema validation for expert artifacts), reflection-validate (schema validation for reflection evaluations), memory-summary (format injection summary for display), validate-checks (syntax validation for acceptanceCriteria check commands — detects broken Python in `python3 -c` checks, including f-string brace nesting errors), research-validate (schema validation for research.json including optional designHandoff), research-summary (format research output for display including designHandoffCount), trace-validate (schema validation for trace.jsonl with required field checks)
- **Build** (1 command): finalize — validates role briefs, computes directory overlaps, validates state transitions, and computes SHA256 checksums for verification specs in one atomic operation
- **Test** (1 command): self-test — exercises every command against synthetic fixtures in a temp directory, reports pass/fail per command as JSON

Design uses query + finalize. Execute uses all commands. Research uses query + research-validate + research-summary. Improve uses query + finalize (same as design). `worker-pool` reads roles directly — one worker per role, named by role (e.g., `api-developer`, `test-writer`). Workers read `plan.json` directly — no per-worker task files needed.

Scripts use python3 stdlib only (no dependencies), support Python 3.8+, and follow a consistent CLI pattern: `python3 plan.py <command> [plan_path] [options]`. All output is JSON to stdout with exit code 0 for success, 1 for errors.

### Data Contracts: .design/plan.json and .design/research.json

Skills communicate through structured JSON files in `.design/` (gitignored). Two primary contracts:

**`.design/plan.json` (schemaVersion 4)** — used by design, execute, simplify, and reflect for role-based execution:

Key points:

- `.design/plan.json` is the authoritative state; the TaskList is a derived view
- Schema version 4 is required
- Roles use name-based dependencies resolved to indices by `finalize`
- `finalize` validates role briefs and computes `directoryOverlaps` from scope directories/patterns (strict j>i ordering to prevent bidirectional deadlocks)
- No prompt assembly — workers read role briefs directly from plan.json and decide their own implementation approach
- Expert artifacts (`expert-*.json`) are preserved in `.design/` for execute workers to reference via `expertContext` entries. The lead must never write expert artifacts — only experts save their own findings
- Memory storage: `.design/memory.jsonl` contains cross-session semantic learnings (JSONL format with UUID, category, keywords, content, timestamp, importance 1-10). Categories include: convention, pattern, mistake, approach, failure, and procedure (learned execution patterns). Entries must pass five quality gates: transferability, category fit, surprise-based importance, deduplication, and specificity. Session-specific observations (metrics, counts, file lists) are rejected
- Memory retrieval uses keyword matching with recency decay (10%/30 days) and importance weighting (score = keyword_match * recency_factor * importance/10). Dynamic importance tracking via --boost/--decay flags correlates outcomes with memory relevance
- Reflection storage: `.design/reflection.jsonl` contains per-run episodic self-evaluations (JSONL format with UUID, skill, goal, outcome, goalAchieved, evaluation object, timestamp). Both design and execute append entries at end of each run. Memory-curator reads reflections as primary signal for what to record
- **Persistent `.design/` files** (survive archiving): `memory.jsonl`, `reflection.jsonl`, `research.json`, `trace.jsonl`. Everything else is archived to `.design/history/{timestamp}/`
- Plan history: completed runs are archived to `.design/history/{timestamp}/`; design pre-flight archives stale artifacts
- Verification specs: optional schema layer for property-based testing. Lead writes spec files in `.design/specs/{role-name}.{ext}` (shell scripts or native test framework). Specs are immutable during execution; workers run them after acceptance criteria pass and report failures as blocking. `finalize` validates spec references and computes SHA256 checksums for tamper detection.

**Top-level fields**: schemaVersion (4), goal, context {stack, conventions, testCommand, buildCommand, lsp}, expertArtifacts [{name, path, summary}], designDecisions [{conflict, experts, decision, reasoning}], verificationSpecs [] (optional), roles[], auxiliaryRoles[], progress {completedRoles: []}

**Role fields** — each role is a goal-directed scope for one specialist worker:
- `name` — worker identity and naming (e.g., `api-developer`, `prompt-writer`)
- `goal` — clear statement of what this role must achieve
- `model` — preferred Claude model (`sonnet`, `opus`, `haiku`)
- `scope` — `{directories, patterns, dependencies}` where dependencies are role names resolved to indices
- `expertContext` — array of `{expert, artifact, relevance}` referencing full expert artifacts
- `constraints` — array of hard rules the worker must follow
- `acceptanceCriteria` — array of `{criterion, check}` where `check` is a concrete, independently runnable shell command (e.g., `"bun run build"`, `"python3 -m pytest tests/"`). Checks must verify functional correctness, not just pattern existence (a grep confirming a rule exists is insufficient — verify it takes effect). Check commands must exit non-zero on failure. Anti-patterns to avoid: grep-only checks, `|| echo` or `|| true` fallbacks, `test -f` as sole verification, `wc -l` counts, pipe chains without explicit exit-code handling. Workers execute these literally during CoVe verification
- `assumptions` — array of `{text, severity}` documenting assumptions (`blocking` or `non-blocking`)
- `rollbackTriggers` — array of conditions that should cause the worker to stop and report
- `fallback` — alternative approach if primary fails (included in initial brief)

**Status fields** (initialized by finalize): status (`pending`), result (null), attempts (0), directoryOverlaps (computed)

**Verification spec fields** (optional, generated in design Step 4.5, validated/checksummed by finalize):
- `verificationSpecs[]` — top-level array of `{role: string, path: string, runCommand: string, properties: [string], sha256: string}`. Each entry maps a role to its verification spec file (e.g., `.design/specs/api-developer.test.ts`).
  - `role` — role name this spec applies to (must match a role in roles[])
  - `path` — path to the spec file; runnable in the project's test framework (bun test, pytest, cargo test) or as a shell script
  - `runCommand` — shell command to execute the spec (e.g., `bun test .design/specs/spec-api-developer.test.ts`)
  - `properties` — array of brief descriptions of what each spec tests (property invariants, boundary conditions, integration contracts)
  - `sha256` — SHA256 checksum of the spec file (computed by finalize); integration-verifier checks this to detect spec tampering
- Specs test broad behavioral properties (e.g., "rate limit resets after window", "API endpoints return valid JSON") rather than implementation details. Failures are blocking — workers must fix code to pass specs, never modify the spec file itself.

**Auxiliary roles** — standalone Task tool agents (not team members) that improve quality without directly implementing features:
- `challenger` (pre-execution) — reviews plan, challenges assumptions, finds gaps. Blocking issues are mandatory gates: lead must address each one before proceeding
- `scout` (pre-execution) — reads actual codebase to verify expert assumptions match reality. Verifies that referenced dependencies resolve (classes→CSS, imports→modules, types→definitions)
- `integration-verifier` (post-execution) — verifies cross-role integration, runs full test suite. Reports "skipped" for checks requiring unavailable capabilities (e.g., browser rendering) — never infers results
- `memory-curator` (post-execution) — distills reflection.jsonl and role results into actionable memory entries in .design/memory.jsonl. Reflections are the primary signal for what to record

**Auxiliary role fields**: name, type (pre-execution|post-execution), goal, model, trigger

**`.design/research.json` (schemaVersion 1)** — used by `/do:research` for comprehensive knowledge research output:

Research produces structured knowledge across 5 sections with ranked recommendations. Key points:

- Schema fields: schemaVersion (1), goal, context {same as plan.json}, sections {prerequisites, mentalModels, usagePatterns, failurePatterns, productionReadiness}, recommendations[], researchGaps[], designHandoff[] (optional)
- **Section fields**: name (string), findings (array of finding objects), synthesis (string summary). Notable sub-fields: prerequisites.conceptDependencyGraph[] (ordered learning paths), usagePatterns.evolutionPaths[] (stage/pattern/trigger progression), productionReadiness.teamAdoption {learningTimeline, documentationQuality, communitySupport}
- **Recommendation fields**: id, title, summary, confidence (low/medium/high), effort (low/medium/high), prerequisites (array), reasoning (string), bestFit[] (scenarios where this is the right choice), wrongFit[] (scenarios where this is the wrong choice)
- **Finding fields**: id, section, source, summary, domain (codebase/literature/comparative/theoretical)
- **Design handoff fields**: source (reference-material|codebase-analysis|expert-finding|literature), element (what the building block is), material (concrete content — string, array, or object), usage (how /do:design should use it)
- Recommendations include confidence levels and effort estimates for adoption planning
- Research gaps document areas needing additional investigation
- Design handoff preserves concrete building blocks from expert artifacts so /do:design can read research.json alone without re-reading expert artifacts (token efficiency)

### Verification Specs Protocol

Verification specs are broad, property-based tests that workers must satisfy. They codify expert-provided properties as executable tests without constraining implementation creativity. `/do:design` can generate verification specs in its optional Step 4.5.

**When to generate specs:**
- **Mandatory** for complex goals: 4+ roles, new skills, API integration
- **Optional** for simple goals: 1-3 roles, docs/config-only, sparse verificationProperties
- Expert artifacts must contain concrete verificationProperties sections
- Stack supports test execution (context.testCommand or context.buildCommand exists)

**Authorship:**
- **Simple goals** (1-3 roles, clear external interfaces): Lead writes specs from expert verificationProperties
- **Complex goals** (4+ roles): Spawn a spec-writer Task agent with `Task(subagent_type: "general-purpose")` that CAN read source code. Prompt: "Read expert verificationProperties from `.design/expert-*.json` and the actual codebase in scope directories from plan.json roles. Write verification spec files in `.design/specs/{role-name}.{ext}` using the project's test framework (bun test, pytest, cargo test) or shell scripts as fallback. Specs test behavioral properties, not implementation details. Return paths of created spec files."

**Spec generation steps:**
1. Read expert verificationProperties sections from all expert artifacts
2. For each role, extract relevant properties (filter by role scope/goal alignment)
3. Create `mkdir -p .design/specs`
4. Write spec files in project's native test framework or shell scripts:
   - **Native tests** (preferred): `.design/specs/spec-{role-name}.test.{ext}` using bun test, pytest, jest, cargo test, etc. Use property-based testing frameworks where available (fast-check, hypothesis, proptest)
   - **Shell fallback**: `.design/specs/spec-{role-name}.sh` with exit 0 = pass
5. For each spec file created, add an entry to plan.json's `verificationSpecs[]` array:
   ```json
   {
     "role": "{role-name}",
     "path": ".design/specs/spec-{role-name}.{ext}",
     "runCommand": "{command to execute spec, e.g., 'bun test .design/specs/spec-api.test.ts'}",
     "properties": ["brief description of each property tested"]
   }
   ```

**Spec content guidelines:**
- Test WHAT the system does (external behavior), not HOW (implementation structure)
- Include positive cases (valid inputs succeed) AND negative cases (invalid inputs fail correctly)
- Use property-based testing where possible (for all X, property P(X) holds)
- Test cross-role contracts for integration boundaries
- Specs must be independently runnable via their runCommand (no global setup dependencies)

**Finalization:**
Run `python3 $PLAN_CLI finalize .design/plan.json` to validate structure, compute overlaps, and compute SHA256 checksums for spec files (tamper detection).

### Execution Model

All five skills use the **main conversation as team lead** with Agent Teams (or Task for single-agent skills). Runtime behavior is defined in each SKILL.md file — this section covers structural facts only.

- **Lead** (main conversation): orchestration only via `TeamCreate`, `SendMessage`, `TaskCreate`/`TaskUpdate`/`TaskList`, `Bash` (scripts, git, verification), `AskUserQuestion`. Never reads project source files.
- **Teammates**: specialist agents spawned into the team. Discover lead name via `~/.claude/teams/{team-name}/config.json`.

**`/do:design`** — team name: `do-design-{project}-{hash}` (generated by `team-name` command)
- Protocol guardrail: lead must follow the flow step-by-step and never answer goals directly before pre-flight
- Phase announcements: lead announces each major phase (pre-flight, expert spawning, cross-review, synthesis, finalization) for user visibility
- Lifecycle context: runs `plan-health-summary` to display recent reflections at skill start
- TeamCreate health check: verifies team is reachable, retries once on failure
- Memory injection: lead searches .design/memory.jsonl for relevant past learnings (using importance-weighted scoring) and injects top 3-5 into expert prompts with transparency (shows what was injected to user). Expert prompts request verificationProperties (behavioral invariants, boundary conditions, integration contracts) to inform spec generation. Expert prompts include anti-pattern warnings for acceptance criteria (shift-left prevention of grep-only checks). Memory search failures gracefully fallback to empty results
- Expert prompts include INSIGHT: instruction: agents emit intermediate findings during analysis with INSIGHT: prefix for real-time user feedback on discovery progress.
- Lead spawns expert teammates (architect, researcher, domain-specialists) based on goal type awareness (implementation/meta/research). Expert prompts include behavioral trait instructions (e.g., "prefer composable patterns", "be skeptical of X") and require measurable verificationProperties based on actual code metrics (not theoretical estimates)
- Expert liveness pipeline: completion checklist tracking which experts have reported, turn-based timeout (3 turns then re-spawn), re-spawn ceiling (max 2 attempts then proceed with available artifacts)
- Cross-review: interface negotiation and perspective resolution via actual expert messaging (lead must not perform cross-review solo). Audit trail saved to `.design/cross-review.json`. Lead resolves unresolved conflicts in designDecisions[]
- Draft plan review: for complex/high-stakes goals (based on complexity tier), lead displays draft plan.json to user for brief review before finalization
- Complexity-proportional auxiliary selection: plans with roleCount ≤ 2 skip challenger and scout auxiliaries (lower token overhead). Plans with roleCount > 2 run challenger (with adversarial behavioral traits) and scout (when the goal touches code). Integration-verifier and memory-curator always run post-execution.
- Lead synthesizes expert findings into role briefs in plan.json directly (no plan-writer delegate)
- Step 4.5 (conditional, after role briefs written): Lead generates verification specs from expert verificationProperties and role briefs. Mandatory for complex goals (4+ roles, new skills, API integration). Optional for simple goals (1-3 roles, docs/config-only, sparse verificationProperties). For complex goals, a standalone spec-writer Task agent can assist. Specs are written to `.design/specs/{role-name}.{ext}` in the project's test framework (or shell scripts as fallback) and added to plan.json's verificationSpecs[].
- `finalize` validates role briefs (including that not all acceptance criteria are surface-only checks), validates verificationSpecs schema (if present), computes SHA256 checksums for spec files, and computes directory overlaps (no prompt assembly)
- End-of-run summary: displays role count, complexity tier, expert artifacts produced, design decisions made, and verification specs generated

**`/do:execute`** — team name: `do-execute-{project}-{hash}` (generated by `team-name` command)
- Phase announcements: lead announces each major phase (pre-flight, auxiliary spawning, worker execution, post-execution) for user visibility
- Lifecycle context: runs `plan-health-summary` to display recent reflections at skill start
- TeamCreate health check: verifies team is reachable, retries once on failure
- Complexity-proportional auxiliaries: plans with roleCount ≤ 2 skip challenger and scout auxiliaries (lower token overhead for trivial goals). Plans with roleCount > 2 run pre-execution auxiliaries (challenger with adversarial traits, scout with fact-checking focus) in parallel before workers spawn with structured output formats. After parallel completion, challenger results (plan.json constraint injection) are processed first, then scout results are consumed. Scout verifies that verificationSpec files exist and that runCommands reference valid tools/paths if specs are present.
- AC pre-validation: before worker spawning, lead runs each role's acceptance criteria `check` commands to detect always-pass or broken criteria early. Workers then verify criteria again during completion as a fresh question.
- Memory injection: lead searches .design/memory.jsonl per role (using importance-weighted scoring with role.goal + scope as context) and injects top 2-3 into worker prompts with transparency (shows injected memories to user). Memory search failures gracefully fallback to empty results
- Lead creates TaskList from plan.json, spawns one persistent worker per role via `worker-pool`. Worker instructions use structured tables for clarity (identity, brief, context, verification, reporting)
- Adaptive model escalation: workers start on assigned model (haiku/sonnet/opus), escalate to next-higher tier on retry (haiku→sonnet→opus). Model escalation shown in worker status updates
- Peer-to-peer worker handoff: when a role completes and is a dependency for others, worker can send keyDecisions and contextForDependents directly to dependent workers via SendMessage (notifyOnComplete). Lead still controls task unblocking. Enables faster context delivery for dependent roles.
- Worker liveness pipeline: turn-based silence detection with 3-turn timeout then re-spawn (max 2 attempts per role before proceeding with available progress). Workers must acknowledge fix requests within 1 turn (no idle-without-responding). Simplified from previous 5-turn ping + 7-turn timeout
- Workers report completion as structured JSON schema: `{role, achieved, filesChanged[], acceptanceCriteria[{criterion, passed, evidence}], keyDecisions[], contextForDependents}`
- Workers provide progress reporting for significant events (file writes, test runs, criterion verification). Tool boundaries: workers do NOT use WebFetch, WebSearch, or Task
- Workers use CoVe-style self-verification: before reporting completion, MUST run every acceptance criterion's `check` command as a separate shell invocation (not assumed from other checks). Each criterion's check is a concrete shell command; workers execute them literally and report exit codes. If a verificationSpec is present for the role, workers then run the spec via its runCommand after all acceptance criteria pass; spec failures are blocking. Lead performs file state verification (git diff + ls) before rejecting completions to avoid stale diagnostic false rejections.
- Directory overlap serialization: concurrent roles touching overlapping directories get runtime `blockedBy` constraints
- Retry budget: max 3 attempts per role with reflexion (analyze root cause, incorrect assumptions, alternative approaches before retry) and adaptive model escalation. Fix-worker retries are constrained to modifications only (no new file creation). Reflexion format: `--- Retry N Reflexion ---` separates analysis from failure data
- Cascading failures: explicit TaskUpdate instructions for cascaded entries (increment blockedBy, remove from worker-pool)
- Circuit breaker: abort if >50% remaining roles would be skipped (bypassed for plans with 3 or fewer roles)
- Post-execution auxiliaries (integration verifier with structured report format, memory curator with strict quality persona) after all roles complete. Integration verifier checks verificationSpec SHA256 checksums for tampering and runs all specs, reporting results in structured format.
- Memory curator: distills reflection.jsonl and role results into .design/memory.jsonl entries, applying five quality gates before storing: transferability (useful in a new session?), category fit (convention/pattern/mistake/approach/failure/procedure), surprise (unexpected findings score higher), deduplication (no redundant entries), and specificity (must contain concrete references). Importance scored 1-10 based on surprise value, not uniform. Session-specific data (test counts, metrics, file lists) is explicitly rejected. When goal originated from `/do:reflect`, explicitly records which doNextTime items were addressed and how using category "procedure". Curator shows curation summary to user for transparency
- Goal review evaluates whether completed work achieves the original goal
- Self-reflection: both design and execute write structured self-evaluations to `.design/reflection.jsonl` at end of each run (episodic memory). Memory-curator reads reflections as primary signal
- End-of-run summary: displays roles completed/failed/skipped, files changed, acceptance criteria results, verification spec results, and memories curated

**`/do:research`** — standalone Task() subagents (not team-based)
- Protocol guardrail: lead must follow the flow step-by-step (pre-flight, researcher spawning, synthesis, output finalization)
- Phase announcements: lead announces each major phase (pre-flight, researcher spawning, synthesis, finalization) for user visibility
- Lifecycle context: runs `plan-health-summary` to display recent reflections at skill start
- Spawns parallel standalone Task() subagents (codebase-analyst, external-researcher, domain-specialist) — research is inherently exploratory, external research is always valuable. Researchers report findings via artifact files in `.design/`, not via team messaging.
- Memory injection: lead searches .design/memory.jsonl for relevant past learnings and injects top 3 into researcher prompts with transparency. Memory search failures gracefully fallback to empty results
- Researcher prompts include behavioral trait instructions (e.g., "prefer empirical evidence", "ground research in concrete findings")
- Researcher quality calibration: behavioral sharpeners per researcher type (codebase-analyst, external-researcher, domain-specialist), DO/DON'T guardrail table with dual-scan posture (seek failure signals AND working constraints), source hierarchy tiers for external-researcher, invisible curriculum elicitation for codebase-analyst and domain-specialist. Minimum research thresholds: >=3 production post-mortems for failure patterns, >=5 beginner mistakes across all sections, quantitative performance claims required
- Synthesis: lead organizes findings across 5 knowledge sections (prerequisites, mentalModels, usagePatterns, failurePatterns, productionReadiness), generates recommendations ranked by confidence and effort
- Synthesis delegation: lead synthesizes by default. For >15 findings across >3 domains, spawns single synthesis Task agent
- `research-validate` validates schema, outputs validation result
- `research-summary` formats findings and recommendations for display
- Output: produces `.design/research.json` (schemaVersion 1) with knowledge sections and recommendations array. Recommendations include confidence, effort, prerequisites, and decision framework (bestFit/wrongFit scenarios) for adoption planning. Sections include concept dependency graphs, evolution paths, and team adoption factors
- Self-reflection: writes structured self-evaluation to `.design/reflection.jsonl` at end of run using `reflection-add`
- End-of-run summary: displays recommendation count, knowledge sections completed, research gaps identified, and findings analyzed

**`/do:reflect`** — no team (direct Bash-based analysis)
- Phase announcements: lead announces each major phase (pre-flight, reflection analysis, hypothesis generation, user selection) for user visibility
- Lifecycle context: runs `plan-health-summary` to display recent reflections at skill start
- Evidence-based improvement using execution reflections (`.design/reflection.jsonl`) as optimization signal
- Requires minimum 2 reflection entries to identify patterns (configurable via `--min-runs`). Uses `reflection-search` command to filter reflections by skill
- Direct Bash-based analysis (no Task agent): lead gathers data via plan.py commands (reflection-search, memory-search), computes metrics via python3, formulates hypotheses directly, and writes artifact — eliminates hallucination risk from unreliable Task agents
- Temporal resolution tracking: recurring failures classified as active (appears in recent 3 runs), likely_resolved (absent from recent runs), or confirmed_resolved (memory.jsonl has resolution record). Non-active patterns skipped during hypothesis generation
- Memory injection: lead searches .design/memory.jsonl for relevant past learnings with transparency. Memory search failures gracefully fallback to empty results
- Hypotheses have confidence levels: high (>=3 reflections), medium (2), low (1 strong signal)
- User selects which improvements to include in plan
- Uses `archive` command (via plan.py) instead of raw shell for consistency with other skills
- Self-reflection at end of run (writes to reflection.jsonl like other skills) using `reflection-add` with validation
- Output: always produces `.design/plan.json` (schemaVersion 4) for `/do:execute` — reflect never writes source files directly
- End-of-run summary: displays reflection count analyzed, hypotheses generated by confidence level, and user-selected improvements

**`/do:simplify`** — team name: `do-simplify-{project}-{hash}` (generated by `team-name` command)
- Protocol guardrail: lead must follow the flow step-by-step (pre-flight, analyst spawning, cascade synthesis, plan output)
- Phase announcements: lead announces each major phase (pre-flight, analyst spawning, cascade synthesis, finalization) for user visibility
- Lifecycle context: runs `plan-health-summary` to display recent reflections at skill start
- TeamCreate health check: verifies team is reachable, retries once on failure
- Target type detection: code (.py/.js/.ts etc), text (.md/SKILL.md/.yaml etc), or mixed — drives which analyst variant spawns
- Spawns 2 analysts (pattern-recognizer, complexity-analyst) with target-type-aware behavioral trait instructions. Text targets get token weight, dead rules, and redundancy analysis instead of git churn/cyclomatic complexity. Analyst prompts include INSIGHT: instruction for intermediate findings.
- Cascade thinking: analysts seek simplification opportunities where one insight eliminates multiple components, reducing cognitive overhead without sacrificing capability
- Anti-pattern guards from improve merged in: token budget tracking, circular simplification detection, regression safety
- Memory injection: lead searches .design/memory.jsonl for relevant past learnings and injects top 3 into analyst prompts with transparency. Memory search failures gracefully fallback to empty results
- Analyst liveness pipeline: completion checklist tracking which analysts have reported, turn-based timeout (3 turns then re-spawn), re-spawn ceiling (max 2 attempts then proceed with available findings)
- Lead synthesizes cascade opportunities into preservation-focused worker roles: roles that remove/restructure code preserve semantics, not just delete
- Complexity-proportional auxiliary selection: plans with roleCount ≤ 2 skip challenger and scout (post-execution only remains). Plans with roleCount > 2 run full auxiliary pipeline (challenger pre-execution, integration-verifier + memory-curator post-execution).
- Output: always produces `.design/plan.json` (schemaVersion 4) for `/do:execute` — simplify never writes source files directly
- End-of-run summary: displays cascade opportunities identified, simplification roles created, and preservation constraints documented

## Requirements

- Claude Code 2.1.32+ with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`
- python3 3.8+ (for helper scripts)

## Commit Conventions

Conventional commits with imperative mood: `feat:`, `fix:`, `chore:`, `refactor:`, `docs:`, `test:`. Example: `feat: add retry context to agent prompt`.

## Pre-commit Checklist

Before every commit and push:

1. **Update docs**: If SKILL.md changes affect architecture, update `CLAUDE.md` (Architecture section) and `README.md` to match. These three must stay in sync.
2. **Update README features**: If a new feature or capability is added, check `README.md` — update the "What's Novel" or "How It Works" sections to reflect it. New user-facing features must be discoverable in the README.
3. **Update changelog**: Add an entry to `CHANGELOG.md` under the current version for every functional change (feat, fix, refactor). Group under Added/Changed/Fixed per Keep a Changelog format. Do not skip this — the changelog is the project's history.
4. **Bump version**: Increment the patch version in `.claude-plugin/plugin.json` (and the version badge in `README.md`) for every functional change. Use semver: patch for fixes/refactors, minor for new features, major for breaking changes.
