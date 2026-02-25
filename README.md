# do - Claude Code Plugin

> Shape specs, frame the approach, build what they describe

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-5.2.0-green.svg)

## What It Does

Three skills for collaborative problem-solving between a human and an AI.

The human has intent and constraints they may not be able to fully articulate. The AI has broad technical knowledge and pattern recognition. A shared spec captures the problem understanding. A context file captures the technology choices. Together they drive the build.

## Skills

| Skill | Description |
|---|---|
| `/do:shape` | Evolve a spec through dialogue — clarify intent, surface constraints, connect ideas to known concepts |
| `/do:frame` | Converge on the approach — research technology options, evaluate fit, capture the chosen stack |
| `/do:build` | Implement what the spec and context describe, compare result, flag mismatches |

## Usage

```bash
# Install
/plugin marketplace add morphiax/claude-do
/plugin install do@do

# Shape the spec — what are we building and why?
/do:shape I want to build a tool that does X

# Frame the approach — what are we building it with?
/do:frame what language and framework should we use?

# Build — implement from spec + context
/do:build

# Refine after building
/do:shape the build revealed that Y doesn't work, let's rethink Z
/do:frame we need to switch from Node to Bun
```

## How It Works

**`/do:shape`** is a conversation that evolves the spec. The AI asks questions, reflects back understanding, connects fuzzy ideas to known concepts, and proposes refinements. The human corrects, sharpens, or redirects. When understanding shifts, the spec is updated — but only after discussion and agreement.

**`/do:frame`** is a conversation that converges on the approach. Given a spec, it researches technology options, evaluates fit against constraints, surfaces tradeoffs, and captures idiomatic practices. Same spec with different context produces different valid implementations.

**`/do:build`** reads the spec and context, then implements what they describe. After building, it compares the result to both. Mismatches are flagged — not silently fixed. The human decides whether to update the spec, the context, or the implementation.

The feedback loop between all three skills is the core mechanism. Build produces evidence. Shape and frame incorporate it. Each cycle sharpens the spec, the context, and the solution.

## Conventions

| File | Purpose |
|---|---|
| `.do/spec.md` | Root spec — the shared understanding of what and why |
| `.do/context.md` | Technology choices and environment facts — the with-what |
| `.do/specs/` | Sub-specs for decomposed problems |
