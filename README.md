# do - Claude Code Plugin

> Team-based planning and production-grade execution for Claude Code

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-1.8.0-green.svg)
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
4. **Synthesize & Challenge** — The lead merges expert findings and writes the plan directly (it has full context from every expert). Before finalizing, the lead performs an adversarial review: challenging assumptions, identifying missing tasks, removing over-engineering, and checking integration risks. The `finalize` script then validates structure, assembles prompts, and computes overlaps.

Expert types vary by goal: **architects** analyze codebase structure, **researchers** find external libraries and patterns, **domain specialists** handle security, performance, i18n, etc. For simple goals, the lead may handle it directly without spawning experts.

### /do:execute — Persistent self-organizing workers

An event-driven lead with persistent worker teammates:

- **Setup** — The lead validates the plan, creates a TaskList with dependency and file-overlap constraints, and computes the worker pool via the `worker-pool` script (role-based naming, optimal concurrency).
- **Workers** — Persistent teammates named by their `agent.role` (e.g., `api-developer`, `test-writer`). Workers self-organize: check TaskList for pending unblocked tasks, claim one, read the task prompt directly from `.design/plan.json`, commit their own changes, and claim the next available task. Workers communicate directly with each other when they find issues with prior work.
- **Deferred verification** — Workers verify their own acceptance criteria during execution. The lead runs a single batched final verification after all tasks complete instead of per-round checks.
- **Goal review** — After individual verification, the lead steps back from the tasks and evaluates whether the completed work actually achieves the original goal. Workers execute mechanically — they don't hold the big picture. The lead checks for completeness gaps (tasks done but goal not met), coherence (do the pieces fit together?), and user intent (is this what was asked for?). Gaps spawn targeted fix workers.
- **Integration testing** — After goal review, an `integration-tester` worker runs the full test suite, checks for cross-task conflicts, and verifies that independently-completed tasks connect correctly (e.g., API endpoints match client calls, components are registered in routes). Issues are routed back to workers for fixing.
- **Session handoff** — On completion, a structured `.design/handoff.md` summarizes what was done, what failed, integration status, key decisions, files changed, known gaps, and concrete next steps — so you can resume work hours or days later without losing context.

The lead monitors execution via an event-driven message loop, handles cascading failures, wakes idle workers when new tasks unblock, manages retries, and evaluates the circuit breaker. Completed runs archive all artifacts (plan, expert files, handoff) to `.design/history/{timestamp}/`.

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
