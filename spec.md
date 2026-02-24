# claude-do Behavioral Specification

Behavioral contracts for claude-do. Technology-agnostic: WHAT and WHY, not HOW. Sufficient to rebuild the system without the existing implementation.

Each testable contract has a stable ID (for example, `[DC-1]`). Status is tracked in a companion store (implementation choice). All contracts start **pending** — absence of a satisfaction record is the signal (§6.3).

---

## 1. System Purpose

claude-do is a multi-agent goal decomposition and execution system. A user states a goal in natural language. The system decomposes it into specialist roles, executes them via parallel agents, and accumulates operational learnings across cycles.

Plugin for an LLM coding assistant. Skills are imperative prompts interpreted at runtime; deterministic scripts handle validation, state management, and computation. LLM: orchestration, judgment, synthesis. Scripts: everything reproducible.

**Key concepts** (referenced throughout; defined here for top-down reading):

- **Lead** — The main conversation context that orchestrates the system. The lead invokes skills, spawns agents, presents results to the user, and makes transition decisions. It does not read source code or write implementation artifacts directly (§4.1).
- **Role** — A scoped unit of work within a plan. Each role has a name, goal, mapped contract IDs, scope directories, expected outputs, context, constraints, verification commands, and a model assignment. Roles are the atoms of work decomposition — one worker per role (§3.1, §4.2).
- **Worker** — A subagent spawned to execute a single role. Workers read the plan directly, operate within their declared scope, and report completion. The lead verifies their claims (§4.2).
- **Skill** — An imperative prompt loaded into an LLM's context at runtime. Skills define complete workflows (design, execute, research, reflect, refine). The prompt IS the implementation (§7.3).

### 1.1 Core Lifecycle

The primary workflow is a cycle:

**Core skills** — user-invoked, lead-driven transitions between them:

1. **Design** — Decompose a goal into expert analysis → role-based execution plan
2. **Execute** — Generate tests from contracts, then spawn specialist workers to implement against those tests

**Auxiliary skills** — invoked by core skills, by each other, or by the user directly:

3. **Research** — Produce structured knowledge artifacts with actionable recommendations
4. **Reflect** — Adversarial review in isolated context, producing classified observations (product/process, immediate/deferred)
5. **Refine** — Improve accepted artifacts in isolated context, preserving functionality while enhancing clarity and consistency

Each cycle produces persistent artifacts (memory, reflections, specs) that inform the next cycle.

#### Lifecycle Orchestration

Core skills do not auto-chain — the lead presents results and gets user direction at each transition. Auxiliary skills are composable: invoked as sub-steps within core skills, no user checkpoint required.

- `[LC-1]` The lifecycle is lead-driven. The lead SHALL invoke core skills explicitly. WHEN a core skill completes, the lead SHALL present its results to the user before invoking the next core skill. The user may direct the lead to proceed, adjust, or stop at any transition point.

#### Skill Composition

- `[LC-2]` Core skills MAY invoke auxiliary skills as sub-steps when required by their contracts. Auxiliary skills MAY invoke other auxiliary skills. Core skills MUST NOT invoke other core skills `[LC-10]`.
- `[LC-3]` Mandatory compositions:
  - Design SHALL invoke research when knowledge gaps are identified `[DC-14]` or conventions require external investigation `[XC-25]`.
  - Design SHALL invoke refine on the spec document after authoring or updating it `[DC-19]`.
  - All core skills SHALL invoke reflect at the end of their run `[XC-15]`. Reflect runs in context isolation `[FC-1]`.
  - Execute SHALL invoke refine after reflect `[LC-7]`, then archive `[LC-8]`.
- `[LC-4]` Auxiliary skill invocations within a core skill do not require user checkpoints. The core skill manages the auxiliary lifecycle and presents consolidated results to the user when the core skill completes.

#### Post-Execution Lifecycle

- `[LC-5]` WHEN execute completes, reflect SHALL be invoked before the cycle is considered complete. Execution without adversarial review is an incomplete cycle — the system does not know whether its output is correct until reflect has examined it.
- `[LC-6]` WHEN reflect produces immediate observations (product or process), the lead SHALL present them to the user for evaluation before proceeding to refine or archive. The user decides per finding whether to patch the artifact, redo the step, or accept the finding as-is. Unresolved immediate findings block the transition to refine.
- `[LC-7]` WHEN all immediate observations from reflect are resolved (or reflect produced none), the lead SHALL invoke refine on the accepted artifacts. Refine is mandatory — every execution cycle produces artifacts that benefit from a consistency and clarity pass. The refine step runs in context isolation `[FC-1]`.
- `[LC-8]` WHEN the cycle is complete — execute, reflect, and refine have run, with all immediate findings resolved — the lead SHALL archive ephemeral artifacts per `[XC-22]` to preserve clean state for the next cycle. A new cycle MUST NOT begin with stale plan state from the previous one `[LC-11]`.
- `[LC-9]` Research is not a fixed lifecycle step. It MAY be invoked at any point — by the user directly, or by any skill when knowledge gaps are identified. Research results persist in the research store and are available to all subsequent skills and cycles.

**Prohibitions**:

- `[LC-10]` Core skills MUST NOT invoke other core skills.
- `[LC-11]` A new cycle MUST NOT begin with stale plan state from the previous one.
- `[LC-12]` Skills MUST NOT skip mandatory invocations (for example, execute MUST invoke reflect before the cycle is considered complete).
- `[LC-13]` Skills MUST NOT perform work assigned to other skills (execute does not write specs, reflect does not modify code, refine does not add features).
- `[LC-15]` WHEN design hands off to execute (the user invokes execute after design completes), the system SHALL verify handoff preconditions before starting execution: (a) the plan exists and is finalized, (b) the spec registry is non-empty when the plan references contract_ids, (c) all plan contract_ids are registered in the spec registry, and (d) at least one plan contract_id is pending — if all are already satisfied, there is no work for execute. Execute SHALL refuse to start when any precondition fails, with a specific report of which precondition was violated.
- `[LC-14]` WHEN a skill invokes another skill that requires context isolation (`[FC-1]`, `[RN-1]`), the invoking skill SHALL spawn a separate agent and instruct that agent to load and execute the target skill. The invoking skill MUST NOT load the target skill's prompt into its own context. Loading an isolation-requiring skill into the invoking context exposes the target to the invoking conversation's reasoning, defeating the isolation that `[FC-1]` and `[RN-1]` require. The invoking skill provides only the arguments and any persistent-state references — the spawned agent loads the skill prompt independently.

### 1.2 Persistent State

Between cycles, the system preserves:

- **Memory** — Accumulated operational learnings with importance scoring
- **Reflections** — Classified observations (product/process, immediate/deferred) about what worked, what failed, and what to improve
- **Specs** — Behavioral contracts that grow monotonically across cycles
- **Traces** — Event log for cross-run analysis
- **Research** — Knowledge artifacts from research runs
- **Conventions** — Project-level implementation conventions (technology choices, coding standards, platform-specific patterns)
- **Aesthetics** — Visual identity and interaction design foundations for user-facing products (aesthetic direction, visual language, mental models, information architecture, state design, interaction patterns)

Ephemeral artifacts (plans, expert findings, worker outputs) are archived to history after each cycle.

### 1.3 Self-Containment

The system SHALL be fully portable — it must work on any machine with no setup beyond the plugin itself.

- All operational state (memory, reflections, specs, traces) lives within the plugin's own artifact directory, portable with the project.
- `[SC-1]` The system MUST NOT depend on host-level user memory, personal configuration, or per-machine state to function correctly. A user who has never run the plugin before SHALL get correct results on first use.
- External user memory (if the host platform provides it) MAY enhance the experience (for example, recalling user preferences) but SHALL NOT be required. The system must produce correct results without it.
- The behavioral spec alone is sufficient to rebuild the system. No external knowledge base, training data, or prior conversation history is assumed.

---

## 2. Skill Contracts

### 2.1 Design

**Purpose**: Reconcile the spec with the product, then decompose a goal into a validated work decomposition with role briefs — goal-directed scopes for specialist workers.

**Behavioral contracts**:

- `[DC-1]` WHEN a goal is provided, the system SHALL identify which pending spec contracts the goal addresses and scope the work decomposition to those contracts. WHEN no goal is provided, the system SHALL perform reconciliation (DC-9) and treat all identified gaps — pending contracts, undocumented behavior, and mismatches — as the work scope. An explicit goal narrows the scope; absence of a goal means "bring spec and product into alignment."
- `[DC-2]` WHEN a goal requires NEW behavioral contracts not yet in the spec, the system SHALL author them as specs that FAIL against the current codebase (TDD: they describe behavior that execute will implement) before including them in the work decomposition. Authored specs SHALL follow the same lifecycle and quality contracts described in §6.

#### Spec–Product Reconciliation

The spec and product SHALL always match. Design enforces this at the start of every cycle.

- `[DC-3]` WHEN design begins, the system SHALL compare the current spec state to the current product state and identify three categories of gaps: (a) spec-only contracts — behavior described in the spec with no corresponding product implementation (pending work), (b) product-only behavior — behavior present in the product with no corresponding spec contract (undocumented), and (c) mismatches — both exist but disagree (drift).
- `[DC-4]` WHEN product-only behavior is found (undocumented), the system SHALL present it to the user and ask: codify it (author a spec contract describing the existing behavior, pre-satisfied since the product already implements it) or flag it for removal (treat the spec's absence as intentional — the behavior is undesired).
- `[DC-5]` WHEN a mismatch is found between spec and product, the system SHALL present the discrepancy to the user and ask: update the spec to match the product (the product is correct, the spec is stale) or update the product to match the spec (the spec is correct, the product has regressed). The user decides per gap — there is no global "spec wins" or "product wins" default.
- `[DC-6]` WHEN the user chooses to codify existing product behavior into the spec, the authored contract SHALL be recorded as pre-satisfied (its verification passes against the current product). This is the exception to the TDD rule in `[DC-2]` — the behavior already exists, so a failing spec would be dishonest.
- `[DC-7]` WHEN design authors or updates behavioral contracts, it SHALL produce a spec document (not just tracking entries) that meets the document form standards in §6.8 — top-down structure, context paragraphs, trigger–obligation contracts, concern grouping, and the rebuild test. The spec document is the primary artifact; the tracking store is its companion.
- `[DC-8]` WHEN scoping work, the system SHALL gather at least 2 expert perspectives with contrasting priorities before committing to a plan structure.
- `[DC-9]` WHEN experts disagree, the system SHALL resolve conflicts through structured negotiation and document the reasoning for each decision.
- `[DC-10]` WHEN the plan is assembled, the system SHALL validate it for structural integrity (no circular dependencies, bounded complexity, unique role names) before allowing execution.
- `[DC-11]` WHEN existing satisfied specs overlap with the work scope, the system SHALL inject them as executable constraints into role briefs, so workers verify they don't regress existing behavior.
- `[DC-12]` WHEN a conventions document exists for the project, design SHALL read it and inject relevant conventions into role constraints, so workers follow established patterns without reading the conventions document directly.
- `[DC-13]` WHEN research artifacts exist that are relevant to the current goal, design SHALL consume them as input to expert analysis and plan construction — not re-derive knowledge that research has already produced. Research findings inform design's decisions; design does not duplicate research.
- `[DC-14]` WHEN design identifies knowledge gaps during scoping — questions that expert analysis cannot resolve from existing knowledge — it SHALL invoke research to fill those gaps before committing to a plan structure. Design does not guess when it can know.
- `[DC-15]` WHEN design scopes a role's working directories, it SHALL trace transitive dependencies (imports, references, shared types) to identify files outside the initial scope that the role will need to read or modify. These files SHALL be included in the role's scope or assigned to a dependency role. A role whose scope omits transitively connected files risks workers modifying code that depends on unscoped files, or missing patterns established in adjacent code.
- `[DC-16]` WHEN design authors or updates the spec document, it SHALL verify internal consistency before proceeding: all contract IDs are unique, all cross-references resolve to existing contracts, section numbering is sequential, required fields referenced across contracts are aligned (for example, the plan field list in the work decomposition contract matches fields referenced by other contracts), and concepts are introduced before they are referenced (top-down reading order per `[SL-31]`). Inconsistencies SHALL be fixed before the spec is considered complete.
- `[DC-19]` WHEN design completes authoring or updating a spec document, it SHALL invoke refine on the document before the design skill completes. Refine applies the density standard `[SL-45]` and form standards of §6.8 — compressing prose, eliminating redundancy, and tightening expression while preserving all contracts and their disambiguating context.
- `[DC-20]` WHEN design assembles a plan with `contract_ids` on roles, it SHALL verify that every referenced contract ID is registered in the spec registry before finalizing the plan. Unregistered contract IDs in a plan are a design failure — they indicate specs were authored in the document but not registered via the operations layer. Design SHALL halt and register missing contracts before proceeding.

**Prohibitions**:

- `[DC-17]` Design MUST NOT execute any part of the plan. It only designs.
- `[DC-18]` Design MUST NOT skip expert analysis for non-trivial goals (3+ roles).

### 2.2 Execute

**Purpose**: Spawn specialist workers from a plan and coordinate their execution with dependency ordering, failure handling, and verification.

#### Test-First Execution

Tests are derived from behavioral contracts before implementation begins. This prevents implementation bias — a test author who has seen the code will unconsciously validate what was written rather than what was specified.

- `[EC-11]` WHEN execution targets pending contracts, the system SHALL generate tests from the behavioral contracts BEFORE spawning implementation workers. Test authorship receives only the spec contracts and plan context — never implementation code. Tests describe the contract's expected behavior as executable assertions.
- `[EC-12]` WHEN tests are generated for pending contracts, the system SHALL verify that all new tests FAIL against the current codebase before proceeding to implementation. A test that passes before implementation is either redundant (the behavior already exists) or vacuous (the test doesn't actually verify the contract). Redundant tests for contracts not authored via reconciliation (`[DC-6]`) indicate a contract that should not be pending.
- `[EC-13]` WHEN implementation workers complete, the system SHALL run the contract tests as the primary satisfaction mechanism. Tests passing IS the proof of satisfaction — no separate satisfaction step is needed for contracts with test coverage. The test suite is the regression gate.

**Behavioral contracts**:

- `[EC-1]` WHEN a plan exists with dependency-ordered roles, the system SHALL spawn workers in dependency order — a role does not start until all its dependencies have completed successfully.
- `[EC-2]` WHEN a worker fails, the system SHALL cascade the failure to all transitively dependent roles, marking them as skipped.
- `[EC-3]` WHEN more than half of currently pending roles (at the time of the cascade) would be skipped due to cascading failures, the system SHALL signal that the execution should abort.
- `[EC-4]` WHEN all workers complete, the system SHALL run the behavioral spec regression gate — all pre-existing specs must still pass. WHEN the regression gate has zero specs to verify, the system SHALL report the gate as vacuous rather than passing — zero is not success, it is absence of protection.
- `[EC-4a]` WHEN execution begins, the system SHALL collect all `contract_ids` referenced across plan roles and verify each exists in the spec registry. WHEN any referenced contract ID is not registered, execution SHALL halt and report the missing IDs — this indicates design failed to register contracts. A plan whose contract_ids reference unregistered specs provides no regression protection and no satisfaction chain. WHEN the spec registry is empty and any plan role references contract_ids, execution SHALL refuse to start — there is nothing to verify against and nothing to satisfy.
- `[EC-4b]` WHEN execution completes the satisfaction step, the system SHALL report satisfaction completeness — listing which contract_ids were satisfied, which remain unsatisfied, and why. WHEN any contract_id from a completed role remains unsatisfied after the satisfaction step, the system SHALL report this as a gap. Silent omission of satisfaction is a process failure.
- `[EC-4c]` WHEN execution begins, the system SHALL first run preflight to re-verify all previously satisfied contracts (some may have regressed). After preflight, the system SHALL determine which plan contract_ids are still satisfied and which are pending. Execution SHALL only target roles whose contract_ids include at least one pending contract — roles whose contracts are all still satisfied after preflight have no work to do. The satisfaction step SHALL only attempt to satisfy contracts that were pending after the preflight check. The work scope IS the delta between satisfied and pending after re-verification — nothing more, nothing less.
- `[EC-5]` WHEN a worker reports completion, the system SHALL verify the worker's claims (check commands exit 0, expected files exist).
- `[EC-6]` WHEN a worker reports completion, the system SHALL mechanically verify that all files created or modified by the worker fall within the role's declared scope directories. Files outside scope are violations. A role with scope violations SHALL be treated as failed — its completion is rejected regardless of whether verification commands passed. Scope matching uses directory prefix comparison — a file is in scope if its path starts with any scope directory. Paths SHALL be normalized (consistent separators) before comparison. A file at `lib/tests/test.py` is in scope for `lib/` but a file at `library/foo.py` is NOT in scope for `lib/` — partial directory name matches do not count.
- `[EC-7]` WHEN a role declares expected outputs, the system SHALL verify that no unexpected files were created within the role's scope directories. Unexpected means files that were not present before the role began execution and are absent from expected outputs — pre-existing files created by earlier roles are not violations. The executor SHALL snapshot the scope directory contents before each role starts and compare against the post-execution state to compute the delta. Undeclared artifacts (new files in the delta absent from expected outputs) SHALL be reported as violations and the role SHALL be treated as failed. This prevents workers from leaving scratch files, debug logs, or convenience artifacts that pollute the project structure.

**Prohibitions**:

- `[EC-8]` Execute MUST NOT modify the plan structure (add/remove roles, change goals). It only executes.
- `[EC-9]` Execute MUST NOT author new behavioral specs. It validates against existing ones.
- `[EC-10]` Workers MUST NOT modify files outside their declared scope directories. This is mechanically enforced by `[EC-6]` via scope-check verification (directory prefix comparison), not left to worker judgment. The enforcement mechanism — scope_check() accepting in-scope files and rejecting out-of-scope files — SHALL have its own execute-type verification per `[SL-47]`.

### 2.3 Research

**Purpose**: Investigate a topic and produce a structured knowledge artifact with actionable recommendations.

Research acquires knowledge for design. Invoked on demand — by the user or any skill — when knowledge gaps exist.

#### Decomposition and Framing

- `[RC-1]` WHEN a topic is provided, the system SHALL decompose it into sub-questions and identify knowledge gaps before investigating.
- `[RC-2]` WHEN beginning investigation, the system SHALL generate competing explanations or approaches before committing to a direction.

#### Investigation

- `[RC-3]` WHEN investigating a topic, the system SHALL draw from three source types: (a) external — published research, official documentation, RFCs, (b) internal — project codebase, memory, reflections, and (c) foundational — frameworks, algorithms, design patterns. Findings SHALL triangulate across source types where possible.
- `[RC-4]` WHEN investigating, the system SHALL check for existing solutions before original analysis. Surface known solutions rather than re-derive them. Confidence SHALL reflect source quality: peer-reviewed or official sources carry higher baseline confidence than informal ones.
- `[RC-5]` WHEN gathering evidence, the system SHALL actively seek disconfirming evidence.

#### Synthesis

- `[RC-6]` WHEN a topic is provided, the system SHALL produce findings organized by knowledge sections (prerequisites, mental models, usage patterns, failure patterns, production readiness).
- `[RC-7]` WHEN findings support actionable recommendations, the system SHALL include concrete recommendations with confidence levels, effort estimates, and fit criteria. Confidence SHALL evolve with evidence — initial assessments are updated as investigation proceeds, not assigned once at the end. WHEN evaluating findings that involve tradeoffs or competing approaches, the system SHALL use structured multi-step reasoning per `[IE-15]`.
- `[RC-8]` WHEN research is complete, the system SHALL preserve building blocks (expert artifacts, key findings) in a handoff format that design can consume without re-researching.

#### Research Storage

- `[RC-10]` WHEN a research artifact is stored, it SHALL include at minimum: topic (what was investigated) and findings (what was discovered). Additional fields are preserved as-is.
- `[RC-11]` WHEN research artifacts are searched, matching SHALL be case-insensitive substring matching on topic and findings fields.

**Prohibitions**:

- `[RC-9]` Research MUST NOT produce execution plans. It produces knowledge, not implementation designs.
- `[RC-12]` Research MUST NOT modify source code, configurations, or project artifacts. Research is read-only.
- `[RC-13]` Research MUST NOT satisfy or author spec contracts. That is design's responsibility.

### 2.4 Reflect

**Purpose**: Honest adversarial review of the most recent skill run, producing classified observations that route to different consumers based on what was observed and how urgently it matters.

Observer, not decision-maker. Surfaces findings; lead/user/downstream skills decide what to do. Reflect lacks the context of why choices were made — what looks wrong may be intentional.

#### Observation Classification

Every observation produced by reflect is classified along two dimensions:

- **Lens** — what is being evaluated:
  - _Product_: Is the artifact correct? Does the output match what was intended?
  - _Process_: Was the method sound? Could the approach that produced the artifact be improved?

- **Urgency** — when does it matter:
  - _Immediate_: Affects the quality of the current cycle's output. The consumer should evaluate before proceeding.
  - _Deferred_: Accumulates for future improvement. Does not block the current cycle.

These cross into four quadrants with distinct consumers:

- Product + immediate → Lead/user evaluates: patch artifact or accept as-is.
- Product + deferred → Design consumes next cycle (spec tightenings, contract gaps).
- Process + immediate → Lead/user evaluates: redo step or accept as intentional.
- Process + deferred → Synthesis process consumes periodically (skill improvement, system evolution).

One store; consumers filter at read time by classification.

#### Context Isolation

Isolation prevents confirmation bias — the reviewing agent sees artifacts, not the reasoning that produced them.

- `[FC-1]` WHEN reflect is invoked automatically at the end of a skill run, it SHALL execute in an isolated context — a separate agent that reads artifacts from persistent state, not from the conversation that produced them. The reviewing agent sees what was produced (files, plans, specs, execution results) but not the reasoning that led there.
- `[FC-2]` WHEN reflect is invoked manually by the user, it MAY run in the current context. The user accepts the reduced objectivity in exchange for conversational continuity.

#### Adversarial Review

**Behavioral contracts**:

- `[FC-3]` WHEN reviewing a skill run, the system SHALL apply structured adversarial reasoning using the best available frameworks from its foundational knowledge per `[XC-29]`. The review SHALL include at minimum: comparison of intended vs actual outcomes, identification of steps needed but skipped, surfacing of counter-evidence and latent assumptions, and prospective failure analysis. The specific frameworks and techniques used SHALL be selected for effectiveness, not convention.

#### Observation Production

- `[FC-4]` WHEN product gaps are found in artifacts, the system SHALL produce concrete patches with specific file locations and content changes, classified as product observations. Patches require user approval before application.
- `[FC-5]` WHEN spec gaps are identified, the system SHALL propose tightenings classified as product + deferred observations that design will apply in the next cycle (reflect does not write specs directly).
- `[FC-6]` WHEN an aesthetics document exists and the reviewed artifacts include user-facing interfaces, reflect SHALL evaluate the artifacts against the product's aesthetic identity and interaction design foundations. WHEN the aesthetics document itself is found to be weak — vague direction, missing interaction foundations, generic defaults, or gaps revealed by the artifacts under review — reflect SHALL propose aesthetics updates classified as product + deferred observations for design to apply in the next cycle. Reflect does not modify the aesthetics document directly, paralleling `[FC-9]` for specs.
- `[FC-7]` WHEN process weaknesses are identified — a skill missing a step, a pattern of repeated errors, a methodology gap — the system SHALL produce process observations describing the weakness, the evidence for it, and a concrete improvement proposal. Process observations do not prescribe action; they inform the consumer.
- `[FC-8]` WHEN the review is complete, the system SHALL record all observations as structured reflection entries, each classified by lens (product or process) and urgency (immediate or deferred), with severity assessment, specific evidence, and actionable proposals.

#### Tooling-Assisted Verification

Reflect leverages deterministic tools to surface correctness and quality signals before applying judgment. These tools produce evidence; reflect interprets it.

- `[FC-12]` WHEN reflect reviews an execute run, it SHALL run the project's test suite and report failures as product + immediate observations. Test failures are objective evidence of broken behavior — they do not require judgment to classify.
- `[FC-13]` WHEN reflect reviews artifacts that include source code, it SHALL run the project's configured linting and static analysis tools (code correctness, type checking) and include violations as evidence in its review. Linting violations are signals, not automatic findings — reflect evaluates whether each violation indicates a real problem or an acceptable pattern.
- `[FC-14]` WHEN reflect reviews artifacts that include source code, it SHALL run complexity analysis tools and report functions or modules exceeding the project's configured thresholds as product + deferred observations. High complexity is a signal for future simplification, not an immediate blocker — unless the complexity masks a correctness issue.

#### Lifecycle Integrity

- `[FC-11]` WHEN reflect reviews an execute run, it SHALL verify lifecycle integrity as part of its review: (a) the spec registry was non-empty when the plan referenced contract_ids, (b) all plan contract_ids were registered, (c) contract satisfaction was attempted for all completed roles, (d) the regression gate was non-vacuous (tested at least one spec). WHEN any of these checks fail, reflect SHALL produce a process + immediate observation — a broken lifecycle is a systemic failure, not a cosmetic one.

**Prohibitions**:

- `[FC-9]` Reflect MUST NOT modify behavioral specs directly. It proposes; design applies.
- `[FC-10]` Reflect MUST NOT override lead judgment. It flags findings; the lead or user decides whether to act. What appears wrong may have been intentional.

### 2.5 Refine

**Purpose**: Improve accepted artifacts in isolated context — enhancing clarity, consistency, and maintainability while preserving all functionality. Makes correct artifacts better; does not make incorrect ones correct.

Execute makes things work. Reflect verifies they're right. Refine makes them clean. Runs only after reflect's immediate findings are resolved — polishing artifacts about to change is wasted effort. Context isolation prevents sunk-cost bias toward one's own abstractions.

#### Context Isolation

- `[RN-1]` WHEN refine is invoked automatically after reflect's immediate findings are resolved, it SHALL execute in an isolated context — a separate agent that reads the produced artifacts from the filesystem, not from the conversation that produced them. The refining agent sees what was produced but not the reasoning that led there.
- `[RN-2]` WHEN refine is invoked manually by the user, it MAY run in the current context. The user accepts the reduced objectivity in exchange for conversational continuity.

#### Scope

- `[RN-3]` Refine SHALL operate only on artifacts produced or modified in the most recent execution, unless the user explicitly directs a broader scope. The default is surgical — improve what was just touched, leave everything else alone.
- `[RN-4]` WHEN a conventions document exists for the project, refine SHALL read it and apply established project standards to the artifacts under review. Conventions are the definition of "better" for this project — refine enforces them on fresh output.
- `[RN-5]` WHEN an aesthetics document exists and the artifacts under review include user-facing interfaces, refine SHALL read it and evaluate the artifacts against the product's visual identity and interaction design foundations. Aesthetics is the definition of "better" for user-facing work — refine enforces visual consistency, interaction quality, and design intent on fresh output, the same way it enforces conventions on implementation quality.

#### Preservation

- `[RN-6]` Refine MUST NOT change what the artifacts do — only how they do it. All original functionality, outputs, and behaviors SHALL remain intact. This is the hard constraint: correctness was established by execute and verified by specs; refine operates strictly within that boundary.
- `[RN-7]` WHEN refine completes, all previously satisfied behavioral specs SHALL still pass. Refine SHALL run the spec regression gate to verify this. A refinement that breaks a spec is rejected.

#### Tooling-Assisted Cleanup

Refine leverages deterministic tools to apply mechanical improvements before applying judgment-based refinements. The test suite gates every change — if tests break, the change is reverted.

- `[RN-12]` WHEN refine operates on source code artifacts, it SHALL run the project's configured formatters (code formatting, import sorting) as the first step. Formatting is mechanical and deterministic — it does not require judgment.
- `[RN-13]` WHEN refine operates on source code artifacts, it SHALL run auto-fix capable linters (safe fixes only — import removal, unused variable cleanup, style normalization) after formatting. Each auto-fix batch SHALL be followed by a test run; if tests fail, the batch is reverted and the change is reported instead of applied.
- `[RN-14]` WHEN refine operates on source code artifacts, it SHALL run dead code detection and remove confirmed dead code (unreachable functions, unused imports, orphaned files). Dead code removal SHALL be followed by a test run; if tests fail, the removal is reverted and reported.
- `[RN-15]` Refine MAY auto-fix any change as long as the test suite passes after the fix. The tests are the judgment boundary — if tests pass, the fix is safe. If tests fail, revert and report. No taxonomy of "safe to auto-fix" categories is needed.

#### Improvement

- `[RN-8]` Refine SHALL improve artifacts by: reducing unnecessary complexity and nesting, eliminating redundant abstractions, improving naming and readability, consolidating related logic, and applying project conventions. The goal is clarity — explicit, readable code over clever or compact code.
- `[RN-9]` Refine SHALL maintain balance — avoiding over-simplification that reduces clarity, creates overly clever solutions, combines too many concerns, removes helpful abstractions, or prioritizes fewer lines over readability. The right simplification makes code easier to understand and extend; the wrong one makes it harder.

**Prohibitions**:

- `[RN-10]` Refine MUST NOT add new functionality, features, or behavior. It improves existing artifacts, not extends them.
- `[RN-11]` Refine MUST NOT author new behavioral specs. It operates within the spec boundary established by design and verified by execute.

---

## 3. Cross-Skill Contracts

### 3.1 Work Decomposition Contract

The plan is a scoped subset of pending spec contracts. Design produces it; execute consumes it.

- `[XC-1]` Every role in the plan SHALL trace to one or more contract IDs from this spec.
- `[XC-2]` The plan SHALL be self-contained: a worker reading only the plan (not the conversation history) must have everything needed to do its job.
- `[XC-3]` The plan SHALL use a versioned schema with backward compatibility — a newer executor must accept plans from the previous schema version.
- `[XC-4]` Each role in the plan SHALL have: a name (unique), a goal (what to achieve), mapped contract IDs (which spec contracts this role satisfies), a scope (where to work), expected outputs (files the role will create or modify), context (domain knowledge — conventions, idioms, patterns, and prior art that make the worker effective at this specific role), constraints (hard rules that are mechanically enforceable), verification checks (how to confirm completion), assumptions (what must be true), rollback triggers (when to stop), a fallback approach, and a model (which model the worker runs on — opus, sonnet, or haiku per `[EM-20]`).
- `[XC-5]` Role context and role constraints SHALL be distinct concerns. Context carries domain knowledge the worker needs to do the job idiomatically (conventions, patterns, prior art references). Constraints carry hard rules the worker must not violate. Design populates context from the conventions document (`[DC-12]`), expert analysis, and domain-specific guidance; it populates constraints from satisfied specs (`[DC-11]`), scope rules, and invariants. Workers treat context as guidance and constraints as enforceable.
- `[XC-6]` Role dependencies SHALL be expressed as names, resolved to execution order by the build step.
- `[XC-7]` WHEN a role completes successfully, the contracts it maps to become candidates for satisfaction (pending the tamper-verified proof in §6.5).

### 3.2 Spec Ownership Contract

Specs are the persistent regression contract that grows across design cycles.

- `[XC-8]` Design is the SOLE author of specs and their verifications. No other skill writes to the spec document or verification registry.
- `[XC-9]` Execute validates against specs as a regression gate (all existing specs must pass post-execution) but never authors new entries.
- `[XC-10]` Specs use TDD: existing specs must PASS before execution (baseline). Newly authored specs must FAIL before execution (they describe behavior execute will implement). A new spec that already passes is redundant and should be removed — UNLESS it was authored via reconciliation (`[DC-6]`) to codify existing product behavior, in which case it is pre-satisfied by definition.
- Reflect proposes spec tightenings (stricter checks, new entries) via reflection entries. Design consumes these proposals in the next cycle.

### 3.3 Memory Contract

Accumulates operational learnings across cycles.

- `[XC-11]` All skills MAY write memory entries. All skills MAY read memory by goal/keyword search. The memory store SHALL be accessible to every skill without restriction.
- `[XC-12]` Memory entries have importance scores on a bounded numeric scale. The scale's range is an implementation choice, but the maximum MUST be enforced (no overflow when boosted).
- `[XC-13]` Quality gates prevent low-value entries from accumulating. Gates are deterministically enforced: required fields (category, keywords, content, source) must be present, and importance must meet a minimum threshold. The threshold is an implementation choice.
- `[XC-14]` Memory SHALL persist across cycles (survive archiving). Memory entries are never discarded by the archive operation.
- Duplicate or outdated entries are managed through feedback mechanisms (boost useful entries, suppress stale ones).

**Prohibitions**:

- `[XC-38]` Memory importance MUST NOT exceed bounds. Non-numeric importance values MUST be rejected.

### 3.4 Reflection Contract

Structured observations about skill runs, classified by lens and urgency. Reflect writes to one store; consumers query at read time.

- `[XC-15]` All skills SHALL invoke reflect in an isolated context per `[FC-1]` at the end of their run. Reflect is the sole producer of reflection entries — skills do not self-assess.
- `[XC-16]` Each reflection entry SHALL include a lens classification (product or process) and an urgency classification (immediate or deferred). Entries without both classifications are rejected by the storage operation.
- `[XC-17]` Reflections that report failures MUST include specific fix proposals — vague "it failed" reflections without actionable fixes are rejected. This is deterministically enforced: the storage operation checks that entries with non-empty failure lists also have non-empty fix proposals, and rejects the write if not.
- `[XC-18]` Immediate observations (both product and process) SHALL be surfaced to the lead or user for evaluation after the reflect skill completes. The lead decides whether to act — reflect does not prescribe action for immediate findings.
- `[XC-19]` Deferred product observations (spec tightenings, contract gaps) flow to design for consumption in the next cycle.
- `[XC-20]` Deferred process observations (skill weaknesses, methodology gaps, systemic patterns) accumulate in the reflection store for periodic synthesis. A separate synthesis process — not reflect itself — reads accumulated process observations, identifies patterns, and proposes system-level improvements (skill prompt changes, workflow adjustments, convention updates). The synthesis trigger and process are implementation choices.

#### Resolution Lifecycle

Findings are not permanent — they get addressed. Without a resolution mechanism, addressed findings accumulate as noise, obscuring active issues and misleading future cycles into re-evaluating work that is already done.

- `[XC-45]` WHEN a reflection finding has been addressed (bug fixed, observation acted upon, or finding determined to be stale), the system SHALL record a resolution that references the finding's identifier, includes what resolved it, and timestamps the resolution. Resolution is append-only — it does not modify the original finding record.
- `[XC-46]` WHEN listing reflections, the system SHALL exclude resolved findings by default — only unresolved findings are actionable. WHEN explicitly requested (for example, for audit or history review), the system SHALL include resolved findings in the output.

**Prohibitions**:

- `[XC-35]` Reflections that report failures MUST NOT be stored without corresponding fix proposals.
- `[XC-36]` Invalid lens or urgency values MUST be rejected — the classification vocabulary is closed.

### 3.5 Archive Contract

Between cycles, the system archives ephemeral artifacts while preserving persistent state.

- `[XC-21]` Persistent files (memory, reflections, traces, specs, research, conventions, aesthetics) SHALL survive archiving in place.
- `[XC-22]` Ephemeral files (plans, expert artifacts, worker outputs) SHALL be moved to timestamped history during archiving.
- `[XC-23]` After archiving, no stale plan state SHALL remain — a fresh design cycle starts with accumulated learnings but clean execution state.
- `[XC-41]` WHEN archive completes, the system SHALL verify its own post-conditions: (a) no ephemeral directories remain under root, (b) all persistent files still exist, (c) the history directory contains the archived artifacts. WHEN any post-condition fails, archive SHALL report the failure rather than silently returning success.
- `[XC-43]` WHEN archive moves a plan to history, it SHALL rename the plan file from its working name to a name derived from the plan's goal — sanitized for filesystem safety (lowercase, hyphens for spaces, punctuation removed, truncated to reasonable length). A history directory where every archived plan is named identically provides no discoverability — the filename should convey what the plan was for without requiring the file to be opened.
- `[XC-44]` WHEN archive completes, it SHALL generate a human-readable summary file in the history destination directory containing: archive timestamp, plan goal, role names and their terminal statuses, contract IDs targeted, and a file inventory of what was archived. This summary enables browsing execution history without opening individual artifacts.

### 3.6 Conventions Contract

The spec defines WHAT. Conventions define HOW a specific project builds it — technology choices, coding standards, platform patterns, file organization.

- `[XC-24]` The system SHALL maintain a persistent, project-level conventions document that captures implementation decisions, coding standards, error handling strategy, testing approach, and host-platform patterns (skill authoring, agent coordination, model selection, context economy, tool availability). This document is always available to skills — not searched by keyword like memory, but present in every session's context.
- `[XC-25]` WHEN no conventions document exists and design is assembling a plan, design SHALL conduct comprehensive external research into the project's technology stack — both the implementation stack (languages, frameworks, libraries) and the host platform stack (agent execution model, skill authoring patterns, available tools, context constraints) — covering idiomatic patterns, community best practices, common failure modes, and documented anti-patterns — then create an initial conventions document that captures both the project's technology choices and the ecosystem-informed guidance that workers need to produce idiomatic, production-quality output. The conventions document must exist before plan finalization so that `[XC-26]` can inject conventions into role constraints.
- `[XC-26]` WHEN design builds a plan, it SHALL read the conventions document and inject relevant conventions into role constraints. Workers receive conventions through the plan — they do not read the conventions document directly. This preserves plan self-containment (`[XC-2]`).
- `[XC-27]` WHEN any skill discovers a reusable implementation pattern worth preserving (a convention that worked, a standard that should be followed), it SHALL propose updating the conventions document. Conventions evolve across cycles as the project matures.
- `[XC-28]` WHEN the system is first implemented or a foundational technology choice is made (runtime language, storage format, module system, dependency strategy, host platform, skill delivery mechanism, agent spawning model, model selection, available subagent tools), the conventions document SHALL record the choice with its rationale — what alternatives were considered, why this option was selected, and what constraints drove the decision. Technology choices without documented reasoning are conventions by accident, not by design. This ensures a future rebuild makes deliberate choices informed by prior reasoning rather than arbitrary ones.
- `[XC-39]` The conventions document SHALL capture host-platform specifics alongside implementation specifics. The execution model (§4) — lead boundaries, agent spawning mechanism, model selection, context economy strategies — and the skill delivery mechanism (§7.3) — prompt format, invocation syntax, tool availability per agent type — are foundational technology choices subject to `[XC-28]`. A conventions document that covers only the implementation language and storage format is incomplete.
- `[XC-40]` A conventions document SHALL be considered complete only when it covers at minimum: technology choices with rationale per `[XC-28]`, host-platform patterns per `[XC-39]`, error handling strategy (how errors propagate, what degrades gracefully, what callers can expect), testing approach (what to test, fixture strategy, verification relationship), coding standards, and project tooling per `[XC-42]`. A conventions document that lists tools without operational guidance for workers is incomplete — workers need to know not just what tools are used but how to use them correctly within the project's error and testing patterns.
- `[XC-42]` The conventions document SHALL declare the project's quality toolchain — formatters, linters, static analyzers, complexity analyzers, and dead code detectors — with their configuration and invocation commands. These tools are consumed by reflect (`[FC-12]`–`[FC-14]`) and refine (`[RN-12]`–`[RN-15]`) as part of their standard workflows. The toolchain is project-internal: it runs through the project's command surface (`[XC-31]`), not through external host-level hooks or CI. This ensures deterministic, portable quality enforcement that any agent can invoke.
- The conventions document format is an implementation choice. Behavioral contract: conventions exist, persist, design reads them, workers receive them through the plan.

**Prohibitions**:

- `[XC-37]` Conventions MUST NOT be written directly by skills. They are proposed to the user, who decides.

### 3.7 Foundational Knowledge Contract

Skills and workers leverage established knowledge — frameworks, algorithms, design patterns, methodologies — rather than reasoning ad-hoc.

- `[XC-29]` WHEN a skill's core methodology has an established body of practice (published frameworks, research methodologies, reasoning techniques, analytical approaches), the skill SHALL identify and apply the most effective available approaches from its foundational knowledge rather than ad-hoc reasoning. The selection SHALL be justified — why this approach fits this task. The system MUST NOT hardcode specific frameworks `[XC-34]` — it SHALL use the best available knowledge at the time of execution, which evolves as new research emerges.

**Prohibitions**:

- `[XC-34]` The system MUST NOT hardcode specific frameworks — it SHALL use the best available knowledge at the time of execution, which evolves as new research emerges.

### 3.8 Aesthetics Contract

The spec defines WHAT. Conventions define HOW it's built. Aesthetics defines HOW it looks, feels, and works — visual identity and interaction design foundations for user-facing products. Visual identity and interaction design are two lenses on the same concern; they live in one document because workers need both together.

Conventions and aesthetics are complementary: conventions govern implementation quality, aesthetics governs experiential quality. Both flow into plans through the same mechanism.

Applies to any product with user-facing interfaces, regardless of modality (graphical, terminal, voice, spatial). The system's own skill outputs — plans, observations, reconciliation summaries, expert analyses, status updates — are user-facing interfaces; aesthetics governs them equally.

#### Persistence and Availability

- `[DS-1]` WHEN the project produces user-facing interfaces, the system SHALL maintain a persistent aesthetics document that captures the product's visual identity and interaction design foundations. The document covers two complementary concerns: (a) visual identity — aesthetic direction, visual language, spatial principles, color and typography choices, and (b) interaction design — user mental models, information architecture, state design, cognitive load analysis, and flow integrity. Like conventions, this document persists across cycles and is always available to design. The system's own skill outputs — plans, observations, reconciliation summaries, expert analyses, status updates, and all other artifacts presented to the user — are user-facing interfaces. Aesthetics governs their presentation with the same standards applied to any product the system builds.
- `[DS-2]` Aesthetics SHALL persist across cycles (survive archiving) alongside conventions, memory, and other persistent state.

#### Population

- `[DS-3]` WHEN a goal produces user-facing interfaces and no aesthetics document exists, design SHALL establish one before implementation begins. A goal "produces user-facing interfaces" when any of: (a) the plan includes roles that create or modify interfaces users interact with, (b) the system being built has user-facing interfaces as defined by `[DS-1]` and this is a foundational build cycle (greenfields or rebuild), or (c) the plan includes roles whose output shapes — data structures, envelope formats, error representations — flow into user-facing presentation layers. Scoping a cycle to backend work does not exempt it from aesthetics when the backend is part of a user-facing system being built from scratch — the aesthetic identity should inform implementation choices, not be retrofitted after them. Establishment requires analysis of purpose, audience, and desired tone, followed by commitment to a distinctive aesthetic direction — not defaulting to generic, safe, or platform-standard choices. Aesthetics is an intentional identity decision, not an afterthought.
- `[DS-4]` WHEN establishing aesthetics, the system SHALL apply the best available design methodology from its foundational knowledge per `[XC-29]` — published visual design frameworks, established interaction design principles, and proven UX methodologies. The system does not invent design methodology ad-hoc; it draws on the body of practice in visual and interaction design.
- `[DS-5]` WHEN establishing aesthetics, the system SHALL document choices with rationale — what alternatives were considered, why this direction was selected, and what qualities it optimizes for. This parallels `[XC-28]` for technology choices: design decisions without documented reasoning are aesthetics by accident, not by design.

#### Interaction Design Foundations

Aesthetics is not only how the product looks — it is how the product works. The following contracts ensure interaction design is analyzed before interfaces are implemented.

- `[DS-6]` WHEN establishing or updating aesthetics, the system SHALL analyze user mental models — what users believe the system does, what misconceptions are likely, and what the interface must reinforce or correct.
- `[DS-7]` WHEN establishing or updating aesthetics, the system SHALL enumerate all concepts the user will encounter, organize them into a logical information architecture, and classify each as primary (always visible), secondary (available on demand), or progressive (revealed as needed).
- `[DS-8]` WHEN establishing or updating aesthetics, the system SHALL define state behavior for interface elements — at minimum: empty, loading, success, error, and partial states. For each state: what the user sees, what they understand, what they can do next.
- `[DS-9]` WHEN establishing or updating aesthetics, the system SHALL identify cognitive load points — moments where the user makes a decision, faces uncertainty, or waits — and document simplification strategies (defaults, progressive disclosure, reduced choices).
- `[DS-10]` WHEN establishing or updating aesthetics, the system SHALL verify flow integrity — where first-time users could get lost, where the path forward is ambiguous, and what must be explicitly visible versus safely implied.

#### Flow into Plans

- `[DS-11]` WHEN design builds a plan that includes roles implementing user-facing interfaces, it SHALL read the aesthetics and inject relevant visual direction and interaction design foundations into those roles' context. Workers receive both design intent and interaction requirements through the plan — they do not read the aesthetics document directly. This preserves plan self-containment (`[XC-2]`) and parallels how conventions flow via `[XC-26]`.
- `[DS-12]` WHEN design builds a plan that includes roles authoring skill prompts, it SHALL inject the system's own presentation aesthetics into those roles' context. Skill prompts govern how the system presents information to the user — plan summaries, reconciliation tables, expert findings, progress updates, observation reports. These are the system's user interface and SHALL reflect the aesthetic identity established for the system itself.
- `[DS-13]` WHEN a goal produces user-facing interfaces, at least one expert perspective in design (`[DC-8]`) SHALL address visual and interaction design — evaluating whether the proposed approach serves the product's aesthetic identity and interaction foundations, or defaults to generic choices.

#### Evolution

- `[DS-14]` WHEN any skill discovers a reusable visual or interaction pattern worth preserving, it SHALL propose updating the aesthetics document. Aesthetics evolves across cycles as the product matures — paralleling `[XC-27]` for conventions.
- `[DS-15]` An aesthetics document SHALL be considered complete only when it covers both visual identity (aesthetic direction, tone, output formatting, information architecture, state presentation) and interaction design foundations (mental models per `[DS-6]`, cognitive load analysis per `[DS-9]`, flow integrity per `[DS-10]`), each with documented rationale per `[DS-5]`. An aesthetics document that defines how the product looks without analyzing how users think about and navigate it is incomplete — visual identity without interaction design produces interfaces that are styled but not usable.
- `[XC-30]` WHEN design builds a plan, it SHALL identify foundational knowledge relevant to each role's specific task — algorithms, design patterns, established methodologies, domain-specific best practices — and inject it into the role's context field. Workers receive foundational knowledge through the plan so they can apply proven approaches rather than re-derive solutions. This complements `[RC-4]` (prior art obligation) at the execution level: research finds existing solutions for the goal, design distributes relevant knowledge to each role for its specific task.

### 3.9 Project Command Surface

Common operations (test, build, lint, format, check) are invoked across skills, workers, and human sessions. Without a single discoverable surface, commands scatter — leading to inconsistency, fragile references, and wasted discovery effort.

- `[XC-31]` The project SHALL maintain a discoverable, declarative command surface that maps short task names to underlying operations. The command surface is the canonical reference for how to run tests, builds, checks, and other repeatable project operations. Both humans and AI discover available operations by reading this single artifact.
- `[XC-32]` WHEN design assembles a plan, it SHALL reference the command surface in role verification commands rather than raw tool invocations. WHEN the command surface itself is produced by a role in the plan (bootstrap case), roles that execute before that role SHALL use raw tool invocations in their verification commands — the command surface requirement applies only to roles that execute after the command surface exists. WHEN new operations are introduced by a plan, design SHALL add them to the command surface before finalization.
- `[XC-33]` Workers and skills SHALL invoke operations through the command surface when an entry exists, rather than constructing raw commands. This ensures consistency — the same operation runs the same way regardless of who invokes it.
- The command surface tool (justfile, Makefile, npm scripts, etc.) is an implementation choice recorded in conventions per `[XC-24]`. Behavioral contract: one discoverable artifact maps names to operations; all participants use it.

### 3.10 Version Control Contract

The project SHALL be under version control. Each skill run produces a discrete unit of change — version control captures that unit as a reviewable, revertable snapshot.

- `[VC-1]` The project SHALL use a version control system. The specific tool is an implementation choice recorded in conventions per `[XC-24]`.
- `[VC-2]` WHEN a skill run (core or auxiliary) completes and has produced changes, the system SHALL commit those changes before the skill is considered complete. Each skill run is one logical commit — the version history reflects the skill sequence.
- `[VC-3]` WHEN committing after a skill run, the working tree SHALL be clean afterward — no untracked, unstaged, or uncommitted changes. WHEN untracked files exist, the system SHALL resolve each by: (a) adding it to version control if it is a legitimate project artifact, (b) adding it to the ignore rules if it is a generated or environment-specific file, or (c) deleting it if it is scratch output that should not persist. Silent accumulation of untracked files is a hygiene failure.
- `[VC-4]` WHEN a skill run produces no changes (no modified, added, or deleted files), no commit is required. Empty commits are noise.

**Prohibitions**:

- `[VC-5]` The system MUST NOT leave the working tree in a dirty state between skill runs. A dirty working tree at skill boundary is ambiguous — it is unclear whether the changes are intentional output or accidental residue.

---

## 4. Execution Model Contracts

### 4.1 Lead Boundaries

The lead (main conversation) orchestrates but does not implement.

- `[EM-1]` The lead SHALL only use orchestration tools: agent spawning, messaging, task management, script invocation, and user questions.
- `[EM-2]` The lead MUST NOT read project source files directly. Agents read the codebase; the lead reads their findings.
- `[EM-3]` The lead MUST NOT write artifacts that agents should produce. Lead interpretation is not specialist analysis.

**Exception**: Lead MAY read a small specific file to verify a factual claim, avoiding expensive agent spawns for trivial fact-checks.

### 4.2 Agent Coordination

- `[EM-4]` Agent spawning is blocking — the system waits for the agent to return, with no polling.
- `[EM-5]` Workers SHALL read the plan directly — no per-worker task files or message-based distribution.
- `[EM-6]` One worker per role, named by the role name.
- `[EM-7]` Teammates SHALL be able to discover each other's identities without relying on the lead to relay introductions.

### 4.3 Dependency Ordering

- `[EM-8]` Roles execute in dependency order: a role does not start until all its dependencies have completed.
- Independent roles MAY execute in parallel.
- `[EM-9]` WHEN parallel roles have overlapping file scopes, they SHOULD be serialized to prevent conflicts.

### 4.4 Failure Handling

- `[EM-10]` WHEN a role fails, all transitively dependent pending roles SHALL be marked as skipped.
- `[EM-11]` WHEN a role's status reaches a terminal state (completed, failed, skipped), it MUST NOT transition to any other state.

Valid status transitions follow this state machine:

| Current State | Allowed Transitions  | Terminal? |
| ------------- | -------------------- | --------- |
| pending       | in_progress, skipped | No        |
| in_progress   | completed, failed    | No        |
| completed     | —                    | Yes       |
| failed        | —                    | Yes       |
| skipped       | —                    | Yes       |

- `[EM-12]` WHEN an invalid status transition is attempted, the system SHALL reject it.
- `[EM-13]` WHEN more than half of currently pending roles (at the time of the cascade) would be skipped by cascading failures, the system SHALL signal abort.

### 4.5 Graceful Degradation

- `[EM-14]` Trace write failures MUST NOT crash the skill. Tracing is observability, not control flow.
- `[EM-15]` Memory write failures MUST NOT block skill completion. They SHOULD be logged but SHALL NOT prevent the skill's primary workflow from completing.
- `[EM-16]` Corrupted entries in append-only files (memory, reflection, trace) MUST NOT prevent reading valid entries.

### 4.6 Context Economy

Lead context is finite. Minimize it.

- `[EM-17]` The lead SHALL delegate codebase reading, analysis, and implementation to subagents. The lead orchestrates; it does not read project source files or write implementation code.
- `[EM-18]` Deterministic operations (validation, state management, computation) SHALL be performed by helper scripts, not by LLM reasoning in the lead's context. Scripts consume zero context tokens.
- `[EM-19]` Subagent results that enter the lead's context SHALL be summaries, not full artifacts. Full output is stored in files; the lead receives a synopsis sufficient for orchestration decisions.
- Prefer blocking calls that return compact results over streaming output that accumulates in context.

### 4.7 Cost-Aware Model Selection

Use the cheapest model that can do the job. Three models, named directly — no abstract tiers.

- `[EM-20]` Each task SHALL specify its model by name: **opus**, **sonnet**, or **haiku**. The model on the role is a binding dispatch parameter, not advisory.
- **opus**: The lead orchestrator, complex architectural decisions, adversarial analysis, cross-domain synthesis, ambiguous judgment calls.
- **sonnet**: Expert analysis, implementation work, code writing, research, most worker tasks. The default for any task not clearly requiring a different model.
- **haiku**: Mechanical operations, simple curation, template-following tasks, low-judgment work (memory curation, format validation, simple summarization).
- Model is specified per-role in the execution plan, allowing the same skill to use different models for different roles based on task complexity.
- `[EM-21]` The executor MUST spawn workers using the model specified on the role. No mapping or translation — the plan says `opus`, the agent runs opus.
- WHEN a task fails at a cheaper model, the system MAY retry at a more capable one — but this is a fallback, not a default strategy.

**Prohibitions**:

- `[EM-22]` Trace entries MUST NOT be deleted or modified. The audit trail is append-only and immutable.

---

## 5. Plan Validation Contracts

Structural validation enforced before execution:

### 5.1 Role Constraints

- `[PV-1]` The plan SHALL have between 1 and 8 roles (bounded complexity for agent platforms).
- `[PV-2]` All role names SHALL be unique within a plan.
- `[PV-3]` Role dependencies SHALL form a directed acyclic graph (circular dependencies are rejected).

### 5.2 Build Step (Finalize)

- `[PV-4]` Finalize SHALL validate structure, compute directory overlaps between roles, initialize all role statuses to pending, and resolve name-based dependencies to indices — in one atomic operation. The original plan data SHALL NOT be mutated — finalization produces a new copy.
- `[PV-5]` WHEN validation fails, finalize SHALL reject the plan with a specific error (not silently succeed).
- `[PV-9]` WHEN a plan declares dependencies, each dependency name SHALL resolve to an existing role in the same plan. Unresolvable dependency names are rejected.

### 5.3 Structural Coherence

- `[PV-6]` WHEN a behavioral contract elsewhere in this spec imposes a constraint on plan role structure (required fields, allowed values, mandatory metadata), that constraint SHALL be reflected in the plan's required fields (`[XC-4]`) and mechanically enforced by validation (`[PV-4]`). Behavioral SHALLs that affect plan structure MUST NOT rely on manual compliance — they must be enforceable by the build step.

### 5.4 Schema Versioning

- `[PV-7]` The system SHALL accept plans in the current schema version and the previous version (backward compatibility).
- `[PV-8]` WHEN the system receives a plan in an unsupported schema version, it SHALL reject it with a machine-readable error token (prefixed with a recognizable identifier like `bad_schema`).

---

## 6. Behavioral Spec Lifecycle

Persistent store of behavioral contracts that grows across design cycles. Storage mechanism is an implementation choice.

### 6.1 Persistence and Growth

- `[SL-1]` The system SHALL maintain a persistent record of behavioral contracts that grows monotonically across execution cycles. WHEN a contract is first registered, the system SHALL compute and store a content hash from its verification content.
- `[SL-2]` Behavioral contracts SHALL survive system restarts, artifact cleanup, and archiving.
- `[SL-3]` New contracts added during design SHALL be testable against the current implementation. WHEN a contract ID already exists in the registry, registration SHALL fail with a duplicate error.
- `[SL-4]` The system SHALL prevent silent degradation of the contract store (no undetected removal of contracts).

### 6.2 Contract Hierarchy and Verification Methods

Contracts range from broad purpose down to specific observable behaviors. Verification method varies by contract type.

- `[SL-5]` Lower-level contracts (boundary conditions, behavioral invariants) SHALL have verification that proves the behavior holds.
- `[SL-6]` The hierarchy SHALL enforce that children are more specific than their parents.

#### Verification Methods

Every testable contract has a verification method that determines how satisfaction is proven.

- `[SL-7]` **Execute verification**: a deterministic command that exits successfully when the behavior holds. The system runs the command and checks the exit code. This is the equivalent of a unit test — mechanical, repeatable, binary pass/fail. WHEN registered with type execute, the content SHALL be a structured object containing the verification command.
- `[SL-8]` **Review verification**: a structured question evaluated by an LLM agent against a specified artifact. The agent reads the artifact, evaluates the question, and returns pass/fail with cited evidence. This is for quality standards that require judgment — structural organization, information density, technology-agnosticism. WHEN registered with type review, the content SHALL be a structured object containing the review question, artifact path, and evidence commands.
- `[SL-9]` Review verifications MAY include **evidence commands** — preparatory commands whose output feeds into the LLM's evaluation context before it makes its judgment. Evidence commands mechanically surface signals (metrics, pattern matches, structural counts) so the LLM interprets data rather than reading everything from scratch.
- `[SL-10]` WHEN an LLM performing a review verification identifies a gap that a mechanical tool could have caught, it SHALL propose adding that tool as an evidence command for the next cycle. The evidence command list grows over time as the system learns what signals are useful — review verifications become progressively more tool-assisted and less purely judgment-based.

- `[SL-47]` WHEN a prohibition contract claims mechanical enforcement (e.g., "mechanically enforced by [X]"), the enforcing contract [X] SHALL have execute-type verification that proves the enforcement mechanism works — including rejection of prohibited inputs. A prohibition backed by code that is only verified by review is a false assurance. Design SHALL register the enforcement contract with tests that exercise the rejection path, not just the happy path.

Verification registry tracks both types: execute-type entries store a command; review-type entries store a question, artifact path, and optional evidence commands.

### 6.3 Contract Identity and Status

- `[SL-11]` Each testable contract SHALL have a stable, short identifier assigned at authorship time that persists across spec revisions. Identifiers MUST NOT change once assigned.
- Each testable contract has a status: **pending** (not yet satisfied) or **satisfied** (proven by running its verification).
- Delta between all-satisfied and new-pending IS the work for execute — no separate work-tracking needed.
- Contracts without a satisfaction record are pending — absence of proof is the signal.
- `[SL-12]` WHEN design tightens an existing contract (changes its verification), the contract reverts to pending.

#### Spec Document and Verification Registry

Two complementary artifacts:

- **Spec document** — authoritative behavioral description; contract IDs embedded inline within prose. Defines WHAT and WHY.
- **Verification registry** — maps contract IDs to verifications, tracks satisfaction status, records proof. Defines HOW TO PROVE behavior holds.
- `[SL-13]` The spec document is always authoritative. The verification registry is derived from the spec document and is recreatable — design can regenerate it at any time by reading the spec document and authoring verifications for each contract ID. The only data lost on regeneration is satisfaction status, which preflight can re-derive by running the verifications.
- `[SL-14]` WHEN the system detects that contract IDs in the spec document and the verification registry have diverged (IDs present in one but not the other), it SHALL report the discrepancy. IDs in the spec document without registry entries are unregistered contracts. IDs in the registry without spec document entries are orphaned verifications.

### 6.4 Verification Integrity

Design is the sole author of contracts and their verifications. Content hashing detects accidental drift between what design authored and what gets executed.

- `[SL-15]` At authorship time, design SHALL compute a content hash of each contract's verification content (the execute command, or the review question and evidence commands). This hash detects accidental modification.
- `[SL-16]` To satisfy a contract, the system SHALL automatically recompute the content hash from the stored contract content and verify it matches the hash recorded at authorship before recording satisfaction. This verification is internal — callers do not supply the hash. A mismatch indicates the contract content was modified outside of design and satisfaction MUST be rejected.
- `[SL-17]` The system SHALL detect when a contract's verification has been modified outside of design (drift detection).

Hash is a consistency check, not a security boundary — catches accidental drift, not deliberate circumvention. Regression protection is continuous re-verification (§6.5).

### 6.5 Satisfaction and Continuous Verification

Satisfaction is "last known to pass" — new development can regress it. The system continuously re-verifies.

- `[SL-18]` For **execute-type** contracts: satisfaction SHALL be recorded WHEN the command exits with code 0 AND the content hash matches. The proof is independently verifiable — anyone can re-run the command.
- `[SL-19]` For **review-type** contracts: satisfaction SHALL be recorded WHEN an LLM agent evaluates the question against the artifact and returns pass with cited evidence. The proof is the cited evidence — auditable by reflect or a human reviewer.
- `[SL-20]` WHEN the system begins a new cycle, it SHALL re-verify all previously satisfied contracts. Execute-type contracts are re-run mechanically. Review-type contracts are re-evaluated when their target artifact has changed since the last review — re-evaluation uses the artifact content hash snapshotted at satisfaction time `[SL-44]` to detect drift. If a previously satisfied contract now fails, its satisfaction is revoked — it becomes pending work.
- `[SL-21]` Satisfaction SHALL persist across cycles unless revoked by re-verification failure or tightened by design (which changes the verification content and invalidates the hash).
- `[SL-44]` WHEN a review-type contract is satisfied, the system SHALL snapshot the target artifact's content hash. This snapshot enables drift detection during preflight re-verification `[SL-20]`.

### 6.6 Recursive Application

Lifecycle contracts in §6.1–6.5 apply equally to specs created for products the system builds. When design authors contracts for a target product via `[DC-2]`:

- `[SL-22]` Product specs SHALL follow the same lifecycle: stable IDs, pending/satisfied status, integrity-checked verification, continuous re-verification, and the TDD cycle (new specs fail, execute satisfies them). Product specs SHALL use both verification methods (execute and review) as appropriate to the contract.
- `[SL-23]` Product specs SHALL meet the same authorship quality and document form standards (§6.7, §6.8): technology-agnostic descriptions, portability test, no failure-masking verification commands, top-down structure, trigger–obligation form, the rebuild test, and bidirectional traceability between spec IDs and implementation artifacts.
- `[SL-24]` Product spec contracts SHALL trace back to this system's contracts — the system's spec methodology is self-consistent.

#### Product Infrastructure Propagation

The system creates some artifacts operationally — conventions (§3.6) and aesthetics (§3.8) are produced by the design skill's workflow and exist for every project the system works on. These do not need to be authored into the product spec because the system creates and maintains them.

Other infrastructure concerns only exist in a product if design explicitly authors them as behavioral contracts. These are design-time decisions — the system's skills do not create them automatically.

- `[SL-47]` WHEN design authors a product spec, it SHALL evaluate every cross-cutting and information exchange contract in this spec (§3, §7) for product applicability. A contract is product-applicable when it describes a quality the product itself needs to exhibit — independent of whether the multi-agent system is involved. Design SHALL author product-appropriate contracts for each applicable concern, adapted to the product's domain. Contracts governing the system's internal orchestration (lead boundaries, agent spawning, worker dispatch, plan structure, dependency ordering, failure cascading, memory accumulation, reflection production, archive lifecycle, spec ownership, foundational knowledge selection, context economy, model selection) are system-internal and do not propagate. Contracts that the system already creates operationally (conventions, aesthetics) do not need product spec entries — they exist as operational artifacts. Everything else is a design-time decision that must be explicitly authored or it will not exist in the product.
- `[SL-48]` At minimum, design SHALL author product contracts for these infrastructure concerns unless the product's nature makes them inapplicable:
  - **Version control** (§3.10): tracked changes, clean working tree discipline, committed state at boundaries.
  - **Command surface** (§3.9): discoverable, declarative surface for repeatable operations.
  - **Operation results** (§7.1): uniform success/failure envelopes with machine-readable error codes.
  - **Artifact durability** (§7.2): data integrity patterns appropriate to the product's storage needs.
  - **Creativity/trustworthiness separation** (§7.4): creative outputs pass through validation gates before persistence.
  - **Self-verification** (§7.6): the operations layer has comprehensive self-testing.
  - **Test-first development** (§2.2): tests are derived from behavioral contracts before implementation, verified to fail against the current state, then used as the satisfaction mechanism after implementation.

  This list is a minimum floor, not exhaustive. `[SL-47]`'s evaluation rule is authoritative — design may identify additional applicable concerns from §3 and §7 based on the product's specific needs.

### 6.7 Authorship Quality

- `[SL-25]` Contract descriptions SHALL be technology-agnostic: no tool names, file paths, command names, or internal API fields. They describe WHAT the system does, not HOW it's currently implemented.
- `[SL-26]` Contract descriptions SHALL be knowledge-agnostic: they describe required capabilities and outcomes, not specific frameworks, algorithms, or methodologies by name. Naming a framework freezes knowledge that may be superseded. Contracts SHALL specify what the approach must achieve (for example, "surface counter-evidence and latent assumptions") not which framework to use (for example, "apply Pre-mortem analysis"). This ensures each rebuild draws on the best available knowledge at execution time rather than knowledge frozen at authorship time.
- Verification commands MAY reference the current implementation — implementation-specific proof of abstract behavior.
- `[SL-27]` Every contract SHALL pass the portability test: "If the system were reimplemented in a different language/framework, would this description still make sense?"
- `[SL-28]` Every contract SHALL pass the **freshness test**: "If better approaches, frameworks, or methodologies emerge after this spec was written, would this contract prevent their adoption?" If yes, the contract is over-specified.
- `[SL-29]` Verification commands that mask failures (always-true fallbacks, exit-code swallowing) are prohibited.
- `[SL-30]` Implementation artifacts (code, skill prompts, configuration) SHALL reference the contract IDs they satisfy, enabling bidirectional traceability between the spec and the implementation. Given a contract ID, it SHALL be possible to find both the spec definition and every implementation artifact that addresses it through a simple text search.

### 6.8 Document Form

The spec is a single readable document (not a database or flat list). The spec document is authoritative; the verification registry is derived from it and recreatable (§6.3). This section defines what a well-formed spec document looks like.

#### Structure

- `[SL-31]` A spec document SHALL be organized top-down: system purpose → capabilities and lifecycle → per-component behavioral contracts → cross-cutting contracts → operational/execution contracts. Higher sections provide context; lower sections provide testable specifics. A reader encountering the document for the first time builds understanding progressively — never encountering a contract that references concepts not yet introduced.
- `[SL-32]` Each section SHALL open with a context paragraph explaining what the section covers and why, before any contracts appear. Contracts without framing are a list of rules with no mental model — the prose IS the specification; the contracts are its testable commitments.

#### Contract Form

- `[SL-33]` Testable contracts SHALL use trigger–obligation form: "WHEN <observable trigger>, the system SHALL <observable outcome>."
- `[SL-34]` Contracts SHALL be grouped by concern, sharing an ID prefix (DC- for design, EC- for execution, etc.). The prefix is a navigation aid.
- `[SL-35]` Each concern group SHALL separate positive contracts (what the system does) from prohibitions (what it must not do). Prohibitions are labeled explicitly. A system is defined as much by what it refuses to do as by what it does.
- `[SL-36]` Every SHALL, MUST, or MUST NOT obligation describing testable behavior SHALL have a stable contract ID. Context paragraphs, implementation-choice notes, factual definitions, and MAY/SHOULD guidance do not require IDs.

#### Quality Gates

- `[SL-37]` A spec document SHALL pass the **rebuild test**: given only the spec document and no access to any existing implementation, a competent builder (human or LLM) could construct a functionally equivalent system. The resulting system may differ in implementation details but would satisfy every testable contract. If the spec fails this test, it is underspecified.
- `[SL-38]` A spec document SHALL pass the **recreation test**: the system built from the spec, when asked to produce a spec for a different product, generates a document of equivalent structural quality — same top-down organization, same trigger–obligation contracts, same separation of concerns. If the system cannot recreate spec quality, the spec did not adequately encode its own standards.
- `[SL-39]` WHEN the system authors a product spec, it SHALL be a single document with contract IDs embedded inline within prose — not a separate tracking artifact. The companion verification registry tracks satisfaction status of those IDs but the document is the authoritative behavioral description.
- `[SL-40]` Implementation-specific choices SHALL be called out explicitly in the spec document (for example, "the storage mechanism is an implementation choice") to maintain the boundary between behavioral contracts and implementation decisions.
- `[SL-45]` Spec documents SHALL be optimized for instruction-following density. Context paragraphs frame the concern concisely. Rationale that restates a contract's own trigger–obligation form SHALL be eliminated. Every sentence carries either orienting context for a first-time reader or a testable obligation — not both restated.

**Prohibitions**:

- `[SL-41]` Contracts MUST NOT be modified outside the design skill. Direct registry edits bypass hash integrity.
- `[SL-42]` Satisfaction MUST NOT be recorded without hash verification. Stale proofs against modified criteria are invalid.
- `[SL-43]` Preflight MUST NOT skip any satisfied contract — all must be re-verified.
- `[SL-46]` The system SHALL provide a coverage check that cross-references a plan's contract_ids against the spec registry, reporting for each contract: whether it is registered, its current status (pending or satisfied), and whether it needs work. This is a deterministic query — no side effects.

---

## 7. Information Exchange Contracts

### 7.1 Operation Result Convention

Every deterministic operation returns a result through one channel in one shape. Callers never need to check multiple output paths or parse different formats. This uniformity enables skills to chain operations without per-operation error handling.

- `[IE-1]` All deterministic operations SHALL return a result containing a boolean success indicator and either a data payload (on success) or an error description (on failure).
- `[IE-2]` Failures SHALL include a machine-readable error code following `MODULE_CONDITION` format in uppercase with underscores (for example, `SPEC_NOT_FOUND`, `PLAN_CIRCULAR_DEPENDENCY`), alongside a human-readable description sufficient for automated handling.
- `[IE-3]` All deterministic operations SHALL return results through a uniform envelope on a single output channel. The envelope SHALL contain a consistent field distinguishing success from failure, so callers branch on one pattern regardless of which operation was invoked. Error details are part of the envelope, not a separate channel.
- `[IE-4]` Operations that are observability-only (tracing, logging) SHALL degrade gracefully — their failure MUST NOT block the skill's primary workflow.

### 7.2 Artifact Durability

The system's operational state lives in files. Power loss, process crashes, and concurrent writes must not corrupt accumulated state. Two storage patterns serve different needs: atomic overwrites for single-document artifacts, and append-only logs for accumulating records.

- Artifacts fall into two categories: **single-document** (overwritten atomically — plans, research, specs) and **append-only** (entries accumulate — memory, reflections, traces).
- `[IE-5]` Append-only artifacts SHALL tolerate corrupted individual entries without losing valid entries.
- `[IE-6]` Single-document artifacts SHALL be overwritten atomically (no partial writes that corrupt state).
- `[IE-25]` Single-document artifacts SHALL be serialized in human-readable format (indented). These artifacts — plans, research, specs — are read by humans during debugging and by skills during analysis. Append-only records (JSONL) SHALL use compact serialization (no indentation, minimal separators) to minimize file size and preserve one-record-per-line structure.

### 7.3 Skill Definitions and Invocation

- Skills are defined as imperative prompts that the LLM interprets at runtime.
- `[IE-7]` Each skill definition SHALL declare its name, description, and argument hint as structured metadata.
- The prompt IS the implementation — there is no compiled code, only instructions the LLM follows.
- `[IE-8]` The system SHALL provide a mechanism for users to invoke skills by name with optional arguments (for example, `/do:design build a web scraper`). The invocation syntax is determined by the host platform's plugin system.
- `[IE-9]` WHEN a skill is invoked, the system SHALL load the skill's prompt into the LLM's context and begin executing its flow. The skill prompt defines the complete behavior — the system does not add implicit behavior beyond what the prompt specifies.
- `[IE-10]` Skills SHALL be discoverable: the user can see which skills are available and what each one does without reading the prompt source.
- `[IE-11]` Skill prompts SHALL be written for high information density — optimized for LLM consumption, not human readability. Use direct imperatives, structured lists, and terse labels over narrative prose. Every token should carry instructional weight. Compress aggressively but not past the point where the LLM loses clarity on what to do, when, and why.

### 7.4 Creativity and Trustworthiness Separation

LLMs excel at synthesis and judgment but cannot guarantee deterministic correctness. Deterministic scripts guarantee correctness but cannot synthesize. Each skill separates these concerns: creative steps (authorship, analysis, judgment) produce candidates; trustworthy steps (validation, hashing, state transitions) gate them before persistence. The boundary between creative and trustworthy is the error amplification boundary — a mistake in a creative step affects one artifact, but a mistake in a trustworthy step silently corrupts the system.

- `[IE-12]` Each skill SHALL separate creative operations (authorship, judgment, synthesis) from trustworthy operations (validation, state transitions, integrity checks).
- `[IE-13]` Trustworthy operations SHALL be deterministic. Test: "if this produces the wrong result, will we know?" If no (silent corruption), it must be deterministic.
- `[IE-14]` Creative outputs that become inputs to other components SHALL pass through a trustworthy validation gate before persistence. **Bookend pattern**: load state (trustworthy) → think/synthesize (creative) → validate and persist (trustworthy).
- Higher cascade amplification of an error → stronger trustworthiness requirement.

### 7.5 Structured Reasoning for Complex Judgments

Single-pass LLM responses work for straightforward tasks but fail on complex judgments — evaluating expert claims, resolving conflicts, adversarial review. These require explicit multi-step reasoning where each step is visible, revisable, and can branch into alternative paths.

- `[IE-15]` WHEN the system faces a complex judgment call, it SHALL use explicit, multi-step reasoning rather than single-pass responses. Complex judgment calls include: evaluating whether expert claims are correct, resolving conflicting recommendations, adversarial self-review, assessing whether a goal is ambiguous, and weighing architectural trade-offs.
- `[IE-16]` Each reasoning step SHALL be visible and traceable — not hidden inside a single response.
- `[IE-17]` The reasoning process SHALL support revision — earlier conclusions updated as later steps reveal new information.
- `[IE-18]` The reasoning process SHALL support branching — exploring alternative paths without losing the main thread.
- `[IE-19]` WHEN the system produces a recommendation or resolves a conflict between competing approaches, it SHALL state the conditions under which the chosen direction would be wrong — what evidence, if discovered, would invalidate the recommendation. A recommendation without falsification conditions cannot be meaningfully challenged by adversarial review.
- The mechanism for structured reasoning is an implementation choice. Behavioral contract: complex judgments produce explicit, revisable, multi-step reasoning chains.

### 7.6 Self-Verification

The operations layer is the trustworthy foundation — if it produces wrong results, every skill built on it is compromised. Self-testing is the guard: every operation has tests, and all tests passing is the baseline invariant.

- `[IE-20]` The deterministic operations layer SHALL have comprehensive self-testing that exercises every operation against synthetic fixtures.
- `[IE-21]` WHEN self-test is run, all tests SHALL pass. Any failure indicates a regression in the operations layer.

### 7.7 Store Abstraction

Multiple stores (memory, reflections, traces) share the same append-only pattern: records accumulate, corrupt entries are skipped, identifiers and timestamps are auto-assigned. These common behaviors are contracted once here rather than repeated per store.

- `[ST-1]` WHEN a record is added to a store, the system SHALL automatically assign a unique identifier and a UTC timestamp. The caller does not supply these fields.
- `[ST-2]` WHEN a store is searched, matching SHALL be case-insensitive substring matching across all text fields by default. WHEN specific fields are requested, only those fields SHALL be searched.
- `[ST-3]` WHEN a store add operation includes a validation function, the validator SHALL run before any write occurs. WHEN the validator rejects the record, the store file SHALL not be modified.
- `[ST-4]` WHEN a store file does not exist, read operations SHALL return an empty collection — not an error.

### 7.8 Content Integrity

Content hashing serves two purposes: tamper detection (has a contract's verification been modified outside design?) and change tracking (has an artifact changed since the last review?). Hashes must be deterministic and order-independent — the same logical content always produces the same hash.

- `[CI-1]` WHEN the system computes a content hash, it SHALL use canonical serialization (sorted keys, minimal separators) followed by a cryptographic digest. The result SHALL be identical regardless of key insertion order in the input.

**Prohibitions**:

- `[IE-22]` The command-line interface MUST NOT produce output on stderr under any circumstance.
- `[IE-23]` Append-only stores MUST NOT silently discard valid entries — only corrupted or unparseable entries may be skipped.
- `[IE-24]` Atomic writes MUST NOT leave temporary files behind after completion (success or failure).

---

## 8. Implementation Choices

Explicit implementation decisions (changeable without affecting behavioral contracts):

1. **Storage format**: Append-only stores use line-delimited structured records (one record per line). Research artifacts use individual files (one per artifact) to support large documents.
2. **Hashing algorithm**: Content integrity uses SHA-256 with canonical (sorted-key, minimal-separator) serialization.
3. **Atomic write mechanism**: Temporary file in same directory followed by atomic rename.
4. **Plan schema version**: Currently version 2, with backward compatibility for version 1.
5. **Exit code convention**: 0 for success, 1 for business logic errors, 2 for usage/argument errors.
6. **Importance bounds**: Memory importance ranges from 3 (minimum/default) to 10 (maximum). Suppression sets to 0.
7. **Role count bounds**: Plans support 1–8 roles.
8. **Subprocess timeout**: Verification commands time out after 30 seconds.
9. **Cascade abort threshold**: When more than half of pending roles would be skipped, the abort flag is set.
10. **Persistent store location**: All operational state resides under a configurable root directory.
11. **Context isolation mechanism**: Skills requiring context isolation (`[FC-1]`, `[RN-1]`) use the host platform's skill-level fork directive (`context: fork` in skill metadata). When invoked, the host platform spawns an isolated subagent that loads the skill prompt independently — the invoking skill's context never receives the target skill's prompt. This satisfies `[LC-14]` without manual agent spawning in the skill prompt.
