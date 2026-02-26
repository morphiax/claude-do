---
description: "Version bump, changelog, docs sync, commit, and push."
argument-hint: "patch | minor | major"
---

# Release

Prepare and ship a new version of the current project.

## Steps

1. **Detect versioning.** Find all version sources in the project. Common locations:
   - `package.json` (version field)
   - `pyproject.toml` / `setup.cfg` / `setup.py`
   - `Cargo.toml`
   - `.claude-plugin/plugin.json`
   - Version constants in source code (e.g., `__version__`, `VERSION`)
   - Version badges in `README.md`
   Report what you found and the current version.

2. **Determine bump type.** Use `$ARGUMENTS` if provided (patch, minor, or major). If omitted, infer from git log since the last tag — breaking changes → major, new features → minor, fixes → patch. Confirm with the user if ambiguous.

3. **Bump versions.** Update every version source found in step 1 to the new version. All must match.

4. **Update changelog.** Find or create `CHANGELOG.md`. Add an entry for the new version using Keep a Changelog format. Populate it from git log since the last version tag — group under Added, Changed, Fixed, Removed as appropriate. Write concise, human-readable entries (not raw commit messages).

5. **Sync docs.** Read `README.md` and compare it against the full diff since the last version tag (`git diff <last-tag>..HEAD`). Look for prose that has become inaccurate — feature descriptions that no longer match behavior, API examples using old signatures, removed options still documented, new capabilities not mentioned. Update the prose to reflect reality. Also update version references (badges, install instructions). Don't rewrite sections that are still accurate.

6. **Commit.** Stage all changed files and commit with message: `release: vX.Y.Z`. All commit messages and changelog entries must read as human-written — no AI attribution, co-authorship trailers, or any indication of AI/LLM involvement.

7. **Tag.** Create an annotated git tag: `vX.Y.Z`

8. **Push.** Push the commit and tag to the remote. Confirm with the user before pushing.

## Scope

Only version, changelog, docs, commit, tag, push. Don't run builds, publish to registries, or create GitHub releases — those are separate concerns.
