# do - Claude Code Plugin

> Team-based planning and production-grade execution for Claude Code

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-1.1.0-green.svg)
![Claude Code](https://img.shields.io/badge/Claude%20Code-2.1.32%2B-orange.svg)

## Why do?

Most planning plugins use a single agent to decompose goals. `do` is different:

- **A team plans your work, not one agent.** `/do:design` spawns a goal analyst, domain scanners, approach architects, and a critic that stress-tests the plan before it ships. Adaptive complexity scaling (minimal/standard/full tiers) matches team size to goal difficulty.
- **Plans are execution blueprints, not task lists.** Every task includes assumptions with shell-verified pre-flight checks, acceptance criteria with automated validation, rollback triggers, context files, and agent specialization (role, model, approach).
- **Execution has safety rails.** `/do:execute` runs dependency-graph scheduling with retry budgets (3 attempts with failure context), cascading failure propagation, a circuit breaker (abort at >50% skip rate), progressive plan trimming, and git checkpoints per batch.

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

A thin-lead orchestrator spawns a dynamically growing team. The lead never analyzes — all analytical work happens inside agents.

1. **Pre-flight** — Checks for existing plans, cleans stale artifacts, preserves `.design/history/`
2. **Goal Analyst** — First teammate spawned. Uses `sequential-thinking` MCP to deeply understand the goal, explore the codebase, propose 2-3 approaches with tradeoffs, and assess complexity. Writes `.design/goal-analysis.json` with a recommended expert team composition
3. **Complexity branching** — The analyst's `complexity` rating determines the pipeline:
   - **Minimal** (1-3 tasks): single lightweight plan-writer, no experts or critic
   - **Standard** (4-8 tasks): experts + plan-writer, no critic
   - **Full** (9+ tasks): experts + critic + plan-writer — the critic challenges assumptions, evaluates coherence, and flags over/under-engineering before the plan-writer synthesizes
4. **Cleanup & Summary** — Verifies `plan.json` schema, tears down the team, reports task count and dependency depth

Experts come in two types: **scanners** (analyze _what_ needs to happen from a domain lens) and **architects** (design _how_ to solve sub-problems with 2-3 concrete strategies). Each writes `.design/expert-{name}.json`. The critic writes `.design/critic.json`. Two-tier fallback ensures plan generation even if the team fails.

### /do:execute — Dependency-graph scheduling

A thin-lead orchestrator delegates all mechanical work to subagents:

- **Setup Subagent** — Reads and validates `.design/plan.json`, creates the task list, computes file overlap matrix for parallel safety, assembles worker prompts into `.design/tasks.json`
- **Workers** — One Task subagent per ready task. Workers self-read full instructions from `.design/tasks.json` via a bootstrap prompt, return COMPLETED/FAILED/BLOCKED status lines, and write detailed logs to `.design/worker-{N}.log`
- **Batch Finalizer** — Parses worker results, spot-checks file artifacts, runs acceptance criteria, determines retries with failure context, updates `.design/plan.json`, performs progressive trimming on completed tasks, and computes cascading failures

The lead handles only: worker spawning, git commits per batch, circuit breaker evaluation, and user interaction. Ready-sets are computed dynamically from `blockedBy` dependencies — no pre-computed waves. Completed plans archive to `.design/history/`.

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
- **sequential-thinking MCP server** — recommended for /do:design (falls back to inline reasoning)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - Copyright 2026 morphiax
