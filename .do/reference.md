# Claude Code Plugin System

## Plugin structure

```
.claude-plugin/
  plugin.json          — name, version, description, author, homepage
  marketplace.json     — marketplace metadata (owner, plugin list)
skills/
  <skill-name>/
    SKILL.md           — skill prompt with YAML frontmatter
commands/
  <command-name>.md    — command prompt with YAML frontmatter
```

## SKILL.md frontmatter

```yaml
---
name: work
description: "Short description shown in skill list"
argument-hint: "[optional hint] — shown after skill name"
---
```

The body after frontmatter is the full prompt injected when the skill is invoked.

## Argument substitution

When the user invokes `/do:work implement search`, the string `implement search` is available as `$ARGUMENTS` in the skill prompt. The skill must handle the case where `$ARGUMENTS` is empty (no argument provided).

## Invocation

- `/do:work` — invokes the work skill from the do plugin
- `/do:release patch` — invokes the release command with argument "patch"
- Format: `/<plugin-name>:<skill-or-command-name> [arguments]`

## Installation paths

Plugins exist in two locations after installation:

- **Marketplace source:** `~/.claude/plugins/marketplaces/<marketplace>/<plugin>/`
- **Cache (resolved):** `~/.claude/plugins/cache/<plugin>/<plugin>/<version>/`

The cache path is what Claude Code actually loads at runtime. The marketplace path is the source of truth for edits. Edits to marketplace files are reflected in cache on next plugin resolution.

## Plugin resolution

`~/.claude/plugins/installed_plugins.json` tracks which plugins are installed. `known_marketplaces.json` maps marketplace names to sources.

## Skill vs command

Both are Markdown files with YAML frontmatter. The distinction is semantic:
- **Skills** (`skills/<name>/SKILL.md`) — complex behavioral prompts, typically multi-mode
- **Commands** (`commands/<name>.md`) — focused procedural prompts, single workflow

## Runtime tools available to skills

Skills have access to all Claude Code tools at invocation time:
- **TaskCreate/TaskUpdate/TaskList/TaskGet** — task list management
- **Agent** — spawn subagents with `mode: "bypassPermissions"` for execution, or specific subagent_types (Explore, Plan) for information gathering
- **EnterPlanMode/ExitPlanMode** — read-only plan mode with user approval flow
- **AskUserQuestion** — structured choice presentation (2-4 options)
- **sequentialthinking** (MCP) — extended reasoning for competing constraints
- **Read/Write/Edit/Glob/Grep/Bash** — standard file and system tools
- **WebSearch/WebFetch** — web research

## Subagent mechanics

Subagents spawned via Agent tool receive only what you pass them — the preamble and task description. They don't inherit the parent's conversation history. `mode: "bypassPermissions"` lets them execute without per-tool user approval. The `model` parameter selects tier (haiku/sonnet/opus).

## Context management

Long sessions compact earlier messages. Critical context that must survive compaction should live in `.do/` files (which get re-read at session start), not in conversation history.

## Pseudocode effectiveness for LLM instruction

Research grounding for the pseudocode-first approach used throughout this system.

### Evidence hierarchy

| Construct | Impact | Source |
|---|---|---|
| Code structure (control flow, branching, nesting) | Highest — primary driver of gains | IBM EMNLP 2023, Waheed 2024 |
| Indentation and visual formatting | Load-bearing — removal is among most damaging perturbations | Waheed 2024 |
| Typed function signatures | Consistent improvement across models | IBM EMNLP 2023 |
| Docstrings (one-line contract + Parameters/Returns) | 2-3 ROUGE-L points; acts as chain-of-thought anchor | IBM EMNLP 2023 |
| Inline comments on non-obvious lines | Consistent improvement; reinforces step-by-step reasoning | IBM EMNLP 2023 |
| Descriptive function/variable names | 15% gain over generic names | IBM EMNLP 2023 |
| Hard/soft contract distinction | Transparency effect — severity categories improve compliance | ABC 2026 |

### Key findings

- Pseudocode prompts produce 7-38% improvement over prose (IBM, 132 tasks, EMNLP 2023)
- Structure > semantics: LLMs are more sensitive to structural perturbations than semantic ones; gap widens with model scale (Waheed, 3331 experiments, 2024)
- Pseudocode achieves 50-70% token reduction while retaining ~95%+ baseline performance on non-code tasks (Waheed 2024)
- Step-by-step natural language procedures are consistently the worst representation across all task types (Waheed 2024)
- Code-form plans show 25% average improvement across 13 benchmarks; gains scale with task complexity (CodePlan, ICLR 2025)
- 0-shot pseudocode outperforms 2-shot — models generate continuation patterns instead of following instructions when given few-shot pseudocode (IBM 2023)
- Adding verbosity beyond the 50-70% density sweet spot actively hurts performance (Waheed 2024)
- Simply specifying behavioral contracts improves compliance before enforcement — the "transparency effect" (ABC 2026)
- Full pseudocode stack (structure + docstrings + comments + types) in 0-shot outperforms all other combinations including few-shot variants (IBM 2023)

### Pseudocode style rules (empirically grounded)

1. Python-like, PEP 8 formatting — Python's proximity to natural language makes it optimal for behavioral specs (Waheed 2024)
2. Typed function signatures: `def name(arg: Type) -> ReturnType:` (IBM 2023)
3. One-line docstrings stating the function's behavioral contract (IBM 2023)
4. Inline `#` comments on non-obvious lines as reasoning cues (IBM 2023)
5. Descriptive function and variable names — never generic placeholders (IBM 2023)
6. Control flow via if/elif/else, for loops — never prose descriptions of branching (IBM 2023, Waheed 2024)
7. Sub-task functions named but not defined — names encode intent (IBM 2023)
8. No classes, imports, generators, list comprehensions — basic constructs only (IBM 2023)
9. Each line does one thing — atomic steps (IBM 2023)
10. Indentation is load-bearing structure, not decoration — never flatten (Waheed 2024)
11. 50-70% token density of full code — lean, not verbose (Waheed 2024)

### What doesn't help

- Few-shot examples with pseudocode — models treat them as continuation patterns (IBM 2023)
- Pseudocode for trivially simple instructions — benefit is proportional to structural complexity (IBM 2023)
- Verbose enrichment beyond 50-70% density — actively degrades performance (Waheed 2024)
- Variable naming semantics — canonical placeholders barely hurt; structure matters far more (Waheed 2024)

### Sources

- Mishra et al. "Prompting with Pseudo-Code Instructions" EMNLP 2023. arxiv.org/abs/2305.11790
- Waheed et al. "On Code-Induced Reasoning in LLMs" 2024. arxiv.org/abs/2509.21499
- Chae et al. "CodePlan: Unlocking Reasoning Potential" ICLR 2025. arxiv.org/abs/2409.12452
- "Agent Behavioral Contracts (ABC)" 2026. arxiv.org/abs/2602.22302
