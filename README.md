# do - Claude Code Plugin

> Multi-agent planning with structured debate, self-verifying execution, and cross-session memory

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-2.6.0-green.svg)
![Claude Code](https://img.shields.io/badge/Claude%20Code-2.1.32%2B-orange.svg)

## What's Novel

**Structured debate with defense rounds** — For complex goals, experts cross-review each other's artifacts, challenge specific claims (claim/severity/evidence/alternative), then defend their positions before the lead resolves conflicts.

**CoVe-style worker verification** — Workers independently re-verify each acceptance criterion as a fresh question before reporting completion (not from implementation memory).

**Reflexion on retries** — Failed roles analyze root cause, identify incorrect assumptions, and propose alternatives before retry.

**Importance-scored memory** — Cross-session learnings rated 1-10, retrieved with keyword matching + recency decay + importance weighting (`score = keyword_match * recency_factor * importance/10`).

**Scout auxiliaries** — Pre-execution agents read the actual codebase to verify expert assumptions match reality (when the goal touches code).

## Usage

```bash
/plugin marketplace add morphiax/claude-do
/plugin install do@do

# Plan and execute a goal
/do:design implement user authentication with JWT tokens
/do:execute

# Analyze and improve a skill with scientific methodology
/do:improve skills/design/SKILL.md
/do:execute
```

## How It Works

**`/do:design`** spawns experts (architects, researchers, domain specialists) based on goal type. For complex goals, experts debate via structured challenges/defenses. The lead synthesizes findings into role briefs with acceptance criteria. Scout auxiliaries verify expert assumptions against the real codebase.

**`/do:execute`** spawns persistent worker agents per role. Workers use CoVe-style verification, apply reflexion on failures, and report progress. Safety rails: retry budgets, cascading failures, circuit breaker, overlap serialization. Memory curator distills outcomes (including failures) into importance-rated learnings.

**`/do:improve`** analyzes Claude Code skills using 7 quality dimensions (Protocol Clarity, Constraint Enforcement, Error Handling, Agent Coordination, Information Flow, Prompt Economy, Verifiability). For general analysis, spawns 2-3 experts; for targeted improvements, uses a single analyst. Produces testable hypotheses with predicted behavioral impacts. Always outputs `.design/plan.json` for `/do:execute` — never writes source files directly. Anti-pattern guards prevent token bloat, circular improvements, and regressions.

## Requirements

Claude Code 2.1.32+ | Python 3.8+ | [CONTRIBUTING.md](CONTRIBUTING.md) | MIT License
