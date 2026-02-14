---
name: design
description: "Decompose a goal into a structured plan."
argument-hint: "<goal description>"
---

# Design

Decompose a goal into `.design/plan.json`. Spawn the experts you need, get their analysis, write the plan. **This skill only designs — it does NOT execute.**

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
2. If >12 tasks likely needed, suggest phases. Design only phase 1.
3. Check existing plan: `python3 $PLAN_CLI status .design/plan.json`. If `ok` and `isResume`: ask user "Existing plan has {counts} tasks. Overwrite?" If declined, stop.
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
3. Report the planned team composition to the user.

**Expert Selection**

Analyze the goal and spawn the experts you need:
- **architect** — system design, patterns, trade-offs (nearly always useful)
- **researcher** — prior art, libraries, best practices (when external solutions exist)
- **domain specialists** — spawn based on goal domain (security, performance, UX, data, etc.)

Not exhaustive. If the goal involves authentication, spawn a security specialist. If it's a UI overhaul, spawn a UX specialist. If unsure, ask the user.

**For trivial goals** (1-3 tasks, single obvious approach): skip experts. Write the plan directly.

### 3. Spawn Experts

Create the team and spawn experts in parallel.

1. `TeamDelete(team_name: "do-design")` (ignore errors), `TeamCreate(team_name: "do-design")`. If TeamCreate fails, tell user Agent Teams is required and stop.
2. `TaskCreate` for each expert. No plan-writer — the lead writes the plan.
3. Spawn experts as teammates using the Task tool with `team_name: "do-design"` and `name: "{expert-name}"`. Write prompts appropriate to the goal and each expert's focus area. Experts report findings via `SendMessage` to the lead. Supplementary artifacts go in `.design/expert-{name}.json`. Expert budget: report findings in ≤500 words.

### 4. Synthesize and Challenge

The lead collects expert findings and writes the plan directly.

1. Collect all expert findings (messages and `.design/expert-*.json` files).
2. When experts disagree, evaluate trade-offs and decide. Note reasoning.
3. Merge findings into `.design/plan.json` — resolve conflicts, deduplicate, sequence tasks.
4. **Adversarial review checklist**: implicit assumptions that could fail? | missing tasks (error handling, migrations, edge cases)? | unnecessary tasks (over-engineering)? | dependency ordering and parallelism optimal? | integration risks between tasks touching related files? Revise as needed.
5. Run `python3 $PLAN_CLI finalize .design/plan.json` to validate structure, assemble prompts, compute overlaps.

**Task granularity**: Each task completable by one worker in one session. If it needs multiple files AND multiple approaches, split it.

**Task example** (all fields — `finalize` assembles `prompt` and computes `fileOverlaps`):
```json
{
  "subject": "Add rate limiting middleware to API routes",
  "description": "Implement token-bucket rate limiting on /api/* endpoints.",
  "activeForm": "Adding rate limiting middleware",
  "status": "pending",
  "blockedBy": [0],
  "metadata": { "type": "feature", "files": { "create": ["src/middleware/rateLimit.ts"], "modify": ["src/routes/api.ts"] } },
  "agent": {
    "role": "api-developer", "model": "sonnet",
    "approach": "1. Create rateLimit.ts with token-bucket algorithm\n2. Wire middleware into api.ts router",
    "contextFiles": [{ "path": "src/routes/api.ts", "reason": "Existing route structure" }],
    "constraints": ["Use stdlib only, no Redis"],
    "acceptanceCriteria": [{ "criterion": "Rate limit enforced", "check": "curl -s returns 429 after N requests" }],
    "assumptions": [{ "text": "Express middleware pattern used", "severity": "non-blocking" }],
    "rollbackTriggers": ["Existing tests fail"], "fallback": "Use simple counter if token-bucket too complex"
  }
}
```

### 5. Complete

1. Validate: `python3 $PLAN_CLI status .design/plan.json`. Stop if `ok: false`.
2. Shut down teammates, delete team.
3. Clean up TaskList (delete all planning tasks so `/do:execute` starts clean).
4. Summary: `python3 $PLAN_CLI summary .design/plan.json`. Display:

```
Plan: {goal}
Tasks: {taskCount}, max depth {maxDepth}

Depth 1:
- Task 0: {subject}

Depth 2:
- Task 2: {subject} [blocked by: 0, 1]

Context: {stack}
Test: {testCommand}

Run /do:execute to begin.
```

**Fallback** (if finalize fails):
1. Fix validation errors and re-run finalize.
2. If structure is fundamentally broken: rebuild plan inline from expert findings, one task at a time.

---

## Contracts

### plan.json (schemaVersion 3)

The authoritative interface between design and execute. Execute reads this file; design produces it.

**Top-level fields**: schemaVersion, goal, context {stack, conventions, testCommand, buildCommand, lsp}, progress {completedTasks: []}, tasks[]

Note: `progress.completedTasks` MUST be an empty array `[]`, not `0` or `null`.

**Task fields**: subject, description, activeForm, status (`"pending"`), result (null), attempts (0), blockedBy (array of task indices), prompt (null — assembled by finalize), fileOverlaps ([] — computed by finalize), metadata, agent

**Agent sub-field formats** (finalize expects these exact structures):
- `contextFiles`: array of `{"path": "...", "reason": "..."}` objects
- `acceptanceCriteria`: array of `{"criterion": "...", "check": "..."}` objects
- `assumptions`: array of `{"text": "...", "severity": "blocking"|"non-blocking"}` objects
- `rollbackTriggers`: array of strings
- `constraints`: array of strings

Scripts validate via `finalize` command.

### Analysis Artifacts

Preserved in `.design/` for execute workers to reference:
- `expert-{name}.json` — per-expert findings and task recommendations

**Goal**: $ARGUMENTS
