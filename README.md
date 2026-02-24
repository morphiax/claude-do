# do - Claude Code Plugin

> Spec-first multi-agent planning, execution, and refinement

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-4.0.0-green.svg)
![Claude Code](https://img.shields.io/badge/Claude%20Code-2.1.32%2B-orange.svg)

## What's Novel

**Spec-first development** — `spec.md` is the single source of truth. Everything else — skills, helper scripts, tests — is disposable output rebuilt from the spec. Behavioral contracts use trigger-obligation form (`WHEN <trigger>, system SHALL <outcome>`), stable IDs, and technology-agnostic language. Design authors contracts that must fail (TDD). Execute satisfies them. The delta is the work remaining.

**Modular CLI package** — Three-layer architecture (`store/` → `ops/` → `cli/`) replacing the previous monolith. Seven domains (spec, memory, reflection, trace, research, plan, archive) with proper separation of concerns. 365 tests across 18 modules.

**Spec lifecycle with regression gates** — Design registers contracts (pending). Execute satisfies them (proven by checks). Preflight re-verifies all satisfied contracts before and after execution — regressions are revoked automatically. Divergence detection compares the spec document against the registry.

**Adversarial reflection** — `/do:reflect` runs in an isolated context (`context: fork`), reviewing execution against five mandatory dimensions: intended vs actual, skipped steps, counter-evidence, prospective failure, and lifecycle integrity.

**Convention-aware refinement** — `/do:refine` applies project conventions systematically with spec regression gates. Five improvement categories applied in order: complexity reduction, redundancy elimination, naming/readability, logic consolidation, conventions application.

**Hypothesis-driven research** — `/do:research` generates competing hypotheses before investigating, seeks disconfirming evidence for every sub-question, and structures findings with confidence levels and direct recommendations.

**Cross-session memory** — Importance-scored learnings (3-10) persisted in JSONL, searchable by keyword. Boost/suppress operations. Injected into agent prompts with transparency.

**Execution observability** — Append-only trace log captures lifecycle events. Reflections capture product gaps, spec gaps, and process weaknesses with lens/urgency classification.

## Skills

| Skill | Description |
|---|---|
| `/do:design` | Reconcile spec with product, author behavioral contracts (TDD), expert analysis, plan assembly |
| `/do:execute` | Test generation, topological execution, worker verification, spec satisfaction |
| `/do:research` | Hypothesis-driven investigation, structured synthesis, design handoff |
| `/do:reflect` | Adversarial post-execution review (5 dimensions), observation persistence |
| `/do:refine` | Convention-aware code refinement with regression gates |

## Usage

```bash
# Install
/plugin marketplace add morphiax/claude-do
/plugin install do@do

# Research a topic
/do:research how do we implement OAuth 2.0 authentication

# Design and execute
/do:design implement user authentication with JWT tokens
/do:execute

# Post-execution review and refinement (invoked automatically by execute)
/do:reflect
/do:refine
```

## How It Works

**`/do:design`** reconciles the spec document against the product. Classifies gaps as spec-only, product-only, or mismatches. Authors new behavioral contracts using TDD (new specs must fail against current codebase). Spawns experts for analysis and debate on complex goals. Assembles a plan with role briefs linking to contract IDs. Bootstraps conventions and aesthetics when missing.

**`/do:execute`** generates tests from contracts before implementation (red phase). Executes roles in topological order — each worker implements until generated tests pass. Scope checks and file deltas verify worker output. Post-execution regression gate re-verifies all satisfied specs. Satisfies contracts for completed roles. Cascades failures to dependents with abort threshold (>50%).

**`/do:research`** decomposes topics into sub-questions, generates competing hypotheses, investigates across three source types (codebase, foundational knowledge, external), and synthesizes into structured findings with confidence levels. Output is consumable by `/do:design`.

**`/do:reflect`** runs adversarially in an isolated context. Reviews intended vs actual outcomes, identifies skipped steps, seeks counter-evidence, projects forward failures, and audits lifecycle integrity (registry health, satisfaction completeness, coverage gate). Persists observations with lens and urgency classification.

**`/do:refine`** applies five improvement categories in order against completed role outputs. Regression gate before and after — any newly failed contract triggers bisection and revert. Proposes convention and aesthetics updates when new patterns are discovered.

## Architecture

```
shared/
  do.py                 ← Entry point (symlink target)
  cli/                  ← Python CLI package
    cli/                  Argument parsing (7 domain modules)
    ops/                  Business logic
    store/                Persistence primitives (atomic, hash, jsonl)
skills/{name}/
  SKILL.md              ← Imperative prompt
  scripts/do.py         → symlink to shared/do.py
```

CLI invocation: `python3 $DO <domain> <command> --root .do`

Runtime state in `.do/`: `specs.jsonl`, `memory.jsonl`, `reflections.jsonl`, `traces.jsonl`, `research/`, `plans/`, `conventions.md`, `aesthetics.md`.

## Requirements

Claude Code 2.1.32+ | Python 3.10+ | MIT License
