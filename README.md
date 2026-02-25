# do - Claude Code Plugin

> Shape specs collaboratively, build what they describe

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Version](https://img.shields.io/badge/version-5.0.0-green.svg)

## What It Does

Two skills for collaborative problem-solving between a human and an AI.

The human has intent and constraints they may not be able to fully articulate. The AI has broad technical knowledge and pattern recognition. A shared spec document is where their understanding meets — persisting across sessions so context is never lost.

## Skills

| Skill | Description |
|---|---|
| `/do:shape` | Evolve a spec through dialogue — clarify intent, surface constraints, connect ideas to known concepts |
| `/do:build` | Implement what the spec describes, compare result to spec, flag mismatches |

## Usage

```bash
# Install
/plugin marketplace add morphiax/claude-do
/plugin install do@do

# Start shaping a new spec
/do:shape I want to build a tool that does X

# Build what the spec describes
/do:build

# Refine after building
/do:shape the build revealed that Y doesn't work, let's rethink Z
```

## How It Works

**`/do:shape`** is a conversation, not a drafting exercise. The AI asks questions, reflects back understanding, connects fuzzy ideas to known concepts, and proposes refinements. The human corrects, sharpens, or redirects. When understanding shifts, the spec is updated — but only after discussion and agreement.

**`/do:build`** reads the spec and implements what it describes, using its own judgment on technology and approach. After building, it compares the result to the spec. Mismatches are flagged — not silently fixed. The human decides whether to update the spec or fix the implementation.

The feedback loop between shape and build is the core mechanism. Build produces evidence. Shape incorporates it. Each cycle sharpens both the spec and the solution.

## Spec Convention

The spec lives at `.do/spec.md` in your project. When problems decompose, sub-specs go under `.do/specs/`. The root spec acts as an index.

## Requirements

Claude Code 2.1.32+ | MIT License
