# do-redo

## What this is

A Claude Code plugin that provides two skills — `/shape` and `/build` — for collaborative problem-solving between a human and an AI, where neither party fully understands the problem at the start, but together they converge on both understanding and solution.

The human brings domain knowledge, intent, and constraints they may not be able to fully articulate. The AI brings broad technical knowledge, pattern recognition, and the ability to structure fuzzy ideas. The spec is the shared document where their understanding meets.

This spec is both the description of the process and the first application of it.

## The problem it solves

Working with AI on complex projects breaks down over time. Context is lost between sessions. Constraints that live only in the human's head get violated. The human re-explains. The AI drifts. The cycle repeats.

The root cause: there is no persistent, shared source of truth that captures what we're trying to achieve and what must hold true while we achieve it.

The spec solves this by persisting across sessions. At the start of any new session, the AI reads the spec and re-enters the shared understanding. No re-explanation needed. The spec is the re-entry point. The first shape session creates the spec. Every session after that reads it.

## Where the spec lives

The root spec lives at `.do/spec.md`. This file is always loaded — it's passive context available on every turn without the AI needing to decide to look it up.

When a problem decomposes into smaller problems, each gets its own spec under `.do/specs/`. The root spec acts as an index — a compressed map of what exists and where to find it. Sub-specs contain the full detail for their scope. The AI reads the root spec on every session and pulls in sub-specs as needed.

## How it works

Two operations, expressed as skills. That's it.

### Shape

A conversation that evolves the spec. Not a drafting exercise — a dialogue. The AI asks questions, the human answers, and those answers may lead to new questions. Understanding emerges through the exchange, not from either party working alone.

When decisions arise, shape uses structured questions to get quick, clear human input. The conversation narrows the circle — each exchange makes the shared understanding more precise.

Shape is not one-directional. The human isn't dictating requirements. The AI isn't just transcribing. It's a brainstorm where both contribute what the other lacks. But the human has final authority over the spec. Shape never writes to the spec unilaterally — changes are discussed and agreed in conversation first, then captured.

### Build

Read the spec. Implement what it describes. Use judgment on technology, architecture, patterns, and approach — the spec describes outcomes and constraints, not mechanisms.

After building, compare the result to the spec. When a mismatch is found, build stops and flags it. It doesn't silently deviate and it doesn't unilaterally fix the spec. The mismatch feeds back into shape — either the spec needs updating (our understanding evolved) or the implementation needs fixing (it drifted from intent). That decision belongs to the human.

This feedback loop is the core mechanism. Build produces evidence. Shape incorporates that evidence into shared understanding. The cycle continues until spec and implementation agree.

## What the spec contains

- **Intent**: What we're trying to achieve. Starts vague, sharpens over time.
- **Constraints**: Things that must hold. Both conceptual (the system must be simple) and environmental (must use Python, must run on X).
- **Understanding**: Concepts, patterns, and frameworks we've identified together that inform the solution.

The spec is written for both audiences — the human and the AI. The human carries context between sessions; the AI reads the spec fresh each time. The language should serve both: clear enough for the human to skim and confirm, structured enough for the AI to act on without ambiguity.

The spec is not a contract system. It's not numbered requirements. It's a living document in plain language. If it's getting long or complex, that's a signal to decompose — break the problem into smaller problems, each with their own spec under `.do/specs/`.

## Constraints

- **Simplicity above all.** Eliminate before solving. Reuse before building. The right amount of complexity is the minimum needed for the current problem. This hierarchy — eliminate > reuse > configure > extend > build — is the default approach for all work driven by this process.
- **Outcomes over mechanisms.** The spec describes what, not how. The AI is trusted to choose the best approach.
- **The spec is the source of truth.** If the spec and the solution disagree, one of them needs to change. Which one depends on whether our understanding has evolved.
- **Human authority.** Both human and AI contribute to shaping the spec. Understanding flows both ways. But the human has final say on what the spec contains.
- **No ceremony for ceremony's sake.** If a step in the process doesn't directly help us converge on understanding or build the right thing, it doesn't belong.

## Bootstrapping

This spec describes a process for writing and implementing specs. The tools built from this spec are used to write better specs, which produce better tools, which write better specs. Each cycle sharpens both.
