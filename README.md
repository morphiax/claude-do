# do - Claude Code Plugin

> Team-based planning and production-grade execution for Claude Code

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-2.1.0-green.svg)
![Claude Code](https://img.shields.io/badge/Claude%20Code-2.1.32%2B-orange.svg)

## Why do?

Most planning plugins use a single agent to decompose goals. `do` is different:

- **Role briefs, not micro-tasks.** `/do:design` creates goal-directed role briefs with expert context, acceptance criteria, and constraints — workers decide HOW to implement by reading the actual codebase.
- **Cross-session memory.** A memory agent accumulates learnings across sessions in `.design/memory.jsonl` and injects relevant context into experts and workers based on keyword matching and recency weighting.
- **Diverse debate.** For complex goals with >=3 experts, experts cross-review each other's findings and challenge assumptions before the lead synthesizes — conflicts are resolved and documented in `designDecisions[]`.
- **Auxiliary agents for quality.** Pre-execution challengers review the plan for gaps. Scouts verify expert assumptions against the real codebase. Post-execution integration verifiers catch cross-role issues. Memory curators distill session outcomes into reusable learnings.
- **Dynamic expert teams.** Design spawns experts based on the goal's nature — architects, researchers, domain specialists. The lead determines team composition, not a fixed pipeline.
- **Execution has safety rails.** `/do:execute` spawns persistent, self-organizing workers that claim roles from the dependency graph, commit their own changes, and communicate with each other. Safety rails include retry budgets, cascading failure propagation, and a circuit breaker.
- **Script-assisted orchestration.** A shared python3 helper script (12 commands) handles deterministic operations — validation, dependency computation, overlap analysis, memory search/add, and plan manipulation — reserving LLM usage for analytical and creative work.

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

### /do:design — Expert-informed role briefs with memory and debate

The lead reads the goal, retrieves past learnings, spawns the right experts with contrasting perspectives, facilitates debate, and synthesizes findings into role briefs.

1. **Pre-flight** — Checks for existing plans, archives stale artifacts to `.design/history/`
2. **Lead research** — Scans project metadata, assesses complexity tier (trivial → high-stakes), determines expert team
3. **Memory injection** — Searches `.design/memory.jsonl` for relevant past learnings (keyword-based with recency weighting) and injects top 3-5 into expert prompts
4. **Spawn experts** — Dynamic team: architects (system design), researchers (prior art), domain specialists (security, performance, etc.). For complex/high-stakes goals with >=3 experts, chooses at least 2 with contrasting priorities to enable productive debate.
5. **Expert cross-review (optional)** — For complex/high-stakes tiers with >=3 experts: experts read each other's artifacts, challenge assumptions and gaps, cite specific claims. Lead collects challenges and resolves conflicts in `designDecisions[]`.
6. **Synthesize into role briefs** — The lead merges expert findings and conflict resolutions into goal-directed role briefs. Each brief defines WHAT and WHY — workers decide HOW. Expert artifacts are preserved as structured JSON for workers to reference directly.
7. **Auxiliary roles** — Based on complexity: challenger (pre-execution plan review), scout (codebase reality check), integration verifier (post-execution cross-role validation).

### /do:execute — Autonomous specialist workers with memory

An event-driven lead with persistent worker teammates:

- **Pre-execution auxiliaries** — Challenger reviews the plan for gaps and risks. Scout reads the actual codebase to verify expert assumptions. Both report findings before workers spawn.
- **Memory injection** — Lead searches `.design/memory.jsonl` per role (using role goal + scope as context) and injects top 2-3 relevant learnings into worker prompts.
- **Workers** — One persistent specialist per role (e.g., `api-developer`, `test-writer`). Workers receive past learnings, explore their scope directories, plan their own approach based on the real codebase, implement, test against acceptance criteria, commit, and report.
- **Goal review** — After all roles complete, the lead evaluates whether the work achieves the original goal: completeness, coherence, and user intent. Gaps spawn targeted fix workers.
- **Post-execution auxiliaries** — Integration verifier runs the full test suite, checks cross-role contracts, and validates end-to-end goal achievement. Memory curator distills handoff.md and role results into actionable memory entries (max 200 words, category-tagged, keyword-indexed) in `.design/memory.jsonl`.
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
