# do - Claude Code Plugin

> Structured planning and wave-based execution for Claude Code

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-1.0.0-green.svg)
![Claude Code](https://img.shields.io/badge/Claude%20Code-1.0.33%2B-orange.svg)

## What It Does

The `do` plugin adds two powerful skills to Claude Code:

- **/do:design** — Spawns a dynamic planning team (2-5 specialists tailored to your goal) that analyzes the problem from multiple angles, then synthesizes their findings into a structured `.plan.json` with enriched agent specifications, safety checks, and wave-based execution strategy
- **/do:execute** — Reads `.plan.json`, creates a task list for progress tracking, spawns Task subagents wave-by-wave, and coordinates parallel execution with retry budgets, circuit breakers, and git checkpoints

Plans are self-contained execution blueprints that include task dependencies, agent role specialization, assumption verification, acceptance criteria, and rollback triggers.

## Features

- **Dynamic Multi-Agent Planning** — A situation-tailored team of 2-5 specialist agents collaborates to decompose goals, catching blind spots that single-agent planning misses
- **Context-Efficient Delegation** — Mechanical work (plan reading, result parsing, state updates) is delegated to subagents, keeping the lead's context focused on orchestration
- **Native Task Management** — Uses Claude Code's built-in task system (TaskCreate, TaskUpdate, TaskList) for structured tracking with automatic dependency resolution
- **Agent Teams** — Planning uses Claude Code's agent teams for specialist collaboration; execution uses Task subagents for isolated parallel work
- **Agent Specialization** — Each task specifies role, expertise, model choice (opus/sonnet/haiku), approach, and context files
- **Safety First** — Automatic assumption verification, acceptance criteria, and rollback triggers for every task
- **Wave-Based Parallelism** — Tasks in the same wave execute concurrently unless they share files
- **Retry Budget** — Each task gets 3 attempts with failure context passed to retries
- **Cascading Failure Handling** — Failed/blocked tasks automatically skip dependent tasks
- **Circuit Breaker** — Execution aborts if >50% of remaining tasks would be skipped
- **Progressive Plan Trimming** — Completed tasks are stripped of verbose fields to reduce plan size as execution proceeds
- **Git Checkpoints** — Each completed wave gets a commit for rollback capability
- **Resume Support** — Partially completed plans can be resumed from the last wave

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

This spawns a planning team that analyzes your codebase from multiple angles, validates the goal, decomposes it into tasks, and writes `.plan.json`.

### 2. Execute the Plan

```bash
/do:execute
```

This reads `.plan.json`, creates a task list for progress tracking, and spawns Task subagents wave-by-wave. Subagents return results; the lead verifies acceptance criteria, handles retries (max 3), and commits per wave. Cascading failures and circuit breakers prevent runaway execution.

### Example Flow

```bash
# Plan a feature
/do:design add a REST API endpoint for user profiles

# Review the plan (optional)
cat .plan.json

# Execute
/do:execute

# If interrupted, resume later
/do:execute
```

## Requirements

- **Claude Code** 1.0.33 or later
- **Agent Teams** enabled (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in settings) — required for /do:design
- **sequential-thinking MCP server** — recommended for /do:design (has fallback to inline reasoning)

## How It Works

1. **/do:design** uses a delegation architecture for context-efficient planning:
   - Context scan is delegated to an Explore subagent to keep codebase exploration out of the lead's context
   - Lead uses sequential-thinking to determine specialist roles needed (2-5 agents)
   - Planning team agents analyze the entire goal in parallel through their domain lens
   - Lead synthesizes all findings using sequential-thinking
   - Plan Writer subagent handles validation, safety generation, and `.plan.json` writing
   - Lead only handles user-facing interactions (overwrite confirmation)

2. **/do:execute** uses a thin-lead delegation architecture:
   - Setup Subagent reads `.plan.json`, creates TaskList, computes file overlaps, assembles worker prompts
   - Lead spawns one Task subagent per task in each wave (workers return COMPLETED/FAILED/BLOCKED)
   - Wave Processor Subagent parses results, spot-checks files, runs acceptance criteria, determines retries
   - Lead commits completed wave files with a single wave summary commit
   - Plan Updater Subagent applies results to `.plan.json`, computes cascading failures, performs progressive trimming
   - Circuit breaker aborts if >50% of remaining tasks would be skipped
   - All delegation subagents have fallback to inline execution if they fail

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute to this plugin.

## License

MIT License - Copyright 2026 morphiax
