# do - Claude Code Plugin

> Structured planning and dependency-graph execution for Claude Code

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-1.0.0-green.svg)
![Claude Code](https://img.shields.io/badge/Claude%20Code-2.1.32%2B-orange.svg)

## What It Does

The `do` plugin adds two powerful skills to Claude Code:

- **/do:design** — Uses Claude Code Agent Teams to spawn a dynamic planning team (2-5 specialists tailored to your goal) that analyzes the problem from multiple angles, then synthesizes their findings into a structured `.design/plan.json` with enriched agent specifications, safety checks, and dependency-graph execution strategy
- **/do:execute** — Reads `.design/plan.json`, creates a task list for progress tracking, spawns Task subagents in dependency-based batches, and coordinates parallel execution with retry budgets, circuit breakers, and git checkpoints

Plans are self-contained execution blueprints that include task dependencies, agent role specialization, assumption verification, acceptance criteria, and rollback triggers.

## Features

- **Dynamic Multi-Agent Planning** — A situation-tailored team of 2-5 specialist agents collaborates to decompose goals, catching blind spots that single-agent planning misses
- **Context-Efficient Delegation** — Mechanical work (plan reading, result parsing, state updates) is delegated to subagents, keeping the lead's context focused on orchestration
- **Native Task Management** — Uses Claude Code's built-in task system (TaskCreate, TaskUpdate, TaskList) for structured tracking with automatic dependency resolution
- **Claude Code Agent Teams** — Planning uses Agent Teams (TeamCreate, SendMessage, TaskList) for specialist collaboration; execution uses Task subagents for isolated parallel work
- **Agent Specialization** — Each task specifies role, expertise, model choice (opus/sonnet/haiku), approach, and context files
- **Safety First** — Automatic assumption verification, acceptance criteria, and rollback triggers for every task
- **Dependency-Based Parallelism** — Tasks in the same batch execute concurrently unless they share files
- **Retry Budget** — Each task gets 3 attempts with failure context passed to retries
- **Cascading Failure Handling** — Failed/blocked tasks automatically skip dependent tasks
- **Circuit Breaker** — Execution aborts if >50% of remaining tasks would be skipped
- **Progressive Plan Trimming** — Completed tasks are stripped of verbose fields to reduce plan size as execution proceeds
- **Git Checkpoints** — Each completed batch gets a commit for rollback capability
- **Resume Support** — Partially completed plans can be resumed from the last batch

## Installation

### Via Marketplace (Recommended)

```bash
/plugin marketplace add morphiax/claude-do
/plugin install do@do
```

### Manual Installation

```bash
git clone https://github.com/morphiax/claude-do.git
claude --plugin-dir ./claude-do
```

## Usage

### 1. Create a Plan

```bash
/do:design implement user authentication with JWT tokens
```

This spawns a planning team that analyzes your codebase from multiple angles, validates the goal, decomposes it into tasks, and writes `.design/plan.json`.

### 2. Execute the Plan

```bash
/do:execute
```

This reads `.design/plan.json`, creates a task list for progress tracking, and spawns Task subagents in dependency-based batches. Subagents return results; the lead verifies acceptance criteria, handles retries (max 3), and commits per batch. Cascading failures and circuit breakers prevent runaway execution.

### Example Flow

```bash
# Plan a feature
/do:design add a REST API endpoint for user profiles

# Review the plan (optional)
cat .design/plan.json

# Execute
/do:execute

# If interrupted, resume later
/do:execute
```

## Requirements

- **Claude Code** 2.1.32 or later
- **sequential-thinking MCP server** — recommended for /do:design (has fallback to inline reasoning)

## How It Works

1. **/do:design** uses a unified team pipeline (6 steps):
   - Context scan delegated to a subagent that writes `.design/context.json`
   - Lead performs lightweight domain-to-role mapping (2-5 specialists)
   - A single Claude Code Agent Team contains experts + synthesizer + plan-writer, pipeline-ordered via TaskList dependencies
   - Experts self-read mandates from `.design/team-briefing.json` (bootstrap prompt pattern)
   - Plan-writer sends result JSON to lead via SendMessage upon completion
   - Two-tier fallback: retry with sequential subagents, then inline with context minimization

2. **/do:execute** uses a thin-lead delegation architecture:
   - Setup Subagent reads `.design/plan.json`, creates TaskList, computes file overlaps, assembles worker prompts (`.design/tasks.json`)
   - Workers self-read full instructions via bootstrap template, return COMPLETED/FAILED/BLOCKED
   - Batch Processor reads worker logs, spot-checks files, runs acceptance criteria, writes results to `.design/processor-batch-{N}.json`
   - Plan Updater reads processor output from file, applies results to `.design/plan.json`, performs progressive trimming
   - Lead only handles: worker spawning, git commits, circuit breaker, user interaction
   - All subagents have scoped minimal-mode fallbacks if they fail

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute to this plugin.

## License

MIT License - Copyright 2026 morphiax
