# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`claude-do` is a Claude Code plugin providing five skills: `/do:design` (spec reconciliation, expert analysis, plan assembly), `/do:execute` (dependency-graph execution with test generation and regression gates), `/do:research` (comprehensive knowledge research), `/do:reflect` (adversarial post-execution review), and `/do:refine` (convention-aware code refinement with regression gates). `spec.md` is the single source of truth — everything else is disposable output rebuilt from the spec.

Skills are implemented as SKILL.md prompts. Deterministic operations (spec management, plan finalization, memory/reflection/trace stores) are delegated to a modular Python CLI package (`shared/cli/`).

## Testing

```bash
# Run the full test suite (365 tests)
PYTHONPATH=shared pytest tests/ -x

# Or via justfile
just test
```

Additional dev commands: `just lint`, `just format`, `just typecheck`, `just check` (all four).

Functional testing (after code changes):
```bash
claude --plugin-dir ~/.claude/plugins/marketplaces/do
/do:design <some goal>
/do:execute
```

## Architecture

### Plugin Structure

```
.claude-plugin/
  plugin.json             — Plugin manifest (name, version, metadata)
  marketplace.json        — Marketplace distribution config
shared/
  do.py                   — Entry point (resolves through symlinks)
  cli/                    — Python CLI package
    __init__.py           — Package root (__version__)
    __main__.py           — Argparse dispatcher (7 domains)
    envelope.py           — Result envelope formatting {ok, data/error}
    cli/                  — CLI layer (argument parsing → ops)
      archive.py, memory.py, plan.py, reflection.py,
      research.py, spec.py, trace.py
    ops/                  — Business logic layer
      archive.py, memory.py, plan.py, reflection.py,
      research.py, spec.py, trace.py
    store/                — Persistence primitives
      atomic.py           — Atomic JSON file writes (mkstemp → fsync → replace)
      hash.py             — SHA-256 content hashing
      jsonl.py            — JSONL read/append (O_APPEND for atomicity)
skills/
  {design,execute,research,reflect,refine}/
    SKILL.md              — Skill definition (imperative prompt)
    scripts/
      do.py → ../../../shared/do.py  — Symlink to entry point
spec.md                   — Behavioral specification (source of truth)
tests/                    — pytest test suite (18 modules, 365 tests)
pyproject.toml            — Project config (ruff, mypy, pytest)
justfile                  — Dev commands
```

### Layered Architecture

Three layers with strict dependency direction: `cli/` → `ops/` → `store/`.

- **`store/`** — Low-level persistence primitives. Atomic file writes, content hashing, JSONL read/append.
- **`ops/`** — Business logic. Plan finalization/DAG validation, spec registry (register/satisfy/preflight/divergence), memory/reflection/trace/research stores, archive management.
- **`cli/`** — Argument parsing. Registers domain subparsers, delegates to ops, renders JSON envelopes.

### CLI Invocation

Skills resolve `scripts/do.py` (a symlink to `shared/do.py`). The entry point uses `os.path.realpath()` to find `shared/`, adds it to `sys.path`, and imports `cli.__main__`.

```bash
python3 $DO <domain> <command> --root .do
```

Seven domains: `spec`, `memory`, `reflection`, `trace`, `research`, `plan`, `archive`. All output is JSON to stdout (`{ok: true/false, ...}`). Exit 0 for success, 1 for errors.

For dev tooling (tests, linting), use `PYTHONPATH=shared` so Python can find the `cli` package:

```bash
PYTHONPATH=shared pytest tests/ -x
```

### Skill Files Are the Implementation

The SKILL.md files are imperative prompts that Claude interprets at runtime. Each has YAML frontmatter (`name`, `description`, `argument-hint`, `allowed-tools`, `model`, `satisfies`) that must be preserved.

- **design**: Reconcile spec with product, author behavioral contracts (TDD), expert analysis, plan assembly
- **execute**: Test generation, topological execution, worker verification, spec satisfaction, regression gates
- **research**: Hypothesis-driven investigation with three source types, structured synthesis
- **reflect**: Adversarial review (5 dimensions), observation persistence. Runs in `context: fork`
- **refine**: Convention-aware code refinement with regression gates. Runs in `context: fork`

### Runtime Data (`.do/`)

Skills communicate through JSONL stores in `.do/` (gitignored):

- `specs.jsonl` — Behavioral contract registry (register → satisfy → preflight)
- `memory.jsonl` — Cross-session learnings (importance-scored, keyword-searchable)
- `reflections.jsonl` — Post-execution observations (lens: product/process, urgency: immediate/deferred)
- `traces.jsonl` — Append-only event log
- `research/` — Per-artifact JSON files
- `conventions.md` — Project-specific conventions (per-project, created by design)
- `aesthetics.md` — UI/UX guidelines (per-project, created by design)
- `plans/current.json` — Active execution plan
- `history/` — Archived ephemeral state (timestamped)

Persistent files (survive archiving): `specs.jsonl`, `memory.jsonl`, `reflections.jsonl`, `traces.jsonl`, `conventions.md`, `aesthetics.md`, `research/`.

## Requirements

- Claude Code 2.1.32+
- Python 3.10+ (for CLI package)

## Commit Conventions

Conventional commits with imperative mood: `feat:`, `fix:`, `chore:`, `refactor:`, `docs:`, `test:`. Example: `feat: add retry context to agent prompt`.

## Pre-commit Checklist

Before every commit and push:

1. **Run tests**: `PYTHONPATH=shared pytest tests/ -x` — all must pass.
2. **Update docs**: If SKILL.md changes affect architecture, update `CLAUDE.md` and `README.md` to match.
3. **Update changelog**: Add an entry to `CHANGELOG.md` under the current version for every functional change.
4. **Bump version**: Increment version in `.claude-plugin/plugin.json`, `shared/cli/__init__.py`, and `README.md` badge.
