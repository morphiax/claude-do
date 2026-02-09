# Contributing to do

Thank you for your interest in contributing to the `do` plugin for Claude Code.

## How to Contribute

### Fork and PR Workflow

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Make your changes
4. Test locally with `claude --plugin-dir /path/to/claude-do`
5. Commit using conventional commit format (see below)
6. Push to your fork
7. Open a Pull Request

### Testing Your Changes

Before submitting a PR, test your changes locally:

```bash
# Test the plugin in Claude Code
claude --plugin-dir /path/to/your/fork/claude-do

# Then try the skills
/do:design <some goal>
/do:execute
```

### Commit Conventions

Follow conventional commit format with imperative mood:

- `feat: add new feature`
- `fix: resolve bug`
- `chore: update dependencies`
- `refactor: restructure code`
- `docs: update documentation`
- `test: add tests`

Do NOT use past tense (Added, Fixed, etc.) - use imperative present (Add, Fix, etc.)

### Skill Modifications

When modifying skill files (`skills/design/SKILL.md` or `skills/execute/SKILL.md`):

- Preserve the YAML frontmatter (name, description, argument-hint)
- Test the full workflow (plan generation and execution)
- Update documentation if behavior changes

### Reporting Issues

Open an issue on GitHub with:

- Clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Claude Code version
- Plugin version

## Code of Conduct

Be respectful, constructive, and professional. This is a small community plugin - let's keep it welcoming.

## Questions?

Open a discussion on GitHub or file an issue.
