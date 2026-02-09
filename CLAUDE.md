# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`claude-do` is a Claude Code plugin providing two skills: `/do:design` (team-based goal decomposition into `.design/plan.json`) and `/do:execute` (dependency-graph execution with task subagents). It leverages Claude Code's native Agent Teams and Tasks features for multi-agent collaboration. It is a documentation-only plugin — no source code, no build step, no dependencies.

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

The two skills communicate through `.design/plan.json` (schemaVersion 3) written to the `.design/` directory at runtime (gitignored). The complete schema and validation rules are documented in the SKILL.md files. Key points:

- `.design/plan.json` is the authoritative state; the TaskList is a derived view
- Schema version 3 is required
- Tasks use dependency-only scheduling — no wave field in task schema, execute computes batches dynamically from `blockedBy`
- Progressive trimming: completed tasks are stripped of verbose agent fields to reduce plan size as execution proceeds
- Intermediate artifacts (goal-analysis.json, expert-\*.json, expert-\*.log, critic.json, critic.log) are cleaned up after plan generation

### Execution Model

`/do:design` uses a thin-lead delegation architecture with adaptive complexity scaling:

- **Lead responsibilities** (never delegated): pre-flight, team lifecycle (TeamCreate, SendMessage, shutdown), reading analyst's output (`complexity` and `recommendedTeam`), spawning agents, lightweight verification, summary output. The lead NEVER analyzes the goal or reads source files.
- **Dynamically growing team**: The team starts with a single goal analyst, then grows based on goal complexity. One team (`do-design`), dynamic membership.
- **Goal analyst** (Step 2): First teammate spawned. Uses `sequential-thinking` MCP (if available) + codebase exploration to deeply understand the goal, propose 2–3 high-level approaches with tradeoffs, assess complexity, and recommend expert team composition. Experts are typed as `scanner` (domain analysis) or `architect` (approach design). Writes `.design/goal-analysis.json` including `complexity`, `complexityRationale`, `codebaseContext`, `approaches`, and `recommendedTeam`.
- **Complexity tiers** (analyst's `complexity` field determines pipeline):
  - **Minimal** (1-3 tasks, single obvious approach): skip expert/critic/plan-writer teammates. Spawn single lightweight plan-writer Task subagent reading only `goal-analysis.json`. Quality gate warns if plan exceeds 3 tasks or depth 2.
  - **Standard** (4-8 tasks, some design decisions): spawn experts + plan-writer (skip critic). Plan-writer blockedBy experts directly.
  - **Full** (9+ tasks, multiple approaches, cross-cutting concerns): spawn experts + critic + plan-writer. Critic blockedBy experts, plan-writer blockedBy critic.
- **Expert agents** (Step 3, standard/full only): Two types. **Scanners** analyze from a domain lens — what needs to happen. **Architects** design how to solve specific sub-problems — propose 2–3 concrete strategies with tradeoffs and recommend one. Each writes `.design/expert-{name}.json`.
- **Critic** (Step 3, full only): blockedBy all experts. Stress-tests proposals: challenges assumptions, evaluates approach coherence, identifies missing risks, flags over/under-engineering, checks goal alignment. Writes `.design/critic.json` with challenges and a verdict.
- **Plan-writer** (Step 3, standard/full only): teammate blockedBy critic (full) or experts (standard). Merges expert analyses, incorporates critique (full only), validates, enriches. Records approach decisions in `progress.decisions`. Writes `.design/plan.json`.
- **Two-tier fallback** (standard/full only): If the team fails to produce `.design/plan.json` (1) retry with a single plan-writer Task subagent, or (2) perform merge and plan writing inline with context minimization (process expert files one at a time)
- The lead never reads raw expert analyses — data flows through file-based artifacts. The ONE file the lead reads is `.design/goal-analysis.json` (for `complexity` and `recommendedTeam` only).

`/do:execute` uses a thin-lead delegation architecture:

- **Lead responsibilities** (never delegated): spawn Task subagents, collect return values, git commits, user interaction (AskUserQuestion), circuit breaker evaluation, progress display, compute ready-sets from dependencies
- **Setup Subagent** (Plan Bootstrap): reads and validates `.design/plan.json`, creates TaskList, computes file overlap matrix, assembles worker prompts, writes single task file (`.design/tasks.json`). Delegation fallback: if the subagent fails, the lead performs setup inline with simplified prompts (no file overlap computation)
- **Batch Processor Subagent** (Result Processor): parses worker FINAL status lines, reads detailed output from `.design/worker-{planIndex}.log` files, spot-checks files, runs acceptance criteria, determines retries, cleans up failed artifacts, assembles retry prompts. Writes detailed results to `.design/processor-batch-{N}.json` and returns summary JSON. Delegation fallback: if the subagent fails, the lead processes results inline (status line parsing, primary file verification, retry assembly, skip acceptance checks)
- **Plan Updater Subagent** (State Updater): reads `.design/processor-batch-{N}.json`, applies results to `.design/plan.json`, performs progressive trimming on completed tasks, computes cascading failures, writes atomically. Delegation fallback: if the subagent fails, the lead updates the plan inline (skip trimming and cascading failure computation)
- **File-based data routing**: Processor-to-updater communication flows through `.design/processor-batch-{N}.json` rather than inline JSON — the lead relays only round context to the updater
- **Task subagents** (workers): one per task in each ready-set batch, self-read full instructions from `.design/tasks.json` via bootstrap template, return COMPLETED:/FAILED:/BLOCKED: as FINAL line, write detailed work log to `.design/worker-{planIndex}.log`
- The lead never reads raw `.design/plan.json` — all plan data flows through subagent outputs
- **Dependency-graph scheduling**: orchestration uses ready-set loop (spawn all tasks whose `blockedBy` dependencies are completed), no pre-computed waves
- Progressive trimming: completed tasks are stripped of verbose agent fields (keep only subject, status, result, metadata.files, blockedBy, agent.role, agent.model)
- Retry budget: max 3 attempts per task with failure context passed to retries
- Cascading failures: failed/blocked tasks automatically skip dependents
- Circuit breaker: abort if >50% of remaining tasks would be skipped (plans with ≤3 tasks bypass this check)
- Resume support: status-scan based (reset `in_progress` tasks to `pending` with artifact cleanup), no wave tracking needed

## Requirements

- Claude Code 1.0.33+
- `sequential-thinking` MCP server — used by the goal analyst for deep goal reasoning (fallback to inline reasoning if unavailable)

## Commit Conventions

Conventional commits with imperative mood: `feat:`, `fix:`, `chore:`, `refactor:`, `docs:`, `test:`. Example: `feat: add retry context to agent prompt`.
