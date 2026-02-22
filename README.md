# do - Claude Code Plugin

> Multi-agent planning with structured debate, self-verifying execution, and cross-session memory

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-3.3.0-green.svg)
![Claude Code](https://img.shields.io/badge/Claude%20Code-2.1.32%2B-orange.svg)

## What's Novel

**Verification spec layer** — Design produces immutable property-based test specs that execute workers must satisfy, codifying correctness without constraining implementation. Specs test behavioral invariants (e.g., "rate limit resets after window") via the project's native test framework or shell scripts. SHA256 integrity prevents tampering.

**Structured debate with defense rounds** — For complex goals, experts cross-review each other's artifacts, challenge specific claims (claim/severity/evidence/alternative), then defend their positions before the lead resolves conflicts.

**CoVe-style worker verification** — Workers independently re-verify each acceptance criterion as a fresh question before reporting completion (not from implementation memory).

**Reflexion on retries** — Failed roles analyze root cause, identify incorrect assumptions, and propose alternatives before retry.

**Importance-scored memory** — Cross-session learnings rated 1-10, retrieved with keyword matching + recency decay + importance weighting (`score = keyword_match * recency_factor * importance/10`).

**Scout auxiliaries** — Pre-execution agents read the actual codebase to verify expert assumptions match reality. High-impact discrepancies are injected as role constraints before worker spawning.

**Self-monitoring** — All skills self-evaluate after every run, recording prompt-improvement-focused observations to `.design/reflection.jsonl`: specific SKILL.md text fixes with MAST failure classes (`promptFixes`), structured AC failure triples (`acGradients`), skipped protocol steps (`stepsSkipped`), and ignored instructions (`instructionsIgnored`). Unresolved improvements are injected directly into agent prompts at spawn time (Reflexion-style prepend), sorted failures-first (OPRO ascending-sort). Memory feedback loop boosts/decays injected memories based on role outcomes. Lamarckian technique derives fixes by reverse-engineering from desired outcomes.

**verificationChecks + spec-based validation** — Roles use `verificationChecks [{label, check}]` for ephemeral build/test/integration gates (not promoted to specs). Lead-side verification re-runs every check before marking roles complete (trust-but-verify). Surface-only checks (grep, file-existence) are flagged as anti-patterns. Spec invariants are injected directly into role constraints with full check commands, giving workers executable verification targets without needing to scan a global spec store.

**Persistent behavioral spec store with TDD (spec.jsonl)** — Design authors behavioral specs directly in `.design/spec.jsonl` using EARS notation — the primary behavioral artifact, not promoted from role checks. New specs are authored through 5 quality gates, validated via TDD (existing specs must pass, new specs must fail before execution). Execute runs spec-run pre-flight (classifying pre-existing passing vs TDD targets) and a post-execution regression gate. Reflect proposes spec tightenings. SHA256 tamper detection, importance-based compaction with protected floor, and JSONL format for line-level fault isolation. `spec-extract` enables characterization testing — generating spec candidates from observed CLI behavior.

**Execution observability via trace.jsonl** — Append-only event log capturing agent lifecycle events (spawn, completion, failure, respawn) with timestamps and session grouping. `trace-search` and `trace-summary` commands enable post-execution analysis and debugging.

**Automated self-test suite** — `plan.py self-test` exercises all 40 commands against synthetic fixtures in a temp directory, enabling CI-style validation of the helper script.

**Shared lead protocol** — Design, execute, research, and simplify skills share canonical lead protocols defined in `shared/lead-protocol-core.md` (boundaries, trace emission, memory injection) and `shared/lead-protocol-teams.md` (team setup, liveness tracking), eliminating protocol drift and ensuring consistent orchestration across all skills.

**Comprehensive knowledge research** — `/do:research` gathers and structures knowledge across 5 sections (prerequisites, mental models, usage patterns, failure patterns, production readiness). Spawns researchers to map findings across codebase, external sources, and domain expertise. Minimum research thresholds enforce quality floors (>=3 post-mortems, >=5 beginner mistakes, quantitative performance claims). Concept dependency graphs order learning paths. Evolution paths capture pattern progression at scale. Team adoption factors assess learning timeline, documentation quality, and community support. Decision framework (bestFit/wrongFit scenarios) makes recommendations actionable. Design handoff preserves concrete building blocks for `/do:design`.

## Usage

```bash
/plugin marketplace add morphiax/claude-do
/plugin install do@do

# Research: gather structured knowledge before planning
/do:research how do we implement OAuth 2.0 authentication

# Plan and execute a goal
/do:design implement user authentication with JWT tokens
/do:execute

# Simplify code or text using cascade thinking
/do:simplify
/do:simplify skills/design/SKILL.md
```

## How It Works

**`/do:research`** spawns 3 parallel standalone Task() subagents (codebase analyst, external researcher, domain specialist) — research is inherently exploratory, so external sources are always included. Researchers gather findings across codebase, literature, and comparative/theoretical domains with minimum quality thresholds (>=3 post-mortems, >=5 beginner mistakes, quantitative performance claims), then save findings to `.design/expert-*.json` artifacts. Lead synthesizes findings into 5 knowledge sections with concept dependency graphs, evolution paths, and team adoption factors. Recommendations include decision framework (bestFit/wrongFit scenarios) alongside confidence and effort. Outputs to `.design/research.json`. Memory injection with transparency. End-of-run summary shows recommendation count and research gaps identified.

**`/do:design`** spawns experts (architects, researchers, domain specialists) based on goal type. For complex goals, experts debate via structured challenges/defenses. The lead synthesizes findings into role briefs with verificationChecks (build/test gates) and injects spec invariants directly into role constraints. Step 7 authors behavioral specs in spec.jsonl using EARS notation with TDD validation. Scout auxiliaries verify expert assumptions against the real codebase. Phase announcements show progress. Draft plan review checkpoint for complex goals. Memory injection with transparency. End-of-run summary with metrics.

**`/do:execute`** spawns standalone worker agents per role. Spec pre-flight runs before worker spawning to classify pre-existing passing specs (regression baseline) vs TDD targets (newly authored, expected to fail). Workers run spec invariant checks (injected in constraints) + verificationChecks (build/test) + verificationSpecs (if present) during Pre-Completion Verification. Lead-side verification re-runs all checks. Adaptive model escalation on retry (haiku→sonnet→opus). Worker-to-worker handoff injects completed role context into dependent workers. Post-execution spec regression gate: all spec.jsonl entries must pass — failures trigger targeted fix workers. Memory curator distills outcomes into importance-rated learnings. End-of-run summary with detailed metrics.

**`/do:simplify`** analyzes code or text for cascade simplification opportunities — where one insight eliminates multiple components at once, reducing cognitive overhead without sacrificing capability. Target type detection (code/text/mixed) drives analyst variant selection: code targets get git churn × cyclomatic complexity analysis, text targets get token weight, dead rules, and redundancy analysis. Spawns pattern-recognizer and complexity-analyst. Pattern-recognizer's primary lens is "Everything is a special case of..." — seeking paradigm-level cascades (not just component unification) with worked examples spanning component, system, and paradigm levels. Anti-pattern guards prevent token bloat, circular simplification, and regressions. Lead synthesizes findings into plan.json with preservation-focused worker roles for `/do:execute`. Memory injection with transparency. 3-turn liveness timeout.

## Requirements

Claude Code 2.1.32+ | Python 3.8+ | [CONTRIBUTING.md](CONTRIBUTING.md) | MIT License
