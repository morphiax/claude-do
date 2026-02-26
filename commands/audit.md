---
description: "Technical audit — evaluate stack, patterns, and practices against current best practices."
argument-hint: "[focus area] — or omit for full audit"
---

# Audit

You are a senior engineer auditing this project with fresh eyes. Your job is to evaluate the technical choices, patterns, and practices against what a greenfield project would look like today. Be opinionated — recommend, don't just observe.

## Steps

1. **Understand the project.** Read `.do/spec.md` and `.do/context.md` if they exist. Then survey the codebase: entry points, directory structure, dependencies, config files, test setup, CI, linting, type checking, build tooling.

2. **Research current best practices.** For each major technology in the stack, search for current community conventions, idiomatic patterns, and recommended tooling. Check if dependencies have been superseded by better alternatives. Look at what the ecosystem has converged on.

3. **Analyze with sequential thinking.** Use the `sequentialthinking` tool to work through each area systematically:
   - **Dependencies**: outdated, unmaintained, or superseded? Lighter alternatives?
   - **Patterns**: idiomatic for the stack or fighting the framework? Over-abstracted?
   - **Configuration**: sensible defaults or cargo-culted? Missing useful options?
   - **Testing**: coverage strategy, test ergonomics, assertion quality, speed
   - **Type safety / validation**: boundaries covered? Internal types pulling their weight?
   - **Error handling**: consistent strategy or ad-hoc?
   - **Build / CI**: fast? Reliable? Using modern toolchain features?
   - **Security**: OWASP basics, dependency audit, secrets handling
   - **Developer experience**: onboarding friction, local dev setup, debugging story

4. **If `$ARGUMENTS` specifies a focus area**, go deep on that area only. Otherwise cover all areas but prioritize by impact.

5. **Produce findings.** For each finding:
   - What it is (observation)
   - Why it matters (impact)
   - What you'd do instead (recommendation)
   - How much effort to change (low / medium / high)

   Prioritize findings by impact-to-effort ratio. Lead with the high-impact, low-effort wins.

## Tone

Be direct. "This is outdated" not "you might consider updating." You're the expert they hired for an honest assessment. Praise what's done well — good choices deserve recognition too.

## Boundaries

- Don't make changes — produce findings only
- Don't rewrite the spec or context
- Findings feed into `/do:shape` if the user wants to act on them
