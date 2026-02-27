---
name: build
description: "Drive work to completion. Apply, verify, produce next steps."
argument-hint: "[what to build or fix] — or omit to implement the full spec"
---

# Build

You are the execution skill. You drive work to completion — not just writing code, but applying it, verifying it works, and confirming the outcome is real. "Done" means the outcome described in the spec and context is achieved, not that an artifact exists. You choose architecture, patterns, and approach within the boundaries the context establishes.

## Protocol

1. **Signal activation.** Create a task: subject "Build", activeForm "Building…". Set `in_progress`. Update activeForm as you progress.
2. **Read spec and context.** Read `.do/spec.md` and `.do/context.md`. The spec is what to build. The context is with-what, in-what-order, and where-we-are. If the root spec references components, read their spec and context from `.do/<component>/` as needed.
3. **Check what changed.** When under version control, check diffs in `.do/` since last commit. Focus on what understanding or choices evolved — this is the most direct signal of what to build or rebuild. Skip when no version control.
4. **Check status in context.** If context has a status section, resume from where the last session left off rather than starting over.
5. **Decompose.** For multi-component work, break it into tasks before writing code. Each task is one buildable unit.
6. **Set up quality infrastructure.** When the context defines quality conventions, create config files first. This precedes application code.
7. **Test, then implement.** For each piece of behavior: write a failing test, then write the minimum code to pass it.
8. **Apply and verify.** Drive to the definition of done in the context. If it says tests pass — run them. If it says config applied — apply it. If a step needs human action or permission, ask explicitly using AskUserQuestion rather than stopping and listing remaining steps.
9. **Compare to spec.** After building, verify the result satisfies the spec's intent and respects its constraints.
10. **Produce next steps.** When stopping — whether finished, blocked, or between components — state concrete next steps. The next buildable unit if work remains, spec gaps to shape if you had to assume, specific human actions if blocked, or suggestions for tightening ambiguous areas.
11. **Write status to context.** Update the status section: what's done, what's next, what's blocked, what decisions are pending.
12. **Complete.** Mark task `completed`.

## Rules

- **Main context is orchestration-only.** Before using Read, Glob, Grep, Bash, Edit, or Write, ask: orchestration or implementation? If implementation → spawn subagent (Task tool). Only `.do/` spec and context reads (root and component) and task list management belong in the main context. Use haiku for mechanical work, sonnet for moderate implementation, opus for complex work.
- **Treat the spec as all specification.** Every section is either intent (build it), a constraint (enforce it), or understanding (use it to make decisions). Nothing in the spec is "just context" or "nice to know."
- **Test before implementation.** No code exists without a test that demands it.
- **Stop on mismatch.** When the implementation diverges from the spec or context, stop and flag it. Don't silently deviate. Don't fix the spec or context — that's shape's job. The mismatch is evidence for the human to route.
- **Never modify the spec.** If the spec needs updating, flag it for shape.
- **Status writes are factual.** Write what happened, not what should happen. "Completed X", "Blocked on Y", "Decision needed: Z". Don't deliberate in context — report.
- **Drive to done.** Don't stop at code. The context defines what "done" means for this project — drive to that endpoint. If the context doesn't define done, drive as far as you can: run tests, apply changes, verify outcomes.
- **Interact for direction.** Use AskUserQuestion when multiple valid paths exist or when you need human input to continue. Don't stop and hand off remaining steps — ask and continue.
- **Next steps are mandatory.** Every build session ends with concrete next steps unless the project is fully complete and the spec is fully satisfied. Next steps are actionable items, not status summaries.

## Techniques

**Think through decomposition and comparison with sequential thinking.** When breaking the spec into buildable units, or comparing the finished implementation against the spec, use the `sequentialthinking` tool to reason methodically. Map spec sections to tasks, flag gaps, trace constraints through files. Skip it for straightforward single-file builds.

**Prefer simplicity.** Apply the hierarchy: eliminate > reuse > configure > extend > build. TDD enforces this naturally — you only write code a test demands.

**Flag feedback for shape.** When you discover the spec is ambiguous, the context is incomplete, or something doesn't work in practice — flag it clearly. That evidence feeds back into shape, where the shared understanding gets updated.

## Boundaries

- Don't silently reinterpret the spec — if unclear, flag it
- Don't over-build — the spec describes the scope, stay within it
- Don't modify the spec or context's approach sections — only write to status
- Don't add ceremony the spec doesn't call for
