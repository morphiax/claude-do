---
name: build
description: "Implement what the spec describes. Compare result to spec. Flag divergences."
argument-hint: "[what to build or fix] — or omit to implement the full spec"
---

# Build

You are implementing what the spec and context describe. The spec is the source of truth for intent and constraints. The context establishes the technology choices and environment. You choose how to get there within those boundaries.

## Signal activation

Create a task with TaskCreate: subject "Build from spec", activeForm "Building from spec…". Set it to `in_progress` immediately. Update the activeForm as you progress (e.g., "Setting up quality infrastructure…", "Writing tests…", "Implementing…", "Comparing to spec…"). Mark `completed` when the build is done and verified.

## Read the spec and context first

Read `.do/spec.md` and `.do/context.md`. The spec tells you what to build and why. The context tells you what to build it with — language, framework, tools, conventions. If the root spec references sub-specs under `.do/specs/`, read those too.

If there's no context file, use your judgment on technology — but flag that the context is missing so frame can establish it.

## Check what changed

When the project is under version control, check what changed in the spec and context since the last commit (`git diff .do/`) before starting. The diff shows what understanding or technology choices evolved — it's the most direct signal of what needs to be built or rebuilt. When version control isn't available, skip this step.

## What you do

**Treat the spec as all specification.** The spec contains no explanations, no background context, no philosophy. Every section is either intent (build it), a constraint (enforce it), or understanding (use it to make decisions). If a section describes behavior — even abstractly — that behavior needs to exist in the implementation. Don't classify any section as "just context" or "nice to know." That's what `context.md` is for. If it's in the spec, it's work.

**Set up quality infrastructure first.** When the context defines quality conventions (linter, formatter, test runner), create the config files that encode them before writing application code — `.prettierrc`, `eslint.config.js`, `ruff.toml`, test runner config, etc. The config files are the source of truth for quality practices; `context.md` has the human-readable summary, config files have the machine-readable details.

**Delegate implementation to subagents.** Spawn subagents via the Task tool for each build task. Use haiku for mechanical work (config files, boilerplate), sonnet for moderate implementation (straightforward modules, test suites), opus for complex work (architectural code, nuanced logic). The main context stays clean — it orchestrates and verifies, subagents do the writing.

**Test first, then implement.** For every piece of behavior, write a failing test before writing the implementation. The test describes what the code should do. Then write the minimum code to make it pass — nothing more. No code exists without a test that demands it. This is not optional; it is how build works.

**Prefer simplicity.** Apply the hierarchy: eliminate the need before solving it. Reuse an existing solution before building one. Configure before extending. Extend before creating from scratch. TDD enforces this naturally — you only write code a test demands.

**Think through decomposition and comparison with sequential thinking.** When breaking the spec into buildable units, or when comparing the finished implementation against the spec, use the `sequentialthinking` tool to work through it methodically. Each thought can map a spec section to an implementation task, flag a gap, revise an earlier decomposition as dependencies become clear, or trace a constraint through multiple files. This catches mismatches that a quick scan would miss. Don't use it for straightforward single-file builds — use it when the spec-to-implementation mapping has enough moving parts to benefit from structured reasoning.

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
