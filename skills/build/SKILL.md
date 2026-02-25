---
name: build
description: "Implement what the spec describes. Compare result to spec. Flag divergences."
argument-hint: "[what to build or fix] — or omit to implement the full spec"
---

# Build

You are implementing what the spec and context describe. The spec is the source of truth for intent and constraints. The context establishes the technology choices and environment. You choose how to get there within those boundaries.

## Read the spec and context first

Read `.do/spec.md` and `.do/context.md`. The spec tells you what to build and why. The context tells you what to build it with — language, framework, tools, conventions. If the root spec references sub-specs under `.do/specs/`, read those too.

If there's no context file, use your judgment on technology — but flag that the context is missing so frame can establish it.

## Check what changed

When the project is under version control, check what changed in the spec and context since the last commit (`git diff .do/`) before starting. The diff shows what understanding or technology choices evolved — it's the most direct signal of what needs to be built or rebuilt. When version control isn't available, skip this step.

## What you do

**Implement.** Read the spec and context, then build what they describe. Use your judgment on architecture, patterns, and approach within the technology choices the context establishes. The spec tells you what and why. The context tells you with-what. You decide the rest.

**Prefer simplicity.** Apply the hierarchy: eliminate the need before solving it. Reuse an existing solution before building one. Configure before extending. Extend before creating from scratch. Build the minimum that satisfies the spec.

**Compare.** After building, compare the result to the spec and context. Does the implementation satisfy the intent? Does it respect the constraints? Does it use the technology the context establishes?

**Stop on mismatch.** When you find a mismatch, stop and flag it. Don't silently deviate and don't unilaterally fix the spec or context. The mismatch is evidence — it means either the spec needs updating (understanding evolved), the context needs updating (technology choice doesn't fit), or the implementation needs fixing (it drifted). That decision belongs to the human. Raise it so they can take it back to shape or frame, or tell you to fix the implementation.

## Track progress with tasks

When the build involves multiple components — more than one file, module, or logical piece — use the task list to track progress:

1. **Decompose** the work into tasks using TaskCreate before writing code. Each task should be one buildable unit (a module, a template, a test suite).
2. **Mark in_progress** when you start a task, **completed** when it's done and verified.
3. **Check the list** at the start of any session. If tasks already exist, resume from where you left off rather than starting over.

This makes multi-component builds visible and resumable. The human can see what's done, what's in progress, and what's left — especially useful across sessions.

Skip the task list for trivial builds (single file, quick fix). Use it when the work has enough parts that tracking matters.

## The feedback loop

Build produces evidence. When you implement something and discover that the spec is ambiguous, the context is incomplete, or something doesn't work in practice — that's valuable. Flag it clearly. That evidence feeds back into shape (for spec issues) or frame (for technology/context issues), where the shared understanding gets updated. Then build continues.

This loop — build, compare, flag, shape/frame, build again — is how spec, context, and implementation converge.

## What you don't do

- Don't silently reinterpret the spec — if something is unclear, ask or flag it
- Don't over-build — the spec describes the scope, stay within it
- Don't modify the spec or context — if they need changing, say so and let shape or frame handle it
- Don't add ceremony that the spec doesn't call for
