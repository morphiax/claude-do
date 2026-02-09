# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`claude-do` is a Claude Code plugin providing two skills: `/do:design` (team-based goal decomposition into `.design/plan.json`) and `/do:execute` (wave-based execution with task subagents). It leverages Claude Code's native Agent Teams and Tasks features for multi-agent collaboration. It is a documentation-only plugin — no source code, no build step, no dependencies.

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
- `skills/design/SKILL.md` — `/do:design` skill definition
- `skills/execute/SKILL.md` — `/do:execute` skill definition

### Skill Files Are the Implementation

The SKILL.md files are imperative prompts that Claude interprets at runtime. They contain the entire logic: there is no backing source code. Changes to behavior mean editing these markdown files.

Each SKILL.md has YAML frontmatter (`name`, `description`, `argument-hint`) that must be preserved.

### Data Contract: .design/plan.json

The two skills communicate through `.design/plan.json` (schemaVersion 2) written to the `.design/` directory at runtime (gitignored). The complete schema and validation rules are documented in the SKILL.md files. Key points:

- `.design/plan.json` is the authoritative state; the TaskList is a derived view
- Schema version 2 is required
- Progressive trimming: completed tasks are stripped of verbose agent fields to reduce plan size as execution proceeds
- Intermediate artifacts (goal-analysis.json, expert-\*.json, expert-\*.log) are cleaned up after plan generation

### Execution Model

`/do:design` uses a thin-lead delegation architecture for context-efficient planning:

- **Lead responsibilities** (never delegated): goal understanding (sequential thinking), pre-flight, team composition, team spawning (TeamCreate, SendMessage, shutdown), lightweight verification, summary output
- **Pipeline**: goal understanding → team composition → experts → plan-writer (4 steps total). Files carry data between stages via `.design/` directory
- **Sequential thinking in Step 1**: The lead uses `sequential-thinking` for conceptual goal reasoning (no file reads, no commands) — decomposing the goal, mapping to known patterns/frameworks, identifying prior art hints, and refining scope. Output written to `.design/goal-analysis.json` and consumed by experts and plan-writer.
- **No separate context scan**: experts gather their own context (source files, configs, web research) as part of their domain analysis, guided by prior art hints from the goal analysis
- **Domain-driven team composition**: informed by goal analysis domains and concepts, maps to 2–5 specialist roles with enriched mandates. Roles are invented as the goal demands (system-architect, codebase-archaeologist, online-researcher, etc.)
- **Unified expert-to-plan team**: A single Agent Team contains domain experts and a plan-writer. Pipeline ordering is enforced via TaskList dependencies (plan-writer blockedBy all experts). Expert agents receive self-contained prompts with goal + mandate inline. The plan-writer merges expert analyses, validates, enriches, extracts codebase context, and writes plan.json. The lead waits for one SendMessage from the plan-writer containing the result JSON.
- **Two-tier fallback**: If the team fails to produce `.design/plan.json` (1) retry with a single plan-writer Task subagent, or (2) perform merge and plan writing inline with context minimization (process expert files one at a time)
- The lead never reads raw expert analyses — data flows through file-based artifacts

`/do:execute` uses a thin-lead delegation architecture:

- **Lead responsibilities** (never delegated): spawn Task subagents, collect return values, git commits, user interaction (AskUserQuestion), circuit breaker evaluation, progress display
- **Setup Subagent** (Plan Bootstrap): reads and validates `.design/plan.json`, creates TaskList, computes file overlap matrix, assembles worker prompts, writes per-wave prompt files (`.design/wave-{N}.json`). Delegation fallback: if the subagent fails, the lead performs setup inline with simplified prompts (no file overlap computation)
- **Wave Processor Subagent** (Result Processor): parses worker FINAL status lines, reads detailed output from `.design/worker-{planIndex}.log` files, spot-checks files, runs acceptance criteria, determines retries, cleans up failed artifacts, assembles retry prompts. Writes detailed results to `.design/processor-wave-{N}.json` and returns summary JSON. Delegation fallback: if the subagent fails, the lead processes results inline (status line parsing, primary file verification, retry assembly, skip acceptance checks)
- **Plan Updater Subagent** (State Updater): reads `.design/processor-wave-{N}.json`, applies results to `.design/plan.json`, performs progressive trimming on completed tasks, computes cascading failures, writes atomically. Delegation fallback: if the subagent fails, the lead updates the plan inline (skip trimming and cascading failure computation)
- **File-based data routing**: Processor-to-updater communication flows through `.design/processor-wave-{N}.json` rather than inline JSON — the lead relays only wave context to the updater
- **Task subagents** (workers): one per task in each wave, self-read full instructions from `.design/wave-{N}.json` via bootstrap template, return COMPLETED:/FAILED:/BLOCKED: as FINAL line, write detailed work log to `.design/worker-{planIndex}.log`
- The lead never reads raw `.design/plan.json` — all plan data flows through subagent outputs
- Progressive trimming: completed tasks are stripped of verbose agent fields (keep only subject, status, result, metadata.files, wave, blockedBy, agent.role, agent.model)
- Retry budget: max 3 attempts per task with failure context passed to retries
- Cascading failures: failed/blocked tasks automatically skip dependents
- Circuit breaker: abort if >50% of remaining tasks would be skipped (plans with ≤3 tasks bypass this check)
- Resume support: can resume from `progress.currentWave` by resetting `in_progress` tasks to `pending` with artifact cleanup

## Requirements

- Claude Code 1.0.33+
- Agent Teams enabled (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`) — required for `/do:design` only
- `sequential-thinking` MCP server — used in `/do:design` Step 1 for goal understanding (fallback to inline reasoning if unavailable)

## Commit Conventions

Conventional commits with imperative mood: `feat:`, `fix:`, `chore:`, `refactor:`, `docs:`, `test:`. Example: `feat: add retry context to agent prompt`.
