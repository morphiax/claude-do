# do - Claude Code Plugin

> Team-based planning and production-grade execution for Claude Code

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-1.5.0-green.svg)
![Claude Code](https://img.shields.io/badge/Claude%20Code-2.1.32%2B-orange.svg)

## Why do?

Most planning plugins use a single agent to decompose goals. `do` is different:

- **A team plans your work, not one agent.** `/do:design` spawns a goal analyst, domain architects, external researchers, and a critic that stress-tests the plan before it ships. Adaptive complexity scaling (minimal/standard/full tiers) matches team size to goal difficulty.
- **Plans are execution blueprints, not task lists.** Every task includes assumptions with shell-verified pre-flight checks, acceptance criteria with automated validation, rollback triggers, context files, and agent specialization (role, model, approach).
- **Execution has safety rails.** `/do:execute` spawns persistent, self-organizing workers that claim tasks from the dependency graph, commit their own changes, and communicate with each other when issues arise. Safety rails include retry budgets (3 attempts with failure context), cascading failure propagation, a circuit breaker (abort at >50% skip rate), progressive plan trimming, and deferred final verification.
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

A thin-lead orchestrator spawns a dynamically growing team of specialist agents. The lead never analyzes — all analytical work happens inside agents.

1. **Pre-flight** — Checks for existing plans, cleans stale artifacts, preserves `.design/history/`
2. **Goal Analyst** — First teammate spawned. Uses `sequential-thinking` MCP to deeply understand the goal, explore the codebase, propose 2-3 approaches with tradeoffs, and assess complexity. Writes `.design/goal-analysis.json` with a recommended expert team composition
3. **Complexity branching** — The analyst's `complexity` rating determines the pipeline:
   - **Minimal** (1-3 tasks): single lightweight plan-writer, no experts or critic
   - **Standard** (4-8 tasks): experts + plan-writer, no critic
   - **Full** (9+ tasks): experts + critic + plan-writer — the critic challenges assumptions, evaluates coherence, and flags over/under-engineering before the plan-writer synthesizes
4. **Cleanup & Summary** — Verifies `plan.json` schema, tears down the team, reports task count and dependency depth

Experts come in two types: **architects** (analyze the codebase — structure, patterns, what needs to change) and **researchers** (search externally via WebSearch/WebFetch — community patterns, libraries, idiomatic solutions, best practices). Each writes `.design/expert-{name}.json`. The critic writes `.design/critic.json`. All teammates signal completion via `SendMessage` to the lead. Two-tier fallback ensures plan generation even if the team fails.

### /do:execute — Persistent self-organizing workers

An event-driven lead with persistent worker teammates:

- **Setup** — The lead validates the plan, creates a TaskList with dependency and file-overlap constraints, pre-extracts all task files, and computes the worker pool via the `worker-pool` script (role-based naming, optimal concurrency).
- **Workers** — Persistent teammates named by their `agent.role` (e.g., `api-developer`, `test-writer`). Workers self-organize: check TaskList for pending unblocked tasks, claim one, execute it from pre-extracted task files (`.design/worker-task-{N}.json`), commit their own changes, and claim the next available task. Workers communicate directly with each other when they find issues with prior work.
- **Deferred verification** — Workers verify their own acceptance criteria during execution. The lead runs a single batched final verification after all tasks complete instead of per-round checks.

The lead monitors execution via an event-driven message loop, handles cascading failures, wakes idle workers when new tasks unblock, manages retries, and evaluates the circuit breaker. Completed plans archive to `.design/history/`.

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
