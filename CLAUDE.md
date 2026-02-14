# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`claude-do` is a Claude Code plugin providing two skills: `/do:design` (team-based goal decomposition into `.design/plan.json`) and `/do:execute` (dependency-graph execution with worker teammates). It leverages Claude Code's native Agent Teams and Tasks features for multi-agent collaboration. Both skills use the main conversation as team lead with teammates for analytical/execution work. Skills are implemented as SKILL.md prompts augmented with python3 helper scripts for deterministic operations.

## Testing

No automated test suite exists. Testing is manual and functional:

```bash
# Load the plugin locally
claude --plugin-dir /path/to/claude-do

# Test the full workflow
/do:design <some goal>
/do:execute
```

Both skills must be tested end-to-end. A change to one skill may affect the other since they share the `.design/plan.json` contract.

## Architecture

### Plugin Structure

- `.claude-plugin/plugin.json` — Plugin manifest (name, version, metadata)
- `.claude-plugin/marketplace.json` — Marketplace distribution config
- `scripts/plan.py` — Shared helper script (10 commands: 7 query, 2 mutation, 1 build)
- `skills/design/SKILL.md` — `/do:design` skill definition
- `skills/design/scripts/plan.py` — Symlink → `../../../scripts/plan.py`
- `skills/execute/SKILL.md` — `/do:execute` skill definition
- `skills/execute/scripts/plan.py` — Symlink → `../../../scripts/plan.py`

### Skill Files Are the Implementation

The SKILL.md files are imperative prompts that Claude interprets at runtime. Deterministic operations (validation, dependency computation, plan manipulation) are delegated to per-skill python3 helper scripts. Each skill resolves its local `scripts/plan.py` path at runtime and invokes subcommands via `python3 $PLAN_CLI <command> [args]`. All script output follows JSON convention (`{ok: true/false, ...}`).

Each SKILL.md has YAML frontmatter (`name`, `description`, `argument-hint`) that must be preserved.

### Scripts

A single `scripts/plan.py` at the repo root provides all deterministic operations. Each skill symlinks to it from `skills/{name}/scripts/plan.py` so SKILL.md can resolve a skill-local path.

- **Query** (7 commands): status, summary, overlap-matrix, tasklist-data, worker-pool, retry-candidates, circuit-breaker
- **Mutation** (2 commands): resume-reset, update-status — atomically modify plan.json via temp file + rename
- **Build** (1 command): finalize — validates role briefs and computes directory overlaps in one atomic operation

Design uses query + finalize. Execute uses all commands. `worker-pool` reads roles directly — one worker per role, named by role (e.g., `api-developer`, `test-writer`). Workers read `plan.json` directly — no per-worker task files needed.

Scripts use python3 stdlib only (no dependencies), support Python 3.8+, and follow a consistent CLI pattern: `python3 plan.py <command> [plan_path] [options]`. All output is JSON to stdout with exit code 0 for success, 1 for errors.

### Data Contract: .design/plan.json

The two skills communicate through `.design/plan.json` (schemaVersion 4) written to the `.design/` directory at runtime (gitignored). Key points:

- `.design/plan.json` is the authoritative state; the TaskList is a derived view
- Schema version 4 is required
- Roles use name-based dependencies resolved to indices by `finalize`
- `finalize` validates role briefs and computes `directoryOverlaps` from scope directories/patterns
- No prompt assembly — workers read role briefs directly from plan.json and decide their own implementation approach
- Expert artifacts (`expert-*.json`) are preserved in `.design/` for execute workers to reference via `expertContext` entries
- Plan history: completed runs are archived to `.design/history/{timestamp}/`; design pre-flight archives stale artifacts

**Top-level fields**: schemaVersion (4), goal, context {stack, conventions, testCommand, buildCommand, lsp}, expertArtifacts [{name, path, summary}], roles[], auxiliaryRoles[], progress {completedRoles: []}

**Role fields** — each role is a goal-directed scope for one specialist worker:
- `name` — worker identity and naming (e.g., `api-developer`, `prompt-writer`)
- `goal` — clear statement of what this role must achieve
- `model` — preferred Claude model (`sonnet`, `opus`, `haiku`)
- `scope` — `{directories, patterns, dependencies}` where dependencies are role names resolved to indices
- `expertContext` — array of `{expert, artifact, relevance}` referencing full expert artifacts
- `constraints` — array of hard rules the worker must follow
- `acceptanceCriteria` — array of `{criterion, check}` defining goal-based success conditions
- `assumptions` — array of `{text, severity}` documenting assumptions (`blocking` or `non-blocking`)
- `rollbackTriggers` — array of conditions that should cause the worker to stop and report
- `fallback` — alternative approach if primary fails (included in initial brief)

**Status fields** (initialized by finalize): status (`pending`), result (null), attempts (0), directoryOverlaps (computed)

**Auxiliary roles** — meta-agents that improve quality without directly implementing features:
- `challenger` (pre-execution) — reviews plan, challenges assumptions, finds gaps
- `scout` (pre-execution) — reads actual codebase to verify expert assumptions match reality
- `integration-verifier` (post-execution) — verifies cross-role integration, runs full test suite

**Auxiliary role fields**: name, type (pre-execution|post-execution), goal, model, trigger

### Execution Model

Both skills use the **main conversation as team lead** with Agent Teams. Runtime behavior is defined in each SKILL.md file — this section covers structural facts only.

- **Lead** (main conversation): orchestration only via `TeamCreate`, `SendMessage`, `TaskCreate`/`TaskUpdate`/`TaskList`, `Bash` (scripts, git, verification), `AskUserQuestion`. Never reads project source files.
- **Teammates**: specialist agents spawned into the team. Discover lead name via `~/.claude/teams/{team-name}/config.json`.

**`/do:design`** — team name: `do-design`
- Lead spawns expert teammates (architect, researcher, domain-specialists) based on goal analysis
- Complexity tier (trivial/standard/complex/high-stakes) drives auxiliary role selection
- Lead synthesizes expert findings into role briefs in plan.json directly (no plan-writer delegate)
- `finalize` validates role briefs and computes directory overlaps (no prompt assembly)

**`/do:execute`** — team name: `do-execute`
- Pre-execution auxiliaries (challenger, scout) run before workers spawn
- Lead creates TaskList from plan.json, spawns one persistent worker per role via `worker-pool`
- Workers explore their scope directories, plan their own approach, implement, test, and verify against acceptance criteria
- Directory overlap serialization: concurrent roles touching overlapping directories get runtime `blockedBy` constraints
- Retry budget: max 3 attempts per role | Cascading failures: skip dependents of failed roles
- Circuit breaker: abort if >50% remaining roles would be skipped (bypassed for plans with 3 or fewer roles)
- Post-execution auxiliaries (integration verifier) after all roles complete
- Goal review evaluates whether completed work achieves the original goal
- Session handoff: `.design/handoff.md` written on completion for context recovery

## Requirements

- Claude Code 2.1.32+ with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`
- python3 3.8+ (for helper scripts)

## Commit Conventions

Conventional commits with imperative mood: `feat:`, `fix:`, `chore:`, `refactor:`, `docs:`, `test:`. Example: `feat: add retry context to agent prompt`.

## Pre-commit Checklist

Before every commit and push:

1. **Update docs**: If SKILL.md changes affect architecture, update `CLAUDE.md` (Architecture section) and `README.md` to match. These three must stay in sync.
2. **Bump version**: Increment the patch version in `.claude-plugin/plugin.json` (and the version badge in `README.md`) for every functional change. Use semver: patch for fixes/refactors, minor for new features, major for breaking changes.
