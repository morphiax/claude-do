# do:work — Implementation Context

This file maps the behavioral spec to the Claude Code plugin system. The spec describes WHAT; this file describes HOW within the current technology.

## Skill invocation

```yaml
name: do:work
description: Project intelligence — orient, plan, execute, and maintain projects through a deliberate observe-orient-decide-act loop.
argument-hint: "[what you want to do, a bug to fix, 'audit', 'challenge', or empty to infer]"
```

The user invokes via `$ARGUMENTS`.

## Model directory

The persistent mental model lives in `.do/` under the project root. Six files:

```
.do/spec.md
.do/reference.md
.do/stack.md
.do/design.md
.do/decisions.md
.do/pitfalls.md
```

Algorithm pseudocode lives in spec.md (not a separate architecture file).

Subprojects use `.do/<component>/` with whichever files are needed.

## Self-targeting path

When `$ARGUMENTS` references the do plugin itself:
```
path = ~/.claude/plugins/marketplaces/do/.do/
```
Otherwise:
```
path = <cwd>/.do/
```

## Version control

Orient uses:
```
git log --oneline -10
git diff HEAD~1 --stat
```

## Worker dispatch

The spec's "worker" maps to the `Agent` tool:

```
dispatch_worker(task):
  Agent(
    mode:             "bypassPermissions",
    model:            task.tier,
    prompt:           preamble + task.description,
    run_in_background: true
  )
```

Independent tasks launch as multiple Agent calls in a single message (concurrent). Dependent tasks wait for predecessors.

## Complexity tier mapping

The spec's complexity tiers map to Claude models:

```
mechanical  = haiku    # file renaming, simple refactors, boilerplate
standard    = sonnet   # feature implementation, test writing, moderate analysis
complex     = opus     # architectural decisions, multi-file refactors, nuanced interpretation
```

## Task management

The spec's task operations map to Claude Code task tools:

```
create_task(title, description)  ->  TaskCreate(subject=title, activeForm=description)
set_dependencies(blocked_by)     ->  TaskUpdate(taskId, addBlockedBy=blocked_by)
mark(task, in_progress)          ->  TaskUpdate(taskId, status="in_progress")
mark(task, completed)            ->  TaskUpdate(taskId, status="completed")
```

## Context boundary enforcement

The spec's orchestrator/worker boundary maps to:

```
ORCHESTRATOR (main context):
  allowed:   Read .do/*, Bash(git commands), dialogue, planning
  forbidden: Read/Glob/Grep on non-.do/ paths, Edit/Write code files

WORKER (Agent subagent):
  receives:  preamble string (built from .do/ files) + task description
  inherits:  nothing — clean context, no conversation history
```

## Preamble construction

```
build_preamble(project):
  content = ""
  for file in read_all(project.do_path):
    content += file.content
  content += validate_output_test   # from spec section 13
  return content
```

## Reasoning tool

The spec's constraint identification and multi-factor tradeoff analysis map to `sequentialthinking`:

```
competing_constraints or fuzzy_intent -> mcp__sequential-thinking__sequentialthinking()
```

Use for: decomposing complex problems, working through risk ordering, resolving ambiguous mode routing. Keep internal unless the reasoning chain itself is informative to the user.

## Investigation dispatch

When routing detects a bug/issue, investigate via subagent before choosing QUICK_FIX or DIALOGUE:

```
root_cause = Agent(
  model: "sonnet",
  prompt: "Investigate: {bug_description}. Read relevant files. Return one-sentence diagnosis or 'unclear'.",
  run_in_background: true
)
```
