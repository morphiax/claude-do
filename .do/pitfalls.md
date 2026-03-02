# Pitfalls

## Spec/code drift after execution

**Symptom:** Project files describe behaviors, layouts, or API contracts that don't match the actual implementation. The spec looks correct until someone reads both the spec and the code side by side. New behaviors exist in code but not in spec. Removed behaviors persist in spec.

**Root cause:** After successful execution with passing tests, the system has strong momentum to report completion. The sync step competes with the pull to ship and loses. The implementer considers the task "done" when the code works, not when the spec reflects the code.

**Fix:** The sync gate requires specific output after every execution: enumerate each behavior changed, confirm spec coverage for each, and either propose updates or explicitly state "Sync gate: all changes reflected in project files." The mandatory output format makes skipping visible — a response without a sync gate section is conspicuously incomplete.

**Pattern class:** Dual-representation drift. Any system with two representations of the same truth (docs/code, schema/implementation, spec/tests) suffers this. Aspirational sync instructions fail under momentum. Mechanical gates with required output survive because skipping them produces a visible gap.

## Main context absorbs implementation work

**Symptom:** The orchestrator reads implementation files directly — starting with "just one file to verify" — and soon the context window contains seven files of implementation detail. Task tools are unused. Subagents are never dispatched. The fix works but no structural invariant was followed.

**Root cause:** Subagent dispatch has overhead: formulate a prompt, wait for results, handle incomplete answers. Under efficiency pressure, reading directly feels faster. The rule against main-context reads is negative ("don't do X") and competes with the positive pull to "get the answer now." Once one file is read, the boundary is already broken and subsequent reads feel free.

**Fix:** The context boundary is explicit: main context reads `.do/` files and git commands only. All implementation file reads go to subagents. When a subagent returns incomplete results, dispatch a targeted follow-up with a narrower prompt informed by the first attempt — frame the compliant path as the efficient path, not as compliance overhead.

**Pattern class:** Negative-rule erosion. Rules that say "don't do X" lose to efficiency pressure when X is immediately available. Reframing the compliant path as faster (targeted follow-up vs. unbounded main-context reads) makes compliance the path of least resistance.

## Quick fix bypasses all invariants, not just plan approval

**Symptom:** Small obvious fix is implemented directly in main context. No TaskCreate. No subagent. No sync gate. The fix works but violates every structural invariant — not because the system decided each was unnecessary, but because the heavyweight pipeline was rejected wholesale.

**Root cause:** With only full planning available (enter plan mode, human approval, task creation, subagent dispatch), the system treats small fixes as "not worth the ceremony" and bypasses everything. The all-or-nothing dynamic means rejecting the ceremony also rejects the invariants embedded within it.

**Fix:** The quick-fix execution path provides graduated ceremony: skip plan approval (the unnecessary part) while preserving subagents for implementation, task tools for progress visibility, and the sync gate for knowledge capture. The threshold is clarity (fix is unambiguous), not size.

**Pattern class:** Graduated-path absence. When a process has only a heavyweight path, users and systems bypass the entire process rather than just the unnecessary parts. Provide graduated paths that scale ceremony to task size while preserving core invariants.

## Stop-and-wait instruction ignored before quick fix

**Symptom:** The system states a diagnosis and proposed fix, then immediately dispatches the implementation in the same message. The human never has a chance to redirect, add context, or disagree. Agreement was assumed, not obtained.

**Root cause:** "Get human agreement" is ambiguous — it can mean "state it and proceed unless they object" (optimistic) or "state it and wait for a response" (explicit). The system interprets it optimistically because dispatching immediately feels more efficient, and the instruction doesn't require a message boundary.

**Fix:** The quick-fix sequence says "stop and wait for the human's response" with the rationale inline: "they may have context that changes the approach." The word "stop" requires a message boundary. The rationale converts the rule from arbitrary ceremony into a justified pause.

**Pattern class:** Ambiguous-gate collapse. Instructions that can be interpreted as either blocking or non-blocking will be interpreted as non-blocking under momentum. Use unambiguous verbs ("stop," "wait") and justify the pause so the system understands why it matters.

## Information routed to wrong project file

**Symptom:** A debugging insight ends up in spec.md as a behavioral note. A technology convention appears in decisions.md as a choice rationale. A behavioral contract sits in stack.md as a convention. Future sessions look in the right file and don't find what they need.

**Root cause:** The seven-file routing heuristic requires distinguishing signal types: what it should do (spec) vs. what broke (pitfalls) vs. why we chose this (decisions) vs. how we build (stack). Under time pressure or when content spans multiple categories, the system picks the file it's currently editing rather than the correct target.

**Fix:** Apply the routing function before writing: what should the system DO -> spec, how does an EXTERNAL system work -> reference, TECHNOLOGY choices -> stack, AESTHETIC direction -> design, HOW an algorithm works -> architecture, WHY a choice was made -> decisions, what BROKE -> pitfalls. When content spans categories, split it — the behavioral contract goes to spec, the rationale goes to decisions, the failure that motivated it goes to pitfalls.

**Pattern class:** Routing-under-pressure collapse. When multiple valid destinations exist and the routing function requires thought, the system defaults to proximity (current file) instead of correctness (right file). Explicit routing functions applied before writing prevent this.

## Subagent preamble missing validate_output test

**Symptom:** Subagent produces output that passes its task requirements but fails the system-wide quality bar. Code works but tests assert implementation details instead of behaviors. Spec entries are capability lists without quality bars. The output is functional but doesn't meet the standard.

**Root cause:** The preamble is assembled at dispatch time from project files and task description. If the assembler omits the `validate_output` test — or includes project file content but not the quality gate — the subagent has no way to know the standard. It optimizes for task completion, not quality.

**Fix:** The preamble specification explicitly requires: relevant `.do/` content AND the `validate_output` test. The test is part of the preamble contract, not optional supplementary material. Treat preamble assembly as a checklist: project context, task description, quality gate.

**Pattern class:** Context-window quality decay. When a subagent receives task instructions without quality standards, it produces task-complete but quality-deficient output. Quality gates must travel with the work, not live only in the orchestrator's context.

## Plan tasks that require prior context to execute

**Symptom:** A subagent receives a task description and cannot execute it without information not present in the description. It guesses at file locations, invents patterns that don't match existing code, or asks clarifying questions that the orchestrator already resolved during planning.

**Root cause:** The planner has full context — exploration results, project file knowledge, conversation history — and writes task descriptions that assume the reader shares that context. "Implement the search endpoint" is clear to the planner but useless to a zero-context subagent.

**Fix:** Each task must pass `validate_task`: specific file paths, existing patterns to follow, concrete test assertion, implementation approach with enough detail to start, model tier, and named risks. After writing the plan, re-read it as if you have zero context. If any task requires information not in its description, the plan is underspecified.

**Pattern class:** Curse-of-knowledge in delegation. The delegator's context makes instructions feel complete when they're actually dependent on shared knowledge. The fix is always a zero-context test: can someone with only this text execute the task?
