# do-redo

## What this is

A collaborative sensemaking system. Two parties — a human and an AI — converge on shared understanding of a problem and its solution through dialogue, with that understanding externalized in persistent documents that survive across sessions.

The human brings domain knowledge, intent, and constraints they may not be able to fully articulate. The AI brings pattern recognition, broad technical knowledge, and the ability to structure fuzzy ideas. Neither fully understands the problem at the start. Understanding emerges through the exchange, not from either party working alone.

The spec is the externalized shared mental model — the single document where understanding meets. It captures what we're trying to achieve and what must hold true while we achieve it. The context captures the approach — technology, conventions, plan, and progress. Together they are the complete re-entry point: any new session reads them and picks up where the last one left off.

This spec is both the description of the process and the first application of it.

## The problem it solves

Working with AI on complex projects breaks down over time. Context is lost between sessions. Constraints that live only in the human's head get violated. The human re-explains. The AI drifts. The cycle repeats.

The root cause: there is no persistent, shared source of truth that captures what we're trying to achieve and what must hold true while we achieve it.

The spec solves this by persisting across sessions. At the start of any new session, the AI reads the spec and re-enters the shared understanding. No re-explanation needed. The spec is the re-entry point. The first shape session creates the spec. Every session after that reads it.

## Where the spec and context live

The root spec lives at `.do/spec.md` and the root context at `.do/context.md`. These are always loaded — passive context available on every turn without the AI needing to decide to look them up. The root level is the integration layer: cross-cutting intent, shared constraints, how components relate, shared conventions, and environment facts.

When a problem has distinct components with different concerns, each gets its own folder under `.do/`. The trigger for decomposition is logical separation, not size — two components with different concerns should be separate from the start, even if they'd fit in one file. Each component folder is a workspace containing `spec.md` and `context.md` as the structured core, plus whatever supporting material the component needs — designs, images, reference data, Figma exports, anything that helps shape or build understand it. The root spec acts as an index — a compressed map of what components exist and how they relate.

The spec describes what; the context describes with-what, in-what-order, and where-we-are. They exist at both levels. The root context captures shared conventions and environment. Component contexts capture component-specific technology choices, definition of done, and build status. Same spec with different context produces different valid implementations.

The context is not the spec. The spec is portable and technology-agnostic. The context is specific and may vary per environment or team. They change for different reasons — the spec changes when understanding of the problem evolves, the context changes when technology choices, plans, or progress change.

The context is a shared document. Shape writes the approach — technology choices, conventions, environment facts, the plan for what to build next, and the definition of done — what verification and completion looks like for this project. Build writes status — what's done, what's blocked, what decisions are pending. The definition of done tells build what to drive toward: for an infrastructure project it might mean "config applied, cluster healthy"; for a library it might mean "tests pass, package builds." This makes the context the complete handoff between sessions: shape plans, build executes and reports, the next session picks up from what the context says.

## How it works

Two skills — shape and build — expressed as a Claude Code plugin. Skills run in the main agent context for human interaction only. The main context is reserved for dialogue and orchestration — all other work (file reading, research, implementation) runs in subagents. Skills use structured sequential thinking when a problem has enough dimensions that reasoning in a single pass would lose nuance. Skills signal their activity so the human can see what's happening and at what phase.

Each skill is an instruction set the agent reads fresh each session. A well-formed skill makes three things unambiguous: what to do and in what order (protocol), what must always hold (rules), and what to apply situationally (techniques). An agent following the skill should produce consistent behavior — the same skill with the same inputs should yield recognizably similar sessions.

### Shape

The dialogue skill. Shape is how the human and AI talk about the project — both what it should do and how to build it. It writes to two files only: the spec and the context. Intent, constraints, and behavior go in the spec; technology choices, conventions, plan, and environment go in the context. Shape does not create, edit, or delete any other files — no code, no config, no skill files. That's build's job. Shape routes internally based on what the conversation is about.

Shape is a brainstorm where both parties contribute what the other lacks. The human brings domain knowledge and intent. The AI brings pattern recognition and the ability to connect ideas to established concepts. Both propose, challenge, and refine. But the human has final authority. Shape never writes to the spec or context unilaterally — changes are discussed and agreed first, then captured.

When decisions arise, shape presents structured choices — not prose questions buried in output. Each exchange should make the shared understanding more precise.

When the conversation touches technology — language, framework, tools, deployment — shape evaluates options against the spec's constraints, surfaces tradeoffs, and captures choices in the context. Before researching new options, it audits what's already in place, comparing current tooling against ecosystem best practices and surfacing gaps.

Shape sometimes starts from existing code rather than a blank page. When this happens, the code is evidence, not the spec. Code details become probes to surface intent — but the spec is written from the human's answers, not from the code structure.

Shape periodically steps back to assess the spec as a whole — is it still coherent? Has it accumulated redundancy or fragmentation through incremental changes? Could the same intent be expressed more clearly? This zoom-out is not a separate operation but a mode shape enters when the spec has grown or shifted enough to warrant it.

Shape writes a project CLAUDE.md with the skill boundary principle: shape writes to `.do/` spec and context only, all other file modifications go through build. This ensures the agent respects skill boundaries on every session. CLAUDE.md is loaded into context on every turn, so the instruction is always visible.

Shape can target either the current project or do itself. By default it works on the project.

### Build

The execution skill. Build drives work to completion through two phases — planning and execution — separated by a structural gate.

**Planning phase.** Build reads the spec and context, enters plan mode, and explores the codebase. Plan mode constrains build to read-only operations — no files are created or modified during planning. Build produces a concrete plan: work decomposed into tasks, each with its test specified alongside its implementation goal. The plan makes visible what will be built, in what order, and how each piece will be verified. Exiting plan mode requires human approval — the plan is reviewed before any implementation begins.

The plan is the complete execution contract. It must be self-sufficient — executable by an agent with no context beyond the plan itself. This means the plan carries everything forward from the planning phase: the execution mechanism (how tasks are dispatched and isolated), execution conventions (TDD order, coding standards, quality gates), relevant codebase patterns and file paths, and enough context per task that no prior knowledge is assumed. After plan approval, the plan may be the only instruction set available — skill instructions loaded at session start may not survive the handoff. The plan must stand alone. The planning phase's value is absorbing the spec, context, and codebase, then distilling that into a plan that loses nothing at the handoff.

**Execution phase.** After plan approval, build implements. Each task follows test-driven development: the test specified in the plan is written first, then the minimum implementation to pass it. Execution runs without interruption — the plan approval is the permission gate. Build uses judgment on architecture, patterns, and approach within the boundaries the plan establishes.

Build interacts with the human during planning when multiple valid paths exist. During execution, build follows the approved plan. If execution reveals something the plan didn't anticipate — a spec ambiguity, a technical constraint, a mismatch — build stops and flags it rather than deviating silently.

When the context defines quality conventions, build sets up quality infrastructure first — the config files that encode those conventions. This precedes application code.

After building, build compares the result to the spec and context. Mismatches are evidence for the human to route — either the spec, context, or implementation needs updating. That decision belongs to the human.

When build reaches its limit — finished, blocked, or between components — it produces concrete next steps and writes factual status to the context. The context becomes the handoff: the next session reads it and knows where to resume.

This feedback loop is the core mechanism. Build produces evidence. Shape incorporates that evidence into shared understanding. The cycle continues until spec, context, and implementation agree.

### Commands

Commands are single-purpose actions. Unlike skills, they don't participate in the shape/build cycle — they run, produce output, and finish. They don't maintain state in `.do/` files. Some read the spec and context for orientation, but none write to them.

Three commands:

- **Release** (`/do:release`) — operational. Detects all version sources in the project, bumps them, updates the changelog from git history, syncs README prose against actual code changes, commits, tags, and pushes. The only command that makes changes. Accepts a bump type (patch, minor, major) or infers it from the commit history.
- **Audit** (`/do:audit`) — analytical. Evaluates the tech stack, patterns, dependencies, and practices against current best practices and community conventions. Researches what a greenfield project would look like today. Produces opinionated findings prioritized by impact-to-effort ratio. Does not make changes.
- **Challenge** (`/do:challenge`) — analytical. Reviews the project from a product manager's perspective — pressure-tests the value proposition, questions assumptions, identifies gaps, and researches the competitive landscape. Produces findings grounded in evidence. Does not propose technical solutions.

Audit and challenge are the bridge to shape: they produce raw material — findings — that the human can route into shape to evolve the spec or context. Release operates independently on completed work.

The distinction: skills are collaborative and stateful — they evolve shared understanding over sessions. Commands are fire-and-forget — they do one thing and they're done.

### Gap detection through version control

When a project is under version control, each skill checks what changed since the last commit at session start. The diff is evidence of what happened between sessions — each skill reads it through its own lens.

- **Shape** reads code, dependency, and implementation diffs against both the spec and context. If the code changed in ways the spec doesn't account for, shape surfaces it — was this intentional, or should the spec catch up? If tools or infrastructure changed without a context update, shape surfaces that too. Shape also uses commit history to detect recurring patterns — repeated fixes in the same area signal something that may need rethinking.
- **Build** reads spec and context diffs to see what understanding or choices evolved, and focuses its work accordingly.

The diff is a conversation starter, not an action trigger. Each skill uses it to ask better questions and focus its work, not to act unilaterally. When version control isn't available, the skills work without it.

## What the spec contains

- **Intent**: What we're trying to achieve. Starts vague, sharpens over time.
- **Constraints**: Things that must hold. Conceptual constraints (the system must be simple) belong in the spec. Environmental and technology constraints (must use Python, must run on X) belong in the context.
- **Understanding**: Concepts, patterns, and frameworks we've identified together that inform the solution.

The spec is written for both audiences — the human and the AI. The human carries context between sessions; the AI reads the spec fresh each time. The language should serve both: clear enough for the human to skim and confirm, structured enough for the AI to act on without ambiguity.

Behavior exists at two levels, and the spec captures both:

- **User-facing behavior**: What the user does and what they see. "The user swipes to vote on a selfie."
- **System behavior**: What happens behind the scenes when an event occurs — triggers, cascades, pipelines, side-effect chains. "When a vote is created, the system updates selfie counts, recalculates the owner's stats, updates leaderboard buckets, checks for milestones, and queues a notification."

For simple systems, user-facing behavior may be sufficient. For systems with backend processes, scheduled jobs, event-driven triggers, or multi-step pipelines, the process chains are the behavior that most constrains architecture. A build agent that knows the features but not the cascades will invent a different system. Capture both levels.

Every line should describe intent, state a constraint, or capture understanding that affects future decisions. Two categories don't belong:

- **Deliberation artifacts**: justifications, rationale for rejected alternatives, explanatory prose that doesn't change behavior. Those were resolved in conversation.
- **Implementation artifacts**: file paths, API field names, specific code changes, deletion checklists, line numbers. These feel concrete and actionable, which is why they slip in — but they describe what exists or what to change, not what to achieve. They belong in context or in build's task list.

**When the system produces artifacts, define their properties.** A spec that describes a system generating reports, APIs, config files, or any other output should define what properties those artifacts must have — not their format, but what makes them well-formed. This gives build a target and gives shape a question to ask: "what properties must this output have?"

**The spec contains no explanations.** Everything is specification. Build treats every section as actionable — either something to implement, a constraint to respect, or understanding that steers decisions. If a section describes behavior, build builds it. If it states a property, build ensures it holds. There is no "background context" in the spec — that's what `context.md` is for. This means shape must write concretely: when a conversation surfaces something that needs to be built, capture it as behavior (what it does, what it takes, what it produces), not as a concept (why it matters, what category it belongs to).

The spec is not a contract system. It's not numbered requirements. It's a living document in plain language. When the problem has distinct components with different concerns, decompose — each component gets its own folder under `.do/` with a spec, context, and whatever supporting material it needs.

## Constraints

- **Simplicity above all.** Eliminate before solving. Reuse before building. The right amount of complexity is the minimum needed for the current problem. This hierarchy — eliminate > reuse > configure > extend > build — is the default approach for all work driven by this process.
- **Outcomes over mechanisms.** The spec describes what, not how. The AI is trusted to choose the best approach.
- **The spec and context are the source of truth.** If they disagree with the solution, something needs to change. Which one depends on whether understanding, technology choices, or the implementation drifted.
- **Human authority.** Both human and AI contribute to shaping the spec. Understanding flows both ways. But the human has final say on what the spec contains.
- **No ceremony for ceremony's sake.** If a step in the process doesn't directly help us converge on understanding or build the right thing, it doesn't belong.

## Bootstrapping

This spec describes a process for writing and implementing specs. The tools built from this spec are used to write better specs, which produce better tools, which write better specs. Each cycle sharpens both.
