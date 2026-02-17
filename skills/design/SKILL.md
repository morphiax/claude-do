---
name: design
description: "Decompose a goal into a structured plan."
argument-hint: "<goal description>"
---

# Design

Decompose a goal into `.design/plan.json` with role briefs — goal-directed scopes for specialist workers. **This skill only designs — it does NOT execute.**

**PROTOCOL REQUIREMENT: Do NOT answer the goal directly. Your FIRST action after reading the goal MUST be the pre-flight check. Follow the Flow step-by-step.**

**Do NOT use `EnterPlanMode`** — this skill IS the plan.

**CRITICAL: Always use agent teams.** When spawning any expert via Task tool, you MUST include `team_name: $TEAM_NAME` and `name: "{role}"` parameters. Without these, agents are standalone and cannot coordinate.

**Lead boundaries**: Use only `TeamCreate`, `TeamDelete`, `TaskCreate`, `TaskUpdate`, `TaskList`, `SendMessage`, `Task`, `AskUserQuestion`, and `Bash` (cleanup, verification, `python3 $PLAN_CLI` only). Project metadata (CLAUDE.md, package.json, README) allowed. Application source code prohibited. **Never use Read, Grep, Glob, Edit, Write, LSP, WebFetch, or WebSearch on project source files.** The lead orchestrates — agents think.

**No polling**: Messages auto-deliver automatically. Never use `sleep`, loops, or Bash waits. When a teammate sends a message, it appears in your next turn.

---

## Clarification Protocol

| ASK (`AskUserQuestion`) when | SKIP when |
|---|---|
| Multiple valid interpretations exist | Codebase contains the answer |
| Scope is underspecified | Standard practice is clear |
| Technology choice is open and impacts approach | Any reasonable choice works |
| Data source is ambiguous | User preference doesn't change approach |

### Script Setup

Resolve the plugin root directory (containing `.claude-plugin/` and `skills/`). Set:

```
PLAN_CLI = {plugin_root}/skills/design/scripts/plan.py
```

All script calls: `python3 $PLAN_CLI <command> [args]` via Bash. Output is JSON with `{"ok": true/false, ...}`.

**Team name** (project-unique, avoids cross-contamination between terminals):
```
TEAM_NAME = $(python3 $PLAN_CLI team-name design).teamName
```

---

## Flow

### 1. Pre-flight

1. **Check for ambiguity**: If the goal has multiple valid interpretations per the Clarification Protocol, use `AskUserQuestion` before proceeding.
2. If >5 roles likely needed, suggest phases. Design only phase 1.
3. Check existing plan: `python3 $PLAN_CLI status .design/plan.json`. If `ok` and `isResume`: ask user "Existing plan has {counts} roles. Overwrite?" If declined, stop.
4. Archive stale artifacts: `python3 $PLAN_CLI archive .design`

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

4. Select auxiliary roles. Challenger and integration-verifier always run. Scout runs when the goal touches code (implementation, refactoring, bug fixes — not pure docs/research/config).
5. Report the planned team composition and auxiliaries to the user.

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

**For trivial goals** (1-2 roles, single obvious approach): skip experts. Write the plan directly. Skip to Step 4.

**When uncertain about goal type**: Ask the user to clarify intent before spawning experts.

### 3. Spawn Experts

Create the team and spawn experts in parallel.

1. `TeamDelete(team_name: $TEAM_NAME)` (ignore errors), `TeamCreate(team_name: $TEAM_NAME)`. If TeamCreate fails, tell user Agent Teams is required and stop. If TeamDelete succeeds, a previous session's team was cleaned up.
2. **TeamCreate health check**: Verify team is reachable. If verification fails, `TeamDelete`, then retry `TeamCreate` once. If retry fails, abort with clear error message.
3. **Memory injection**: Run `python3 $PLAN_CLI memory-search .design/memory.jsonl --goal "{goal}" --stack "{stack}"`. If `ok: false` or no memories returned, proceed without memory injection. Otherwise inject top 3-5 memories into expert prompts as a "Past Learnings" section (format: `- {category}: {summary} (from {created})`).
4. `TaskCreate` for each expert.
5. Spawn experts as teammates using the Task tool. For each expert:
   - Use Task with `team_name: $TEAM_NAME` and `name: "{expert-name}"`.
   - Write prompts appropriate to the goal and each expert's focus area. Ask them to score relevant dimensions and trace scenarios.
   - Every expert prompt MUST end with: "In your findings JSON, include a `verificationProperties` section: an array of properties that should hold regardless of implementation (behavioral invariants, boundary conditions, cross-role contracts). Format: `[{\"property\": \"...\", \"category\": \"invariant|boundary|integration\", \"testableVia\": \"how to test this with concrete commands/endpoints\"}]`. Provide concrete, externally observable properties that can be tested without reading source code."
   - Instruct: "Save your complete findings to `.design/expert-{name}.json` as structured JSON."
   - Instruct: "Then SendMessage to the lead with a summary."

   Expert artifacts flow directly to execution workers — they are structured JSON with sections that can be referenced selectively.
6. **Expert liveness tracking**: After spawning N experts, maintain a completion checklist. Mark each expert complete when: (a) its SendMessage arrives AND (b) its artifact file exists (`ls .design/expert-{name}.json`). Only proceed to Step 3.5 when all N experts are complete.
   - **Turn-based timeout**: If an expert has not completed after 2 turns of processing other experts, send: "Status check — artifact expected at `.design/expert-{name}.json`. Report completion or blockers."
   - **Re-spawn after 1 more turn**: If still no completion after the status ping and 1 additional turn, re-spawn the expert with the same prompt (max 2 re-spawn attempts per expert).
   - **Proceed with available data**: After 2 re-spawn attempts, if the expert still hasn't completed, log the failure and proceed to Step 3.5 with the artifacts from responsive experts.
   - **Never write artifacts yourself** — the lead's interpretation is not a substitute for specialist analysis.

### 3.5. Interface Negotiation & Cross-Review

Expert coordination prevents **integration failures** (domains don't fit together) and **convergence failures** (experts reach incompatible conclusions). Assess which phases apply per the decision matrix, then execute them.

**CRITICAL ENFORCEMENT**: The lead MUST NOT perform cross-review solo. Every phase requires actual `SendMessage` calls to experts and collecting their responses. Skipping expert interaction when the decision matrix says a phase is mandatory is a protocol violation.

| Phase | Trigger | Purpose |
|---|---|---|
| **A: Interface negotiation** | >=2 experts whose roles will share data/APIs/file boundaries | Producer-consumer pairs agree on shared interface contracts |
| **B: Perspective reconciliation** | >=2 experts analyzed same domain from different angles, OR >=3 experts in complex/high-stakes tier | Resolve conflicting recommendations about the same thing |
| **C: Cross-domain challenge** | Complex/high-stakes tier with >=3 experts | Catch cross-domain assumptions neither A nor B would surface |

**Decision matrix**: If condition matches → phase is **mandatory**. If <2 experts or trivial tier → skip all phases.

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

### 4. Synthesize into Role Briefs

The lead collects expert findings and writes the plan.

1. Collect all expert findings (messages and `.design/expert-*.json` files).
2. **Resolve conflicts from cross-review** (if debate occurred): For each challenge, evaluate trade-offs and decide. Document resolution in plan.json under `designDecisions[]` (schema: {conflict, experts, decision, reasoning}).
2b. **Incorporate interface contracts**: If `.design/interfaces.json` was produced in Step 3.5, add each interface as a constraint on the relevant producer and consumer roles. Interface contracts are binding — workers must implement the agreed interface shape.
3. Identify the specialist roles needed to execute this goal:
   - Each role scopes a **coherent problem domain** for one worker
   - If a role would cross two unrelated domains, split into two roles
   - Workers decide HOW to implement — briefs define WHAT and WHY
4. Write `.design/plan.json` with role briefs (see schema below).
5. For each role, include `expertContext[]` referencing specific expert artifacts and the sections relevant to that role. **Do not lossy-compress expert findings into terse fields** — reference the full artifacts.
6. Write criteria-based `acceptanceCriteria` — define WHAT should work, not WHICH files should exist. Workers verify against criteria, not file lists. **Every criterion MUST have a `check` that is a concrete, independently runnable shell command** (e.g., `"bun run build 2>&1 | tail -5"`, `"bun test --run 2>&1 | tail -10"`). Never leave checks as prose descriptions — workers execute these literally. If a role touches compiled code, include BOTH a build check AND a test check as separate criteria. **Checks must verify functional correctness, not just pattern existence.** A grep confirming a CSS rule exists is insufficient — the check must verify the rule actually takes effect (e.g., start a dev server and curl the page, or verify that referenced classes/imports resolve to definitions). At least one criterion per role should test end-to-end behavior, not just file contents.
7. Add `auxiliaryRoles[]` (see Auxiliary Roles section).
8. Write to `.design/plan.json` (do NOT run finalize yet — that happens in Step 4.5).

### 4.5. Generate Verification Specs (OPTIONAL)

See **Verification Specs Protocol** in CLAUDE.md for the full protocol (when to generate, authorship rules, spec generation steps, content guidelines, and finalization).

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
    { "criterion": "Build succeeds", "check": "npm run build 2>&1 | tail -20" },
    { "criterion": "Existing tests pass", "check": "npm test 2>&1 | tail -20" }
  ],
  "assumptions": [
    { "text": "Express middleware pattern used", "severity": "non-blocking" }
  ],
  "rollbackTriggers": ["Existing tests fail"],
  "fallback": "If token-bucket too complex for stdlib, use simple sliding window counter"
}
```

### 5. Auxiliary Roles

Add auxiliary roles to `auxiliaryRoles[]` in plan.json. Challenger and integration-verifier are always included. Scout is included when the goal touches code. These are meta-agents that improve quality without directly implementing features.

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

### 6. Complete

1. Validate: `python3 $PLAN_CLI status .design/plan.json`. Stop if `ok: false`.
2. Shut down teammates, delete team.
3. Clean up TaskList (delete all planning tasks so `/do:execute` starts clean).
4. Summary: `python3 $PLAN_CLI summary .design/plan.json`. Display:

```
Plan: {goal}
Roles: {roleCount}, max depth {maxDepth}
Auxiliary: {auxiliaryRoles}

Depth 1:
- Role 0: {name} ({model})

Depth 2:
- Role 2: {name} ({model}) [after: role-a, role-b]

Context: {stack}
Test: {testCommand}

Run /do:execute to begin.
```

5. **Self-reflection** — Evaluate this design run. Write a structured reflection entry:

   Assess: (a) Did the plan capture the goal effectively? (b) Were experts well-chosen? (c) Did cross-review add value or was it redundant? (d) What should be done differently next time?

   ```bash
   echo '{"expertQuality":"<which experts contributed most/least>","crossReviewValue":"<useful|redundant|skipped>","planCompleteness":"<assessment>","whatWorked":["<item>"],"whatFailed":["<item>"],"doNextTime":["<item>"]}' | \
     python3 $PLAN_CLI reflection-add .design/reflection.jsonl \
       --skill design \
       --goal "<the goal>" \
       --outcome "<completed|partial|failed|aborted>" \
       --goal-achieved <true|false>
   ```

   On failure: proceed (reflection is valuable but not blocking).

**Fallback** (if finalize fails):
1. Fix validation errors and re-run finalize.
2. If structure is fundamentally broken: rebuild plan inline from expert findings, one role at a time.

---

## Contracts

### plan.json (schemaVersion 4)

The authoritative interface between design and execute. Execute reads this file; design produces it.

**Top-level fields**: schemaVersion (4), goal, context {stack, conventions, testCommand, buildCommand, lsp}, expertArtifacts [{name, path, summary}], interfaceContracts (path to .design/interfaces.json, if produced), designDecisions [], verificationSpecs [] (optional), roles[], auxiliaryRoles[], progress {completedRoles: []}

**designDecisions fields**: conflict, experts (array), decision, reasoning. Documents lead's resolution of expert disagreements.

**verificationSpecs fields** (optional): Array of `{role, path, runCommand, properties, sha256}`. Maps roles to property-based test specs. SHA256 checksums computed by finalize for tamper detection. Workers fix code to pass specs, never modify specs.

**Role fields**: name, goal, model, scope {directories, patterns, dependencies}, expertContext [{expert, artifact, relevance}], constraints [], acceptanceCriteria [{criterion, check}], assumptions [{text, severity}], rollbackTriggers [], fallback. Status fields (status, result, attempts, directoryOverlaps) are initialized by finalize.

**Auxiliary role fields**: name, type (pre-execution|post-execution), goal, model, trigger. See Step 5 for examples.

### Interface Contracts (interfaces.json)

Produced during Step 3.5 Phase A when roles share domain boundaries. Array of `{boundary, producer, consumer, contract, negotiationNotes}`. Workers treat interface contracts as binding constraints.

### Analysis Artifacts

Preserved in `.design/` for execute workers:
- `expert-{name}.json` — per-expert findings (structured JSON)
- `interfaces.json` — agreed interface contracts (if produced in Step 3.5)

**Goal**: $ARGUMENTS
