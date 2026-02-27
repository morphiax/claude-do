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

## Status

**Completed**: Updated both SKILL.md files for component folder model — replaced `.do/specs/` references with `.do/<component>/`, updated main context rules to allow component spec/context reads. Spec and skills are aligned.
