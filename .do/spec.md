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

## Where the spec lives

The root spec lives at `.do/spec.md`. This file is always loaded — it's passive context available on every turn without the AI needing to decide to look it up.

When a problem decomposes into smaller problems, each gets its own spec under `.do/specs/`. The root spec acts as an index — a compressed map of what exists and where to find it. Sub-specs contain the full detail for their scope. The AI reads the root spec on every session and pulls in sub-specs as needed.

## Where the context lives

The context lives at `.do/context.md`, alongside the spec. It captures everything that steers and tracks the build — technology choices, conventions, environment facts, the current plan, and progress. The spec describes what; the context describes with-what, in-what-order, and where-we-are. Same spec with different context produces different valid implementations.

The context is not the spec. The spec is portable and technology-agnostic. The context is specific and may vary per environment or team. They change for different reasons — the spec changes when understanding of the problem evolves, the context changes when technology choices, plans, or progress change.

The context is a shared document. Shape writes the approach — technology choices, conventions, environment facts, and the plan for what to build next. Build writes status — what's done, what's blocked, what decisions are pending. This makes the context the complete handoff between sessions: shape plans, build executes and reports, the next session picks up from what the context says.

## How it works

Two skills — shape and build — expressed as a Claude Code plugin. Skills run in the main agent context for human interaction only. The main context is reserved for dialogue and orchestration — all other work (file reading, research, implementation) runs in subagents. Skills use structured sequential thinking when a problem has enough dimensions that reasoning in a single pass would lose nuance. Skills signal their activity so the human can see what's happening and at what phase.

Each skill is an instruction set the agent reads fresh each session. A well-formed skill makes three things unambiguous: what to do and in what order (protocol), what must always hold (rules), and what to apply situationally (techniques). An agent following the skill should produce consistent behavior — the same skill with the same inputs should yield recognizably similar sessions.

### Shape

The dialogue skill. Shape is how the human and AI talk about the project — both what it should do and how to build it. It writes to both documents: intent, constraints, and behavior go in the spec; technology choices, conventions, plan, and environment go in the context. Shape routes internally based on what the conversation is about.

Shape is a brainstorm where both parties contribute what the other lacks. The human brings domain knowledge and intent. The AI brings pattern recognition and the ability to connect ideas to established concepts. Both propose, challenge, and refine. But the human has final authority. Shape never writes to the spec or context unilaterally — changes are discussed and agreed first, then captured.

When decisions arise, shape presents structured choices — not prose questions buried in output. Each exchange should make the shared understanding more precise.

When the conversation touches technology — language, framework, tools, deployment — shape evaluates options against the spec's constraints, surfaces tradeoffs, and captures choices in the context. Before researching new options, it audits what's already in place, comparing current tooling against ecosystem best practices and surfacing gaps.

Shape sometimes starts from existing code rather than a blank page. When this happens, the code is evidence, not the spec. Code details become probes to surface intent — but the spec is written from the human's answers, not from the code structure.

Shape periodically steps back to assess the spec as a whole — is it still coherent? Has it accumulated redundancy or fragmentation through incremental changes? Could the same intent be expressed more clearly? This zoom-out is not a separate operation but a mode shape enters when the spec has grown or shifted enough to warrant it.

Shape writes a project CLAUDE.md with file conventions — which files are modified through which skills. This ensures the agent respects skill boundaries on every session. CLAUDE.md is loaded into context on every turn, so the instruction is always visible.

Shape can target either the current project or do itself. By default it works on the project.

### Build

The execution skill. Build reads the spec and context, then implements what they describe. It uses judgment on architecture, patterns, and approach within the boundaries the context establishes.

Build follows test-driven development. For every piece of behavior, build writes a failing test first, then writes the minimum code to make it pass. The test is the specification made executable. This naturally enforces minimality: no code exists without a test that demands it.

When the context defines quality conventions, build sets up quality infrastructure first — the config files that encode those conventions. This precedes application code.

When the build involves multiple components, build decomposes the work into tasks before writing code. Each task is one buildable unit. Tasks are tracked so multi-component builds are visible and resumable across sessions.

After building, build compares the result to the spec and context. When a mismatch is found, build stops and flags it — it doesn't silently deviate and it doesn't unilaterally fix the spec or context. The mismatch is evidence: either the spec needs updating, the context needs updating, or the implementation drifted. That decision belongs to the human.

Build writes status to the context — what's done, what's next, what's blocked, what decisions are pending. This is factual reporting, not deliberation. The context becomes the handoff: the next session reads it and knows where to resume.

This feedback loop is the core mechanism. Build produces evidence. Shape incorporates that evidence into shared understanding. The cycle continues until spec, context, and implementation agree.

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

The spec is not a contract system. It's not numbered requirements. It's a living document in plain language. If it's getting long or complex, that's a signal to decompose — break the problem into smaller problems, each with their own spec under `.do/specs/`.

## Constraints

- **Simplicity above all.** Eliminate before solving. Reuse before building. The right amount of complexity is the minimum needed for the current problem. This hierarchy — eliminate > reuse > configure > extend > build — is the default approach for all work driven by this process.
- **Outcomes over mechanisms.** The spec describes what, not how. The AI is trusted to choose the best approach.
- **The spec and context are the source of truth.** If they disagree with the solution, something needs to change. Which one depends on whether understanding, technology choices, or the implementation drifted.
- **Human authority.** Both human and AI contribute to shaping the spec. Understanding flows both ways. But the human has final say on what the spec contains.
- **No ceremony for ceremony's sake.** If a step in the process doesn't directly help us converge on understanding or build the right thing, it doesn't belong.

## Bootstrapping

This spec describes a process for writing and implementing specs. The tools built from this spec are used to write better specs, which produce better tools, which write better specs. Each cycle sharpens both.
