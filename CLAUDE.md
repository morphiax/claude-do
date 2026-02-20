# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`claude-do` is a Claude Code plugin providing four skills: `/do:design` (team-based goal decomposition into `.design/plan.json`), `/do:execute` (dependency-graph execution with worker teammates), `/do:research` (comprehensive knowledge research producing actionable research.json with recommendations), and `/do:simplify` (cascade simplification for code and text — one insight eliminates multiple components — producing plan.json with preservation-focused worker roles). All skills self-monitor their execution by recording structured observations to `.design/reflection.jsonl` via the Self-Monitoring protocol documented in the shared lead protocol. It leverages Claude Code's native Agent Teams and Tasks features for multi-agent collaboration. All skills use the main conversation as team lead with teammates for analytical/execution work. Skills are implemented as SKILL.md prompts augmented with python3 helper scripts for deterministic operations.

## Testing

No automated test suite exists. Testing is manual and functional:

```bash
# Load the plugin locally
claude --plugin-dir ~/.claude/plugins/marketplaces/do

# Test the full workflow
/do:design <some goal>
/do:execute
```

All four skills must be tested end-to-end. Changes to design, execute, research, or simplify may affect the others since they share the `.design/plan.json` contract (or `.design/research.json` for research) and persistent files (`memory.jsonl`, `reflection.jsonl`).

## Architecture

### Plugin Structure

- `.claude-plugin/plugin.json` — Plugin manifest (name, version, metadata)
- `.claude-plugin/marketplace.json` — Marketplace distribution config
- `shared/plan.py` — Shared helper script (35 commands: 17 query, 7 mutation, 9 validation, 1 build, 1 test)
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
- `skills/simplify/SKILL.md` — `/do:simplify` skill definition
- `skills/simplify/scripts/plan.py` — Symlink → `shared/plan.py`
- `skills/simplify/lead-protocol-core.md` — Symlink → `shared/lead-protocol-core.md`
- `skills/simplify/lead-protocol-teams.md` — Symlink → `shared/lead-protocol-teams.md`

### Skill Files Are the Implementation

The SKILL.md files are imperative prompts that Claude interprets at runtime. Deterministic operations (validation, dependency computation, plan manipulation) are delegated to per-skill python3 helper scripts. Each skill resolves its local `scripts/plan.py` path at runtime and invokes subcommands via `python3 $PLAN_CLI <command> [args]`. All script output follows JSON convention (`{ok: true/false, ...}`).

Each SKILL.md has YAML frontmatter (`name`, `description`, `argument-hint`) that must be preserved.

**Shared Lead Protocol**: Design, execute, research, and simplify share common orchestration patterns through two symlinked files. `shared/lead-protocol-core.md` (consumed by all team-based skills) covers boundaries, no-polling guarantees, trace emission, memory injection, phase announcements, self-monitoring protocol, and INSIGHT handling. `shared/lead-protocol-teams.md` (consumed by design/execute/simplify only) covers TeamCreate enforcement, liveness pipeline patterns, and team-member coordination. Research uses standalone Task() subagents and consumes only the core protocol.

### Scripts

A single `shared/plan.py` at the repo root provides all deterministic operations. Each skill symlinks to it from `skills/{name}/scripts/plan.py` so SKILL.md can resolve a skill-local path.

- **Query** (runtime-invoked): team-name, status, summary, overlap-matrix, tasklist-data, worker-pool, retry-candidates, circuit-breaker, memory-search, plan-health-summary
- **Mutation** (runtime-invoked): update-status, memory-add, memory-feedback, reflection-add, resume-reset, archive, trace-add
- **Validation** (runtime-invoked): expert-validate, validate-checks, research-validate, research-summary
- **Build** (1 command): finalize — validates role briefs, computes directory overlaps, validates state transitions, and computes SHA256 checksums for verification specs in one atomic operation
- **Test** (1 command): self-test — exercises every command against synthetic fixtures in a temp directory, reports pass/fail per command as JSON
- **Developer inspection tools** (not invoked by skills at runtime): reflection-search, memory-review, health-check, plan-diff, sync-check, trace-search, trace-summary, reflection-validate, memory-summary, trace-validate

Design uses query + finalize. Execute uses all commands. Research uses query + research-validate + research-summary. `worker-pool` reads roles directly — one worker per role, named by role (e.g., `api-developer`, `test-writer`). Workers read `plan.json` directly — no per-worker task files needed.

Scripts use python3 stdlib only (no dependencies), support Python 3.8+, and follow a consistent CLI pattern: `python3 plan.py <command> [plan_path] [options]`. All output is JSON to stdout with exit code 0 for success, 1 for errors.

### Data Contracts: .design/plan.json and .design/research.json

Skills communicate through structured JSON files in `.design/` (gitignored). Two primary contracts:

**`.design/plan.json` (schemaVersion 4)** — used by design, execute, and simplify for role-based execution:

- Authoritative state; TaskList is a derived view. Schema version 4 required.
- Roles use name-based dependencies resolved to indices by `finalize`.
- **Persistent `.design/` files** (survive archiving): `memory.jsonl`, `reflection.jsonl`, `research.json`, `trace.jsonl`. Everything else archived to `.design/history/{timestamp}/`
- **Reflection fields**: `promptFixes` (primary — captures failure-driven AND lead-side workarounds), `highValueInstructions` (proven instructions to protect from simplification), `acGradients` (execute only), `stepsSkipped`, `instructionsIgnored`, `whatWorked`/`whatFailed`
- Verification specs: optional `verificationSpecs[]` in plan.json. `finalize` computes SHA256 checksums for tamper detection.

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

**Verification spec fields**: `verificationSpecs[]` — top-level array of `{role, path, runCommand, properties, sha256}`. See SKILL.md Step 4.5 for authorship and content guidelines.

**Auxiliary roles** — standalone Task tool agents (not team members) that improve quality without directly implementing features:
- `challenger` (pre-execution) — reviews plan, challenges assumptions, finds gaps. Blocking issues are mandatory gates: lead must address each one before proceeding
- `scout` (pre-execution) — reads actual codebase to verify expert assumptions match reality. Verifies that referenced dependencies resolve (classes→CSS, imports→modules, types→definitions)
- `integration-verifier` (post-execution) — verifies cross-role integration, runs full test suite. Reports "skipped" for checks requiring unavailable capabilities (e.g., browser rendering) — never infers results
- `memory-curator` (post-execution) — distills reflection.jsonl and role results into actionable memory entries in .design/memory.jsonl. Reflections are the primary signal for what to record

**Auxiliary role fields**: name, type (pre-execution|post-execution), goal, model, trigger

**`.design/research.json` (schemaVersion 1)** — used by `/do:research` for comprehensive knowledge research output:

- Top-level: schemaVersion (1), goal, context, sections {prerequisites, mentalModels, usagePatterns, failurePatterns, productionReadiness}, recommendations[], researchGaps[], designHandoff[] (optional)
- **Recommendation fields**: id, title, summary, confidence (low/medium/high), effort (low/medium/high), prerequisites, reasoning, bestFit[], wrongFit[]
- **Finding fields**: id, section, source, summary, domain (codebase/literature/comparative/theoretical)
- **Design handoff fields**: source, element, material, usage — preserves expert building blocks so /do:design can read research.json without re-reading expert artifacts

### Execution Model

All four skills use the **main conversation as team lead** with Agent Teams (or Task for single-agent skills). Runtime behavior is defined in each SKILL.md file — this section covers structural facts only.

- **Lead** (main conversation): orchestration only via `TeamCreate`, `SendMessage`, `TaskCreate`/`TaskUpdate`/`TaskList`, `Bash` (scripts, git, verification), `AskUserQuestion`. Never reads project source files.
- **Teammates**: specialist agents spawned into the team. Discover lead name via `~/.claude/teams/{team-name}/config.json`.

Team naming convention: `do-{skill}-{project}-{hash}` (generated by `team-name` command). Research uses standalone Task() subagents instead of a persistent team.

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
