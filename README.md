# do - Claude Code Plugin

> Collaborative sensemaking — shape understanding through dialogue, build what it describes

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-6.2.0-green.svg)

## What It Does

Two skills for collaborative problem-solving between a human and an AI.

The human has intent and constraints they may not be able to fully articulate. The AI has broad technical knowledge and pattern recognition. A shared spec captures the problem understanding. A context file captures the approach, plan, and progress. Together they drive the build.

## Skills

| Skill | Description |
|---|---|
| `/do:shape` | Talk about the project — clarify intent, evaluate technology, surface constraints, plan what to build next |
| `/do:build` | Implement what the spec describes, compare result, write status to context |

## Usage

```bash
# Install
/plugin marketplace add morphiax/claude-do
/plugin install do@do

# Shape — what are we building, why, and with what?
/do:shape I want to build a tool that does X

# Build — implement from spec + context
/do:build

# Refine after building
/do:shape the build revealed that Y doesn't work, let's rethink Z
/do:shape we need to switch from Node to Bun
```

## How It Works

**`/do:shape`** is the dialogue skill. The human talks about the project — both what it should do and how to build it. Shape routes internally: intent, constraints, and behavior go in the spec; technology choices, conventions, plan, and environment go in the context. It audits existing tooling, researches options, evaluates fit against constraints, and surfaces tradeoffs. Periodically it steps back to assess whether the spec is still coherent.

**`/do:build`** is the execution skill. It reads the spec and context, implements what they describe using TDD, then compares the result to both. Mismatches are flagged — not silently fixed. Build writes status to the context (what's done, what's next, what's blocked), making it the complete handoff for the next session.

The feedback loop is the core mechanism. Build produces evidence. Shape incorporates it into shared understanding. Each cycle sharpens the spec, the context, and the solution.

## Conventions

| File | Purpose |
|---|---|
| `.do/spec.md` | Root spec — the shared understanding of what and why |
| `.do/context.md` | Approach, plan, and progress — the with-what and where-we-are |
| `.do/specs/` | Sub-specs for decomposed problems |
