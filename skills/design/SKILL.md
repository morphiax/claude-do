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
     find .design -mindepth 1 -maxdepth 1 ! -name history -exec mv {} "$ARCHIVE_DIR/" \;
   fi
   ```

### 2. Lead Research

The lead directly assesses the goal to determine needed perspectives.

1. Read the goal. Quick WebSearch (if external patterns/libraries relevant) or scan project metadata (CLAUDE.md, package.json) via Bash to understand stack.
2. Decide what expert perspectives would help.
3. Assess complexity tier (drives auxiliary role selection):

| Tier | Roles | Auxiliaries |
|---|---|---|
| Trivial (1-2 roles, obvious approach) | 1-2 | None |
| Standard (clear domain) | 2-4 | Integration verifier |
| Complex (cross-cutting concerns) | 4-6 | Challenger + scout + integration verifier |
| High-stakes (production, security, data) | 3-8 | Challenger + scout + integration verifier |

4. Report the planned team composition and complexity tier to the user.

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

### 3.5. Expert Cross-Review (optional)

**When**: Complex or high-stakes tiers with >=3 experts. Skip for <3 experts or trivial/standard tiers.

After all experts have saved artifacts and sent initial messages:

1. Lead broadcasts to all experts: "All experts: read artifacts at {paths}. Identify disagreements, gaps, or invalid assumptions in others' findings. Challenge specific claims via SendMessage to lead using this format:

   **Challenge to {expert-name}**
   - **Claim challenged**: '{exact quote from their artifact}'
   - **Severity**: [blocking|important|minor]
   - **Evidence**: {why this claim is incorrect or problematic}
   - **Alternative**: {your proposed alternative approach}

   Send one message per challenge. If you have no challenges, send 'No challenges found'."

2. Each expert reads OTHER experts' artifacts (not their own).
3. Each expert sends structured challenge messages to lead.
4. Lead collects all challenges. For each challenge:
   - Forward the challenge to the targeted expert via SendMessage
   - Wait for the targeted expert to defend their position or concede
   - Targeted expert responds with either: (a) defense of their claim with additional evidence, or (b) acknowledgment and revision
5. After all challenged experts have responded (timeout: if no defense after 2 turns, proceed), lead resolves conflicts.

Challenges and defenses inform conflict resolution in the next step.

### 4. Synthesize into Role Briefs

The lead collects expert findings and writes the plan.

1. Collect all expert findings (messages and `.design/expert-*.json` files).
2. **Resolve conflicts from cross-review** (if debate occurred): For each challenge, evaluate trade-offs and decide. Document resolution in plan.json under `designDecisions[]` (schema: {conflict, experts, decision, reasoning}).
3. Identify the specialist roles needed to execute this goal:
   - Each role scopes a **coherent problem domain** for one worker
   - If a role would cross two unrelated domains, split into two roles
   - Workers decide HOW to implement — briefs define WHAT and WHY
4. Write `.design/plan.json` with role briefs (see schema below).
5. For each role, include `expertContext[]` referencing specific expert artifacts and the sections relevant to that role. **Do not lossy-compress expert findings into terse fields** — reference the full artifacts.
6. Write criteria-based `acceptanceCriteria` — define WHAT should work, not WHICH files should exist. Workers verify against criteria, not file lists.
7. If complexity tier warrants, add `auxiliaryRoles[]` (see Auxiliary Roles section).
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
    { "criterion": "Existing tests pass", "check": "npm test exits 0" }
  ],
  "assumptions": [
    { "text": "Express middleware pattern used", "severity": "non-blocking" }
  ],
  "rollbackTriggers": ["Existing tests fail"],
  "fallback": "If token-bucket too complex for stdlib, use simple sliding window counter"
}
```

### 5. Auxiliary Roles

Based on complexity tier, add auxiliary roles to `auxiliaryRoles[]` in plan.json. These are meta-agents that improve quality without directly implementing features.

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

**Top-level fields**: schemaVersion (4), goal, context {stack, conventions, testCommand, buildCommand, lsp}, expertArtifacts [{name, path, summary}], designDecisions [], roles[], auxiliaryRoles[], progress {completedRoles: []}

**designDecisions fields**: conflict (string), experts (array of expert names), decision (string), reasoning (string). Documents how lead resolved expert disagreements during cross-review.

**Role fields**: name, goal, model, scope {directories, patterns, dependencies}, expertContext [{expert, artifact, relevance}], constraints [], acceptanceCriteria [{criterion, check}], assumptions [{text, severity}], rollbackTriggers [], fallback

**Status fields** (initialized by finalize): status ("pending"), result (null), attempts (0), directoryOverlaps (computed by finalize)

**Auxiliary role fields**: name, type (pre-execution|post-execution|per-role), goal, model, trigger (before-execution|after-role-complete|after-all-roles-complete)

Scripts validate via `finalize` command.

### Analysis Artifacts

Preserved in `.design/` for execute workers to reference:
- `expert-{name}.json` — per-expert findings (structured JSON, no word limit)

**Goal**: $ARGUMENTS
