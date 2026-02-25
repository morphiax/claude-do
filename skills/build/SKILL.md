---
name: build
description: "Implement what the spec describes. Compare result to spec. Flag divergences."
argument-hint: "[what to build or fix] — or omit to implement the full spec"
---

# Build

You are implementing what the spec describes. The spec is the source of truth for intent and constraints. You choose how to get there.

## Read the spec first

Read `.do/spec.md`. Understand the intent, constraints, and current shared understanding. This is what you're building toward. If the root spec references sub-specs under `.do/specs/`, read those too — the root spec is an index, the detail lives in the sub-specs.

## What you do

**Implement.** Read the spec, then build what it describes. Use your judgment on technology, architecture, patterns, and approach. The spec tells you what and why — you decide how.

**Prefer simplicity.** Apply the hierarchy: eliminate the need before solving it. Reuse an existing solution before building one. Configure before extending. Extend before creating from scratch. Build the minimum that satisfies the spec.

**Compare.** After building, compare the result to the spec. Does the implementation satisfy the intent? Does it respect the constraints?

**Stop on mismatch.** When you find a mismatch between spec and implementation, stop and flag it. Don't silently deviate and don't unilaterally fix the spec. The mismatch is evidence — it means either the spec needs updating (our understanding evolved) or the implementation needs fixing (it drifted from intent). That decision belongs to the human. Raise it so they can take it back to shape or tell you to fix the implementation.

## The feedback loop

Build produces evidence. When you implement something and discover that the spec is ambiguous, incomplete, or describes something that doesn't work in practice — that's valuable. Flag it clearly. That evidence feeds back into shape, where the spec gets updated to reflect the new understanding. Then build continues from the updated spec.

This loop — build, compare, flag, shape, build again — is how the spec and implementation converge.

## What you don't do

- Don't silently reinterpret the spec — if something is unclear, ask or flag it
- Don't over-build — the spec describes the scope, stay within it
- Don't modify the spec — if it needs changing, say so and let shape handle it
- Don't add ceremony that the spec doesn't call for
