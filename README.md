# do

A Claude Code plugin for collaborative project development — `/do:work` evolves understanding through dialogue, plans and builds through execution, and analyzes through audit and challenge modes.

## What it does

`/do:work` is a unified skill for working on projects through four modes:

| Mode | What it does | When to use |
|------|-------------|-------------|
| Dialogue | Conversation about the project, update understanding | Clarifying intent, evaluating technology, surfacing constraints |
| Planning | Decompose work into testable tasks | Ready to implement something |
| Execution | Build the approved plan via TDD | Plan approved, ready to code |
| Analysis | Technical audit or product challenge | Want an honest assessment |

`/do:release` ships versions — bump, changelog, docs sync, commit, tag, push.

## How it works

### Pseudocode-driven specs

The core of the system is a behavioral spec written as pseudocode rather than prose. This isn't a stylistic preference — it's grounded in research:

- **7-38% improvement** over prose prompts across 132 tasks (IBM, EMNLP 2023)
- **Structure matters more than semantics** — LLMs are more sensitive to control flow and indentation than variable names or comments, and this gap *widens* with model scale (Waheed, 3331 experiments, 2024)
- **25% average improvement** with code-form plans across 13 benchmarks, with gains *scaling with task complexity* (CodePlan, ICLR 2025)

Every function in the spec has a typed signature (`def name(arg: Type) -> ReturnType:`) and a one-line docstring stating its behavioral contract. Comments are reasoning cues, not documentation — if removing a comment loses a behavior, it becomes a pseudocode statement instead. The full style is codified in `validate_pseudocode_style` and enforced self-referentially: the spec validates against its own quality rules.

### Session loop

Each session runs an orient-decide-act-observe loop. The system reads project files and git diffs to reconstruct current state, then enters whichever mode the request demands. Modes transition fluidly — discovering a gap during execution pauses into dialogue to propose a project file update, then resumes.

### Orchestrator/worker separation

The main conversation context handles dialogue, planning, and orchestration only. All implementation — code reads, edits, tests — runs in subagents that receive a preamble and task description with zero inherited context. This prevents implementation details from polluting the project-level reasoning window.

### Bidirectional sync

Project files and code stay in sync. After execution, a sync gate requires enumerating each changed behavior and confirming coverage across project files — or explicitly stating nothing drifted. Neither can change without the other.

### Quality system

The spec includes validation functions for every output type — plans, dialogue exchanges, findings, spec entries, model file entries. Each validation function is a set of mechanical tests, not subjective criteria. Invariants are split into hard (single violation is a breach) and soft (recoverable within session), which improves compliance through the transparency effect (ABC Framework, 2026).

## Project files

The plugin maintains shared understanding in six files under `.do/`:

| File | Purpose | Question it answers |
|------|---------|-------------------|
| `spec.md` | Behaviors, constraints, algorithm pseudocode | What should it do? |
| `reference.md` | External system models | How does the target system work? |
| `stack.md` | Runtime, frameworks, conventions | What are we building with? |
| `design.md` | Output surfaces, tone, density, skeletons | What should it look and feel like? |
| `decisions.md` | Decision log with rationale | Why did we choose this? |
| `pitfalls.md` | Failure modes and fixes | What breaks and how to avoid it? |

## Usage

### Start a new project
```
/do:work what problem are we solving?
```

### Continue working
```
/do:work
```
Reads project files, checks git diffs, picks up where you left off.

### Build something
```
/do:work implement the search feature
```
Plans in read-only mode, gets approval, executes via TDD.

### Audit the stack
```
/do:work audit
```
Technical evaluation against current best practices.

### Challenge assumptions
```
/do:work challenge the onboarding flow
```
Product review from PM perspective.

### Ship a version
```
/do:release minor
```

## Install

```
claude plugin add morphiax/do
```
