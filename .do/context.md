# do:work — Context

This file maps the behavioral spec to the Claude Code plugin system and captures technology choices and external system knowledge. The spec describes WHAT; this file describes HOW within the current technology.

## Runtime

Pure Markdown. No runtime code, no dependencies, no build step. The plugin is a collection of prompt files that Claude Code loads and injects.

## Structure and conventions

Semantic versioning in `.claude-plugin/plugin.json`. Tagged `vX.Y.Z`. Use `/do:release` to ship. Distributed via Claude Code marketplace: `claude plugin add morphiax/do`.

```
.claude-plugin/
  plugin.json            — name, version, description, author
  marketplace.json       — owner, plugin list
.do/                     — project model files (this directory)
skills/
  work/SKILL.md          — YAML frontmatter (name, description, argument-hint) + prompt body
commands/
  release.md             — YAML frontmatter (description, argument-hint) + procedural prompt
CHANGELOG.md             — Keep a Changelog format, newest first
README.md                — usage examples and install instructions
LICENSE
```

## Model directory

The persistent mental model lives in `.do/` under the project root. Four files:

```
.do/spec.md       — behaviors + algorithms (what the system does)
.do/context.md    — technology, conventions, external system facts
.do/design.md     — aesthetic direction, output surfaces
.do/lessons.md    — decisions (why) + pitfalls (what broke)
```

## Self-targeting path

`~/.claude/plugins/marketplaces/do/.do/` when arguments reference the do plugin itself, otherwise `<cwd>/.do/`.

## Version control

Orient uses:
```
git log --oneline -10
git diff HEAD~1 --stat
```

## Worker dispatch

```
dispatch_worker(task):
  Agent(
    mode:             "bypassPermissions",
    model:            task.tier,
    prompt:           preamble + task.description,
    run_in_background: true
  )
```

Independent tasks launch as multiple Agent calls in a single message (concurrent). Dependent tasks wait for predecessors. Investigation dispatch uses the same pattern: `Agent(model: "sonnet", prompt: "Investigate: {bug}. Read relevant files. Return one-sentence diagnosis or 'unclear'.")`.

## Complexity tier mapping

```
mechanical  = haiku    # file renaming, simple refactors, boilerplate
standard    = sonnet   # feature implementation, test writing, moderate analysis
complex     = opus     # architectural decisions, multi-file refactors, nuanced interpretation
```

## Task management

```
create_task(title, description)  ->  TaskCreate(subject=title, activeForm=description)
set_dependencies(blocked_by)     ->  TaskUpdate(taskId, addBlockedBy=blocked_by)
mark(task, in_progress)          ->  TaskUpdate(taskId, status="in_progress")
mark(task, completed)            ->  TaskUpdate(taskId, status="completed")
```

## Context boundary enforcement

```
ORCHESTRATOR (main context):
  allowed:   Read .do/*, Bash(git commands), dialogue, planning, TaskCreate, TaskUpdate
  forbidden: Read/Glob/Grep on non-.do/ paths, Edit/Write code files, EnterPlanMode
WORKER (Agent subagent):
  receives preamble + task description only — clean context, no conversation history
```

## Preamble construction

```
build_preamble(project):
  content = ""
  for file in read_all(project.do_path):
    content += file.content
  content += validate_output_test   # from spec section 9
  return content
```

## Claude Code plugin system

`$ARGUMENTS` is the string after the skill name; handle empty case.

### Invocation

Format: `/<plugin-name>:<skill-or-command-name> [arguments]`

### Installation paths

- **Marketplace source:** `~/.claude/plugins/marketplaces/<marketplace>/<plugin>/` — source of truth for edits
- **Cache (resolved):** `~/.claude/plugins/cache/<plugin>/<plugin>/<version>/` — what Claude Code loads at runtime
- **Resolution:** `~/.claude/plugins/installed_plugins.json` tracks installed plugins; `known_marketplaces.json` maps marketplaces to sources

### Runtime tools available to skills

- **TaskCreate/TaskUpdate/TaskList/TaskGet** — task list management
- **Agent** — spawn subagents with `mode: "bypassPermissions"` for execution, or specific subagent_types (Explore, Plan) for information gathering
- **AskUserQuestion** — structured choice presentation (2-4 options)
- **mcp__sequential-thinking__sequentialthinking()** — extended reasoning for competing constraints or fuzzy intent
- **Read/Write/Edit/Glob/Grep/Bash** — standard file and system tools
- **WebSearch/WebFetch** — web research

## Pseudocode effectiveness for LLM instruction

Research grounding for the pseudocode-first approach used throughout this system.

Per-construct evidence: code structure and indentation have the highest impact, followed by typed signatures, docstrings, inline comments, and descriptive names (IBM EMNLP 2023, Waheed 2024). Hard/soft contract distinction improves compliance via transparency effect (ABC 2026).

### Key findings

- Pseudocode prompts produce 7-38% improvement over prose (IBM, 132 tasks, EMNLP 2023)
- Structure > semantics: LLMs are more sensitive to structural perturbations than semantic ones; gap widens with model scale (Waheed, 3331 experiments, 2024)
- Pseudocode achieves 50-70% token reduction while retaining ~95%+ baseline performance; verbosity beyond this sweet spot actively hurts (Waheed 2024)
- Step-by-step natural language procedures are consistently the worst representation across all task types (Waheed 2024)
- Code-form plans show 25% average improvement across 13 benchmarks; gains scale with task complexity (CodePlan, ICLR 2025)
- 0-shot pseudocode outperforms 2-shot — models generate continuation patterns instead of following instructions when given few-shot pseudocode (IBM 2023)
- Simply specifying behavioral contracts improves compliance before enforcement — the "transparency effect" (ABC 2026)
- Full pseudocode stack (structure + docstrings + comments + types) in 0-shot outperforms all other combinations including few-shot variants (IBM 2023)

Benefits scale with structural complexity; variable naming barely matters compared to structure (IBM 2023, Waheed 2024). Style rules derived from this evidence are codified in spec §9 `validate_pseudocode_style`.

### Sources

- Mishra et al. "Prompting with Pseudo-Code Instructions" EMNLP 2023. arxiv.org/abs/2305.11790
- Waheed et al. "On Code-Induced Reasoning in LLMs" 2024. arxiv.org/abs/2509.21499
- Chae et al. "CodePlan: Unlocking Reasoning Potential" ICLR 2025. arxiv.org/abs/2409.12452
- "Agent Behavioral Contracts (ABC)" 2026. arxiv.org/abs/2602.22302
