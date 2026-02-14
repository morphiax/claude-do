---
name: design
description: "Decompose a goal into a structured plan."
argument-hint: "<goal description>"
---

# Design

Decompose a goal into `.design/plan.json` with role briefs — goal-directed scopes for specialist workers. **This skill only designs — it does NOT execute.**

**PROTOCOL REQUIREMENT: Do NOT answer the goal directly. Your FIRST action after reading the goal MUST be the pre-flight check. Follow the Flow step-by-step.**

**Do NOT use `EnterPlanMode`** — this skill IS the plan.

**CRITICAL: Always use agent teams.** When spawning any expert via Task tool, you MUST include `team_name: "do-design"` and `name: "{role}"` parameters. Without these, agents are standalone and cannot coordinate.

**Lead boundaries**: Use only `TeamCreate`, `TeamDelete`, `TaskCreate`, `TaskUpdate`, `TaskList`, `SendMessage`, `Task`, `AskUserQuestion`, and `Bash` (cleanup, verification, `python3 $PLAN_CLI` only). Project metadata (CLAUDE.md, package.json, README) allowed. Application source code prohibited. The lead orchestrates — agents think.

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

---

## Flow

### 1. Pre-flight

1. **Check for ambiguity**: If the goal has multiple valid interpretations per the Clarification Protocol, use `AskUserQuestion` before proceeding.
2. If >5 roles likely needed, suggest phases. Design only phase 1.
3. Check existing plan: `python3 $PLAN_CLI status .design/plan.json`. If `ok` and `isResume`: ask user "Existing plan has {counts} roles. Overwrite?" If declined, stop.
4. Archive stale artifacts (instead of deleting — avoids destructive commands):
   ```bash
   mkdir -p .design/history
   if [ "$(find .design -mindepth 1 -maxdepth 1 ! -name history | head -1)" ]; then
     ARCHIVE_DIR=".design/history/$(date -u +%Y%m%dT%H%M%SZ)"
     mkdir -p "$ARCHIVE_DIR"
     find .design -mindepth 1 -maxdepth 1 ! -name history ! -name memory.jsonl -exec mv {} "$ARCHIVE_DIR/" \;
   fi
   ```

### 2. Lead Research

The lead directly assesses the goal to determine needed perspectives.

1. Read the goal. Quick WebSearch (if external patterns/libraries relevant) or scan project metadata (CLAUDE.md, package.json) via Bash to understand stack.
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

**For trivial goals** (1-2 roles, single obvious approach): skip experts. Write the plan directly.

**When uncertain about goal type**: Ask the user to clarify intent before spawning experts.

### 3. Spawn Experts

Create the team and spawn experts in parallel.

1. `TeamDelete(team_name: "do-design")` (ignore errors), `TeamCreate(team_name: "do-design")`. If TeamCreate fails, tell user Agent Teams is required and stop.
2. **Memory injection**: Run `python3 $PLAN_CLI memory-search .design/memory.jsonl --goal "{goal}" --stack "{stack}"`. If `ok: true` and memories exist, inject top 3-5 into expert prompts as a "Past Learnings" section (format: `- {category}: {summary} (from {created})`).
3. `TaskCreate` for each expert.
4. Spawn experts as teammates using the Task tool with `team_name: "do-design"` and `name: "{expert-name}"`. Write prompts appropriate to the goal and each expert's focus area. Experts report findings via `SendMessage` to the lead. Experts MUST save detailed artifacts to `.design/expert-{name}.json` — these flow directly to execution workers. Expert artifacts are structured JSON with sections that can be referenced selectively.

### 3.5. Interface Negotiation & Cross-Review

Research on boundary objects (Star & Griesemer 1989), consumer-driven contracts (Fowler/Robinson), and the Delphi method shows that expert coordination prevents two distinct failure modes: **integration failures** (domains don't fit together) and **convergence failures** (experts with different lenses reach incompatible conclusions about the same thing). The protocol addresses both.

#### Two coordination needs

| Need | When it applies | Example |
|---|---|---|
| **Interface negotiation** | Experts in *different domains* produce/consume across boundaries | Backend architect + frontend designer must agree on API response shape |
| **Perspective reconciliation** | Experts with *different lenses* analyze the *same domain* | Architect, researcher, and prompt-engineer all analyze a SKILL.md — architect wants more structure, researcher finds simpler protocols have better adherence |

Both can apply in the same design session. Assess each independently.

#### Decision Matrix — When to Run Each

| Condition | Interface negotiation | Perspective reconciliation |
|---|---|---|
| >=2 experts whose execution roles will share data, APIs, or file boundaries | **Mandatory** | — |
| >=2 experts analyzed the same artifact/domain from different angles | — | **Mandatory** |
| Both conditions apply | **Run both** | **Run both** |
| All experts operate on fully independent domains with no shared interfaces or overlapping analysis | Skip | Skip |
| <2 experts or trivial tier | Skip | Skip |

#### Phase A: Interface Negotiation

**Trigger**: Execution roles will share data, APIs, or file boundaries.

After all experts have saved artifacts:

1. **Lead identifies domain boundaries**: Read expert artifacts and list every point where one role's output feeds another role's input (API response shapes, database schemas consumed by multiple roles, file formats, shared state).

2. **Lead drafts interface contracts**: For each boundary, write a concrete contract specifying the shared interface. Use **consumer-driven contracts** — define what the *consuming* side expects:

   ```
   Interface: {boundary-name}
   Producer: {expert/role-name}
   Consumer: {expert/role-name}
   Contract: {concrete specification — field names, types, response shape, error format}
   ```

3. **Send contracts to both sides**: Message each producer-consumer pair with their shared contract. Ask: "Does this interface work for your domain? Flag any constraints that make this infeasible."

4. **Collect responses**: Each expert confirms feasibility or proposes modifications. **Maximum 2 rounds** of negotiation per interface (Delphi research: diminishing returns after 2-3 rounds). If no convergence after 2 rounds, lead decides and documents reasoning.

5. **Save agreed interfaces**: Store finalized contracts in `.design/interfaces.json` (array of `{boundary, producer, consumer, contract, negotiationNotes}`). These flow to execution workers as binding constraints.

#### Phase B: Perspective Reconciliation

**Trigger**: Multiple experts analyzed the same domain/artifact from different angles, OR complex/high-stakes tier with >=3 experts.

This resolves conflicting recommendations when experts with different priorities (performance vs maintainability, structure vs simplicity, security vs usability) examine the same thing.

1. **Lead identifies overlapping analysis**: Find topics where >=2 experts made recommendations about the same thing. List specific conflicts or tensions.

2. Lead messages the relevant experts (not broadcast — only those with overlapping analysis): "Experts {A} and {B}: you both analyzed {topic}. Your recommendations differ:
   - {Expert A}: '{summary of their position}'
   - {Expert B}: '{summary of their position}'

   Read each other's artifact at {path}. Then each send me: (a) where you agree, (b) where you disagree and why your approach is better, (c) any synthesis that combines both perspectives."

3. Experts read the other's artifact and respond with agreements, disagreements, and proposed synthesis.

4. **Maximum 2 rounds**. If experts converge — great. If they don't converge after 2 rounds, lead decides based on the goal's priorities and documents the trade-off.

#### Phase C: Cross-Domain Challenge (for complex/high-stakes with >=3 experts)

**Trigger**: Complex or high-stakes tier with >=3 experts. Runs after Phase A and/or B if applicable.

This catches cross-domain assumptions that neither interface negotiation nor perspective reconciliation would surface — e.g., a metadata expert assuming the database supports a feature that the architect flagged as unavailable.

1. Lead broadcasts to all experts: "Read OTHER experts' artifacts at {paths}. Challenge claims that make assumptions about your domain or affect shared interfaces.

   **Challenge to {expert-name}**
   - **Claim challenged**: '{exact quote from their artifact}'
   - **Severity**: [blocking|important|minor]
   - **Evidence**: {why this claim is incorrect or problematic for your domain}
   - **Alternative**: {your proposed alternative}

   Send one message per challenge. If you have no challenges, send 'No challenges found'."

2. Each expert reads OTHER experts' artifacts (not their own).
3. Each expert sends structured challenge messages to lead.
4. Lead collects challenges. For each:
   - Forward to the targeted expert
   - Targeted expert responds with defense or concession
   - **Maximum 2 rounds per challenge** — if unresolved, lead decides
5. Lead resolves all conflicts. Update `.design/interfaces.json` if any interface contracts changed.

Interfaces, reconciled perspectives, and challenge resolutions all inform conflict resolution in the next step.

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
8. Run `python3 $PLAN_CLI finalize .design/plan.json` to validate structure and compute overlaps.

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

#### Challenger (pre-execution)
Reviews the plan before execution. Challenges assumptions, finds gaps, identifies risks, questions scope.

```json
{
  "name": "challenger",
  "type": "pre-execution",
  "goal": "Review plan and expert artifacts. Challenge assumptions, find gaps, identify risks, propose alternatives.",
  "model": "sonnet",
  "trigger": "before-execution"
}
```

#### Scout (pre-execution)
Reads the actual codebase to verify expert assumptions match reality. Produces a reality-check report that workers read first.

```json
{
  "name": "scout",
  "type": "pre-execution",
  "goal": "Read actual codebase structure in scope directories. Map patterns, conventions, integration points. Flag discrepancies with expert assumptions.",
  "model": "sonnet",
  "trigger": "before-execution"
}
```

#### Integration Verifier (post-execution)
Verifies all roles' work integrates correctly. Runs tests, checks cross-role contracts, validates goal achievement end-to-end.

```json
{
  "name": "integration-verifier",
  "type": "post-execution",
  "goal": "Run full test suite. Check cross-role contracts. Validate all acceptanceCriteria. Test goal end-to-end.",
  "model": "sonnet",
  "trigger": "after-all-roles-complete"
}
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

**Fallback** (if finalize fails):
1. Fix validation errors and re-run finalize.
2. If structure is fundamentally broken: rebuild plan inline from expert findings, one role at a time.

---

## Contracts

### plan.json (schemaVersion 4)

The authoritative interface between design and execute. Execute reads this file; design produces it.

**Top-level fields**: schemaVersion (4), goal, context {stack, conventions, testCommand, buildCommand, lsp}, expertArtifacts [{name, path, summary}], interfaceContracts (path to .design/interfaces.json, if produced), designDecisions [], roles[], auxiliaryRoles[], progress {completedRoles: []}

**designDecisions fields**: conflict (string), experts (array of expert names), decision (string), reasoning (string). Documents how lead resolved expert disagreements during cross-review.

**Role fields**: name, goal, model, scope {directories, patterns, dependencies}, expertContext [{expert, artifact, relevance}], constraints [], acceptanceCriteria [{criterion, check}], assumptions [{text, severity}], rollbackTriggers [], fallback

**Status fields** (initialized by finalize): status ("pending"), result (null), attempts (0), directoryOverlaps (computed by finalize)

**Auxiliary role fields**: name, type (pre-execution|post-execution|per-role), goal, model, trigger (before-execution|after-role-complete|after-all-roles-complete)

Scripts validate via `finalize` command.

### Interface Contracts (interfaces.json)

Produced during Step 3.5 Phase A when roles share domain boundaries. Array of:

```json
{
  "boundary": "Game list API response shape",
  "producer": "database-optimizer",
  "consumer": "frontend-modernizer",
  "contract": "GET /api/games returns {games: [{title, genres: string[], rating, ...}], total: int}",
  "negotiationNotes": "Frontend needs genres as array (not JSON string) for badge rendering"
}
```

Execution workers treat interface contracts as binding constraints alongside role briefs.

### Analysis Artifacts

Preserved in `.design/` for execute workers to reference:
- `expert-{name}.json` — per-expert findings (structured JSON, no word limit)
- `interfaces.json` — agreed interface contracts between roles (if produced in Step 3.5)

**Goal**: $ARGUMENTS
