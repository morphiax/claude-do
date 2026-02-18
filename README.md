# do - Claude Code Plugin

> Multi-agent planning with structured debate, self-verifying execution, and cross-session memory

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-2.15.0-green.svg)
![Claude Code](https://img.shields.io/badge/Claude%20Code-2.1.32%2B-orange.svg)

## What's Novel

**Verification spec layer** — Design produces immutable property-based test specs that execute workers must satisfy, codifying correctness without constraining implementation. Specs test behavioral invariants (e.g., "rate limit resets after window") via the project's native test framework or shell scripts. SHA256 integrity prevents tampering.

**Structured debate with defense rounds** — For complex goals, experts cross-review each other's artifacts, challenge specific claims (claim/severity/evidence/alternative), then defend their positions before the lead resolves conflicts.

**CoVe-style worker verification** — Workers independently re-verify each acceptance criterion as a fresh question before reporting completion (not from implementation memory).

**Reflexion on retries** — Failed roles analyze root cause, identify incorrect assumptions, and propose alternatives before retry.

**Importance-scored memory** — Cross-session learnings rated 1-10, retrieved with keyword matching + recency decay + importance weighting (`score = keyword_match * recency_factor * importance/10`).

**Scout auxiliaries** — Pre-execution agents read the actual codebase to verify expert assumptions match reality. High-impact discrepancies are injected as role constraints before worker spawning.

**Execution reflections** — Skills self-evaluate after every run, storing structured assessments in episodic memory. `/do:reflect` analyzes these to identify recurring failures and generate evidence-based improvements (inspired by Reflexion and GEPA research).

**Acceptance criteria validation** — Design-time syntax validation catches broken `python3 -c` checks (including f-string brace nesting errors) before execution. Shift-left anti-pattern warnings in expert prompts prevent grep-only criteria from entering plans. Lead-side verification re-runs every criterion before marking roles complete (trust-but-verify). Surface-only checks (grep, file-existence) are flagged as anti-patterns.

**Execution observability via trace.jsonl** — Append-only event log capturing agent lifecycle events (spawn, completion, failure, respawn) with timestamps and session grouping. `trace-search` and `trace-summary` commands enable post-execution analysis for `/do:reflect` and debugging.

**Automated self-test suite** — `plan.py self-test` exercises all 32 commands against synthetic fixtures in a temp directory, enabling CI-style validation of the helper script.

**Meadows-based reconnaissance** — `/do:recon` analyzes goals through systems thinking before design. Spawns researchers to map leverage points (paradigm shifts, goal alignment, feedback loops, structure, parameters). Ranks interventions by impact using Meadows framework adapted for software. Outputs ranked designGoals + constraints (not implementation suggestions) to `.design/recon.json`.

## Usage

```bash
/plugin marketplace add morphiax/claude-do
/plugin install do@do

# Reconnaissance: identify high-leverage interventions
/do:recon improve observability in our microservices

# Plan and execute a goal
/do:design implement user authentication with JWT tokens
/do:execute

# Analyze and improve a skill with scientific methodology
/do:improve skills/design/SKILL.md
/do:execute

# Improve skills based on real execution outcomes
/do:reflect
/do:execute
```

## How It Works

**`/do:recon`** always spawns full research team (codebase analyst, external researcher, domain specialist) — recon is inherently exploratory, so external research is always included. Researchers gather findings across multiple domains. Lead synthesizes findings using 7-level Meadows framework (paradigm/goals/rules/information_flows/feedback_loops/structure/parameters) with software-adjusted weights. Ranks interventions by tier-weight formula (leverageLevel × confidence ÷ effort). Outputs to `.design/recon.json` with designGoal + constraints per intervention (NOT implementation suggestions). Max 5 interventions. Detects contradictions. Memory injection with transparency. 3-turn liveness timeout. End-of-run summary shows top leverage levels and findings analyzed.

**`/do:design`** spawns experts (architects, researchers, domain specialists) based on goal type. For complex goals, experts debate via structured challenges/defenses. The lead synthesizes findings into role briefs with acceptance criteria. Scout auxiliaries verify expert assumptions against the real codebase. Phase announcements show progress. Draft plan review checkpoint for complex goals. Memory injection with transparency. Behavioral trait instructions for experts and auxiliaries. 3-turn liveness timeout (simplified from 5+7). End-of-run summary with metrics.

**`/do:execute`** spawns persistent worker agents per role. Workers use CoVe-style verification, apply reflexion on failures, and report structured completion reports (role, achieved, filesChanged, acceptanceCriteria results). Adaptive model escalation on retry (haiku→sonnet→opus). Worker-to-worker handoff injects completed role context into dependent workers. Liveness pipeline detects worker silence with 3-turn timeout and re-spawn (simplified from 5+7). Safety rails: retry budgets, cascading failures, circuit breaker, overlap serialization. Memory curator distills outcomes (including failures) into importance-rated learnings with 6 categories (convention/pattern/mistake/approach/failure/procedure). Dynamic importance tracking via boost/decay. Progress reporting for significant events. Curation transparency. End-of-run summary with detailed metrics.

**`/do:improve`** analyzes Claude Code skills using 7 quality dimensions (Protocol Clarity, Constraint Enforcement, Error Handling, Agent Coordination, Information Flow, Prompt Economy, Verifiability). For general analysis, spawns 2-3 experts; for targeted improvements, uses a single analyst. Produces testable hypotheses with predicted behavioral impacts. Always outputs `.design/plan.json` for `/do:execute` — never writes source files directly. Anti-pattern guards prevent token bloat, circular improvements, and regressions. Expert artifact schema validation. 3-turn liveness timeout. Compressed quality rubric (1/3/5 anchors). Behavioral trait instructions. Phase announcements and end-of-run summary.

**`/do:reflect`** uses execution outcomes (from `.design/reflection.jsonl`) to identify what's actually working and what isn't. Direct Bash-based analysis (no Task agent) gathers data via plan.py commands, computes metrics, and formulates hypotheses — eliminating hallucination risk. Temporal resolution tracking classifies patterns as active/likely_resolved/confirmed_resolved using a 3-run recency window and memory.jsonl cross-referencing, preventing duplicate improvement work on already-fixed issues. Hypotheses are grounded in real evidence with confidence levels. Requires >=2 reflections to identify patterns. Complements `/do:improve` (static prompt quality) with dynamic functional optimization. Phase announcements and end-of-run summary.

## Requirements

Claude Code 2.1.32+ | Python 3.8+ | [CONTRIBUTING.md](CONTRIBUTING.md) | MIT License
