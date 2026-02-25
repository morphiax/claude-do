# do-redo

## What this is

A Claude Code plugin that provides three skills — `/shape`, `/frame`, and `/build` — for collaborative problem-solving between a human and an AI, where neither party fully understands the problem at the start, but together they converge on both understanding and solution.

The human brings domain knowledge, intent, and constraints they may not be able to fully articulate. The AI brings broad technical knowledge, pattern recognition, and the ability to structure fuzzy ideas. The spec is the shared document where their understanding meets.

This spec is both the description of the process and the first application of it.

## The problem it solves

Working with AI on complex projects breaks down over time. Context is lost between sessions. Constraints that live only in the human's head get violated. The human re-explains. The AI drifts. The cycle repeats.

The root cause: there is no persistent, shared source of truth that captures what we're trying to achieve and what must hold true while we achieve it.

The spec solves this by persisting across sessions. At the start of any new session, the AI reads the spec and re-enters the shared understanding. No re-explanation needed. The spec is the re-entry point. The first shape session creates the spec. Every session after that reads it.

## Where the spec lives

The root spec lives at `.do/spec.md`. This file is always loaded — it's passive context available on every turn without the AI needing to decide to look it up.

When a problem decomposes into smaller problems, each gets its own spec under `.do/specs/`. The root spec acts as an index — a compressed map of what exists and where to find it. Sub-specs contain the full detail for their scope. The AI reads the root spec on every session and pulls in sub-specs as needed.

## Where the context lives

The context lives at `.do/context.md`, alongside the spec. It captures the specific choices and facts that steer the build — language, framework, deployment target, paths, conventions. The spec describes what; the context describes with-what. Same spec with different context produces different valid implementations.

The context is not the spec. The spec is portable and technology-agnostic. The context is specific and may vary per environment or team. They change for different reasons — the spec changes when understanding of the problem evolves, the context changes when technology choices or environment change.

Context captures choices and environment facts that affect how future work is done. It does not capture build outputs, runtime statistics, or results from specific runs — those are ephemeral and belong in commit messages or session notes, not in a document that steers the next build.

## How it works

Three operations, expressed as skills. Each skill runs in the main agent context for human interaction, but delegates heavy lifting — code surveys, research, implementation — to subagents via the Task tool. This keeps the main context clean and focused on the dialogue.

Subagents are spawned with a model tier matching the task complexity: haiku for mechanical work (creating config files, reading and summarizing files), sonnet for moderate work (researching a library, implementing a straightforward module), opus for complex work (architectural decisions, nuanced code requiring deep understanding). The skill chooses the tier per subtask.

### Shape

A conversation that evolves the spec. Not a drafting exercise — a dialogue. The AI asks questions, the human answers, and those answers may lead to new questions. Understanding emerges through the exchange, not from either party working alone.

When decisions arise, shape uses AskUserQuestion to present structured choices — not prose questions buried in output. This gives the human clear, quick decision points. The conversation narrows the circle — each exchange makes the shared understanding more precise.

Shape is not one-directional. The human isn't dictating requirements. The AI isn't just transcribing. It's a brainstorm where both contribute what the other lacks. But the human has final authority over the spec. Shape never writes to the spec unilaterally — changes are discussed and agreed in conversation first, then captured.

Shape sometimes starts from existing code rather than a blank page — the human has built something but never captured the intent behind it. When this happens, the code is evidence, not the spec. Shape does a quick survey to understand the domain, then pivots to the human: what problem were you solving? What was broken? What does success look like? Code details become probes to surface intent — "I see you built X, is that because Y?" — but the spec is written from the human's answers, not from the code structure.

Shape can target either the current project's spec or do's own spec. By default it works on the project. When explicitly directed to work on itself, it reads and evolves the do plugin spec instead.

### Frame

A conversation that converges on the approach. Given a spec, frame explores what to build it with — language, framework, tools, patterns, infrastructure. Before researching new options, it audits what's already in place — comparing the project's current tooling against what's idiomatic for the ecosystem, surfacing gaps between what exists and what best practices expect. It then researches options to fill those gaps, evaluates fit against the spec's constraints, surfaces tradeoffs, and captures idiomatic practices and gotchas for the chosen stack.

Frame also captures quality conventions for the chosen stack — which linter, formatter, test runner, and key configuration choices (e.g., strict TypeScript, ruff with specific rule sets). These are technology decisions, same as choosing a framework or database. They go in `context.md` alongside other stack choices.

Like shape, frame is a dialogue. The AI brings broad technical knowledge and awareness of the landscape. The human brings preferences, team constraints, and existing infrastructure realities. Frame proposes, the human decides. The result is captured in `.do/context.md`.

Frame can revisit choices. Switching from Node to Bun, or Python to Rust, is a context change — update `context.md` and rebuild. The spec doesn't change because the problem didn't change.

### Build

Read the spec and the context. Implement what they describe. Use judgment on architecture, patterns, and approach within the technology choices the context establishes.

When the context defines quality conventions, build's first action is setting up quality infrastructure — the config files that encode those conventions (.prettierrc, eslint config, ruff.toml, test runner config, etc.). This precedes application code. The config files are the source of truth for quality practices; no separate documentation layer is needed. `context.md` has the human-readable summary of conventions, config files have the machine-readable details.

When the build involves multiple components, build decomposes the work into tasks (using the task list) before writing code. Each task is one buildable unit — a module, a template, a test suite. Tasks are marked in_progress when started, completed when done and verified. This makes multi-component builds visible and resumable across sessions. At the start of any session, build checks the task list and resumes from where it left off rather than starting over. Skip the task list for trivial builds (single file, quick fix).

After building, compare the result to the spec and context. When a mismatch is found, build stops and flags it. It doesn't silently deviate and it doesn't unilaterally fix the spec or context. The mismatch feeds back — either the spec needs updating (understanding evolved), the context needs updating (technology choice doesn't fit), or the implementation needs fixing (it drifted). That decision belongs to the human.

This feedback loop is the core mechanism. Build produces evidence. Shape and frame incorporate that evidence into shared understanding. The cycle continues until spec, context, and implementation agree.

### Gap detection through version control

When a project is under version control, each skill checks what changed since the last commit at session start. The diff is evidence of what happened between sessions — each skill reads it through its own lens to detect a specific type of gap between what's documented and what's real.

- **Shape** reads code and implementation diffs against the spec. If the code changed in ways the spec doesn't account for, shape surfaces it: was this intentional, or should the spec catch up? This matters because work often happens outside the shape → frame → build flow — quick fixes, experiments, ad-hoc changes. The diff catches those so the spec stays honest.
- **Build** reads spec and context diffs to see what understanding or technology choices evolved, and focuses its work accordingly.
- **Frame** reads code and dependency diffs against the context. If tools, dependencies, or infrastructure changed without a context update, frame surfaces it. Frame also uses commit history to detect recurring patterns — repeated fixes or reverts in the same area signal a technology choice that isn't working and may need rethinking.

The diff is a conversation starter, not an action trigger. Each skill uses it to ask better questions and focus its work, not to act unilaterally. When version control isn't available, the skills work without it — the diff is a signal, not a requirement.

## What the spec contains

- **Intent**: What we're trying to achieve. Starts vague, sharpens over time.
- **Constraints**: Things that must hold. Conceptual constraints (the system must be simple) belong in the spec. Environmental and technology constraints (must use Python, must run on X) belong in the context.
- **Understanding**: Concepts, patterns, and frameworks we've identified together that inform the solution.

The spec is written for both audiences — the human and the AI. The human carries context between sessions; the AI reads the spec fresh each time. The language should serve both: clear enough for the human to skim and confirm, structured enough for the AI to act on without ambiguity.

Every line should describe intent, state a constraint, or capture understanding that affects future decisions. Justifications, rationale for rejected alternatives, and explanatory prose that doesn't change behavior don't belong — those were resolved in conversation. The spec captures what was decided, not the deliberation.

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
