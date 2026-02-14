# do - Claude Code Plugin

> Team-based planning and production-grade execution for Claude Code

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-2.2.0-green.svg)
![Claude Code](https://img.shields.io/badge/Claude%20Code-2.1.32%2B-orange.svg)

## Why do?

Most planning plugins use a single agent to decompose goals. `do` is different:

- **Role briefs, not micro-tasks.** `/do:design` creates goal-directed role briefs with expert context, acceptance criteria, and constraints — workers decide HOW to implement by reading the actual codebase.
- **Cross-session memory.** A memory agent accumulates learnings across sessions in `.design/memory.jsonl` and injects relevant context into experts and workers based on keyword matching, recency weighting, and importance scoring (1-10 scale).
- **Diverse debate with structured challenges.** For complex/high-stakes goals with >=3 experts, experts cross-review each other's findings, challenge specific claims with structured critique format, defend their positions, then the lead resolves conflicts and documents decisions in `designDecisions[]`.
- **Auxiliary agents for quality.** Pre-execution challengers review the plan for gaps. Scouts verify expert assumptions against the real codebase. Post-execution integration verifiers catch cross-role issues. Memory curators distill session outcomes (including failures) into importance-rated reusable learnings.
- **Dynamic expert teams with goal-type awareness.** Design spawns experts based on the goal's nature — architects and researchers for implementation goals, prompt-engineers for meta goals, domain specialists for all types. The lead determines team composition, not a fixed pipeline.
- **Execution has safety rails.** `/do:execute` spawns persistent, self-organizing workers that use CoVe-style verification (independently re-checking acceptance criteria), report progress, apply reflexion learning on retries, and communicate with each other. Safety rails include retry budgets, cascading failure propagation, and a circuit breaker.
- **Script-assisted orchestration.** A shared python3 helper script (12 commands) handles deterministic operations — validation, dependency computation, overlap analysis, importance-weighted memory search/add, and plan manipulation — reserving LLM usage for analytical and creative work.

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

The lead reads the goal, retrieves past learnings, spawns the right experts with contrasting perspectives, facilitates structured debate, and synthesizes findings into role briefs. Protocol guardrails ensure the lead follows the flow step-by-step without answering goals directly.

1. **Pre-flight** — Checks for existing plans, archives stale artifacts to `.design/history/`
2. **Lead research** — Scans project metadata, assesses complexity tier (trivial → high-stakes), determines expert team based on goal type (implementation/meta/research)
3. **Memory injection** — Searches `.design/memory.jsonl` for relevant past learnings (keyword-based with recency weighting and importance scoring) and injects top 3-5 into expert prompts
4. **Spawn experts** — Dynamic team selected by goal type: architects/researchers for implementation, prompt-engineers for meta goals, domain specialists for all types. For complex/high-stakes goals with >=3 experts, chooses at least 2 with contrasting priorities to enable productive debate.
5. **Expert cross-review (optional)** — For complex/high-stakes tiers with >=3 experts: experts read each other's artifacts, challenge specific claims using structured format (claim, severity, evidence, alternative), targeted experts defend their positions or concede. Lead collects challenges and defenses, then resolves conflicts in `designDecisions[]`.
6. **Synthesize into role briefs** — The lead merges expert findings and conflict resolutions into goal-directed role briefs. Each brief defines WHAT and WHY — workers decide HOW. Expert artifacts are preserved as structured JSON for workers to reference directly.
7. **Auxiliary roles** — Based on complexity tier: trivial (none), standard (integration verifier), complex (challenger + scout + integration verifier), high-stakes (challenger + scout + integration verifier).

### /do:execute — Autonomous specialist workers with memory and self-verification

An event-driven lead with persistent worker teammates:

- **Pre-execution auxiliaries** — Challenger reviews the plan for gaps and risks (structured report: issues by category/severity). Scout reads the actual codebase to verify expert assumptions (structured report: scope areas, discrepancies, integration points). Both report findings before workers spawn.
- **Memory injection** — Lead searches `.design/memory.jsonl` per role (using importance-weighted scoring with role goal + scope as context) and injects top 2-3 relevant learnings into worker prompts.
- **Workers with CoVe verification** — One persistent specialist per role (e.g., `api-developer`, `test-writer`). Workers receive past learnings, explore their scope directories, plan their own approach based on the real codebase, implement, test, and **independently re-verify each acceptance criterion as a fresh question** (not from implementation memory) before reporting completion. Workers provide progress updates for significant events.
- **Retry with reflexion** — On failure, workers analyze root cause, identify incorrect assumptions, and propose alternative approaches before retry (max 3 attempts per role).
- **Goal review** — After all roles complete, the lead evaluates whether the work achieves the original goal: completeness, coherence, and user intent. Gaps spawn targeted fix workers.
- **Post-execution auxiliaries** — Integration verifier runs the full test suite, checks cross-role contracts, and validates end-to-end goal achievement (structured report: status, acceptance criteria results, cross-role issues, test results). Memory curator distills handoff.md and **all role results including failed/skipped roles** into actionable memory entries (max 200 words, category-tagged, keyword-indexed, importance-rated 1-10) in `.design/memory.jsonl`.
- **Session handoff** — Structured `.design/handoff.md` for context recovery across sessions.

Safety rails: retry budgets (3 attempts) with reflexion learning, cascading failure propagation, circuit breaker (>50% skip rate), directory overlap serialization. Completed runs archive to `.design/history/{timestamp}/`.

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
