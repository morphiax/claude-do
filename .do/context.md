# Context

## Plugin location

The do plugin lives at `~/.claude/plugins/marketplaces/do`. This is the canonical path for self-improvement — when shape or frame targets do itself, this is where the spec, context, and skills live.

## Technology

- Claude Code plugin (SKILL.md files and command .md files, no runtime code)
- Markdown for all artifacts (spec, context, skills, commands)
- No dependencies beyond Claude Code's plugin system

## Plugin structure

- `skills/shape/SKILL.md` — dialogue skill
- `skills/build/SKILL.md` — execution skill
- `commands/release.md` — version, changelog, docs, commit, tag, push
- `commands/audit.md` — technical audit against best practices
- `commands/challenge.md` — product review from PM perspective
- `.do/spec.md` — this plugin's own spec (self-targeted by shape)
- `.do/context.md` — this file

## Conventions

### Shared skill conventions

Both skills follow these Claude Code tool conventions:
- **Activity signaling** — `TaskCreate` at activation with `activeForm` for spinner text, `TaskUpdate` to reflect phase changes, mark `completed` on finish
- **Main context isolation** — main context is for human interaction and `.do/` file reads only. All other work (file exploration, research, implementation) delegates to subagents via the Task tool
- **Model tiers for subagents** — haiku for mechanical reads, sonnet for moderate analysis, opus for complex interpretation or implementation
- **Structured decisions** — `AskUserQuestion` when tradeoffs, naming choices, or scope boundaries arise. Don't bury decisions in prose.

### Build uses Claude Code plan mode

Build leverages three built-in Claude Code mechanisms:
- **Plan mode** (`EnterPlanMode`/`ExitPlanMode`) for the planning phase — structurally read-only, requires human approval to exit
- **Sequential thinking** for decomposition and spec comparison during planning
- **Task tool with `bypassPermissions`** for execution subagents — plan approval is the single permission gate

TDD is enforced structurally: each task in the plan must specify its test. The approved plan is the TDD contract.

### The plan carries its execution methodology

After plan approval with context clearing, the SKILL.md is no longer in scope. The plan's execution preamble must specify the execution mechanism: create a task list (TaskCreate) for visible progress tracking, execute each task in an isolated subagent (Task tool with `bypassPermissions`), and follow TDD within each subagent. The main context post-approval handles only orchestration — dispatching tasks and handling exceptions.

## Status

**Completed**: Updated both SKILL.md files for component folder model — replaced `.do/specs/` references with `.do/<component>/`, updated main context rules to allow component spec/context reads. Spec and skills are aligned.

**Completed**: Build SKILL.md updated to implement two-phase protocol. Protocol restructured into Orientation → Planning (read-only) → Execution (bypassPermissions) → Completion. TDD enforcement structural — each plan task specifies its test. Plan approval via ExitPlanMode is the single permission gate.
