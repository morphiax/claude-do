---
name: reflect
description: "Honest self-review of the last skill run using structured adversarial thinking. Fixes artifacts in-flight and optionally improves skill instructions."
argument-hint: "[optional: specific focus] [fix-skill: also propose SKILL.md improvements]"
---

# Reflect

Perform an honest, adversarial self-review of the most recent skill run. This skill runs **in the same conversation** as the skill it reviews — you have full context of what happened, what you thought, what you skipped, and what you rationalized.

**This skill exists because automated self-assessment produces garbage.** When an LLM fills in reflection templates at the end of a long run, it defaults to self-congratulation ("researchQuality: thorough"). When a human asks "what went wrong?", the same LLM produces rich, specific, actionable critique. This skill replicates the human's adversarial prompt with a structured thinking sequence grounded in established frameworks.

**Do NOT read `lead-protocol-core.md`.** This skill deliberately breaks from the lead protocol. No team setup, no trace emission, no phase announcements. Just thinking and writing.

**Two output modes:**
- Default: adversarial review + artifact fixes (plan.json, interfaces.json, etc.)
- With `fix-skill`: also proposes permanent SKILL.md instruction improvements

---

## Foundations

This skill's thinking sequence is built on five established frameworks:

| Framework | Source | What it contributes |
|---|---|---|
| After Action Review (AAR) | US Army, 1970s | Intended vs actual outcome comparison — forces the gap to be articulated |
| Backward Chaining | Goal-directed reasoning | Work backwards from ideal to find what steps were needed but skipped |
| "Could You Be Wrong?" | Hills, 2025 — metacognitive debiasing | Surfaces latent counter-evidence the model has but doesn't volunteer |
| Pre-mortem | Klein, 2007 — prospective hindsight | Assume failure has already happened — increases risk identification by 30% |
| Double-loop Learning | Argyris, 1977 | Question the approach itself, not just the execution |

---

## Flow

### 1. Context Gathering

Identify what to reflect on. Do this silently — no user output needed.

1. Check `.design/` for recent artifacts. Determine which skill last ran and what was produced. **Store this skill name** — you will need it in Step 6 for the `--skill` argument:
   - `research.json` → research skill → `--skill research`
   - `plan.json` → design or simplify skill → `--skill design` or `--skill simplify`
   - Worker artifacts, role results → execute skill → `--skill execute`
2. Read the key output artifact(s) to ground the reflection in what was actually produced.
3. **Parse arguments**: Check if `$ARGUMENTS` contains `fix-skill`. If present, enable the Skill Improvement phase (Step 5). Everything else in `$ARGUMENTS` is the focus scope.
4. If the user provided a focus argument (excluding `fix-skill`), scope the reflection to that aspect.
5. If no recent skill artifacts exist, tell the user: "No recent skill output found in `.design/`. Run a skill first, then reflect."
6. **User input during reflection**: If the user provides observations or feedback during the reflection run (mid-conversation messages), incorporate them as high-priority signal. User observations are the highest-quality input available — they see things the model rationalizes away. Integrate user feedback into the thinking steps and, if relevant, into fix-skill proposals.

### 2. Adversarial Thinking

Use `sequential-thinking` (the MCP tool) to work through adversarial steps. **Do not rush. Do not be kind to yourself. The value of this skill is proportional to its honesty.**

**Adaptive depth**: For simple reviews (1-2 roles, no cross-review, clear outcome), use 3 steps: AAR (Step 1) + Could You Be Wrong (Step 3) + Pre-mortem (Step 4). For complex reviews (3+ roles, cross-review occurred, expert artifacts present, or ambiguous outcome), use all 5 steps. Steps 2 (Backward Chaining) and 5 (Double-loop) have diminishing returns on simple reviews but are essential when the approach itself might be wrong.

**Step 1 — After Action Review: Intended vs Actual**

> "What was the ideal outcome for this goal? Describe specifically what a perfect output would look like — what it would contain, what quality level it would hit, what questions it would answer. Now describe what was actually produced. Name the gaps concretely — not 'could be better' but 'missing X, shallow on Y, wrong about Z'."

**Step 2 — Backward Chaining: What steps were needed?**

> "Working backwards from that ideal outcome — what specific actions, investigations, or decisions would have produced it? List them. Now check: which of those did we actually do? Which did we skip, shortcut, or do superficially? For each skipped step, why was it skipped — was it a conscious tradeoff or did we just not think of it?"

**Step 3 — Could You Be Wrong?**

> "Look at what we produced. Where could we be wrong? What assumptions did we make that we didn't verify with evidence? What information did we have access to but didn't use? What counter-evidence or alternative interpretations exist that we didn't consider? What do we claim with high confidence that is actually uncertain?"

This step is the highest-leverage single intervention. Research shows it accesses latent knowledge the model already has but doesn't surface without adversarial prompting (Hills, 2025).

**Step 4 — Pre-mortem: Assume failure**

> "Imagine someone takes this output and acts on it — builds the system, follows the recommendation, uses the design. It fails. What went wrong? What was missing from our output that they needed? What was misleading? What edge case or real-world condition did we not account for? Also consider the user's experience during this run: what was unclear, what required them to intervene or ask for clarification, what output did they have to interpret without enough context? User friction during the run is a pre-mortem signal — if the user had to ask a clarifying question, the skill's output failed to communicate something."

**Step 5 — Double-loop: Was the approach right?**

> "Step back from execution quality. Was the approach itself correct? Should we have used a different skill, scoped differently, asked different questions, or framed the problem differently? If we started completely over with what we know now, what would we do instead? This isn't about doing the same thing better — it's about whether we did the right thing."

**After structural analysis, evaluate instructional quality**: Is the written output (SKILL.md changes, plan.json instructions, expert guidance) clear enough that a new lead would follow it correctly on first read? Ambiguous instructions are gaps, not style issues. Reflect gravitates toward testable/structural issues (CLI flags, file existence) — actively resist this bias by also evaluating clarity, specificity, and potential for misinterpretation.

**Output format quality**: Evaluate the reviewed skill's user-facing output (conversation markdown shown to the user, not just artifact files). Did the summary directly answer each part of the user's original question? Could the user take action from the summary alone without reading `.design/` artifacts? Was output organized to mirror the user's question structure (e.g., if they asked 3 things, are all 3 clearly addressed)? Was the most important finding (the "headline") immediately visible, not buried in a table? Poor communication of correct findings is a gap — note it in the prose.

### 2.5. Memory Cross-Reference

After adversarial thinking produces findings, cross-reference against `.design/memory.jsonl` to detect recurrence patterns. This step enriches the synthesis without biasing the thinking — memories are consulted AFTER independent analysis, not before.

```bash
PLAN_CLI=<resolved path>
# For each significant finding from Step 2, search memory by keywords:
python3 $PLAN_CLI memory-search .design/memory.jsonl --goal "{finding summary}" --keywords "{finding keywords}"
```

For each match:
- **Recurring pattern**: The same issue was stored as a memory from a prior run → note this in the synthesis. If a SKILL.md fix was applied for it previously (check the memory's content), flag that the fix didn't prevent recurrence — this is high-severity signal.
- **Already known**: The finding duplicates an existing memory → lower its novelty in the synthesis. Still worth mentioning if it recurred despite being "known."
- **Genuinely new**: No memory matches → stronger candidate for memory curation after this run.

**Show user** (if any matches found): "Memory cross-reference: {N} findings match prior learnings. {recurring_count} are recurring patterns."

Skip this step if `.design/memory.jsonl` doesn't exist or if adversarial thinking produced no significant findings.

### 3. Synthesis

After completing sequential-thinking, write the reflection as **free-form prose**. Not bullet points. Not JSON fields. Prose — because the nuance, uncertainty, and connections between observations are the value.

The prose should be structured in sections mirroring the thinking steps, but written naturally — as if explaining to a colleague what you'd do differently. Include:

- **Specific observations** — file names, data sources, concrete gaps. Not "research was shallow" but "we never inspected the live RCI.co.za DOM to verify that the CSS selectors from the existing scraper still work."
- **Severity signals** — distinguish between minor polish issues and fundamental gaps that would cause downstream failure.
- **What actually worked** — this isn't only about criticism. Identify what was genuinely good, so future runs preserve it. But be specific — "the codebase analysis was thorough" is useless; "the codebase analyst correctly identified that availability data is scraped but silently dropped at the service worker boundary (CS-001)" is useful.

### 3.5. Plan Verification (design/simplify output only)

**Trigger**: The reviewed skill produced `.design/plan.json` (i.e., skill is design or simplify). **Skip for** execute/research reviews.

Reflect's prose analysis identifies gaps through reasoning. This step verifies them against the codebase — replacing the challenger and scout auxiliaries that execute previously ran.

Spawn a single Task agent:
```
Task(subagent_type: "general-purpose", model: "sonnet")
```

Prompt — **scope the verification to risks identified by thinking steps**, not generic "check everything":
- "Read `.design/plan.json` and all `.design/expert-*.json` artifacts."
- "Read actual project files in each role's scope.directories."
- "**Priority verifications** (from adversarial thinking): {list the specific risks, unverified claims, and CLI signature questions identified in Steps 1-5}. These are the highest-value checks — verify them first."
- "**Standard cross-reference**: Do field names in the plan schema match actual data source field names? Do referenced files contain expected data (not empty)? Do AC check commands reference valid paths and tools? Do interface contracts match actual code signatures?"
- "Save findings to `.design/plan-verification.json`: `{\"verified\": [{\"claim\": \"...\", \"source\": \"...\", \"actual\": \"...\", \"match\": true|false}], \"issues\": [{\"severity\": \"blocking|high-risk|low-risk\", \"description\": \"...\", \"affectedRoles\": [...], \"recommendation\": \"...\"}]}`"

Process results: blocking issues feed into Step 4 (Resolution) as mandatory patches. High-risk issues become warnings in the prose. This replaces challenger+scout — one focused agent instead of two, with reflect's full conversation context informing what to verify.

### 4. Resolution — Fix Artifacts

**Trigger**: gapSeverity is "significant" or "fundamental" AND the reviewed skill produced modifiable artifacts (plan.json, interfaces.json, research.json).

**Skip if**: gapSeverity is "minor" — record observations in the reflection prose only. Minor issues don't warrant artifact modification. **For "moderate" severity**: skip resolution by default, BUT if any finding is a concrete, trivially fixable gap (e.g., a missing AC check, a wrong field name, a constraint with no verification), apply that targeted fix. The threshold protects against over-engineering, not against leaving known 30-second fixes on the table.

**Process**:

1. Use `sequential-thinking` to translate each significant gap from the prose into a concrete artifact patch. For each gap, determine:
   - Which artifact file? (`.design/plan.json`, `.design/interfaces.json`, `.design/research.json`)
   - What type of change? (add constraint, fix AC check, modify role scope, add field, correct assumption)
   - What is the exact edit?

2. Present patches to user via `AskUserQuestion`:
   ```
   "Reflection found {N} artifact issues to fix. Apply?"
   Options:
   - "Apply all" — apply all patches
   - "Review each" — present each patch individually for approval
   - "Skip" — record in reflection only, don't modify artifacts
   ```

3. If approved, apply patches:
   - For plan.json: use Bash with `python3 -c "import json; ..."` to read, modify, and write back
   - For other artifacts: same pattern
   - After modifying plan.json: re-run `python3 $PLAN_CLI validate-checks .design/plan.json` and `python3 $PLAN_CLI finalize .design/plan.json` to ensure integrity

4. **Verify fixes**: After applying any artifact fix that changes a CLI command pattern or interface, run the corrected pattern against a test file to verify it works. Do not deploy untested fixes — structural plausibility is not proof of correctness.

5. Record what was applied in the reflection output under `resolutionsApplied[]`.

**What resolution can do:**
- Add or modify constraints on roles
- Fix broken or weak acceptance criteria checks
- Correct interface contracts in interfaces.json
- Add missing fields to schema definitions
- Fix incorrect format assumptions

**What resolution cannot do:**
- Add or remove entire roles (that's a redesign — suggest re-running `/do:design`)
- Change the goal
- Modify files outside `.design/`

### 5. Skill Improvement — Fix Instructions

**Trigger**: `fix-skill` flag present in arguments. **Skip entirely if not present.**

This phase proposes permanent improvements to SKILL.md files so the same class of error is prevented in ALL future runs, not just patched for this project.

**IMPORTANT: Always edit the MARKETPLACE copy of SKILL.md files** at `~/.claude/plugins/marketplaces/do/skills/{skill}/SKILL.md` — NOT the cache copy at `~/.claude/plugins/cache/do/do/*/skills/{skill}/SKILL.md`. The cache is regenerated from the marketplace; edits to cache files will be lost.

**Process**:

1. From the adversarial thinking (Step 2) and resolution (Step 4), identify findings that are **general** — they would prevent the same error class regardless of project, goal, or technology stack. Filter out project-specific findings. Also evaluate each `doNextTime` item from the reflection prose — if an item describes a general process improvement (not project-specific), draft it as a SKILL.md proposal. Do not stop after the first fix; evaluate all candidates up to the 3-fix cap.

   **General examples**: "Design should verify that data files contain actual data, not just check file existence", "Experts should be instructed to verify their claims against actual output, not just code structure"

   **Project-specific examples**: "The RCI scraper uses UpdatePanel postbacks", "The availability.json uses a dict wrapper not an array"

2. For each general finding, use `sequential-thinking` to draft a specific SKILL.md change:
   - Target file: which SKILL.md? (design, research, execute, reflect, simplify)
   - Target section: which step or section?
   - Change type: add instruction, add constraint, add check, strengthen existing instruction
   - Exact text: the specific addition or modification (keep small — one sentence or one bullet)
   - Rationale: what class of error this prevents

3. Present proposals to user via `AskUserQuestion`. **Always list the proposal titles in the question text** so the user knows what they're approving before choosing a review strategy:
   ```
   "{N} SKILL.md improvements proposed: (1) {title}, (2) {title}, (3) {title}. Apply all?"
   Options:
   - "Apply all" — apply all proposals
   - "Review each" — present each individually with before/after context
   - "Skip" — record in reflection only
   ```
   If "Review each" is selected, present each proposal individually with before/after context and "Apply" / "Skip" options.

4. If approved, apply using Edit tool on the target SKILL.md file.

5. Record all proposals and outcomes in the reflection output under `skillImprovements[]`: `[{"targetSkill": "...", "section": "...", "change": "...", "applied": true|false}]`

**Guardrails for skill improvements:**
- Only propose **additive** changes (add a check, add a bullet, strengthen a requirement). Never restructure or rewrite sections.
- Each change must be **small and specific** — one sentence or one bullet point, not paragraphs.
- The change must prevent a **class** of errors, not a specific instance.
- Maximum 3 proposals from adversarial thinking per reflect run — focus on the highest-impact ones. User-requested improvements during the run (mid-conversation feedback) are separate and not counted against this cap.
- Never modify the frontmatter (name, description, argument-hint) — those are interface contracts.

### 6. Save

Write the reflection to `.design/reflection.jsonl` as a single JSONL entry:

```json
{
  "reflection": "the free-form prose from Step 3 — this is the PRIMARY field",
  "gapSeverity": "minor|moderate|significant|fundamental",
  "approachCorrect": true,
  "whatWorked": ["1-3 specific things that genuinely worked — extracted from the prose"],
  "whatFailed": ["1-3 specific gaps or failures — extracted from the prose"],
  "doNextTime": ["1-3 concrete actions for the next run — extracted from the prose"],
  "resolutionsApplied": ["description of each artifact fix applied in Step 4, or empty if skipped"],
  "skillImprovements": [{"targetSkill": "...", "section": "...", "change": "...", "applied": true}]
}
```

The `reflection` field is primary — it's the free-form prose. The other arrays are extracted FROM the prose as a lightweight summary.

**Important**: `reflection-add` will reject the entry if `whatFailed` is non-empty but `promptFixes` is empty. For the reflect skill, either include a `promptFixes` array (even if simple — just `{"section":"n/a","problem":"...","idealOutcome":"...","fix":"...","failureClass":"spec-disobey"}`) or leave `whatFailed` empty and put the failure detail in the prose `reflection` field only.

**IMPORTANT**: The `--skill` argument must be the skill being reviewed (identified in Step 1 — e.g., `design`, `execute`, `research`). This reflection is an evaluation OF that skill's run, so the entry must be attributed to it. **Exception**: For meta-reviews (reflect reviewing reflect itself), `--skill reflect` IS correct — the reviewed skill is reflect.

Save via `reflection-add`:

```bash
echo '<reflection JSON>' | python3 $PLAN_CLI reflection-add .design/reflection.jsonl \
  --skill <reviewed-skill> --goal "<the goal>" --outcome "<completed|partial|failed|aborted>" --goal-achieved <true|false>
```

If the prose is long, write the JSON to a temp file first and pipe it in:

```bash
python3 $PLAN_CLI reflection-add .design/reflection.jsonl \
  --skill <reviewed-skill> --goal "<goal>" --outcome "<outcome>" --goal-achieved <true|false> < /tmp/reflect-eval.json
```

### 7. Display

Show the user a concise summary:

```
Reflection: {reviewed-skill} — {goal}

Gap severity: {minor|moderate|significant|fundamental}
Approach correct: {yes|no — one sentence why}

What worked:
- {specific strength — name concrete files, patterns, or decisions}

Top omissions:
- {specific gap — name what was missing and why it matters}

{if resolutions applied:}
Resolutions:
| Artifact | Change | Impact |
|----------|--------|--------|
| {file} | {what changed} | {why it matters} |

{if skill improvements applied:}
Skill improvements:
| Skill | Section | Change |
|-------|---------|--------|
| {skill} | {section} | {one-line description} |

{else: "Resolutions: {N applied | skipped | n/a (minor severity)}"}
{else: "Skill improvements: {N applied, M skipped | not requested (no fix-skill flag)}"}

Full reflection saved to .design/reflection.jsonl
```

Do NOT display the full prose — the user can read the file if they want depth. The summary should be scannable in 10 seconds.

---

## Anti-patterns

These are the failure modes this skill is designed to prevent. If you catch yourself doing any of these, stop and restart that thinking step.

| Anti-pattern | Example | Fix |
|---|---|---|
| Vague praise | "The research was thorough and well-structured" | Name what specifically was thorough and what was not |
| Template-filling | "gapSeverity: minor" without justification | The severity must follow from the prose, not precede it |
| Symmetric critique | Equal weight to real gaps and nitpicks | Distinguish fundamental gaps from polish issues |
| Deflection | "RCI's site is slow so we couldn't..." | Focus on what YOU could have done differently, not external constraints |
| Future-hedging | "We could investigate X in a future iteration" | Say whether X should have been done NOW and why it wasn't |
| Process over substance | "We followed all 6 steps of the research flow" | Following the process is not an outcome — what did the process PRODUCE? |
| Shotgun improvements | Proposing 10 SKILL.md changes from one run | Maximum 3 — pick the highest-impact class of error to prevent |

---

## Why Free-form Prose

The previous reflection system used structured JSON fields (`promptFixes` with 5 required sub-fields, `failureClass` from an enumerated list, `acGradients`, etc.). This produced:

1. **Empty or generic fields** — `whatFailed: []` on "successful" runs, missing the gaps that manual review would catch
2. **Template-optimized answers** — fields like `sectionCoverage: "complete"` that have obvious "right" answers
3. **Lost nuance** — the connections between observations, the severity gradients, the "I knew this but didn't surface it" admissions — these don't fit in structured fields

Free-form prose preserves the richness of honest self-assessment. The lightweight `evaluation` summary provides machine-readable hooks for downstream tools without constraining the thinking.

---

## Script Setup

```bash
PLAN_CLI=$(find "$(dirname "$(dirname "$(cd "$(dirname "$0")" && pwd)")")" -name plan.py -path "*/shared/*" | head -1)
```

If `$PLAN_CLI` is not found, write directly to `.design/reflection.jsonl` — the reflection content matters more than the tooling.
