# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`claude-do` is a Claude Code plugin providing two skills: `/do:design` (team-based goal decomposition into `.design/plan.json`) and `/do:execute` (dependency-graph execution with worker teammates). It leverages Claude Code's native Agent Teams and Tasks features for multi-agent collaboration. Both skills use a launcher → dedicated team lead → teammates architecture. Skills are implemented as SKILL.md prompts augmented with python3 helper scripts for deterministic operations.

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
- `scripts/plan.py` — Shared helper script (17 commands: 12 query, 2 mutation, 3 build)
- `skills/design/SKILL.md` — `/do:design` skill definition
- `skills/design/scripts/plan.py` — Symlink → `../../../scripts/plan.py`
- `skills/execute/SKILL.md` — `/do:execute` skill definition
- `skills/execute/scripts/plan.py` — Symlink → `../../../scripts/plan.py`

### Skill Files Are the Implementation

The SKILL.md files are imperative prompts that Claude interprets at runtime. Deterministic operations (validation, dependency computation, plan manipulation) are delegated to per-skill python3 helper scripts. Each skill resolves its local `scripts/plan.py` path at runtime and invokes subcommands via `python3 $PLAN_CLI <command> [args]`. All script output follows JSON convention (`{ok: true/false, ...}`).

Each SKILL.md has YAML frontmatter (`name`, `description`, `argument-hint`) that must be preserved.

### Scripts

A single `scripts/plan.py` at the repo root provides all deterministic operations. Each skill symlinks to it from `skills/{name}/scripts/plan.py` so SKILL.md can resolve a skill-local path.

- **Query** (12 commands): validate, status-counts, summary, overlap-matrix, tasklist-data, ready-set, extract-fields, model-distribution, retry-candidates, collect-files, circuit-breaker, extract-task
- **Mutation** (2 commands): resume-reset, update-status — atomically modify plan.json via temp file + rename
- **Build** (3 commands): validate-structure, assemble-prompts, compute-overlaps — used by the plan-writer for deterministic finalization

Design uses a subset (query + build). Execute uses all commands. `extract-task` writes per-worker `.design/worker-task-{N}.json` files to reduce context window usage.

Scripts use python3 stdlib only (no dependencies), support Python 3.8+, and follow a consistent CLI pattern: `python3 plan.py <command> [plan_path] [options]`. All output is JSON to stdout with exit code 0 for success, 1 for errors.

### Data Contract: .design/plan.json

The two skills communicate through `.design/plan.json` (schemaVersion 3) written to the `.design/` directory at runtime (gitignored). The complete schema and validation rules are documented in the SKILL.md files. Key points:

- `.design/plan.json` is the authoritative state; the TaskList is a derived view
- Schema version 3 is required
- Tasks use dependency-only scheduling — no wave field in task schema, execute computes batches dynamically from `blockedBy`
- Each task includes assembled worker prompts (`prompt` field) and file overlap analysis (`fileOverlaps` field) — design produces these during plan generation
- Progressive trimming: completed tasks are stripped of verbose agent fields (including `prompt`) to reduce plan size as execution proceeds
- Analysis artifacts (goal-analysis.json, expert-\*.json, critic.json) are preserved after plan generation for execute workers to reference via contextFiles
- Plan history: completed plans are archived to `.design/history/{timestamp}-plan.json` on successful execution; design pre-flight preserves this subdirectory during cleanup

### Execution Model

Both skills use a **launcher → dedicated team lead → teammates** architecture:

- **Launcher** (main conversation): pre-flight, `TeamCreate`, spawns a dedicated team lead via `Task(team_name, name: "lead")`, displays summary, `TeamDelete`. Tool-restricted: `TeamCreate`, `TeamDelete`, `Task`, `AskUserQuestion`, `Bash` (PLAN_CLI only).
- **Team lead** (named teammate "lead"): orchestrates all agents/workers within the team. Spawns teammates, manages lifecycle via `SendMessage`/`TaskCreate`/`TaskUpdate`/`TaskList`, performs verification, updates plan state.

`/do:design` — adaptive complexity scaling with a dedicated team lead (`do-design` team):

- **Team lead** spawns and coordinates all agents. Never analyzes the goal or reads source files — purely a lifecycle manager. Reads only `.design/goal-analysis.json` (for `complexity` and `recommendedTeam`).
- **Dynamically growing team**: The team starts with a single goal analyst, then grows based on goal complexity. One team (`do-design`), dynamic membership. Teammates signal completion via `SendMessage(recipient: "lead")`.
- **Goal analyst**: First teammate spawned. Uses `sequential-thinking` MCP (if available) + codebase exploration to deeply understand the goal, propose 2–3 high-level approaches with tradeoffs, assess complexity, and recommend expert team composition. Experts are typed as `architect` (codebase analysis — structure, patterns, what needs to change) or `researcher` (external research — community patterns, libraries, best practices). Writes `.design/goal-analysis.json` including `complexity`, `complexityRationale`, `codebaseContext`, `approaches`, and `recommendedTeam`.
- **Complexity tiers** (analyst's `complexity` field determines pipeline):
  - **Minimal** (1-3 tasks, single obvious approach): skip expert/critic/plan-writer teammates. Team lead spawns single lightweight plan-writer Task subagent (model: sonnet) reading only `goal-analysis.json`. Quality gate warns if plan exceeds 3 tasks or depth 2.
  - **Standard** (4-8 tasks, some design decisions): spawn experts + plan-writer (skip critic). Plan-writer blockedBy experts directly.
  - **Full** (9+ tasks, multiple approaches, cross-cutting concerns): spawn experts + critic + plan-writer. Critic blockedBy experts, plan-writer blockedBy critic.
- **Expert agents** (standard/full only): Two types. **Architects** analyze the codebase through a domain lens — structure, patterns, what needs to change. **Researchers** search externally via WebSearch/WebFetch — community patterns, libraries, idiomatic solutions, best practices. Each writes `.design/expert-{name}.json`.
- **Critic** (full only): blockedBy all experts. Stress-tests proposals: challenges assumptions, evaluates approach coherence, identifies missing risks, flags over/under-engineering, checks goal alignment. Writes `.design/critic.json` with challenges and a verdict.
- **Plan-writer** (standard/full only): teammate blockedBy critic (full) or experts (standard). Merges expert analyses, incorporates critique (full only), validates, enriches. Assembles worker prompts (S1-S9 template) and computes file overlap matrix. Records approach decisions in `progress.decisions`. Writes `.design/plan.json` with fully assembled prompts.
- **Two-tier fallback** (standard/full only): If the team fails to produce `.design/plan.json` (1) retry with a single plan-writer Task subagent, or (2) perform merge and plan writing inline with context minimization (process expert files one at a time)

`/do:execute` — dependency-graph scheduling with a dedicated team lead (`do-execute` team):

- **Team lead** handles: TaskList creation, worker spawning, result collection, verification (batched spot-checks + acceptance criteria), plan updates (status, trimming, cascading failures via `update-status` script), git commits, circuit breaker evaluation, ready-set computation, retry assembly
- **Worker teammates** (name: `worker-{planIndex}`): one per task in each ready-set batch, receive pre-extracted task files (`.design/worker-task-{N}.json`) via `extract-task` script, report results via `SendMessage(recipient: "lead")` with JSON payload (`planIndex`, `status`, `result`). Workers are shut down after each round.
- **Dependency-graph scheduling**: orchestration uses ready-set loop (spawn all tasks whose `blockedBy` dependencies are completed), no pre-computed waves
- Progressive trimming: completed tasks are stripped of verbose agent fields including `prompt` (keep only subject, status, result, metadata.files, blockedBy, agent.role, agent.model)
- Retry budget: max 3 attempts per task with failure context passed to retries
- Cascading failures: failed/blocked tasks automatically skip dependents
- Circuit breaker: abort if >50% of remaining tasks would be skipped (plans with ≤3 tasks bypass this check)
- Resume support: status-scan based (reset `in_progress` tasks to `pending` with artifact cleanup), no wave tracking needed; successful completions archive plan to `.design/history/`

## Requirements

- Claude Code 2.1.32+ with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`
- python3 3.8+ (for helper scripts)
- `sequential-thinking` MCP server — used by the goal analyst for deep goal reasoning (fallback to inline reasoning if unavailable)

## Commit Conventions

Conventional commits with imperative mood: `feat:`, `fix:`, `chore:`, `refactor:`, `docs:`, `test:`. Example: `feat: add retry context to agent prompt`.

## Pre-commit Checklist

Before every commit and push:

1. **Update docs**: If SKILL.md changes affect architecture, update `CLAUDE.md` (Architecture section) and `README.md` to match. These three must stay in sync.
2. **Bump version**: Increment the patch version in `.claude-plugin/plugin.json` (and the version badge in `README.md`) for every functional change. Use semver: patch for fixes/refactors, minor for new features, major for breaking changes.
