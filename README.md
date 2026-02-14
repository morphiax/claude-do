# do - Claude Code Plugin

> Team-based planning and production-grade execution for Claude Code

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-2.0.0-green.svg)
![Claude Code](https://img.shields.io/badge/Claude%20Code-2.1.32%2B-orange.svg)

## Why do?

Most planning plugins use a single agent to decompose goals. `do` is different:

- **Role briefs, not micro-tasks.** `/do:design` creates goal-directed role briefs with expert context, acceptance criteria, and constraints — workers decide HOW to implement by reading the actual codebase.
- **Auxiliary agents for quality.** Pre-execution challengers review the plan for gaps. Scouts verify expert assumptions against the real codebase. Post-execution integration verifiers catch cross-role issues.
- **Dynamic expert teams.** Design spawns experts based on the goal's nature — architects, researchers, domain specialists. The lead determines team composition, not a fixed pipeline.
- **Execution has safety rails.** `/do:execute` spawns persistent, self-organizing workers that claim roles from the dependency graph, commit their own changes, and communicate with each other. Safety rails include retry budgets, cascading failure propagation, and a circuit breaker.
- **Script-assisted orchestration.** A shared python3 helper script (10 commands) handles deterministic operations — validation, dependency computation, overlap analysis, and plan manipulation — reserving LLM usage for analytical and creative work.

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

### /do:design — Expert-informed role briefs

The lead reads the goal, assesses complexity, spawns the right experts, and synthesizes findings into role briefs.

1. **Pre-flight** — Checks for existing plans, archives stale artifacts to `.design/history/`
2. **Lead research** — Scans project metadata, assesses complexity tier (trivial → high-stakes), determines expert team
3. **Spawn experts** — Dynamic team: architects (system design), researchers (prior art), domain specialists (security, performance, etc.). For trivial goals, the lead writes the plan directly.
4. **Synthesize into role briefs** — The lead merges expert findings into goal-directed role briefs. Each brief defines WHAT and WHY — workers decide HOW. Expert artifacts are preserved as structured JSON for workers to reference directly.
5. **Auxiliary roles** — Based on complexity: challenger (pre-execution plan review), scout (codebase reality check), integration verifier (post-execution cross-role validation).

### /do:execute — Autonomous specialist workers

An event-driven lead with persistent worker teammates:

- **Pre-execution auxiliaries** — Challenger reviews the plan for gaps and risks. Scout reads the actual codebase to verify expert assumptions. Both report findings before workers spawn.
- **Workers** — One persistent specialist per role (e.g., `api-developer`, `test-writer`). Workers explore their scope directories, plan their own approach based on the real codebase, implement, test against acceptance criteria, commit, and report.
- **Goal review** — After all roles complete, the lead evaluates whether the work achieves the original goal: completeness, coherence, and user intent. Gaps spawn targeted fix workers.
- **Post-execution auxiliaries** — Integration verifier runs the full test suite, checks cross-role contracts, and validates end-to-end goal achievement.
- **Session handoff** — Structured `.design/handoff.md` for context recovery across sessions.

Safety rails: retry budgets (3 attempts), cascading failure propagation, circuit breaker (>50% skip rate), directory overlap serialization. Completed runs archive to `.design/history/{timestamp}/`.

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
