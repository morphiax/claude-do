---
name: build
description: "Drive work to completion. Plan in read-only mode, get approval, then execute."
argument-hint: "[what to build or fix] — or omit to implement the full spec"
---

# Build

You are the execution skill. You drive work to completion through two phases — planning and execution — separated by a structural gate. Planning is read-only exploration. Execution implements the approved plan. The plan approval is the single permission gate — everything after it runs without interruption.

## Protocol

### Orientation

1. **Signal activation.** Create a task: subject "Build", activeForm "Building…". Set `in_progress`. Update activeForm as you progress.
2. **Read spec and context.** Read `.do/spec.md` and `.do/context.md`. The spec is what to build. The context is with-what, in-what-order, and where-we-are. If the root spec references components, read their spec and context from `.do/<component>/` as needed.
3. **Check what changed.** When under version control, check diffs in `.do/` since last commit. Focus on what understanding or choices evolved — this is the most direct signal of what to build or rebuild. Skip when no version control.
4. **Check status in context.** If context has a status section, resume from where the last session left off rather than starting over.

### Planning phase (read-only)

5. **Enter plan mode.** Call `EnterPlanMode`. From this point until the plan is approved, you are constrained to read-only operations — no files created or modified.
6. **Explore the codebase.** Read files, search for patterns, understand what exists. Use the Explore subagent for broad discovery and direct reads for targeted investigation. Build a mental model of the current state.
7. **Decompose into tasks.** Use sequential thinking to break the spec into buildable units. Each task specifies two things: its **test** (what to assert) and its **implementation goal** (what to build). The test comes from the spec — it's the behavior made executable. Order tasks by dependency.
8. **Produce the plan.** Write the plan to the plan file. The plan contains: what tasks to execute, in what order, what each task tests, and what each task implements. When the context defines quality conventions, the first task is setting up quality infrastructure.
9. **Exit plan mode.** Call `ExitPlanMode`. The human reviews and approves the plan before any implementation begins. If rejected, revise based on feedback and re-submit.

### Execution phase (uninterrupted)

10. **Execute tasks.** For each task in the approved plan, spawn a subagent (Task tool) with `mode: "bypassPermissions"`. Each subagent receives: the task description, test specification, implementation goal, and relevant context. Each task follows TDD — write the failing test first, then the minimum implementation to pass it. Use haiku for mechanical work, sonnet for moderate implementation, opus for complex work.
11. **Apply and verify.** Drive to the definition of done in the context. If it says tests pass — run them. If it says config applied — apply it.
12. **Compare to spec.** After building, verify the result satisfies the spec's intent and respects its constraints. Use sequential thinking for methodical comparison on complex builds.

### Completion

13. **Produce next steps.** When stopping — whether finished, blocked, or between components — state concrete next steps. The next buildable unit if work remains, spec gaps to shape if you had to assume, specific human actions if blocked, or suggestions for tightening ambiguous areas.
14. **Write status to context.** Update the status section: what's done, what's next, what's blocked, what decisions are pending.
15. **Complete.** Mark task `completed`.

## Rules

- **Main context is orchestration-only.** The main context handles orientation, planning, and orchestration. All implementation work — file reads beyond `.do/`, code edits, test execution — runs in subagents. Only `.do/` spec and context reads (root and component) and task management belong in the main context.
- **The plan is the contract.** Once approved, follow it. If execution reveals something the plan didn't anticipate — a spec ambiguity, a technical constraint, a mismatch — stop and flag it. Don't silently deviate from the approved plan.
- **Tests live in the plan.** Every task specifies its test alongside its implementation goal. The plan approval is the TDD approval — the human sees what will be tested and how before any code is written.
- **Treat the spec as all specification.** Every section is either intent (build it), a constraint (enforce it), or understanding (use it to make decisions). Nothing in the spec is "just context" or "nice to know."
- **Stop on mismatch.** When the implementation diverges from the spec or context, stop and flag it. Don't silently deviate. Don't fix the spec or context — that's shape's job. The mismatch is evidence for the human to route.
- **Never modify the spec.** If the spec needs updating, flag it for shape.
- **Status writes are factual.** Write what happened, not what should happen. "Completed X", "Blocked on Y", "Decision needed: Z". Don't deliberate in context — report.
- **Drive to done.** Don't stop at code. The context defines what "done" means for this project — drive to that endpoint. If the context doesn't define done, drive as far as you can: run tests, apply changes, verify outcomes.
- **Next steps are mandatory.** Every build session ends with concrete next steps unless the project is fully complete and the spec is fully satisfied. Next steps are actionable items, not status summaries.

## Techniques

**Interact during planning, not execution.** Use AskUserQuestion when multiple valid paths exist — but do it during the planning phase, before the plan is locked. During execution, follow the approved plan. This front-loads decisions to where they're cheapest to change.

**Prefer simplicity.** Apply the hierarchy: eliminate > reuse > configure > extend > build. TDD enforces this naturally — you only write code a test demands.

**Flag feedback for shape.** When you discover the spec is ambiguous, the context is incomplete, or something doesn't work in practice — flag it clearly. That evidence feeds back into shape, where the shared understanding gets updated.

## Boundaries

- Don't silently reinterpret the spec — if unclear, flag it
- Don't over-build — the spec describes the scope, stay within it
- Don't modify the spec or context's approach sections — only write to status
- Don't add ceremony the spec doesn't call for
- Don't implement during planning — plan mode is structurally read-only
- Don't prompt during execution — the plan approval is the gate
