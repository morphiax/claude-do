# do - Claude Code Plugin

> Team-based planning and production-grade execution for Claude Code

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-1.4.0-green.svg)
![Claude Code](https://img.shields.io/badge/Claude%20Code-2.1.32%2B-orange.svg)

## Why do?

Most planning plugins use a single agent to decompose goals. `do` is different:

- **A team plans your work, not one agent.** `/do:design` spawns a goal analyst, domain architects, external researchers, and a critic that stress-tests the plan before it ships. Adaptive complexity scaling (minimal/standard/full tiers) matches team size to goal difficulty.
- **Plans are execution blueprints, not task lists.** Every task includes assumptions with shell-verified pre-flight checks, acceptance criteria with automated validation, rollback triggers, context files, and agent specialization (role, model, approach).
- **Execution has safety rails.** `/do:execute` runs dependency-graph scheduling with retry budgets (3 attempts with failure context), cascading failure propagation, a circuit breaker (abort at >50% skip rate), progressive plan trimming, and git checkpoints per batch.
- **Script-assisted orchestration.** Both skills use per-skill python3 helper scripts (`skills/{name}/scripts/plan.py`) for deterministic operations like validation, dependency computation, and plan manipulation, reserving LLM usage for analytical and creative work.

## Quick Start

```bash
# Install
/plugin marketplace add morphiax/claude-do
/plugin install do@do

# Plan
/do:design implement user authentication with JWT tokens

# Review (optional)
cat .design/plan.json

# Execute
/do:execute

# Resume if interrupted
/do:execute
```

## How It Works

### /do:design — 4-step team pipeline

A dedicated team lead coordinates a dynamically growing team of specialist agents. The launcher spawns the lead, who orchestrates all analytical work — the launcher never analyzes.

1. **Pre-flight** — Checks for existing plans, cleans stale artifacts, preserves `.design/history/`
2. **Goal Analyst** — First teammate spawned by the team lead. Uses `sequential-thinking` MCP to deeply understand the goal, explore the codebase, propose 2-3 approaches with tradeoffs, and assess complexity. Writes `.design/goal-analysis.json` with a recommended expert team composition
3. **Complexity branching** — The analyst's `complexity` rating determines the pipeline:
   - **Minimal** (1-3 tasks): single lightweight plan-writer, no experts or critic
   - **Standard** (4-8 tasks): experts + plan-writer, no critic
   - **Full** (9+ tasks): experts + critic + plan-writer — the critic challenges assumptions, evaluates coherence, and flags over/under-engineering before the plan-writer synthesizes
4. **Cleanup & Summary** — Verifies `plan.json` schema, tears down the team, reports task count and dependency depth

Experts come in two types: **architects** (analyze the codebase — structure, patterns, what needs to change) and **researchers** (search externally via WebSearch/WebFetch — community patterns, libraries, idiomatic solutions, best practices). Each writes `.design/expert-{name}.json`. The critic writes `.design/critic.json`. All teammates signal completion via `SendMessage(recipient: "lead")`. Two-tier fallback ensures plan generation even if the team fails.

### /do:execute — Dependency-graph scheduling

A dedicated team lead executes using dependency-graph scheduling with worker teammates:

- **Inline setup** — The team lead uses helper scripts for deterministic operations: validation (`validate`), resume detection (`status-counts`), file overlap extraction (`overlap-matrix`), and task list data prep (`tasklist-data`). The team lead still makes TaskCreate calls but reads pre-computed data instead of parsing plan.json manually.
- **Workers** — One worker teammate (`worker-{planIndex}`) per ready task. Workers receive pre-extracted task files (`.design/worker-task-{N}.json`) via the `extract-task` prefilter script (10-20x context reduction vs reading full plan.json). Workers report results via `SendMessage(recipient: "lead")` with JSON payloads and are shut down after each round.
- **Inline verification** — The team lead verifies results via batched Bash scripts per round (spot-checks + acceptance criteria), then uses the `update-status` script for atomic plan.json updates (status changes, progressive trimming, cascading failures).

The team lead handles: worker spawning, result verification, plan updates (via scripts), retry assembly, git commits per round, and circuit breaker evaluation. Ready-sets are computed via the `ready-set` script from `blockedBy` dependencies — no pre-computed waves. Completed plans archive to `.design/history/`.

## Installation

### Via Marketplace (Recommended)

```bash
/plugin marketplace add morphiax/claude-do
/plugin install do@do
```

### Manual

```bash
git clone https://github.com/morphiax/claude-do.git
claude --plugin-dir ./claude-do
```

## Requirements

- **Claude Code** 2.1.32 or later
- **python3** 3.8 or later (for helper scripts)
- **sequential-thinking MCP server** — recommended for /do:design (falls back to inline reasoning)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - Copyright 2026 morphiax
