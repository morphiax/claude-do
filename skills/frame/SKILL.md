---
name: frame
description: "Converge on the approach — research technology options, evaluate fit against the spec, surface tradeoffs, capture the chosen stack."
argument-hint: "[technology question or area to explore] — or omit to review the full context"
---

# Frame

You are helping choose the right approach for building what the spec describes. The spec captures what and why — your job is to figure out with-what. Language, framework, tools, patterns, infrastructure, conventions.

## Read the spec and context first

Read `.do/spec.md` to understand what needs to be built. Read `.do/context.md` if it exists — it captures decisions already made. Everything builds from here.

If no context exists, that's fine — this conversation will produce the first draft.

## Check what changed

When the project is under version control, check what changed in code and dependencies since the last commit (`git diff`, excluding `.do/`). If tools, dependencies, or infrastructure changed without a context update, surface it. Also check recent commit history (`git log --oneline -20`) for recurring patterns — repeated fixes or reverts in the same area signal a technology choice that isn't working and may need rethinking. When version control isn't available, skip this step.

## What you do

**Research options.** Given the spec's intent and constraints, explore what technologies and approaches could work. Look at the landscape — what's mature, what's emerging, what fits the problem shape. Use web search when needed to check current state, community health, and best practices.

**Evaluate fit.** Not every tool fits every problem. Evaluate options against the spec's constraints. If the spec says "must be simple," a framework with heavy boilerplate is a poor fit. If the spec describes real-time interaction, evaluate accordingly. Be specific about why something fits or doesn't.

**Surface tradeoffs.** Every choice has tradeoffs. Make them explicit. "Python is faster to ship but slower to run. Given the spec says X, which matters more?" Use structured questions for clear decision points. Don't bury tradeoffs in paragraphs.

**Capture idiomatic practices.** Once a technology is chosen, capture how to use it well — idiomatic patterns, best practices, common gotchas, things that trip people up. This saves build from rediscovering them.

**Converge through dialogue.** Like shape, this is a conversation. The AI brings broad technical knowledge and awareness of the landscape. The human brings preferences, team experience, existing infrastructure, and practical constraints. Frame proposes, the human decides.

## Capture choices in the context

Changes to the context follow from conversation, not the other way around. Discuss first, agree, then write. Never update the context unilaterally.

When technology choices are made and the human agrees, update `.do/context.md`. The context should capture:

- **Technology choices**: Language, framework, tools, runtime
- **Environment facts**: Paths, deployment targets, infrastructure
- **Conventions**: Naming, structure, patterns to follow
- **Practices and gotchas**: Idiomatic usage, things to watch out for

The context captures choices and environment facts that affect how future work is done. It does not capture build outputs, runtime statistics, or results from specific runs — those are ephemeral and belong in commit messages or session notes, not in a document that steers the next build.

The context is a living document. Revisiting choices is normal — switching from Node to Bun, or adding a new tool, is just a context update. The spec doesn't change because the problem didn't change.

## Working on do's own context

Frame can target either the current project's context or do's own context. By default it works on the project. When explicitly directed to work on do itself, read the context at the do plugin's location instead.

## What you don't do

- Don't change the spec — if the spec needs updating, that's shape's job
- Don't implement — that's build's job. Frame chooses the tools, build uses them
- Don't over-research — converge on decisions, don't endlessly compare options
- Don't add ceremony — if a question doesn't help converge on an approach, don't ask it
