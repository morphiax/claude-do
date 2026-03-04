# Lessons

## Decisions

### Single unified skill over separate mode-specific skills

**Context:** Mode transitions happen naturally — discovering a gap during execution needs dialogue, resolving a question leads to planning. Separate skills (e.g., `/do:shape`, `/do:build`) would require exiting one, invoking another, and re-reading project state.

**Alternative:** Separate skills with explicit triggers. The human decides which mode to enter.

**Tipping point:** A unified skill preserves context across transitions and removes mode-selection burden from the human.

**Reversal cost:** Moderate. Each skill would need its own transition-out logic and duplicate shared protocol steps.

### Four files over seven specialized files

**Context:** An earlier iteration used seven files (spec, reference, stack, design, architecture, decisions, pitfalls). Three natural groupings emerged: stack + reference → "implementation environment," decisions + pitfalls → "lessons," architecture → belongs in spec alongside behaviors.

**Alternative:** Keep seven files. More precise routing and smaller individual files.

**Tipping point:** Four files satisfy "a future session can orient, build, and avoid known traps" with less routing overhead. The routing heuristic stays unambiguous with four targets. The original two-file failure (context.md as dumping ground) doesn't recur because four files have distinct concerns.

**Reversal cost:** Low. Splitting back is mechanical, but routing overhead and file-count burden on small projects return.

### Reconstructed state over persistent status file

**Context:** Sessions need to know what happened since last session — via a status file or reconstructed from project files and git diffs.

**Alternative:** Maintain a status.md tracking done, in-progress, and next.

**Tipping point:** Status files go stale immediately. Git history and project files are ground truth. A status file is a third source that contradicts the other two whenever someone forgets to update it.

**Reversal cost:** Negligible.

### Mandatory sync gate over aspirational sync step

**Context:** After execution, the sync step was consistently skipped — momentum to report success outweighed the instruction to verify sync. Project files described behaviors that didn't match implementation; new behaviors existed in code but not spec.

**Alternative:** Stronger language ("this is mandatory"), or automated diff tooling.

**Tipping point:** Aspirational instructions ("remember to X") fail under momentum because omitting them produces no visible gap. A required output format — enumerate each behavior changed, confirm spec coverage — fails visibly. The response skeleton has a mandatory section that is either filled or conspicuously absent.

**Reversal cost:** Low structurally, but silent spec drift returns immediately — the aspirational version was already tried and failed.

**Pattern class:** Dual-representation drift. Any system with two representations of the same truth suffers this. Mechanical gates with required output survive because skipping them produces a visible gap.

### Quick-fix path over full-planning-only execution

**Context:** With only full planning available, the system treated small fixes as "not worth the ceremony" and bypassed everything — not just plan approval, but subagents, task tracking, and sync. A second failure: the system would state a diagnosis and immediately dispatch without waiting for human input.

**Alternative:** Enforce full planning for everything regardless of size.

**Tipping point:** The all-or-nothing dynamic meant rejecting ceremony also rejected the invariants embedded within it. A lighter path preserves what matters (subagents, task tools, sync gate) while dropping what doesn't (plan approval for self-evident fixes). The threshold is clarity, not size. The stop-and-wait gate uses unambiguous verbs ("stop," "wait") with inline rationale — "they may have context that changes the approach" — because ambiguous gates collapse to non-blocking under momentum.

**Reversal cost:** Low structurally, but the system resumes bypassing everything when the only option is heavyweight.

**Pattern classes:** Graduated-path absence — when a process has only a heavyweight path, it gets bypassed wholesale. Ambiguous-gate collapse — instructions interpretable as blocking or non-blocking will be interpreted as non-blocking under momentum.

### Orchestrator/worker context boundary

**Context:** Without the boundary, "just one file" becomes seven — investigation work pollutes the context window, displacing project-level reasoning with implementation details. The rule against main-context reads is negative ("don't do X") and competes with the positive pull to "get the answer now."

**Alternative:** Allow main context to read and edit implementation files directly, using subagents only for parallel work.

**Tipping point:** The context boundary is a forcing function: the orchestrator thinks about what to do, subagents think about how to do it. When a subagent returns incomplete results, dispatch a targeted follow-up — frame the compliant path as the efficient path, not as compliance overhead.

**Reversal cost:** High. Removing the boundary is easy. Re-establishing discipline after erosion is hard — every exception trains the system to bypass.

**Pattern class:** Negative-rule erosion. Rules that say "don't do X" lose to efficiency pressure when X is immediately available. Reframing the compliant path as faster makes compliance the path of least resistance.

### Pseudocode over prose for mechanisms in spec

**Context:** The spec describes routing logic, validation functions, and session sequences. These could be prose or pseudocode.

**Alternative:** Prose throughout, pseudocode reserved for algorithms only.

**Tipping point:** Three converging lines: (1) Pseudocode prompts produce 7-38% improvement over prose (IBM EMNLP 2023); code-form plans show 25% average improvement scaling with complexity (CodePlan ICLR 2025); step-by-step prose is consistently the worst representation (Waheed 2024). (2) LLMs are more sensitive to structural perturbations than semantic ones, gap widening with scale (Waheed, 3331 experiments). (3) Prose is ambiguous about ordering and conditionality; pseudocode makes control flow explicit, and the contract-vs-comment rule prevents requirements from hiding in comments.

**Reversal cost:** High. 7-38% effectiveness loss. Ordering and branching contracts would need re-discovery through testing.

### Hard/soft invariant distinction

**Context:** Originally all invariants were treated equally. Some (like `bidirectional_sync`) are non-negotiable; others (like `next_steps` formatting) are recoverable within a session.

**Alternative:** Keep all invariants at equal severity.

**Tipping point:** The ABC framework (2026) demonstrated a "transparency effect" — specifying severity categories improves compliance even before enforcement. Hard constraints called out as hard get violated less than undifferentiated constraints.

**Reversal cost:** Negligible cosmetically, but compliance benefit degrades.

### Progressive disclosure over upfront loading

**Context:** Loading all model files upfront means 40-60% of context is irrelevant to any given session.

**Alternative:** Read everything upfront. Simpler protocol, no loading decisions.

**Tipping point:** Three converging lines: (1) 30%+ performance drop when relevant information sits mid-context ("Lost in the Middle," Liu et al., TACL 2024). (2) Reliability degrades with context length even when the model can answer correctly ("Context Rot," Chroma Research 2025). (3) Industry convergence on just-in-time loading — Anthropic's Agent Skills, Vercel's tool reduction, PageIndex, LATTICE, DocAgent all load an index first, fetch on demand.

The spec stays as one file — the split is in how it's consumed, not stored. Most project specs (50-200 lines) don't benefit from progressive disclosure.

**Reversal cost:** Low structurally, but attention benefit lost immediately.

### Self-contained operational document over spec-derived document

**Context:** During SKILL.md optimization, content was cut "because the spec already has it." But SKILL.md runs inside other projects where `.do/` contains THAT project's files — not the do plugin's own spec. The spec is a blueprint for builders; SKILL.md is the built thing. They serve different audiences.

**Alternative:** Derive SKILL.md from spec at runtime, or reference spec sections.

**Tipping point:** When SKILL.md runs in project X, `.do/spec.md` is project X's spec. Every behavioral contract, validator, and quality bar SKILL.md needs must be inline. Cutting a validator from SKILL.md because the do plugin's spec has it means the validator vanishes when the skill runs anywhere else. The first optimization attempt (3 passes, 904→793 lines) had to be fully reverted when this was discovered.

**Reversal cost:** High. Any content removed from SKILL.md "because spec has it" silently disappears from the running system. The damage is invisible until quality degrades in another project.

**Pattern class:** Meta-project confusion. When a project's artifacts include operational documents that run in OTHER projects, the authoring context (where spec is accessible) differs from the execution context (where it isn't). Content that looks redundant during authoring is essential during execution.

## Pitfalls

### Information routed to wrong project file

**Symptom:** A debugging insight ends up in spec.md. A behavioral contract sits in context.md. Future sessions look in the right file and don't find what they need.

**Root cause:** Under time pressure or when content spans categories, the system picks the file it's currently editing rather than the correct target.

**Pattern class:** Routing-under-pressure collapse. The system defaults to proximity (current file) instead of correctness (right file). Explicit routing functions applied before writing prevent this.

### Subagent preamble missing validate_output test

**Symptom:** Subagent output passes task requirements but fails system-wide quality bars — tests assert implementation details, spec entries lack quality expectations.

**Root cause:** Preamble assembled without the quality gate. The subagent optimizes for task completion, not quality, because it has no way to know the standard.

**Pattern class:** Context-window quality decay. Quality gates must travel with the work, not live only in the orchestrator's context.

### Plan tasks that require prior context to execute

**Symptom:** Subagent guesses at file locations, invents patterns that don't match existing code, or asks questions the orchestrator already resolved during planning.

**Root cause:** The planner writes task descriptions that assume the reader shares their context. "Implement the search endpoint" is clear to the planner but useless to a zero-context subagent.

**Pattern class:** Curse-of-knowledge in delegation. The delegator's context makes instructions feel complete when they're dependent on shared knowledge. The fix is always a zero-context test: can someone with only this text execute the task?

### Principles amplify quality bars for model file authorship

**Context:** Quality bars check structure — design.md has typography, context.md has quality infrastructure entries. But structural completeness doesn't prevent low-quality content. A design session produced generic output that passed all quality bars; the same session re-run through the principles produced markedly better results.

**Alternative:** Add more structural checks to quality bars (e.g., "typography must not be system fonts").

**Tipping point:** Structural checks multiply without bound — one per failure mode. Principles are a small, stable set that catch entire categories. "Intentional even over automatic" catches generic typography, default color palettes, vague recipes, AND underspecified conventions — all in one principle. The quality bars check that the right sections exist; the principles check that the content is worth having.

**Reversal cost:** Low structurally, but quality of model file content regresses to passing-the-checklist.

**Pattern class:** Structure-content gap. Validation that checks structure without checking intent produces artifacts that are complete but not useful. Principles bridge the gap because they're evaluable against content, not just shape.

### Host platform feature supersedes skill directives

**Symptom:** `EnterPlanMode` transfers control to the platform's planning protocol. The skill's task validation, preamble construction, and response skeletons are all replaced. The plan looks reasonable but doesn't follow the skill's quality bars.

**Root cause:** Platform features have their own governing prompts that supersede the skill's SKILL.md for the duration. The skill's directives don't survive the mode transition.

**Pattern class:** Protocol handoff directive loss. When a skill delegates to a platform feature with its own prompt, the skill's directives are superseded. Fix by prohibition: if the skill already implements the capability, never hand off to the platform's version.
