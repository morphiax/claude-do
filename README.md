# do - Claude Code Plugin

> Team-based planning and production-grade execution for Claude Code

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-1.6.0-green.svg)
![Claude Code](https://img.shields.io/badge/Claude%20Code-2.1.32%2B-orange.svg)

## Why do?

Most planning plugins use a single agent to decompose goals. `do` is different:

- **Dynamic expert teams, not rigid tiers.** `/do:design` spawns experts based on the goal's nature — architects for codebase analysis, researchers for external libraries, domain specialists for security/performance/etc. The lead determines team composition, not a fixed pipeline.
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

### /do:design — Lead-determined dynamic team

The lead reads the goal, does quick research, then determines which expert perspectives are needed.

1. **Pre-flight** — Checks for existing plans, cleans stale artifacts, preserves `.design/history/`
2. **Lead research** — Quick WebSearch/codebase scan to understand goal context and determine which experts are needed
3. **Spawn experts** — Dynamic team based on goal nature: architects (codebase), researchers (external), domain specialists (security, performance, etc.)
4. **Collect & Finalize** — Merge expert findings, run `finalize` script for validation + prompt assembly + overlap computation, produce `.design/plan.json`

Expert types vary by goal: **architects** analyze codebase structure, **researchers** find external libraries and patterns, **domain specialists** handle security, performance, i18n, etc. For simple goals, the lead may handle it directly without spawning experts. Two-tier fallback ensures plan generation even if the team fails.

### /do:execute — Persistent self-organizing workers

An event-driven lead with persistent worker teammates:

- **Setup** — The lead validates the plan, creates a TaskList with dependency and file-overlap constraints, and computes the worker pool via the `worker-pool` script (role-based naming, optimal concurrency).
- **Workers** — Persistent teammates named by their `agent.role` (e.g., `api-developer`, `test-writer`). Workers self-organize: check TaskList for pending unblocked tasks, claim one, read the task prompt directly from `.design/plan.json`, commit their own changes, and claim the next available task. Workers communicate directly with each other when they find issues with prior work.
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

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - Copyright 2026 morphiax
