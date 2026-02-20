---
name: design
description: "Decompose a goal into a structured plan."
argument-hint: "<goal description>"
---

# Design

Decompose a goal into `.design/plan.json` with role briefs — goal-directed scopes for specialist workers. **This skill only designs — it does NOT execute.**

Before starting the Flow, Read `lead-protocol-core.md` and `lead-protocol-teams.md`. They define the canonical lead protocol (boundaries, team setup, trace emission, liveness, memory injection). Substitute: {skill}=design, {agents}=experts.

---

## Clarification Protocol

| ASK (`AskUserQuestion`) when | SKIP when |
|---|---|
| Multiple valid interpretations exist | Codebase contains the answer |
| Scope is underspecified | Standard practice is clear |
| Technology choice is open and impacts approach | Any reasonable choice works |
| Data source is ambiguous | User preference doesn't change approach |

---

## Flow

### 1. Pre-flight

1. **Lifecycle context**: Run Lifecycle Context protocol (see lead-protocol-core.md).
2. **Check for ambiguity**: If the goal has multiple valid interpretations per the Clarification Protocol, use `AskUserQuestion` before proceeding.
3. If >5 roles likely needed, suggest phases. Design only phase 1.
4. Check existing plan: `python3 $PLAN_CLI status .design/plan.json`. If `ok` and `isResume`: ask user "Existing plan has {counts} roles. Overwrite?" If declined, stop.
5. Archive stale artifacts: `python3 $PLAN_CLI archive .design`

### 2. Lead Research

The lead directly assesses the goal to determine needed perspectives.

1. Read the goal. Scan project metadata (CLAUDE.md, package.json, README) via Bash to understand stack.
2. Decide what expert perspectives would help.
3. Assess complexity tier (drives role count and expert depth):

| Tier | Roles |
|---|---|
| Trivial (1-2 roles, obvious approach) | 1-2 |
| Standard (clear domain) | 2-4 |
| Complex (cross-cutting concerns) | 4-6 |
| High-stakes (production, security, data) | 3-8 |

4. Select auxiliary roles. If complexity tier is Trivial (1-2 roles): only memory-curator runs. Otherwise: challenger and integration-verifier always run; scout runs when the goal touches code (implementation, refactoring, bug fixes — not pure docs/research/config).
5. **Announce to user**: Display planned team composition, complexity tier, and auxiliaries: "Design: {complexity tier}, spawning {N} experts ({names}). Auxiliaries: {list}."

**Expert Selection**

Analyze the goal type and spawn appropriate experts:

**Implementation goals** (build/add/create/implement):
- **architect** — system design, patterns, trade-offs
- **researcher** — prior art, libraries, best practices
- **domain specialists** — security, performance, UX, data, etc.

**Meta goals** (improve this plugin, modify SKILL.md, refactor plan.py):
- **prompt-engineer** — for skill improvements (analyzes SKILL.md structure, protocol gaps)
- **maintainer** — for codebase refactoring (analyzes current architecture, proposes improvements)
- **domain specialist** — if goal targets specific domain (e.g., 'improve memory search' → information-retrieval specialist)

**Research/analysis goals** (analyze/audit/document):
- **researcher** — investigates the area being analyzed
- **documenter** — if output is documentation
- **domain specialist** — for domain-specific analysis (security audit → security specialist)

**For complex/high-stakes goals with >=3 experts**: Choose at least 2 experts with contrasting priorities (e.g., performance vs maintainability, security vs usability) to enable productive debate.

**For trivial goals** (1-2 roles, single obvious approach): skip experts. Write the plan directly. Skip to Step 5.

**When uncertain about goal type**: Ask the user to clarify intent before spawning experts.

### 3. Spawn Experts

Create the team and spawn experts in parallel.

1. `TeamDelete(team_name: $TEAM_NAME)` (ignore errors), `TeamCreate(team_name: $TEAM_NAME)`. If TeamCreate fails, tell user Agent Teams is required and stop. If TeamDelete succeeds, a previous session's team was cleaned up.
2. **TeamCreate health check**: Verify team is reachable. If verification fails, `TeamDelete`, then retry `TeamCreate` once. If retry fails, abort with clear error message.
3. **Memory injection**: Run `python3 $PLAN_CLI memory-search .design/memory.jsonl --goal "{goal}" --stack "{stack}"`. If `ok: false` or no memories → proceed without injection. Otherwise inject top 3-5 into expert prompts. **Show user**: "Memory: injecting {count} past learnings — {keyword summaries}." You MUST follow the Reflection Prepend procedure in lead-protocol-core.md step-by-step — do not skip steps.
4. `TaskCreate` for each expert.
5. Spawn experts as teammates using the Task tool. For each expert:
   - Before Task call: `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event spawn --skill design --agent "{expert-name}" --payload '{"model":"sonnet","memoriesInjected":N}' || true`
   - Use Task with `team_name: $TEAM_NAME`, `name: "{expert-name}"`, and `model: "sonnet"` (experts require Read/Grep/Glob/Bash for codebase analysis).
   - Write prompts appropriate to the goal and each expert's focus area. Ask them to score relevant dimensions and trace scenarios.
   - **Behavioral traits**: Include behavioral instructions — tell experts HOW to think, not WHO to be. Examples: "Question assumptions that feel obvious", "Reject solutions that add complexity without clear benefit", "Focus on failure modes before success paths", "Assume prior art exists — search before inventing." Tailor traits to the expert's focus (e.g., architect: "Prefer composable patterns over monolithic solutions"; security specialist: "Assume every input is hostile until validated").
   - **Measurable estimates**: Instruct experts: "Base verification properties and estimates on actual code metrics (file counts, line counts, test coverage, dependency depth) where possible. Read codebase samples to ground estimates. Avoid theoretical predictions — anchor to observable reality."
   - Every expert prompt MUST end with: "In your findings JSON, include a `verificationProperties` section: an array of properties that should hold regardless of implementation (behavioral invariants, boundary conditions, cross-role contracts). Format: `[{\"property\": \"...\", \"category\": \"invariant|boundary|integration\", \"testableVia\": \"how to test this with concrete commands/endpoints\"}]`. Provide concrete, externally observable properties that can be tested without reading source code. When suggesting testableVia commands, avoid anti-patterns: grep-only checks (verifies text exists, not that feature works), `test -f` as sole check (file exists but may contain errors), `wc -l` counts (size not correctness), `|| echo` or `|| true` fallbacks (always exits 0), pipe chains without exit-code handling (may mask failures)."
   - Instruct: "Save your complete findings to `.design/expert-{name}.json` as structured JSON."
   - Instruct: "Then SendMessage to the lead with a summary."
   - Instruct: "If you discover a surprising finding, SendMessage to lead with prefix INSIGHT: followed by one sentence. Maximum one insight message — choose the most surprising."

6. **Expert liveness pipeline**: You MUST follow the Liveness Pipeline procedure in lead-protocol-teams.md step-by-step — do not skip steps.

### 4. Interface Negotiation & Cross-Review

Expert coordination prevents **integration failures** (domains don't fit together) and **convergence failures** (experts reach incompatible conclusions). Assess which phases apply per the decision matrix, then execute them.

**CRITICAL ENFORCEMENT**: The lead MUST NOT perform cross-review solo. Every phase requires actual `SendMessage` calls to experts and collecting their responses. Skipping expert interaction when the decision matrix says a phase is mandatory is a protocol violation.

| Phase | Trigger | Purpose |
|---|---|---|
| **A: Interface negotiation** | >=2 experts whose roles will share data/APIs/file boundaries | Producer-consumer pairs agree on shared interface contracts |
| **B: Perspective reconciliation** | >=2 experts analyzed same domain from different angles, OR >=3 experts in complex/high-stakes tier | Resolve conflicting recommendations about the same thing |
| **C: Cross-domain challenge** | Complex/high-stakes tier with >=3 experts | Catch cross-domain assumptions neither A nor B would surface |

**Decision matrix**: If condition matches → phase is **mandatory**. If <2 experts or trivial tier → skip all phases. **Announce to user** which phases will run: "Cross-review: running {phases} — {brief reason}."

#### Phase Execution Pattern

All phases follow: **maximum 2 rounds** of negotiation per conflict. If no convergence after 2 rounds, lead decides and documents reasoning.

**Phase A steps**:
1. Lead identifies domain boundaries (API shapes, schemas, file formats, shared state)
2. Lead drafts consumer-driven contracts: `{boundary, producer, consumer, contract}` (use format: `Interface: {name}, Producer: {role}, Consumer: {role}, Contract: {concrete spec}`)
3. SendMessage each contract to producer-consumer pair: "Does this work for your domain? Flag constraints."
4. Collect responses, negotiate (max 2 rounds)
5. Save to `.design/interfaces.json` as binding constraints

**Phase B steps**:
1. Lead identifies overlapping analysis (>=2 experts made recommendations about same thing)
2. SendMessage relevant experts (not broadcast): "You both analyzed {topic}. Your positions differ: {A's position} vs {B's position}. Read each other's artifact. Respond: (a) agreements, (b) disagreements + why yours is better, (c) synthesis."
3. Collect responses, negotiate synthesis (max 2 rounds)
4. Lead decides if no convergence, documents trade-off

**Phase C steps**:
1. Broadcast to all experts: "Read OTHER experts' artifacts. Challenge claims affecting your domain. Format: Challenge to {expert}, Claim: '{quote}', Severity: [blocking|important|minor], Evidence: {why problematic}, Alternative: {proposal}. If no challenges: send 'No challenges found'."
2. Collect structured challenge messages
3. Forward each challenge to targeted expert for defense or concession (max 2 rounds per challenge)
4. Lead resolves conflicts, updates `.design/interfaces.json` if contracts changed

**Checkpoint**: Save `.design/cross-review.json` with audit trail: `{phasesRun: ["A"|"B"|"C"], interfaces: {count, rounds}, reconciliations: {count, rounds}, challenges: {sent, resolved}, skippedPhases: [{phase, reason}]}`. If no phases applicable, save with `phasesRun: []` and skip reasons.

### 5. Synthesize into Role Briefs

**Announce to user**: "Synthesizing expert findings into role briefs."

1. Collect all expert findings (messages and `.design/expert-*.json` files).
2. **Resolve conflicts from cross-review** (if debate occurred): For each challenge, evaluate trade-offs and decide. Document resolution in plan.json under `designDecisions[]` (schema: {conflict, experts, decision, reasoning}). **Show user each decision**: "Decision: {conflict} → {chosen approach} ({one-line reasoning})."
3. **Incorporate interface contracts**: If `.design/interfaces.json` was produced in Step 4, add each interface as a constraint on the relevant producer and consumer roles. Interface contracts are binding — workers must implement the agreed interface shape.
4. Identify the specialist roles needed to execute this goal:
   - Each role scopes a **coherent problem domain** for one worker
   - If a role would cross two unrelated domains, split into two roles
   - Workers decide HOW to implement — briefs define WHAT and WHY
5. Write `.design/plan.json` with role briefs (see schema below).
6. For each role, include `expertContext[]` referencing specific expert artifacts and the sections relevant to that role. **Do not lossy-compress expert findings into terse fields** — reference the full artifacts.
7. Write criteria-based `acceptanceCriteria` — define WHAT should work, not WHICH files should exist. Workers verify against criteria, not file lists. **Every criterion MUST have a `check` that is a concrete, independently runnable shell command** (e.g., `"bun run build"`, `"bun test --run"`). Never leave checks as prose descriptions — workers execute these literally. If a role touches compiled code, include BOTH a build check AND a test check as separate criteria. **Checks must verify functional correctness, not just pattern existence.** A grep confirming a CSS rule exists is insufficient — the check must verify the rule actually takes effect (e.g., start a dev server and curl the page, or verify that referenced classes/imports resolve to definitions). At least one criterion per role should test end-to-end behavior, not just file contents. **Check commands must fail-fast with non-zero exit codes on failure.**

   **Learn from past AC mutations**: If `plan-health-summary` returned `acMutations` from recent execute runs, review them before writing checks. Each mutation shows a check that design got wrong and execute had to fix. Common patterns to avoid: wrong test data (e.g., `--skill test` when only design/execute/research/simplify are valid), fragile position checks (e.g., checking first 30 lines when content may shift), version comparisons that pass trivially (e.g., `int(patch) > 0` passes for any non-zero patch). Use the `after` field as a template for better checks.

   **Acceptance criteria anti-patterns** (NEVER use these as the sole check for a criterion):
   - `grep -q "pattern" file` — anti-pattern: verifies text exists, not that feature works
   - `test -f output.json` — anti-pattern: file exists but may contain errors
   - `wc -l file` — anti-pattern: verifies size, not correctness
   - `cmd || echo "fallback"` or `cmd || true` — anti-pattern: always exits 0, masks failures completely
   - `cmd 2>&1 | tail -N` — anti-pattern: pipe may mask exit code unless `set -o pipefail` is used

   **Check command authoring rules** (apply when writing `check` fields):
   - **Ban f-strings in inline Python**: `python3 -c "..."` check commands must NOT use f-strings — nested quotes and backslash escapes inside `"..."` cause `SyntaxError`. Use `.format()` or `%` formatting instead, or move complex logic to a script file.
   - **Prefer script files for complex checks**: When a check requires >1 logical step, write it to a temp file (`python3 /tmp/check_role.py`) instead of inlining with `-c`. Inline `-c` is limited to simple one-liners.
   - **Fail-fast required**: Every check must exit non-zero on failure with no fallback (`|| true`, `|| echo`) that masks the result.

   **Check command template library** — use these patterns, not custom one-offs:

   | Purpose | Template |
   |---|---|
   | File contains pattern (structural only, not sole check) | `grep -q "pattern" path/to/file` |
   | Python script parses JSON without error | `python3 -c "import json; json.load(open('file.json'))"` |
   | Python script validates field (use .format, not f-string) | `python3 -c "import json; d=json.load(open('f.json')); assert d['k']=='v', d['k']"` |
   | Complex Python check (multi-step) | Write to `/tmp/check_rolename.py`, then: `python3 /tmp/check_rolename.py` |
   | Command exits 0 (build/test) | `bun run build` or `python3 -m pytest tests/` |
   | Schema field exists and is non-empty | `python3 -c "import json,sys; d=json.load(open('f.json')); sys.exit(0 if d.get('field') else 1)"` |
   | Count lines/entries in output | `python3 -c "import json; d=json.load(open('f.json')); assert len(d['items'])>=3"` |
   | Shell script file is executable and exits 0 | `bash path/to/script.sh` |

8. Add `auxiliaryRoles[]` (see Auxiliary Roles section).
9. Write to `.design/plan.json` (do NOT run finalize yet — that happens in Step 6).
10. **Draft plan review** (complex/high-stakes tier only): Display the draft plan to the user before finalization:
   ```
   Draft Plan ({roleCount} roles):
   - Role 0: {name} — {goal one-line} [{model}]
   - Role 1: {name} — {goal one-line} [{model}] [after: {dependencies}]
   ...
   Design decisions: {count}
   ```
   This is non-blocking — continue to finalization. If the user objects, adjust before finalizing. For trivial/standard tiers, skip this review.

**Validate acceptance criteria checks (MANDATORY blocking gate)**: Before running finalize, you MUST run `python3 $PLAN_CLI validate-checks .design/plan.json`. If errors are found, display them to the user with role name and criterion, then fix every check command in plan.json before proceeding. Do NOT call finalize until validate-checks reports zero errors. Apply the check command authoring rules above (ban f-strings, prefer script files for complex checks) when rewriting broken checks.

### 6. Generate Verification Specs

Verification specs are property-based tests workers must satisfy. They codify expert verificationProperties as executable tests without constraining implementation.

**When to generate**:

| Condition | Required? | Rationale |
|---|---|---|
| **4+ roles** | **MANDATORY** | Integration complexity requires property-based validation |
| **New skill creation** (new SKILL.md files) | **MANDATORY** | End-to-end workflow must be testable |
| **API integration** (external services, auth, rate limits) | **MANDATORY** | External contracts need verification |
| **1-3 roles** with simple scope | **OPTIONAL** | Acceptance criteria may suffice |
| **Docs-only** or **config-only** changes | **OPTIONAL** | Low integration risk |
| **Sparse verificationProperties** (experts provide <2 properties) | **OPTIONAL** | Insufficient property coverage |

Additional requirements for all cases: expert artifacts contain verificationProperties AND stack supports tests (context.testCommand/buildCommand exists).

**Authorship**: Simple goals (1-3 roles) → lead writes from expert verificationProperties. Complex goals (4+ roles) → spawn spec-writer Task agent with `Task(subagent_type: "general-purpose", model: "sonnet")` that reads expert artifacts + actual codebase, writes specs in `.design/specs/{role-name}.{ext}` using project's test framework or shell scripts, returns created paths.

**Spec generation**:
1. Read expert verificationProperties from all `.design/expert-*.json` files
2. For each role, extract relevant properties (filter by scope/goal alignment)
3. `mkdir -p .design/specs`
4. Write spec files: native tests (`.design/specs/spec-{role-name}.test.{ext}` using bun test/pytest/jest/cargo test/etc with property-based frameworks like fast-check/hypothesis/proptest) OR shell scripts (`.design/specs/spec-{role-name}.sh` with exit 0 = pass)
5. For each spec, add to plan.json's `verificationSpecs[]`: `{"role": "{role-name}", "path": ".design/specs/spec-{role}.{ext}", "runCommand": "{e.g., 'bun test .design/specs/spec-api.test.ts'}", "properties": ["brief descriptions"]}`

**Spec content**: Test WHAT (external behavior), not HOW (implementation). Include positive AND negative cases. Use property-based testing where possible. Test cross-role contracts. Specs must be independently runnable.

**Finalization**: `python3 $PLAN_CLI finalize .design/plan.json` validates structure, computes overlaps, computes SHA256 checksums for spec files (tamper detection).

**Role brief principles**:
- `goal`: Clear statement of what this role must achieve
- `scope.directories/patterns`: Where in the codebase this role operates (not specific files)
- `constraints`: Hard rules the worker must follow
- `acceptanceCriteria`: Goal-based success checks (not file existence checks)
- `expertContext`: References to expert artifacts with relevance notes
- `assumptions`: What must be true for the approach to work
- `rollbackTriggers`: When the worker should stop and report
- `fallback`: Alternative approach if primary fails (included in initial brief, not hidden until retry)
- **No `approach` field** — workers read the codebase and decide their own implementation strategy

**Role brief example**:
```json
{
  "name": "api-developer",
  "goal": "Implement rate limiting for all API routes using token-bucket algorithm",
  "model": "sonnet",
  "scope": {
    "directories": ["src/middleware/", "src/routes/"],
    "patterns": ["**/*.middleware.*"],
    "dependencies": []
  },
  "expertContext": [
    {
      "expert": "architect",
      "artifact": ".design/expert-architect.json",
      "relevance": "Middleware chain design, Express router structure"
    }
  ],
  "constraints": [
    "Use stdlib only, no Redis dependency",
    "Must not break existing route tests"
  ],
  "acceptanceCriteria": [
    { "criterion": "Rate limiting active on all /api/* routes", "check": "10 rapid requests to /api/health — last returns 429" },
    { "criterion": "Build succeeds", "check": "npm run build" },
    { "criterion": "Existing tests pass", "check": "npm test" }
  ],
  "assumptions": [
    { "text": "Express middleware pattern used", "severity": "non-blocking" }
  ],
  "rollbackTriggers": ["Existing tests fail"],
  "fallback": "If token-bucket too complex for stdlib, use simple sliding window counter"
}
```

### 7. Auxiliary Roles

Add auxiliary roles to `auxiliaryRoles[]` in plan.json. For Trivial tier (1-2 roles): only memory-curator. For Standard and above: challenger and integration-verifier are always included; scout is included when the goal touches code. These are meta-agents that improve quality without directly implementing features.

```json
[
  {
    "name": "challenger",
    "type": "pre-execution",
    "goal": "Review plan and expert artifacts. Challenge assumptions, find gaps, identify risks, propose alternatives.",
    "model": "sonnet",
    "trigger": "before-execution"
  },
  {
    "name": "scout",
    "type": "pre-execution",
    "goal": "Read actual codebase structure in scope directories. Map patterns, conventions, integration points. Flag discrepancies with expert assumptions.",
    "model": "sonnet",
    "trigger": "before-execution"
  },
  {
    "name": "integration-verifier",
    "type": "post-execution",
    "goal": "Run full test suite. Check cross-role contracts. Validate all acceptanceCriteria. Test goal end-to-end.",
    "model": "sonnet",
    "trigger": "after-all-roles-complete"
  },
  {
    "name": "memory-curator",
    "type": "post-execution",
    "goal": "Distill design learnings: expert selection effectiveness, cross-review value, plan structure quality. Apply five quality gates before storing to .design/memory.jsonl.",
    "model": "haiku",
    "trigger": "after-all-roles-complete"
  }
]
```

### 8. Complete

1. Validate: `python3 $PLAN_CLI status .design/plan.json`. Stop if `ok: false`.
2. Shut down teammates, delete team.
3. Clean up TaskList (delete all planning tasks so `/do:execute` starts clean).
4. Summary: `python3 $PLAN_CLI summary .design/plan.json`. Display a rich end-of-run summary:

```
Design Complete: {goal}

Roles ({roleCount}, max depth {maxDepth}):
  Depth 1:
  - Role 0: {name} ({model}) — {goal one-line}
  Depth 2:
  - Role 2: {name} ({model}) [after: role-a] — {goal one-line}

Design Decisions:
- {conflict} → {decision} ({one-line reasoning})

Expert Highlights:
- {expert-name}: {key finding one-liner}

Verification: {spec count if any, acceptance criteria count per role}
Context: {stack}, Test: {testCommand}
Memories applied: {count or "none"}

Run /do:execute to begin.
```

5. **Self-reflection** — You MUST follow the Self-Monitoring procedure in lead-protocol-core.md step-by-step — do not skip steps. Skill-specific fields to include alongside the base schema:

   ```bash
   echo '{"expertQuality":"<which experts contributed most/least>","crossReviewValue":"<useful|redundant|skipped>","planCompleteness":"<assessment>", ...base fields from lead-protocol-core.md...}' | python3 $PLAN_CLI reflection-add .design/reflection.jsonl --skill design --goal "<the goal>" --outcome "<completed|partial|failed|aborted>" --goal-achieved <true|false>
   python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event skill-complete --skill design --payload '{"outcome":"<completed|partial|failed|aborted>","roleCount":N,"expertsSpawned":N,"crossReviewPhases":["A"|"B"|"C"],"specsGenerated":N}' || true
   ```

   On failure: proceed (not blocking).

**Fallback** (if finalize fails):
1. Fix validation errors and re-run finalize.
2. If structure is fundamentally broken: rebuild plan inline from expert findings, one role at a time.

---

## Contracts

### plan.json (schemaVersion 4)

**Top-level fields**: schemaVersion (4), goal, context {stack, conventions, testCommand, buildCommand, lsp}, expertArtifacts [{name, path, summary}], designDecisions [], verificationSpecs [] (optional), roles[], auxiliaryRoles[], progress {completedRoles: []}

**designDecisions fields**: conflict, experts (array), decision, reasoning. Documents lead's resolution of expert disagreements.

**verificationSpecs fields** (optional): Array of `{role, path, runCommand, properties, sha256}`. Maps roles to property-based test specs. SHA256 checksums computed by finalize for tamper detection. Workers fix code to pass specs, never modify specs.

**Role fields**: name, goal, model, scope {directories, patterns, dependencies}, expertContext [{expert, artifact, relevance}], constraints [], acceptanceCriteria [{criterion, check}], assumptions [{text, severity}], rollbackTriggers [], fallback. Status fields (status, result, attempts, directoryOverlaps) are initialized by finalize.

**Auxiliary role fields**: name, type (pre-execution|post-execution), goal, model, trigger. See Step 7 for examples.

### Interface Contracts (interfaces.json)

Produced during Step 4 Phase A when roles share domain boundaries. Array of `{boundary, producer, consumer, contract, negotiationNotes}`. Workers treat interface contracts as binding constraints.

### Analysis Artifacts

Preserved in `.design/` for execute workers:
- `expert-{name}.json` — per-expert findings (structured JSON)
- `interfaces.json` — agreed interface contracts (if produced in Step 4)

**Goal**: $ARGUMENTS
