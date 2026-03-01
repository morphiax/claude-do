# Stack

## Runtime

Pure Markdown. No runtime code, no dependencies, no build step. The plugin is a collection of prompt files that Claude Code loads and injects.

## Conventions

- **Skills**: `skills/<name>/SKILL.md` with YAML frontmatter (name, description, argument-hint)
- **Commands**: `commands/<name>.md` with YAML frontmatter (description, argument-hint)
- **Plugin metadata**: `.claude-plugin/plugin.json` (name, version, description, author)
- **Marketplace metadata**: `.claude-plugin/marketplace.json` (owner, plugin list)
- **Changelog**: `CHANGELOG.md` in Keep a Changelog format, newest first
- **Docs**: `README.md` with usage examples and install instructions

## Versioning

Semantic versioning. Version tracked in `.claude-plugin/plugin.json`. Tagged releases as `vX.Y.Z`. Use `/do:release` to ship.

## Structure

```
.claude-plugin/
  plugin.json
  marketplace.json
.do/                    — plugin's own project files (this directory)
skills/
  work/SKILL.md         — the unified working skill
commands/
  release.md            — version release workflow
CHANGELOG.md
README.md
LICENSE
```

## Subagent dispatch

During execution, subagents are spawned via the Agent tool with `mode: "bypassPermissions"`. Each receives the plan preamble plus its assigned task description.

Model tier selection by task complexity:
- **haiku** — mechanical tasks (file renaming, simple refactors, boilerplate)
- **sonnet** — standard tasks (feature implementation, test writing, moderate analysis)
- **opus** — complex tasks (architectural decisions, multi-file refactors, nuanced interpretation)

## Distribution

Claude Code marketplace. Install via `claude plugin add morphiax/do`.
