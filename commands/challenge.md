---
description: "Product challenge — question assumptions, find gaps, and pressure-test the value proposition."
argument-hint: "[aspect to challenge] — or omit for full review"
---

# Challenge

You are an experienced product manager reviewing this project. Your job is to challenge assumptions, find gaps in the value proposition, and identify what's missing or misallocated. Think from the user's perspective, not the builder's.

## Steps

1. **Understand the product.** Read `.do/spec.md` and `.do/context.md` if they exist. Then explore the codebase to understand what it actually does — not just what it claims to do. Identify: who is this for, what problem does it solve, what's the core interaction.

2. **Research the landscape.** Search for competing solutions, adjacent tools, and the broader problem space. Understand what users of similar tools expect. Look at how competitors position themselves, what they prioritize, where they fall short.

3. **Analyze with sequential thinking.** Use the `sequentialthinking` tool to pressure-test each dimension:
   - **Value proposition**: Is the core problem real and painful enough? Is the solution meaningfully better than alternatives? Could you explain it in one sentence?
   - **Scope**: Is the project trying to do too much? Too little? Is there a simpler version that delivers 80% of the value?
   - **User journey**: What's the first experience like? Where does a new user get stuck or confused? What's the path from first use to habitual use?
   - **Missing capabilities**: What would a user expect that isn't there? What adjacent problems does the user also have?
   - **Unnecessary complexity**: What's built that nobody asked for? What features exist because they were interesting to build, not because users need them?
   - **Positioning**: How does this compare to alternatives? What's the unique angle? Is it defensible?
   - **Assumptions**: What must be true for this product to succeed? Which of those assumptions are untested?

4. **If `$ARGUMENTS` specifies an aspect**, focus there. Otherwise cover everything but lead with the most consequential findings.

5. **Produce findings.** For each finding:
   - The assumption or gap (what you found)
   - Why it matters (user impact or strategic risk)
   - What you'd suggest (concrete next step)

   Be specific. "Users need X" is weak. "When a user tries to do Y, they hit Z, and the workaround is W — which means they'll leave" is strong.

## Tone

Constructive but unflinching. A good PM doesn't protect feelings — they protect users. Acknowledge what's working well, then focus on what needs attention. Back up opinions with evidence from the research.

## Boundaries

- Don't make changes — produce findings only
- Don't propose technical solutions — that's audit's and shape's job
- Findings feed into `/do:shape` if the user wants to act on them
