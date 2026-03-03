---
description: "Version bump, changelog, docs sync, commit, and push."
argument-hint: "patch | minor | major"
---

# Release

Prepare and ship a new version of the current project.

```
release(arguments: str, working_directory: Path):
  """Bump version, changelog, sync docs, commit, tag, and push."""
  sources = detect_versions(working_directory)
  assert len(sources) > 0  # at least one version source must exist
  report(sources, current_version=sources[0].version)

  if sources_disagree(sources):
    warn("version sources are out of sync")
    report(each_source_and_its_version)

  bump = determine_bump(arguments, working_directory)
  new_version = apply_bump(sources[0].version, bump)

  for source in sources:
    update(source, new_version)

  changelog = build_changelog_entry(new_version, working_directory)
  write_changelog(changelog, working_directory)

  sync_docs(new_version, working_directory)

  stage(all_changed_files)
  commit(message=f"release: v{new_version}")
  tag(name=f"v{new_version}", annotated=true)

  assert WAIT_FOR_HUMAN_RESPONSE()  # confirm before pushing
  push(commit_and_tag, to=remote)
```

```
detect_versions(path: Path) -> list[VersionSource]:
  """Find every file that contains a version declaration."""
  candidates = [
    "package.json",           # version field
    "pyproject.toml",         # [project] or [tool.poetry] version
    "setup.cfg", "setup.py",  # Python packaging
    "Cargo.toml",             # Rust
    ".claude-plugin/plugin.json",  # Claude Code plugin
  ]
  sources = []
  for candidate in candidates:
    if exists(path / candidate):
      version = extract_version(candidate)
      if version: sources.append(VersionSource(candidate, version))

  # also scan for version constants in source code
  source_constants = grep(path, patterns=["__version__", "VERSION =", "version ="])
  for match in source_constants:
    if is_version_declaration(match): sources.append(match)

  # check README for version badges or install instructions
  if exists(path / "README.md"):
    badges = find_version_references("README.md")
    for badge in badges: sources.append(badge)

  return sources
```

```
determine_bump(arguments: str, path: Path) -> BumpType:
  """Resolve bump type from arguments or infer from commit history."""
  if arguments in ["patch", "minor", "major"]:
    return BumpType(arguments)

  last_tag = find_last_version_tag(path)
  if no last_tag:
    commits = all_commits(path)
  else:
    commits = commits_since(last_tag)

  # infer from conventional commit patterns
  if any commit has breaking_change:    return MAJOR
  if any commit has new_feature:        return MINOR
  else:                                 return PATCH

  if ambiguous:
    present(evidence_for_each_option)
    assert WAIT_FOR_HUMAN_RESPONSE()
```

```
build_changelog_entry(version: str, path: Path) -> ChangelogEntry:
  """Build a grouped, human-readable changelog entry from commit history."""
  last_tag = find_last_version_tag(path)
  if no last_tag:
    commits = all_commits(path)
  else:
    commits = commits_since(last_tag)

  # group commits by change type
  groups = classify(commits, into=[Added, Changed, Fixed, Removed])

  for group in groups:
    for entry in group:
      # each entry: imperative mood, one line, user-visible change
      assert describes_what_changed_for_user(entry)  # not implementation detail
      assert not raw_commit_message(entry)            # rewrite, don't copy
      assert not mentions_ai_or_llm(entry)            # reads as human-written

    # order within group: most significant first
    group.sort(by=significance)

  # omit: merge commits, version bumps, CI-only changes, formatting-only
  groups = filter_noise(groups)

  if no existing changelog:
    create("CHANGELOG.md", with_header="# Changelog")

  return format_entry(version, date=today, groups=groups)
```

```
sync_docs(new_version: str, path: Path):
  """Update README prose that has become inaccurate since last release."""
  if not exists(path / "README.md"): return  # nothing to sync

  last_tag = find_last_version_tag(path)
  if no last_tag:
    diff = all_changes(path)
  else:
    diff = git_diff(last_tag, "HEAD")

  readme = read("README.md")

  # check each section against the diff
  for section in readme.sections:
    if section describes feature AND feature_changed_in(diff):
      update(section, to_reflect=current_behavior)
    if section has version_reference:
      update(version_reference, to=new_version)
    if section describes removed_feature:
      remove_or_update(section)
    if diff introduces new_capability AND not_mentioned_in(readme):
      add(description, in_appropriate_section)

  # don't rewrite sections that are still accurate
  assert only_changed_sections_that_drifted(readme)
```

## Preconditions

```
check_preconditions(path: Path) -> proceed | abort:
  """Verify the working directory is ready for a release."""
  if not is_git_repo(path):          abort("not a git repository")
  if has_uncommitted_changes(path):  abort("working directory is dirty — commit or stash first")
  if not has_remote(path):           warn("no remote configured — will skip push")
```

## Scope

Only version, changelog, docs, commit, tag, push. Don't run builds, publish to registries, or create GitHub releases — those are separate concerns.

All commit messages and changelog entries must read as human-written — no AI attribution, co-authorship trailers, or any indication of AI/LLM involvement.
