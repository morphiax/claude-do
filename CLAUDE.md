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
- `scripts/plan.py` — Shared helper script (12 commands: 8 query, 3 mutation, 1 build)
- `skills/design/SKILL.md` — `/do:design` skill definition
- `skills/design/scripts/plan.py` — Symlink → `../../../scripts/plan.py`
- `skills/execute/SKILL.md` — `/do:execute` skill definition
- `skills/execute/scripts/plan.py` — Symlink → `../../../scripts/plan.py`

### Skill Files Are the Implementation

The SKILL.md files are imperative prompts that Claude interprets at runtime. Deterministic operations (validation, dependency computation, plan manipulation) are delegated to per-skill python3 helper scripts. Each skill resolves its local `scripts/plan.py` path at runtime and invokes subcommands via `python3 $PLAN_CLI <command> [args]`. All script output follows JSON convention (`{ok: true/false, ...}`).

Each SKILL.md has YAML frontmatter (`name`, `description`, `argument-hint`) that must be preserved.

### Scripts

A single `scripts/plan.py` at the repo root provides all deterministic operations. Each skill symlinks to it from `skills/{name}/scripts/plan.py` so SKILL.md can resolve a skill-local path.

- **Query** (8 commands): status, summary, overlap-matrix, tasklist-data, worker-pool, retry-candidates, circuit-breaker, memory-search (keyword-based search in .design/memory.jsonl with recency weighting and importance scoring)
- **Mutation** (3 commands): update-status (atomically modify plan.json via temp file + rename), memory-add (append JSONL entry with UUID and importance rating 1-10), resume-reset (resets in_progress roles to pending, increments attempts)
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
- Memory storage: `.design/memory.jsonl` contains cross-session learnings (JSONL format with UUID, category, keywords, content, timestamp, importance 1-10). Entries must pass five quality gates: transferability, category fit, surprise-based importance, deduplication, and specificity. Session-specific observations (metrics, counts, file lists) are rejected
- Memory retrieval uses keyword matching with recency decay (10%/30 days) and importance weighting (score = keyword_match * recency_factor * importance/10)
- Plan history: completed runs are archived to `.design/history/{timestamp}/`; design pre-flight archives stale artifacts

**Top-level fields**: schemaVersion (4), goal, context {stack, conventions, testCommand, buildCommand, lsp}, expertArtifacts [{name, path, summary}], designDecisions [{conflict, experts, decision, reasoning}], roles[], auxiliaryRoles[], progress {completedRoles: []}

**Role fields** — each role is a goal-directed scope for one specialist worker:
- `name` — worker identity and naming (e.g., `api-developer`, `prompt-writer`)
- `goal` — clear statement of what this role must achieve
- `model` — preferred Claude model (`sonnet`, `opus`, `haiku`)
- `scope` — `{directories, patterns, dependencies}` where dependencies are role names resolved to indices
- `expertContext` — array of `{expert, artifact, relevance}` referencing full expert artifacts
- `constraints` — array of hard rules the worker must follow
- `acceptanceCriteria` — array of `{criterion, check}` where `check` is a concrete, independently runnable shell command (e.g., `"bun run build 2>&1 | tail -20"`). Workers execute these literally during CoVe verification
- `assumptions` — array of `{text, severity}` documenting assumptions (`blocking` or `non-blocking`)
- `rollbackTriggers` — array of conditions that should cause the worker to stop and report
- `fallback` — alternative approach if primary fails (included in initial brief)

**Status fields** (initialized by finalize): status (`pending`), result (null), attempts (0), directoryOverlaps (computed)

**Auxiliary roles** — meta-agents that improve quality without directly implementing features:
- `challenger` (pre-execution) — reviews plan, challenges assumptions, finds gaps
- `scout` (pre-execution) — reads actual codebase to verify expert assumptions match reality
- `integration-verifier` (post-execution) — verifies cross-role integration, runs full test suite
- `memory-curator` (post-execution) — distills handoff.md and role results into actionable memory entries in .design/memory.jsonl

**Auxiliary role fields**: name, type (pre-execution|post-execution), goal, model, trigger

### Execution Model

Both skills use the **main conversation as team lead** with Agent Teams. Runtime behavior is defined in each SKILL.md file — this section covers structural facts only.

- **Lead** (main conversation): orchestration only via `TeamCreate`, `SendMessage`, `TaskCreate`/`TaskUpdate`/`TaskList`, `Bash` (scripts, git, verification), `AskUserQuestion`. Never reads project source files.
- **Teammates**: specialist agents spawned into the team. Discover lead name via `~/.claude/teams/{team-name}/config.json`.

**`/do:design`** — team name: `do-design`
- Protocol guardrail: lead must follow the flow step-by-step and never answer goals directly before pre-flight
- Memory injection: lead searches .design/memory.jsonl for relevant past learnings (using importance-weighted scoring) and injects top 3-5 into expert prompts
- Lead spawns expert teammates (architect, researcher, domain-specialists) based on goal type awareness (implementation/meta/research)
- Diverse debate: for complex/high-stakes goals with >=3 experts, experts cross-review each other's artifacts, challenge assumptions with structured format, defend their positions; lead resolves conflicts in designDecisions[]
- Complexity tier (trivial/standard/complex/high-stakes) drives auxiliary role selection:
  - Trivial (1-2 roles): no auxiliaries
  - Standard (2-4 roles): integration verifier
  - Complex (4-6 roles): challenger + scout + integration verifier
  - High-stakes (3-8 roles): challenger + scout + integration verifier
- Lead synthesizes expert findings into role briefs in plan.json directly (no plan-writer delegate)
- `finalize` validates role briefs and computes directory overlaps (no prompt assembly)

**`/do:execute`** — team name: `do-execute`
- Pre-execution auxiliaries (challenger, scout) run before workers spawn with structured output formats
- Memory injection: lead searches .design/memory.jsonl per role (using importance-weighted scoring with role.goal + scope as context) and injects top 2-3 into worker prompts
- Lead creates TaskList from plan.json, spawns one persistent worker per role via `worker-pool`
- Workers use CoVe-style self-verification: before reporting completion, MUST run every acceptance criterion's `check` command as a separate shell invocation (not assumed from other checks). Each criterion's check is a concrete shell command; workers execute them literally and report exit codes
- Workers provide progress reporting for significant events (no silent execution)
- Directory overlap serialization: concurrent roles touching overlapping directories get runtime `blockedBy` constraints
- Retry budget: max 3 attempts per role with reflexion (analyze root cause, incorrect assumptions, alternative approaches before retry)
- Cascading failures: skip dependents of failed roles
- Circuit breaker: abort if >50% remaining roles would be skipped (bypassed for plans with 3 or fewer roles)
- Post-execution auxiliaries (integration verifier with structured report format, memory curator) after all roles complete
- Memory curator: distills handoff.md and role results into .design/memory.jsonl entries, applying five quality gates before storing: transferability (useful in a new session?), category fit (convention/pattern/mistake/approach/failure), surprise (unexpected findings score higher), deduplication (no redundant entries), and specificity (must contain concrete references). Importance scored 1-10 based on surprise value, not uniform. Session-specific data (test counts, metrics, file lists) is explicitly rejected
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
