# Pitfalls

## Spec/code drift after implementation

**Symptom:** Project files describe behaviors, layouts, or APIs that don't match the actual code. The spec looks correct until someone reads both the spec and the code side by side.

**Root cause:** Implementation introduces changes — new API fields, layout restructuring, behavioral tweaks — that never get reflected back into project files. The implementer considers the task "done" when the code works, forgetting that the spec is a parallel representation.

**Fix:** Protocol step 5 (Sync project files) and the bidirectional sync rule. After every execution, diff what was built against `.do/` files. Propose updates for any drift. This must be a mechanical step, not a judgment call — drift is always unacceptable.

**Pattern:** Any system with dual representations (docs/code, schema/implementation, spec/tests) suffers this. The fix is always the same: make sync a protocol step, not a hope.

## Self-targeting path confusion

**Symptom:** When directed to work on the do plugin itself, the skill reads the *project's* `.do/` files instead of the plugin's `.do/` files. Or edits go to the wrong location.

**Root cause:** The plugin's project files live at `~/.claude/plugins/marketplaces/do/.do/`, not in the current working directory. Self-targeting requires explicitly switching to the plugin's path.

**Fix:** When self-targeting is invoked, read from and write to the plugin's `.do/` directory, not the cwd's `.do/`. The SKILL.md self-targeting section should specify this path resolution.

## Plugin cache vs marketplace paths

**Symptom:** Edits to the plugin files don't take effect, or the wrong version of a file is read.

**Root cause:** Installed plugins exist in two locations: `~/.claude/plugins/marketplaces/<name>/` (source) and `~/.claude/plugins/cache/<name>/<name>/<version>/` (resolved). Claude Code loads from cache at runtime. Edits to marketplace files may not reflect in cache until plugin re-resolution.

**Fix:** Edit in the marketplace path (that's the source of truth). Be aware that cache may lag. When in doubt, check both paths.

## Protocol step renumbering

**Symptom:** The protocol references step numbers that don't match after editing. For example, "step 6" means different things before and after inserting a new step.

**Root cause:** Steps are numbered sequentially. Inserting a step shifts all subsequent numbers. References to step numbers elsewhere in the document (or in other files) become wrong.

**Fix:** After inserting or removing protocol steps, scan the entire SKILL.md for step number references and update them. Also check README.md and spec.md for references.

## Small fix bypasses all protocol

**Symptom:** Model reads implementation files and makes edits directly in main context. No task tools used. No subagents dispatched. No project file sync. The fix works but violates every structural invariant.

**Root cause:** The skill had no lightweight execution path. With only full planning available (EnterPlanMode → approval → task creation → subagent dispatch), the model treats small obvious fixes as "not worth the ceremony" and shortcuts everything — implementation, task tracking, and sync.

**Fix:** The quick-fix execution path provides a lighter ceremony (skip plan approval) while preserving the invariants that matter: subagents for implementation, task tools for tracking, project file sync for knowledge capture. The main context rule is now explicit: all implementation file reads and code edits go to subagents, no exceptions.

**Pattern:** When a process has only a heavyweight path, users (and models) will bypass the entire process rather than just the unnecessary parts. Provide graduated paths that preserve core invariants while scaling ceremony to task size.
