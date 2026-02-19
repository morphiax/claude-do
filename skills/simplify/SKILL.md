---
name: simplify
description: "Analyze code or text for simplification opportunities using cascade thinking and produce a plan with preservation-focused worker roles."
argument-hint: "<target-path> [--scope <pattern>]"
---

# Simplify

Analyze code or text for simplification opportunities using cascade thinking — one insight eliminates multiple components — and produce `.design/plan.json` with preservation-focused worker roles executable via `/do:execute`.

Works on any target: application code, scripts, SKILL.md prompts, configuration files, documentation. The cascade framework applies equally to code duplication and prose redundancy.

Before starting the Flow, Read `skills/shared/lead-protocol.md`. It defines the canonical lead protocol (boundaries, team setup, trace emission, liveness, memory injection). Substitute: {skill}=simplify, {agents}=analysts.

**CRITICAL BOUNDARY: /do:simplify analyzes and plans — it does NOT execute simplifications. Output is `.design/plan.json` for `/do:execute`. This skill is NOT `/do:design` (which decomposes arbitrary goals).**

---

## Clarification Protocol

| ASK (`AskUserQuestion`) when | SKIP when |
|---|---|
| Scope is unbounded with no project context | Any scope is specified |
| Multiple unrelated codebases in workspace | Project has clear boundaries |
| User intent unclear (code cleanup vs architectural simplification vs config reduction vs prompt tightening) | Recent changes provide natural scope |

---

## Flow

### 1. Pre-flight

1. **Lifecycle context**: Run `python3 $PLAN_CLI plan-health-summary .design` and display to user: "Recent runs: {reflection summaries}." Skip if all fields empty. Then: `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event skill-start --skill simplify || true`
2. **Check for ambiguity**: If the target has multiple valid interpretations per the Clarification Protocol, use `AskUserQuestion` before proceeding.
3. **Parse scope argument**:
   - No args: hotspot-prioritized full scan (git churn x complexity heuristic)
   - `--recent`: recently-modified files only
   - Explicit path: narrow analysis to specified directories/files
   - **Always exclude**: `.design/` directory, `node_modules/`, `.git/`
4. Check existing plan: `python3 $PLAN_CLI status .design/plan.json`. If `ok` and `isResume`: ask user "Existing plan has {counts} roles. Overwrite?" If declined, stop.
5. Archive stale artifacts: `python3 $PLAN_CLI archive .design`

### 2. Scope Assessment

1. Scan project metadata (CLAUDE.md, package.json, README) via Bash to understand stack and conventions.
2. Set `context` fields: `stack`, `conventions`, `testCommand`, `buildCommand`.
3. **Target type detection**: Classify the target to select analyst variants:

| Target type | Detected when | Analysts |
|---|---|---|
| **Code** | `.py`, `.js`, `.ts`, `.go`, `.rs`, etc. — or directories containing source files | complexity-analyst (code), pattern-recognizer |
| **Text** | `.md`, `SKILL.md`, `.txt`, `.yaml`, `.json` config — or prompt/doc files | complexity-analyst (text), pattern-recognizer |
| **Mixed** | Directory containing both code and text targets | complexity-analyst (code), pattern-recognizer, plus text findings included |

4. **Architecture-reviewer trigger** (code targets only): Check whether scope crosses service/package boundaries (heuristic: >3 top-level directories in scope or multiple `package.json`/`go.mod`/`Cargo.toml`). If yes, spawn architecture-reviewer as third analyst.
5. **Anti-pattern guards** (text targets — snapshot for regression check):
   - Copy target file(s) to `.design/skill-snapshot.md` (or `.design/text-snapshot/`) via Bash for baseline comparison.
   - **Circular simplification detection**: Check `.design/history/` for recent simplify runs targeting the same files: `ls .design/history/*/expert-*.json 2>/dev/null | tail -5`. If found, warn user: "Previous simplify runs detected. Review history to avoid circular changes."
6. **Memory injection**: Run `python3 $PLAN_CLI memory-search .design/memory.jsonl --goal "simplify {target}" --keywords "simplification,cascade,preservation"`. If `ok: false` or no memories, proceed without injection. Otherwise inject top 3-5 into analyst prompts. **Show user**: "Memory: injecting {count} past learnings — {keyword summaries}."
7. **Announce to user**: "Simplify ({target type}): analyzing {scope description}. Spawning {N} analysts ({names}). Auxiliaries: challenger, scout, integration-verifier, memory-curator."

### 3. Spawn Analysts

Create the team and spawn analysts in parallel.

1. `TeamDelete(team_name: $TEAM_NAME)` (ignore errors), `TeamCreate(team_name: $TEAM_NAME)`. If TeamCreate fails, tell user Agent Teams is required and stop.
2. **TeamCreate health check**: Verify team is reachable. If verification fails, `TeamDelete`, then retry `TeamCreate` once. If retry fails, abort with clear error message.
3. `TaskCreate` for each analyst.
4. Spawn analysts as teammates using the Task tool. For each analyst:
   - Before Task call: `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event spawn --skill simplify --agent "{analyst-name}" || true`
   - Use Task with `team_name: $TEAM_NAME`, `name: "{analyst-name}"`, and `model: "sonnet"`.
   - Instruct: "Save your complete findings to `.design/expert-{name}.json` as structured JSON."
   - Instruct: "Then SendMessage to the lead with a summary."

**Analyst Prompts**:

All analyst prompts MUST include these 5 mandatory constraints in order:

1. **PRESERVATION FIRST**: Never change behavior, only how it's achieved. Test suite must pass before and after every change. For text targets: all original capabilities, instructions, and behavioral outcomes must remain intact.
2. **SYMPTOM-FIRST**: Identify complexity signals before proposing removals. Evidence before recommendation.
3. **BALANCE WARNING**: Simplification that reduces clarity is NOT simplification. Reducing cyclomatic complexity by obscuring logic is a failure. Tightening prose by losing nuance is a failure.
4. **ORGANIZATIONAL CONTEXT**: Flag items where you cannot determine if complexity is intentional. Mark as `organizationalContextNeeded: yes` rather than recommending removal.
5. **CASCADE THINKING**: For every simplification opportunity, ask "If this is true, what else becomes unnecessary?" Report the elimination chain.

Additional constraint for all analysts: **SKIP recursive algorithms — 42% LLM success rate is too risky for autonomous simplification. Flag and report instead.**

---

#### Code Target Analysts

**Complexity-Analyst (code)** — Hotspot analysis, cognitive complexity, dead code, duplication.
- **Tools granted**: Read, Grep, Glob, Bash (for git log, build/test commands, dependency analysis).
- **Tools denied**: Edit, Write, WebSearch, WebFetch.
- Git hotspot heuristic: `git log --format=format: --name-only --since=12.month | sort | uniq -c | sort -nr | head -20`
- Cross-reference git churn with cyclomatic complexity. Report areas with HIGH churn AND HIGH complexity.
- Run the 5-step cascade process on each hotspot found.
- Report findings as structured JSON with: `cascadeOpportunities[]`, `hotspots[]`, `deadCode[]`.

---

#### Text Target Analysts

**Complexity-Analyst (text)** — Token weight, dead rules, information density, redundancy.
- **Tools granted**: Read, Grep, Glob, Bash (for wc, diff, git log).
- **Tools denied**: Edit, Write, WebSearch, WebFetch.
- Measure total line count and estimate token weight of each major section.
- Identify: dead rules (instructions that can never trigger), redundant constraints (same thing stated differently in multiple places), verbose prose that could be a table, sections that repeat information available elsewhere.
- For SKILL.md targets: check whether referenced plan.py commands exist (`python3 $PLAN_CLI <command> --help`), whether protocol steps have clear success/failure handling, whether constraints are enforceable or merely aspirational.
- Report findings as structured JSON with: `cascadeOpportunities[]`, `heavySections[]`, `deadRules[]`, `redundancies[]`.

---

#### Universal Analyst (both target types)

**Pattern-Recognizer** — Cascade opportunities, over-engineering, unused abstractions.
- **Tools granted**: Read, Grep, Glob, Bash.
- **Tools denied**: Edit, Write.
- Apply the symptom table as primary analytical lens. For EVERY symptom found, run the 5-step process. Report cascade opportunities with eliminationCount.
- **PRIMARY LENS: "Everything is a special case of..."** — This is the core collapse mechanism. Before analyzing any target, ask: what's the unifying principle that makes multiple components unnecessary? One powerful abstraction > ten clever hacks. The pattern is usually already there, just needs recognition.
- Core question: **"What if they're all the same thing underneath?"**
- Ambition calibration: Seek 10x wins (structural collapses), not 10% improvements. Measure in "how many things can we delete?"

Include in pattern-recognizer prompt:

**Simplification Cascades — Symptom Table**

| Symptom | Cascade |
|---|---|
| Same thing implemented/stated 5+ ways | Abstract the common pattern |
| Growing special case list | Find the general case |
| Complex rules with exceptions | Find the rule that has no exceptions |
| Excessive config options | Find defaults that work for 95% |
| Same instruction repeated across sections (text) | State once, reference elsewhere |
| Verbose prose describing what a table could show (text) | Replace with structured table |

**Red flags** (verbal patterns signaling cascade opportunity):
- "We just need to add one more case..." (repeating forever)
- "These are all similar but different" (maybe they're the same?)
- "Refactoring feels like whack-a-mole" (fix one, break another)
- "Growing configuration file"
- "Don't touch that, it's complicated" (complexity hiding pattern)

**5-Step Cascade Process**:
1. List the variations — What's implemented/stated multiple ways?
2. Find the essence — What's the same underneath?
3. Extract abstraction — What's the domain-independent pattern?
4. Test it — Do all cases fit cleanly?
5. Measure cascade — How many things become unnecessary?

**DO/DON'T Calibration Table**:

| DO | DON'T |
|---|---|
| Name a unifying insight that eliminates 2+ components | Report "remove unused imports" as a cascade finding |
| Provide file paths and elimination counts | Give abstract descriptions without evidence |
| Flag organizational context uncertainty | Recommend removal of code/text you can't explain |
| Skip recursive algorithms (42% success rate) | Attempt to simplify recursive algorithms |
| Report cascade chains with concrete evidence | Conflate line-level cleanup with structural cascades |
| Test whether ALL variations fit the abstraction | Propose partial unifications as complete cascades |

**Worked Example 1: Stream Abstraction (code)**
- Before: Separate handlers for batch/real-time/file/network data
- Insight: All inputs are streams — just different sources
- After: One stream processor, multiple stream sources
- Eliminated: 4 separate handler implementations (eliminationCount: 4)

**Worked Example 2: Resource Governance (code)**
- Before: Session tracking, rate limiting, file validation, connection pooling as separate systems
- Insight: All are per-entity resource limits
- After: One ResourceGovernor with 4 resource types
- Eliminated: 4 custom enforcement systems (eliminationCount: 4)

**Worked Example 3: Liveness Protocol Unification (text)**
- Before: 6 SKILL.md files each define their own liveness pipeline with identical timeout/re-spawn/proceed rules copied verbatim
- Insight: All liveness pipelines are the same protocol — just different agent names
- After: One shared "Liveness Pipeline" reference section, each skill references it
- Eliminated: 5 redundant liveness pipeline definitions (eliminationCount: 5)

**Worked Example 4: Immutability (paradigm-level cascade)**
- Before: Defensive copying, locking, cache invalidation, temporal coupling — all separate synchronization mechanisms
- Insight: Treat everything as immutable data + transformations — the paradigm shift eliminates entire classes of problems
- After: Functional programming patterns with immutable data structures
- Eliminated: Entire categories of synchronization, cache invalidation, and temporal coupling bugs (eliminationCount: 4+)
- Note: This example shows cascades can operate at the PARADIGM level, not just the component level. Look for paradigm shifts that make whole problem categories disappear.

Each analyst finding must include:
```json
{
  "type": "eliminate|unify|clarify",
  "scope": "code|architecture|config|text|prompt",
  "target": "specific component or pattern",
  "cascade": "what else becomes unnecessary",
  "eliminationCount": 0,
  "risk": "low|medium|high",
  "organizationalContextNeeded": "yes|no",
  "evidence": "concrete grep/git command output or file references"
}
```

**Architecture-Reviewer** (conditional — code targets only, when scope crosses service boundaries):
- **Tools granted**: Read, Grep, Glob, Bash.
- **Tools denied**: Edit, Write.
- Focus: component count reduction, interface seam elimination, cross-boundary unification.

5. **Analyst liveness pipeline**: Apply the Liveness Pipeline from `lead-protocol.md`. Track completion per analyst: (a) SendMessage received AND (b) artifact file exists (`ls .design/expert-{name}.json`). Show user status: "Analyst progress: {name} done ({M}/{N} complete)."

### 3.5. Cascade-First Resolution

When both complexity-analyst and pattern-recognizer target the same file or area:

1. **Corroborating findings** (same direction): Merge into single role with combined evidence. Higher confidence.
2. **Cascade precedence**: When findings conflict on approach, the finding with `eliminationCount >= 2` takes precedence (it is a cascade; the other is not).
3. **Genuine contradictions**: When both have cascades but in incompatible directions, escalate to user via `designDecisions[]` in plan.json: `{conflict, experts, decision, reasoning}`. **Show user**: "Contradiction: {analyst A} recommends {X}, {analyst B} recommends {Y}. Choosing {decision} because {reasoning}."

### 4. Synthesize into Plan

**Announce to user**: "Synthesizing analyst findings into simplification roles."

1. Collect all analyst findings from messages and `.design/expert-*.json` files via Bash.
2. Validate artifacts: `python3 $PLAN_CLI expert-validate .design/expert-{name}.json` for each.
3. **Organizational context gate**: Collect all findings with `organizationalContextNeeded: yes`. Present to user as a review block:

```
Organizational Context Review:
Items where AI cannot determine if complexity is intentional:

1. {target} — {evidence} — [approve for simplification / dismiss]
2. {target} — {evidence} — [approve for simplification / dismiss]
...

Use AskUserQuestion: "These items may have invisible organizational reasons for their complexity. Which should be included in the simplification plan? (list numbers, or 'none', or 'all')"
```

If ALL findings are `organizationalContextNeeded: yes` with no actionable simplifications, present findings to user and ask whether to proceed with approved items or abort. Never produce an empty plan.json.

4. **Filter and prioritize**: Group actionable findings by type (eliminate, unify, clarify). Prioritize by `eliminationCount` (higher = more cascade impact).
5. **Map cascades to roles**: One role per cascade chain. A cascade chain is a single unifying insight and all the eliminations it enables. Use dependency ordering: abstraction-first, elimination-after. Example: Role 0 implements new abstraction, Role 1 eliminates old implementation A (depends on Role 0), Role 2 eliminates old implementation B (depends on Role 0).
6. **Write plan.json** with role briefs. For every role:
   - `constraints[0]` MUST be: "PRESERVATION FIRST: Never change behavior, only how it's achieved. All original features, outputs, and behaviors must remain intact."
   - `acceptanceCriteria[0]` MUST be: `{"criterion": "All existing tests pass", "check": "{context.testCommand}"}` — test-suite-pass is always first and mandatory. For text-only targets without a test command, use a structural check instead (e.g., YAML frontmatter parses, referenced commands exist).
   - Include `expertContext[]` referencing analyst artifacts with relevance notes.
   - Include rollbackTriggers: test failure, security path detection, organizational context gap.
   - Add constraint: "SKIP recursive algorithms — flag and report instead."

   **Acceptance criteria anti-patterns** (NEVER use as sole check):
   - `grep -q "pattern" file` — verifies text exists, not that feature works
   - `test -f output.json` — file exists but may contain errors
   - `wc -l file` — verifies size, not correctness
   - `cmd || echo "fallback"` or `cmd || true` — always exits 0, masks failures
   - `cmd | tail -N` — pipe may mask exit code

7. **Anti-pattern guards** (CRITICAL — do NOT proceed to finalize if any guard triggers without user approval):
   - **Token budget** (text targets): Calculate net token delta for proposed changes. If total would increase target beyond its current size, ask user to approve flagged changes explicitly.
   - **Circular simplification**: If `.design/history/` contains a previous simplify run, check whether any proposed change reverses a previous simplification. If found, ask user to review before proceeding.
   - **Regression safety**: No capability may be lost. For text targets: no behavioral instruction may be removed without replacement. If a change tightens one area but risks losing nuance in another, note the trade-off and ask user to approve.
8. **Validate checks**: `python3 $PLAN_CLI validate-checks .design/plan.json`. If errors found, fix obvious syntax errors. Non-blocking — proceed even if some checks remain unfixable, but flag to user.
9. If simplification requires updating CLAUDE.md or README.md to stay in sync (per pre-commit checklist), add a `docs-updater` role.
10. Add `auxiliaryRoles[]`:

```json
[
  {
    "name": "challenger",
    "type": "pre-execution",
    "goal": "Review plan and analyst artifacts. Challenge assumptions about what is safe to remove. Be adversarial — assume simplifications will break things and prove otherwise.",
    "model": "sonnet",
    "trigger": "before-execution"
  },
  {
    "name": "scout",
    "type": "pre-execution",
    "goal": "Read actual codebase structure in scope directories. Verify analyst assumptions match reality. Flag discrepancies. Check that referenced code actually exists.",
    "model": "sonnet",
    "trigger": "before-execution"
  },
  {
    "name": "integration-verifier",
    "type": "post-execution",
    "goal": "Run full test suite. Check cross-role contracts. Validate all acceptanceCriteria. Verify behavioral preservation end-to-end. For text targets: verify YAML frontmatter, internal references, and that referenced commands still exist.",
    "model": "sonnet",
    "trigger": "after-all-roles-complete"
  },
  {
    "name": "memory-curator",
    "type": "post-execution",
    "goal": "Distill simplification learnings: cascade effectiveness, preservation success rate, organizational context handling. Apply five quality gates before storing to .design/memory.jsonl.",
    "model": "haiku",
    "trigger": "after-all-roles-complete"
  }
]
```

11. **Finalize**: `python3 $PLAN_CLI finalize .design/plan.json`. Validates structure, computes directory overlaps, computes checksums. If finalize fails, fix validation errors and retry (max 2 attempts). If still failing, ask user for help.
12. **Draft plan review**: Display draft plan to user:

```
Simplification Plan ({roleCount} roles, target type: {code|text|mixed}):
- Role 0: {name} — {goal one-line} [{model}]
- Role 1: {name} — {goal one-line} [{model}] [after: {dependencies}]
...
Cascade impact: {total eliminationCount across all roles}
Design decisions: {count}
Organizational context items: {approved count}/{total count}
```

### 5. Complete

1. Validate: `python3 $PLAN_CLI status .design/plan.json`. Stop if `ok: false`.
2. Shut down teammates, delete team.
3. Clean up TaskList (delete all planning tasks so `/do:execute` starts clean).
4. Summary: `python3 $PLAN_CLI summary .design/plan.json`. Display a rich end-of-run summary:

```
Simplification Analysis Complete: {target}
Target type: {code|text|mixed}

Roles ({roleCount}):
  - Role 0: {name} ({model}) — {goal one-line}
  - Role 1: {name} ({model}) [after: {dependencies}] — {goal one-line}

Cascade Impact:
- Total elimination count: {sum of eliminationCount across findings}
- Cascade chains: {count of distinct cascade chains}

Design Decisions: {count}
Organizational Context: {approved}/{total} items approved by user
Memories applied: {count or "none"}

Run /do:execute to begin simplification.
```

5. **Self-reflection** — Assess: (a) Analysts well-chosen? (b) Cascade analysis depth sufficient? (c) Organizational context handling worked? (d) What differently next time?

```bash
echo '{"targetType":"<code|text|mixed>","analystQuality":"<which analysts contributed most/least>","cascadeDepth":"<deep structural|mostly surface>","preservationConfidence":"<high|medium|low>","organizationalContextItems":<count>,"whatWorked":["<item>"],"whatFailed":["<item>"],"doNextTime":["<item>"]}' | python3 $PLAN_CLI reflection-add .design/reflection.jsonl --skill simplify --goal "<the target>" --outcome "<completed|partial|failed|aborted>" --goal-achieved <true|false>
python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event skill-complete --skill simplify || true
```

On failure: proceed (not blocking).

**Fallback** (if finalize fails):
1. Fix validation errors and re-run finalize.
2. If structure is fundamentally broken: rebuild plan inline from analyst findings, one role at a time.

---

## Contracts

### plan.json (schemaVersion 4)

Output follows the standard plan.json contract — same schema as `/do:design` output. `/do:execute` reads this file directly.

**Top-level fields**: schemaVersion (4), goal, context {stack, conventions, testCommand, buildCommand, lsp}, expertArtifacts [{name, path, summary}], designDecisions [], verificationSpecs [] (optional), roles[], auxiliaryRoles[], progress {completedRoles: []}

**Role fields**: name, goal, model, scope {directories, patterns, dependencies}, expertContext [{expert, artifact, relevance}], constraints [], acceptanceCriteria [{criterion, check}], assumptions [{text, severity}], rollbackTriggers [], fallback. Status fields (status, result, attempts, directoryOverlaps) initialized by finalize.

**Simplification-specific role constraints**:
- `constraints[0]` is always PRESERVATION FIRST
- `acceptanceCriteria[0]` is always test-suite-pass (or structural check for text-only targets)
- Recursive algorithms are always flagged, never simplified
- Dependencies follow abstraction-first ordering (new abstraction before old eliminations)

### Analysis Artifacts

Preserved in `.design/` for execute workers:
- `expert-{name}.json` — per-analyst findings (structured JSON with cascade opportunities, hotspots, evidence)
- `skill-snapshot.md` or `text-snapshot/` — baseline copy of text targets for regression comparison (text targets only)

**Target**: $ARGUMENTS
