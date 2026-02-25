# Changelog

## 5.8.0

Shape actively guards its boundary with frame. Technology questions are redirected, not engaged with — shape steers back to intent and constraints instead of evaluating tools or frameworks.

## 5.7.1

Frame audits existing tooling before researching. Assesses current project tooling against ecosystem best practices, surfaces gaps proactively rather than waiting for the human to ask.

## 5.7.0

Subagent delegation and structured user questions. Skills delegate heavy work to subagents via Task tool with model tiers (haiku/sonnet/opus) based on complexity. Shape and frame use AskUserQuestion for decision points instead of prose questions.

## 5.6.0

Quality infrastructure as project-local concern. Frame captures quality conventions (linter, formatter, test runner) in context.md. Build materializes them as config files before application code.

## 5.5.0

Specs are all specification, no explanations. Shape writes concretely for build — behavior, not concepts. Build treats every spec line as work, not background.

## 5.4.0

Gap detection through version control. All three skills now check git diffs at session start, each through its own lens — shape detects intent drift (code changed, spec didn't), build detects spec/context evolution, frame detects undocumented technology changes and recurring struggles in commit history.

## 5.3.0

Add context boundary and build diff-awareness.

- **Context boundary**: Spec and frame skill now explicitly state that context captures choices and environment facts, not build outputs or runtime stats
- **Build reads the diff**: Build skill checks `git diff` on spec/context before starting — the delta since last commit is the most direct signal of what evolved and what needs attention

## 5.0.0

Complete rewrite. Replaced 5 skills, a Python CLI, 341 behavioral contracts, and 365 tests with 2 skills and a spec convention.

### What changed

- **Skills**: `/do:design`, `/do:execute`, `/do:research`, `/do:reflect`, `/do:refine` replaced by `/do:shape` and `/do:build`
- **No CLI**: Removed the `shared/cli` Python package, all store/ops/cli layers, and helper scripts
- **No contracts**: Removed behavioral contract system (specs.jsonl, contract IDs, tamper detection, preflight verification)
- **No ceremony**: Removed DAG scheduling, FSMs, Eisenhower matrices, content-addressable hashing, double-blind review protocols, regression gates, archive system

### What remains

- A spec file (`.do/spec.md`) as persistent shared understanding
- Two skills: shape (evolve the spec through dialogue) and build (implement and compare)
- A feedback loop between them

### Why

The previous system over-specified a process that works better when left to the LLM's judgment. 341 contracts and 8 mechanical phases per skill constrained creativity without improving outcomes. The core need — persistent shared understanding between human and AI — was buried under infrastructure.

## 4.0.0

Modular CLI package rewrite with three-layer architecture. 365 tests across 18 modules.

## 3.0.0

Spec-based validation with brownfield auto-detection.

## 2.0.0

Migration from acceptance-criteria to spec-based validation.

## 1.0.0

Initial release with five skills and monolithic helper script.
