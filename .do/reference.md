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
