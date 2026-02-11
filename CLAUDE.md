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
- `scripts/plan.py` — Shared helper script (17 commands: 12 query, 2 mutation, 3 build including `worker-pool`)
- `skills/design/SKILL.md` — `/do:design` skill definition
- `skills/design/scripts/plan.py` — Symlink → `../../../scripts/plan.py`
- `skills/execute/SKILL.md` — `/do:execute` skill definition
- `skills/execute/scripts/plan.py` — Symlink → `../../../scripts/plan.py`

### Skill Files Are the Implementation

The SKILL.md files are imperative prompts that Claude interprets at runtime. Deterministic operations (validation, dependency computation, plan manipulation) are delegated to per-skill python3 helper scripts. Each skill resolves its local `scripts/plan.py` path at runtime and invokes subcommands via `python3 $PLAN_CLI <command> [args]`. All script output follows JSON convention (`{ok: true/false, ...}`).

Each SKILL.md has YAML frontmatter (`name`, `description`, `argument-hint`) that must be preserved.

### Scripts

A single `scripts/plan.py` at the repo root provides all deterministic operations. Each skill symlinks to it from `skills/{name}/scripts/plan.py` so SKILL.md can resolve a skill-local path.

- **Query** (12 commands): validate, status-counts, summary, overlap-matrix, tasklist-data, worker-pool, extract-fields, model-distribution, retry-candidates, collect-files, circuit-breaker, extract-task
- **Mutation** (2 commands): resume-reset, update-status — atomically modify plan.json via temp file + rename
- **Build** (3 commands): validate-structure, assemble-prompts, compute-overlaps — used by the plan-writer for deterministic finalization

Design uses a subset (query + build). Execute uses all commands. `worker-pool` computes optimal worker count and role-based naming from the dependency graph. `extract-task` writes per-worker `.design/worker-task-{N}.json` files to reduce context window usage.

Scripts use python3 stdlib only (no dependencies), support Python 3.8+, and follow a consistent CLI pattern: `python3 plan.py <command> [plan_path] [options]`. All output is JSON to stdout with exit code 0 for success, 1 for errors.

### Data Contract: .design/plan.json

The two skills communicate through `.design/plan.json` (schemaVersion 3) written to the `.design/` directory at runtime (gitignored). The complete schema and validation rules are documented in the SKILL.md files. Key points:

- `.design/plan.json` is the authoritative state; the TaskList is a derived view
- Schema version 3 is required
- Tasks use dependency-only scheduling — no wave field in task schema, workers self-organize by claiming unblocked tasks from the TaskList based on `blockedBy` dependencies
- Each task includes a concise assembled worker brief (`prompt` field) and file overlap analysis (`fileOverlaps` field) — design produces these during plan generation via scripts
- Progressive trimming: completed tasks are stripped of verbose agent fields (including `prompt`) to reduce plan size as execution proceeds
- Analysis artifacts (goal-analysis.json, expert-\*.json, critic.json) are preserved after plan generation for execute workers to reference via contextFiles
- Plan history: completed plans are archived to `.design/history/{timestamp}-plan.json` on successful execution; design pre-flight preserves this subdirectory during cleanup

### Execution Model

Both skills use the **main conversation as team lead** with Agent Teams for coordination:

- **Lead** (main conversation): creates team via `TeamCreate`, spawns teammates, manages lifecycle via `SendMessage`/`TaskCreate`/`TaskUpdate`/`TaskList`, performs verification, updates plan state. Tool-restricted to orchestration — never reads project source files.
- **Teammates**: specialist agents (analysts, experts, workers) spawned into the team. Signal completion via `SendMessage` to the lead. Read `~/.claude/teams/{team-name}/config.json` to discover the lead's name.

`/do:design` — organic, research-driven team builder (`do-design` team):

- **Lead responsibilities** (never delegated): pre-flight, team lifecycle, reading analyst's recommendations, spawning agents based on analyst's findings, lightweight verification, summary output. The lead NEVER analyzes the goal or reads source files.
- **Adaptive team growth**: The team starts with a single goal analyst, then grows organically based on what the analyst discovers. The analyst recommends expert composition — could be 1 agent or 5, all architects or all researchers, depending on the goal. No rigid tiers or forced pipeline.
- **Research-first analyst**: First teammate spawned. Does deep multi-hop research — web search for academic approaches, existing libraries with URLs and versions, community patterns, prior art. Uses `sequential-thinking` MCP (if available) + codebase exploration. Quality bar: specific algorithms with names, specific libraries with applicability assessments, practical tradeoffs. Writes `.design/goal-analysis.json`.
- **Mandate-based experts**: Two types. **Architects** analyze the codebase through a domain lens. **Researchers** do deep external research via WebSearch/WebFetch. Each receives a one-line mandate (not a procedure list) and writes `.design/expert-{name}.json`.
- **Plan-writer**: Merges expert analyses, deduplicates, ensures MECE coverage, records decisions. Runs script-assisted finalization (validate-structure, assemble-prompts, compute-overlaps) and writes `.design/plan.json`. For trivial goals (analyst recommends no experts), a single plan-writer Task subagent handles it directly.
- **Natural communication**: All agents report findings in natural language via SendMessage. No rigid JSON protocols or signal codes.
- **Two-tier fallback**: If the team fails to produce `.design/plan.json` (1) retry with a single plan-writer Task subagent, or (2) merge inline with context minimization

`/do:execute` — persistent self-organizing workers with event-driven lead (`do-execute` team):

- **Lead responsibilities**: plan reading/validation/TaskList creation (inline — purely mechanical, no subagent), spawn persistent worker teammates once, monitor execution via event-driven messaging, update `.design/plan.json` (status, trimming, cascading failures via `update-status` script), wake idle workers when new tasks unblock, final batched verification after all tasks complete, user interaction (`AskUserQuestion`), circuit breaker evaluation, retry coordination. Natural communication — the lead interprets worker messages in plain language.
- **Worker teammates** (named by `agent.role`, e.g. `api-developer`, `test-writer`): persistent workers spawned once via `worker-pool` command. Workers self-organize: check TaskList for pending unblocked tasks, claim one, read pre-extracted task file (`.design/worker-task-{N}.json`), execute, commit their own changes (`git add` + `git commit`), mark complete, report to lead naturally, then claim the next available task. Workers go idle when no tasks are available and are woken by the lead when new tasks unblock.
- **Peer communication**: workers message each other directly when they find issues with prior work (e.g., a bug in code committed by another worker). The affected worker fixes the issue and confirms. Lead is CC'd but does not intervene unless escalated.
- **File ownership via dependencies**: the lead augments TaskList dependencies at setup using the overlap matrix — concurrent tasks touching the same files get runtime `blockedBy` constraints so they serialize naturally. No explicit file ownership assignment needed.
- **Deferred verification**: workers verify their own acceptance criteria during execution. The lead runs a single batched final verification (spot-checks + acceptance criteria) after all tasks complete, instead of per-round checks.
- Progressive trimming: completed tasks are stripped of verbose agent fields including `prompt` (keep only subject, status, result, metadata.files, blockedBy, agent.role, agent.model)
- Retry budget: max 3 attempts per task with failure context passed to retries
- Cascading failures: failed/blocked tasks automatically skip dependents
- Circuit breaker: abort if >50% of remaining tasks would be skipped (plans with ≤3 tasks bypass this check)
- Resume support: status-scan based (reset `in_progress` tasks to `pending` with artifact cleanup); successful completions archive plan to `.design/history/`

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
