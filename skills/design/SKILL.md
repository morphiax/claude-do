---
name: design
description: "Decompose a goal into a structured plan."
argument-hint: "<goal description>"
---

# Design

Decompose a goal into `.design/plan.json`. Spawn the experts you need, get their analysis, write the plan. **This skill only designs — it does NOT execute.**

**Do NOT use `EnterPlanMode`** — this skill IS the plan.

**CRITICAL: Always use agent teams.** When spawning any expert or worker via Task tool, you MUST include `team_name: "do-design"` and `name: "{role}"` parameters. Without these, agents are standalone and cannot coordinate.

**Lead boundaries**: Use only `TeamCreate`, `TeamDelete`, `TaskCreate`, `TaskUpdate`, `TaskList`, `SendMessage`, `Task`, `AskUserQuestion`, and `Bash` (cleanup, verification, `python3 $PLAN_CLI` only). Never read source files, use MCP tools, `Grep`, `Glob`, or `LSP`. The lead orchestrates — agents think.

**No polling**: Messages auto-deliver to your conversation automatically. Never use `sleep`, `for i in {1..N}`, or Bash loops to wait. Simply proceed with your work — when a teammate sends a message, it appears in your next turn. The system handles all delivery.

---

## Clarification Protocol

Ask clarifying questions before spawning agents when the goal has ambiguity that affects implementation approach.

**Ask `AskUserQuestion` when:**
- Multiple valid interpretations exist (e.g., "add pictures" = real photos vs stock images vs icons)
- Scope is underspecified (e.g., "upgrade" = visual refresh vs full rewrite vs new feature)
- Technology choice is open and impacts implementation significantly
- Data source is ambiguous (e.g., "show car images" — from where? user-provided? API? scraped?)

**Do NOT ask when:**
- Codebase contains the answer (existing patterns, conventions, similar features)
- Standard practice is clear (use existing test framework, follow existing component patterns)
- User preference doesn't materially change the approach
- The ambiguity is minor and any reasonable choice works

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
   # If .design/ has artifacts beyond history/, archive them
   if [ "$(find .design -mindepth 1 -maxdepth 1 ! -name history | head -1)" ]; then
     ARCHIVE_DIR=".design/history/$(date -u +%Y%m%dT%H%M%SZ)"
     mkdir -p "$ARCHIVE_DIR"
     find .design -mindepth 1 -maxdepth 1 ! -name history -exec mv {} "$ARCHIVE_DIR/" \;
   fi
   ```

### 2. Lead Research

The lead directly assesses the goal to determine needed perspectives.

1. Read the goal. Quick WebSearch (if external patterns/libraries relevant) or scan CLAUDE.md/package.json via Bash to understand stack.
2. Decide what expert perspectives would help. Trust your judgment.
3. Report the planned team composition to the user.

**Expert Selection**

Analyze the goal and spawn the experts you need. Trust your judgment.

Common perspectives that add value:
- **architect** — system design, patterns, trade-offs (nearly always useful)
- **researcher** — prior art, libraries, best practices (when external solutions exist)
- **domain specialists** — spawn based on goal domain (security, performance, UX, data, etc.)

The list is not exhaustive. If the goal involves authentication, spawn a security specialist. If it's a UI overhaul, spawn a UX specialist. If you're unsure what perspectives are needed, ask the user.

**For trivial goals** (1-3 tasks, single obvious approach): skip experts. Write the plan directly.

### 3. Spawn Experts

Create the team and spawn experts in parallel.

1. `TeamDelete(team_name: "do-design")` (ignore errors), `TeamCreate(team_name: "do-design")`. If TeamCreate fails, tell user Agent Teams is required and stop.
2. `TaskCreate` for each expert. No plan-writer — the lead writes the plan (it has full context from all experts).
3. Spawn experts as teammates using the Task tool. Write prompts appropriate to the goal and each expert's focus area. Tell them what you need — don't follow a template. Experts report findings via `SendMessage` to the lead (or write `.design/expert-{name}.json`).

**CRITICAL: Always use agent teams.** When spawning experts via Task tool, you MUST include:
- `team_name: "do-design"` — to make them team members, not standalone agents
- `name: "{expert-name}"` — their role name (architect, researcher, etc.)

### 4. Synthesize and Challenge

The lead collects expert findings and writes the plan directly. The lead has the broadest context — it heard from every expert — so it is the best synthesizer.

1. Collect all expert findings (messages and/or `.design/expert-*.json` files).
2. Merge findings into `.design/plan.json` — resolve conflicts, deduplicate, sequence tasks.
3. **Adversarial review** — Before finalizing, the lead challenges its own plan:
   - Are there implicit assumptions that could fail? (e.g., "assumes API exists", "assumes schema won't change")
   - Are there missing tasks? (error handling, migrations, edge cases, rollback)
   - Are there unnecessary tasks? (over-engineering, premature abstraction)
   - Do the dependencies make sense? Could parallelism be improved?
   - Are there integration risks between tasks that touch related files?
   Revise the plan based on this review. Add/remove/reorder tasks as needed.
4. Run `python3 $PLAN_CLI finalize .design/plan.json` to validate structure, assemble prompts, compute overlaps.

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

**Fields**: schemaVersion, goal, context {stack, conventions, testCommand, buildCommand, lsp}, progress {completedTasks, surprises, decisions}, tasks[]

**Task fields**: subject, description, activeForm, status, result, attempts, blockedBy, prompt, fileOverlaps, metadata {type, files {create, modify}, reads}

Keep tasks focused on the work, not the worker. Write clear descriptions that make it obvious what needs to be done.

Scripts validate via `finalize` command.

### Analysis Artifacts

Preserved in `.design/` for execute workers to reference:
- `expert-{name}.json` — per-expert findings and task recommendations

**Goal**: $ARGUMENTS
