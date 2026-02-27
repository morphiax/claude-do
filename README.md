# do - Claude Code Plugin

> Collaborative sensemaking — shape understanding through dialogue, build what it describes

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-6.4.0-green.svg)

## What It Does

Two skills and three commands for collaborative problem-solving between a human and an AI.

The human has intent and constraints they may not be able to fully articulate. The AI has broad technical knowledge and pattern recognition. A shared spec captures the problem understanding. A context file captures the approach, plan, and progress. Together they drive the build.

## Skills

| Skill | Description |
|---|---|
| `/do:shape` | Talk about the project — clarify intent, evaluate technology, surface constraints, plan what to build next |
| `/do:build` | Drive work to completion — apply, verify, produce next steps |

## Commands

| Command | Description |
|---|---|
| `/do:release` | Version bump, changelog, docs sync, commit, tag, push |
| `/do:audit` | Technical audit — evaluate stack, patterns, and practices against best practices |
| `/do:challenge` | Product challenge — question assumptions, find gaps, pressure-test the value proposition |

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

# Audit — what could be better technically?
/do:audit
/do:audit error handling

# Challenge — is the product right?
/do:challenge
/do:challenge onboarding experience

# Release — ship a version
/do:release
```

## How It Works

**`/do:shape`** is the dialogue skill. The human talks about the project — both what it should do and how to build it. Shape routes internally: intent, constraints, and behavior go in the spec; technology choices, conventions, plan, and environment go in the context. It audits existing tooling, researches options, evaluates fit against constraints, and surfaces tradeoffs. Periodically it steps back to assess whether the spec is still coherent.

**`/do:build`** is the execution skill. It drives work to completion — not just writing code, but applying it, verifying it works, and confirming the outcome is real. It reads the spec and context, implements using TDD, then continues through apply and verify until the context's definition of done is met. Build interacts with the human for direction and permission along the way. When it stops, it produces concrete next steps — the next buildable unit, spec gaps to shape, or human actions needed.

The feedback loop is the core mechanism. Build produces evidence. Shape incorporates it into shared understanding. Each cycle sharpens the spec, the context, and the solution.

**Commands** are single-purpose actions that run and finish. `/do:audit` evaluates the tech stack against current best practices. `/do:challenge` pressure-tests the product from a PM perspective. Both produce findings that feed into shape. `/do:release` handles versioning, changelog, and shipping.

## Conventions

| File | Purpose |
|---|---|
| `.do/spec.md` | Root spec — the shared understanding of what and why |
| `.do/context.md` | Approach, plan, and progress — the with-what and where-we-are |
| `.do/specs/` | Sub-specs for decomposed problems |
