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

- **Query** (7 commands): status, summary, overlap-matrix, tasklist-data, worker-pool, retry-candidates, circuit-breaker
- **Mutation** (2 commands): resume-reset, update-status — atomically modify plan.json via temp file + rename
- **Build** (1 command): finalize — validates structure, assembles prompts, computes overlaps in one atomic operation

Design uses query + finalize. Execute uses all commands. `worker-pool` computes optimal worker count and role-based naming from the dependency graph. Workers read `plan.json` directly — no per-worker task files needed.

Scripts use python3 stdlib only (no dependencies), support Python 3.8+, and follow a consistent CLI pattern: `python3 plan.py <command> [plan_path] [options]`. All output is JSON to stdout with exit code 0 for success, 1 for errors.

### Data Contract: .design/plan.json

The two skills communicate through `.design/plan.json` (schemaVersion 3) written to the `.design/` directory at runtime (gitignored). The complete schema and validation rules are documented in the SKILL.md files. Key points:

- `.design/plan.json` is the authoritative state; the TaskList is a derived view
- Schema version 3 is required
- Tasks use dependency-only scheduling — no wave field in task schema, workers self-organize by claiming unblocked tasks from the TaskList based on `blockedBy` dependencies
- Each task includes a concise assembled worker brief (`prompt` field) and file overlap analysis (`fileOverlaps` field) — design produces these during plan generation via scripts
- Progressive trimming: completed tasks are stripped of verbose agent fields (including `prompt`) to reduce plan size as execution proceeds
- Expert artifacts (`expert-*.json`) are optional and preserved after plan generation for execute workers to reference via contextFiles
- Plan history: completed runs are archived to `.design/history/{timestamp}/` as a folder containing plan.json, expert files, and handoff.md together; design pre-flight archives (not deletes) stale artifacts to avoid triggering destructive-command hooks

### Execution Model

Both skills use the **main conversation as team lead** with Agent Teams for coordination:

- **Lead** (main conversation): creates team via `TeamCreate`, spawns teammates, manages lifecycle via `SendMessage`/`TaskCreate`/`TaskUpdate`/`TaskList`, performs verification, updates plan state. Tool-restricted to orchestration — never reads project source files.
- **Teammates**: specialist agents (analysts, experts, workers) spawned into the team. Signal completion via `SendMessage` to the lead. Read `~/.claude/teams/{team-name}/config.json` to discover the lead's name.

`/do:design` — lead-determined dynamic team (`do-design` team):

- **Lead responsibilities** (never delegated): pre-flight, quick goal research (WebSearch/codebase scan), determine which expert perspectives are needed, spawn experts, collect findings, synthesize plan directly, adversarial review, run `finalize` script, summary output.
- **Dynamic expert team**: The lead reads the goal, does brief research, then determines team composition. Expert types include: **architect** (codebase structure, patterns), **researcher** (external libraries, best practices), **domain-specialist** (security, performance, i18n, etc.). Team size varies by goal complexity — simple goals may need only an architect; complex goals may need multiple perspectives.
- **Expert prompts**: Each expert receives goal + focus area (e.g., "codebase architecture", "external research"). Experts analyze and recommend tasks with full agent specs. May write `.design/expert-{name}.json` or report directly to lead.
- **Plan synthesis**: The lead merges expert findings directly (no plan-writer delegate — the lead has full context from every expert). Before finalizing, the lead performs an adversarial review: challenging assumptions, identifying missing/unnecessary tasks, checking dependency ordering, and flagging integration risks. Then runs `python3 $PLAN_CLI finalize .design/plan.json` to validate structure, assemble prompts, and compute overlaps.
- **Fallback**: If finalize fails, fix validation errors and re-run. If structure is fundamentally broken, rebuild from expert findings inline.

`/do:execute` — persistent self-organizing workers with event-driven lead (`do-execute` team):

- **Lead responsibilities**: plan reading/validation/TaskList creation (inline — purely mechanical, no subagent), spawn persistent worker teammates once, monitor execution via event-driven messaging, update `.design/plan.json` (status, trimming, cascading failures via `update-status` script), wake idle workers when new tasks unblock, final batched verification after all tasks complete, user interaction (`AskUserQuestion`), circuit breaker evaluation, retry coordination. Natural communication — the lead interprets worker messages in plain language.
- **Worker teammates** (named by `agent.role`, e.g. `api-developer`, `test-writer`): persistent workers spawned once via `worker-pool` command. Workers self-organize: check TaskList for pending unblocked tasks, claim one, read `.design/plan.json tasks[planIndex].prompt` directly, execute, commit their own changes (`git add` + `git commit`), mark complete, report to lead naturally, then claim the next available task. Workers go idle when no tasks are available and are woken by the lead when new tasks unblock.
- **Peer communication**: workers message each other directly when they find issues with prior work (e.g., a bug in code committed by another worker). The affected worker fixes the issue and confirms. Lead is CC'd but does not intervene unless escalated.
- **File ownership via dependencies**: the lead augments TaskList dependencies at setup using the overlap matrix — concurrent tasks touching the same files get runtime `blockedBy` constraints so they serialize naturally. No explicit file ownership assignment needed.
- **Deferred verification**: workers verify their own acceptance criteria during execution. The lead runs a single batched final verification (spot-checks + acceptance criteria) after all tasks complete, instead of per-round checks.
- **Goal review**: after individual verification, the lead evaluates whether the sum of completed tasks actually achieves the original goal — checking for completeness gaps, coherence across tasks, and alignment with user intent. Workers execute tasks mechanically; the lead holds the big picture and catches forest-vs-trees issues. Gaps spawn targeted fix workers.
- **Integration testing**: after goal review, an `integration-tester` worker runs the full test suite, checks for cross-task conflicts, and verifies independently-completed tasks connect correctly. Skipped for single-task or fully-independent plans.
- **Session handoff**: on completion, a structured `.design/handoff.md` summarizes what was done, what failed, integration status, key decisions, files changed, known gaps, and next steps — enabling context recovery across sessions.
- Progressive trimming: completed tasks are stripped of verbose agent fields including `prompt` (keep only subject, status, result, metadata.files, blockedBy, agent.role, agent.model)
- Retry budget: max 3 attempts per task with failure context passed to retries
- Cascading failures: failed/blocked tasks automatically skip dependents
- Circuit breaker: abort if >50% of remaining tasks would be skipped (plans with ≤3 tasks bypass this check)
- Resume support: status-scan based (reset `in_progress` tasks to `pending` with artifact cleanup); successful completions archive plan to `.design/history/`

## Requirements

- Claude Code 2.1.32+ with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`
- python3 3.8+ (for helper scripts)

## Commit Conventions

Conventional commits with imperative mood: `feat:`, `fix:`, `chore:`, `refactor:`, `docs:`, `test:`. Example: `feat: add retry context to agent prompt`.

## Pre-commit Checklist

Before every commit and push:

1. **Update docs**: If SKILL.md changes affect architecture, update `CLAUDE.md` (Architecture section) and `README.md` to match. These three must stay in sync.
2. **Bump version**: Increment the patch version in `.claude-plugin/plugin.json` (and the version badge in `README.md`) for every functional change. Use semver: patch for fixes/refactors, minor for new features, major for breaking changes.
