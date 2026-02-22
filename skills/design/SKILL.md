---
name: design
description: "Decompose a goal into a structured plan."
argument-hint: "<goal description>"
---

# Design

Decompose a goal into `.design/plan.json` with role briefs — goal-directed scopes for specialist workers. **This skill only designs — it does NOT execute.**

Before starting the Flow, Read `lead-protocol-core.md`. It defines the canonical lead protocol (boundaries, trace emission, memory injection, phase announcements). Design uses standalone Task() subagents — no team setup required. Task() blocks until done, so no polling logic is needed. Substitute: {skill}=design, {agents}=experts.

---

## Clarification Protocol

| ASK (`AskUserQuestion`) when | SKIP when |
|---|---|
| Multiple valid interpretations exist | Codebase contains the answer |
| Scope is underspecified | Standard practice is clear |
| Technology choice is open and impacts approach | Any reasonable choice works |
| Data source is ambiguous | User preference doesn't change approach |

---

## Flow

### 1. Pre-flight

1. **Lifecycle context**: Run Lifecycle Context protocol (see lead-protocol-core.md). This runs `python3 $PLAN_CLI plan-health-summary .design` and emits the skill-start trace.
2. **Spec check**: If `.design/spec.json` exists, run `python3 $PLAN_CLI spec-search .design/spec.json` and report the entry count and category breakdown to the user. Do NOT load all entries here — spec entries are injected per-role during Step 5 role brief authorship.
3. **Check for ambiguity**: Use `sequential-thinking` to assess: "Is this goal genuinely unambiguous? What assumptions am I making about scope? Does the goal's wording imply something different from what I'm planning to build? Would a reasonable person read this goal and expect a different output?" If any ambiguity surfaces, use `AskUserQuestion` before proceeding. **Scope change gate**: If during design you discover existing solutions that would change what gets built (e.g., "build X" becomes "import from existing X"), use `AskUserQuestion` before proceeding. The user asked for X — building Y instead requires explicit consent, even if Y is more efficient.
4. If >5 roles likely needed, suggest phases. Design only phase 1.
5. Check existing plan: `python3 $PLAN_CLI status .design/plan.json`. If `ok` and `isResume`: ask user "Existing plan has {counts} roles. Overwrite?" If declined, stop.
6. Archive stale artifacts: `python3 $PLAN_CLI archive .design`

### 2. Lead Research

The lead directly assesses the goal to determine needed perspectives.

1. Read the goal. Scan project metadata (CLAUDE.md, package.json, README) via Bash to understand stack.
2. Decide what expert perspectives would help.
3. Assess complexity tier (drives role count and expert depth):

| Tier | Roles |
|---|---|
| Trivial (1-2 roles, obvious approach) | 1-2 |
| Standard (clear domain) | 2-4 |
| Complex (cross-cutting concerns) | 4-6 |
| High-stakes (production, security, data) | 3-8 |

4. Select auxiliary roles. For all tiers: integration-verifier and memory-curator. No pre-execution auxiliaries — `/do:reflect` handles plan review and artifact fixes between design and execute.
5. **Announce to user**: Display planned team composition, complexity tier, and auxiliaries: "Design: {complexity tier}, spawning {N} experts ({names}). Auxiliaries: {list}."

**Expert Selection**

Analyze the goal type and spawn appropriate experts:

**Implementation goals** (build/add/create/implement):
- **architect** — system design, patterns, trade-offs
- **researcher** — prior art, libraries, best practices
- **domain specialists** — security, performance, UX, data, etc.

**Meta goals** (improve this plugin, modify SKILL.md, refactor plan.py):
- **prompt-engineer** — for skill improvements (analyzes SKILL.md structure, protocol gaps)
- **maintainer** — for codebase refactoring (analyzes current architecture, proposes improvements)
- **domain specialist** — if goal targets specific domain (e.g., 'improve memory search' → information-retrieval specialist)

**Research/analysis goals** (analyze/audit/document):
- **researcher** — investigates the area being analyzed
- **documenter** — if output is documentation
- **domain specialist** — for domain-specific analysis (security audit → security specialist)

**For complex/high-stakes goals with >=3 experts**: Choose at least 2 experts with contrasting priorities (e.g., performance vs maintainability, security vs usability) to enable productive debate.

**For trivial goals** (1-2 roles, single obvious approach): skip experts. Write the plan directly. Skip to Step 5.

**When uncertain about goal type**: Ask the user to clarify intent before spawning experts.

### 3. Spawn Experts

Spawn experts as parallel standalone Task() subagents.

1. **Memory injection**: Run `python3 $PLAN_CLI memory-search .design/memory.jsonl --goal "{goal}" --stack "{stack}"`. If `ok: false` or no memories → proceed without injection. Otherwise inject top 3-5 into expert prompts. **Show user**: "Memory: injecting {count} past learnings — {keyword summaries}."
2. **Spawn all experts in the same response** (parallel). Use `Task(subagent_type: "general-purpose", model: "sonnet")` for each — standalone Task calls only, no team or name parameters. Task() returns their result directly when done — no liveness tracking needed.
   - Before each Task call: `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event spawn --skill design --agent "{expert-name}" --payload '{"model":"sonnet","memoriesInjected":N}' || true`
   - Write prompts appropriate to the goal and each expert's focus area. Ask them to score relevant dimensions and trace scenarios.
   - **Behavioral traits**: Include behavioral instructions — tell experts HOW to think, not WHO to be. Examples: "Question assumptions that feel obvious", "Reject solutions that add complexity without clear benefit", "Focus on failure modes before success paths", "Assume prior art exists — search before inventing." Tailor traits to the expert's focus (e.g., architect: "Prefer composable patterns over monolithic solutions"; security specialist: "Assume every input is hostile until validated").
   - **Measurable estimates**: Instruct experts: "Base verification properties and estimates on actual code metrics (file counts, line counts, test coverage, dependency depth) where possible. Read codebase samples to ground estimates. Avoid theoretical predictions — anchor to observable reality."
   - **Verify claims against reality**: Instruct experts: "When claiming existing code/data/infrastructure works, verify by checking actual outputs — not just code structure. Read data files, run scripts, inspect results. A scraper that exists in code but produces empty output is not 'fully functional'. Report what you verified vs what you inferred."
   - **Verify external systems when accessible**: Instruct experts: "When the goal involves integrating with an external system (website, API, service) and the system is accessible, use WebFetch or WebSearch to verify assumptions about the live system — don't rely solely on existing code that may be stale. At minimum, fetch public pages (login pages, docs, status endpoints) to confirm URLs, form fields, and page structure. Report discrepancies between existing code assumptions and live observations."
   - Every expert prompt MUST end with: "In your findings JSON, include a `verificationProperties` section: an array of properties that should hold regardless of implementation (behavioral invariants, boundary conditions, cross-role contracts). Format: `[{\"property\": \"...\", \"category\": \"invariant|boundary|integration\", \"testableVia\": \"how to test this with concrete commands/endpoints\"}]`. Provide concrete, externally observable properties that can be tested without reading source code. When suggesting testableVia commands, avoid anti-patterns: grep-only checks (verifies text exists, not that feature works), `test -f` as sole check (file exists but may contain errors), `wc -l` counts (size not correctness), `|| echo` or `|| true` fallbacks (always exits 0), pipe chains without exit-code handling (may mask failures)."
   - **High-leverage content drafting**: When an expert's domain includes template text, example content, or canonical guidance that workers will copy verbatim into the codebase, instruct the expert to draft that content in their findings. Examples: EARS notation examples for an AC authorship expert, API schema examples for an architect, error message templates for a UX specialist. Workers focused on file editing should not have to invent canonical examples — experts with domain context produce better ones.
   - Instruct: "Save your complete findings to `.design/expert-{name}.json` as structured JSON."
   - Instruct: "Return a one-paragraph summary when done."
3. After all Tasks return, verify artifacts exist: `ls .design/expert-{name}.json` for each expert. If any is missing but Task returned output, write the output to the missing artifact file. If Task errored, spawn a replacement Task() with the same prompt (max 1 retry per expert).

### 4. Interface Negotiation & Cross-Review

Expert coordination prevents **integration failures** (domains don't fit together) and **convergence failures** (experts reach incompatible conclusions). Assess which phases apply per the decision matrix, then execute them.

**CRITICAL ENFORCEMENT**: The lead MUST NOT skip cross-review when the decision matrix mandates a phase. Cross-review uses follow-up Task() calls — lead reads expert artifacts after all initial Task() calls complete, then spawns targeted Task() calls to perform negotiation. Max 2 rounds = max 2 follow-up Task() calls per conflict. Skipping cross-review when the decision matrix says a phase is mandatory is a protocol violation.

| Phase | Trigger | Purpose |
|---|---|---|
| **A: Interface negotiation** | >=2 experts whose roles will share data/APIs/file boundaries | Producer-consumer pairs agree on shared interface contracts |
| **B: Perspective reconciliation** | >=2 experts analyzed same domain from different angles, OR >=3 experts in complex/high-stakes tier | Resolve conflicting recommendations about the same thing |
| **C: Cross-domain challenge** | Complex/high-stakes tier with >=3 experts | Catch cross-domain assumptions neither A nor B would surface |

**Decision matrix**: If condition matches → phase is **mandatory**. If <2 experts or trivial tier → skip all phases. **Announce to user** which phases will run: "Cross-review: running {phases} — {brief reason}."

#### Phase Execution Pattern

All phases follow: **maximum 2 rounds** of negotiation per conflict. If no convergence after 2 rounds, lead decides and documents reasoning. **When resolving conflicts**, use `sequential-thinking` to weigh each position: "What evidence supports each side? What would failure look like if I choose wrong? Is there a synthesis that preserves both positions' strengths?"

**Phase A steps**:
1. Lead reads all expert artifacts from `.design/expert-*.json` files
2. Lead identifies domain boundaries (API shapes, schemas, file formats, shared state)
3. Lead drafts consumer-driven contracts: `{boundary, producer, consumer, contract}` (use format: `Interface: {name}, Producer: {role}, Consumer: {role}, Contract: {concrete spec}`)
4. For each contract requiring input, spawn a follow-up `Task(subagent_type: "general-purpose", model: "sonnet")` with the relevant expert artifact(s) as context: "Read these expert findings. Does this interface contract work for your domain? Flag constraints: {contract}. Return: (a) approved/rejected, (b) constraints, (c) proposed amendments."
5. Collect Task() results, negotiate (max 2 rounds of follow-up Tasks)
6. Save to `.design/interfaces.json` as binding constraints

**Phase B steps**:
1. Lead reads all expert artifacts and identifies overlapping analysis (>=2 experts made recommendations about same thing)
2. For each conflict, spawn a follow-up `Task(subagent_type: "general-purpose", model: "sonnet")` with both expert artifacts as context: "Read these two expert analyses. They differ on {topic}: {positionA} vs {positionB}. Return: (a) agreements, (b) disagreements + which is better supported by evidence, (c) synthesis proposal."
3. Collect Task() results, negotiate synthesis (max 2 rounds of follow-up Tasks)
4. Lead decides if no convergence, documents trade-off

**Phase C steps**:
1. Lead reads all expert artifacts
2. For each expert, spawn a follow-up `Task(subagent_type: "general-purpose", model: "sonnet")` with all OTHER experts' artifacts as context: "Read these expert analyses. Challenge any claims that affect your domain. Format: Challenge to {expert}, Claim: '{quote}', Severity: [blocking|important|minor], Evidence: {why problematic}, Alternative: {proposal}. If no challenges: return 'No challenges found'."
3. Collect challenge Task() results
4. For each blocking/important challenge, spawn a targeted follow-up Task() for the challenged expert to respond (max 2 rounds per challenge)
5. Lead resolves conflicts, updates `.design/interfaces.json` if contracts changed

**Checkpoint**: Save `.design/cross-review.json` with audit trail: `{phasesRun: ["A"|"B"|"C"], interfaces: {count, rounds}, reconciliations: {count, rounds}, challenges: {sent, resolved}, skippedPhases: [{phase, reason}]}`. If no phases applicable, save with `phasesRun: []` and skip reasons.

### 5. Synthesize into Role Briefs

**Announce to user**: "Synthesizing expert findings into role briefs."

1. Collect all expert findings from `.design/expert-*.json` files via Bash (`python3 -c "import json; ..."`).
2. **Evaluate expert claims**: Use `sequential-thinking` before writing role briefs. Run through these three adversarial checkpoints in a single thinking sequence:
   - **Could you be wrong?** "What assumptions from expert findings did we NOT verify with direct evidence? What information did we have access to (live systems, data files, actual outputs) but didn't check? What do we claim with high confidence that is actually uncertain?"
   - **Pre-mortem** "A worker takes this plan, builds it, and it fails. What was missing from our expert findings that they needed? What was misleading? What real-world condition (stale URLs, changed APIs, missing data) did we not account for?"
   - **Backward chaining** "What would the ideal plan contain for a worker to succeed on the first attempt? Do we have verified URLs, confirmed selectors, tested endpoints? What specific investigations would have produced that ideal — and which did we skip?"
   If any checkpoint surfaces a concrete gap (not a hypothetical), address it before writing role briefs: fetch the URL, check the file, verify the endpoint. A 5-second WebFetch now prevents a failed execute run later.
3. **Resolve conflicts from cross-review** (if debate occurred): For each challenge, evaluate trade-offs and decide. Document resolution in plan.json under `designDecisions[]` (schema: {conflict, experts, decision, reasoning}). **Show user each decision**: "Decision: {conflict} → {chosen approach} ({one-line reasoning})."
3. **Incorporate interface contracts**: If `.design/interfaces.json` was produced in Step 4, add each interface as a constraint on the relevant producer and consumer roles. Interface contracts are binding — workers must implement the agreed interface shape.
4. Identify the specialist roles needed to execute this goal:
   - Each role scopes a **coherent problem domain** for one worker
   - If a role would cross two unrelated domains, split into two roles
   - **Shared file check**: If a role modifies a file that exists identically in multiple directories (e.g., shared protocol files, copied configs), the plan MUST scope ALL copies for update — either in the same role or in a dependent role. Run `find` or `ls` to detect duplicates before finalizing scope.
   - **Type/interface ownership**: When multiple roles produce or consume the same data contract (interface, type, schema), designate ONE role as the canonical owner of the definition. Other roles must import from the canonical source, not redefine it. Flag if the same interface already exists in multiple files — add a constraint for one role to consolidate.
   - Workers decide HOW to implement — briefs define WHAT and WHY
5. **Spec injection per role**: If `.design/spec.json` exists, for each role run: `python3 $PLAN_CLI spec-search .design/spec.json --goal "{role goal}" --keywords "{role name} {scope directories joined by space}"`. Take the top 3 returned entries and inject each as a role constraint with the prefix: `"Spec invariant — workers must preserve this behavior: {spec entry ears or description} (spec.json entry '{id}')"`. Spec-derived constraints are invariants — workers must not change system behavior that a spec entry describes, even if their role brief does not explicitly prohibit the change. If spec.json does not exist or spec-search returns zero entries, proceed without injection.
6. Write `.design/plan.json` with role briefs (see schema below).
7. For each role, include `expertContext[]` referencing specific expert artifacts and the sections relevant to that role. **Do not lossy-compress expert findings into terse fields** — reference the full artifacts.
8. Write criteria-based `acceptanceCriteria` — define WHAT should work, not WHICH files should exist. Workers verify against criteria, not file lists. **Before writing any AC check that parses a specific file format** (YAML structure, JSON schema, multi-document layout), use the targeted fact-check exception to read 5-10 lines of the actual target file and confirm its structure matches your assumptions. Do not write checks based solely on expert descriptions of file formats — verify then write, not write then verify. **Every criterion MUST have a `check` that is a concrete, independently runnable shell command** (e.g., `"bun run build"`, `"bun test --run"`). Never leave checks as prose descriptions — workers execute these literally. If a role touches compiled code, include BOTH a build check AND a test check as separate criteria. **Checks must verify functional correctness, not just pattern existence.** A grep confirming a CSS rule exists is insufficient — the check must verify the rule actually takes effect (e.g., start a dev server and curl the page, or verify that referenced classes/imports resolve to definitions). At least one criterion per role should test end-to-end behavior, not just file contents. **Check commands must fail-fast with non-zero exit codes on failure.**

   **Data-dependent roles**: For roles that import, serve, or display data, at least one AC check MUST verify that data actually exists and is correct — not just that the response shape is valid. A check that asserts `'data' in response` passes on empty arrays. Instead: assert `len(response['data']) > 0` or verify specific field values. Include fixture/sample data in the plan so data-dependent checks have something to verify against.

   **External integration roles**: For roles that connect to external systems (scrapers, API clients, webhooks), at least one AC MUST test actual connectivity or output — not just compilation. If the live system can't be tested in CI, require a `--dry-run` or `--mock` mode AC that validates the integration logic against fixture data end-to-end (e.g., "scraper with mock HTML produces valid ScraperOutput JSON"). Static checks (tsc compiles, file exists) are necessary but insufficient for integration roles.

   **Learn from past AC mutations**: If `plan-health-summary` returned `acMutations` from recent execute runs, review them before writing checks. Each mutation shows a check that design got wrong and execute had to fix. Common patterns to avoid: wrong test data (e.g., `--skill test` when only design/execute/research/simplify are valid), fragile position checks (e.g., checking first 30 lines when content may shift), version comparisons that pass trivially (e.g., `int(patch) > 0` passes for any non-zero patch). Use the `after` field as a template for better checks.

   **Acceptance criteria anti-patterns** (NEVER use these as the sole check for a criterion):
   - `grep -q "pattern" file` — anti-pattern: verifies text exists, not that feature works
   - `test -f output.json` — anti-pattern: file exists but may contain errors
   - `wc -l file` — anti-pattern: verifies size, not correctness
   - `cmd || echo "fallback"` or `cmd || true` — anti-pattern: always exits 0, masks failures completely
   - `cmd 2>&1 | tail -N` — anti-pattern: pipe may mask exit code unless `set -o pipefail` is used
   - `! grep -q "removed_thing" file` as sole check — anti-pattern: verifies removal but not that the replacement works. Always pair removal checks with positive checks verifying the new pattern exists in the correct context (e.g., `! grep -q 'old_pattern' f && grep -q 'Task(' f`)

   **EARS notation for behavioral criteria**: When writing criteria that describe system responses to triggers, use EARS (Easy Approach to Requirements Syntax) structure: `"WHEN [trigger condition], THE system SHALL [observable response]"`. Apply EARS only to behavioral-invariant and boundary-contract style criteria — not to build/test runner checks (e.g., `"bun run build"`) and not to architectural-decision criteria. Each EARS criterion must be paired with a `check` that independently verifies the observable response described — not that code implementing it exists. Correct examples:
   - Criterion: `"WHEN 10 requests arrive within 1 second, THE system SHALL return HTTP 429 on the 11th"` → Check: `for i in $(seq 1 11); do curl -s -o /dev/null -w '%{http_code}\n' http://localhost:3000/api/health; done | tail -1 | grep -q 429`
   - Criterion: `"WHEN a required field is missing from POST /users, THE system SHALL return HTTP 400 with an 'errors' field"` → Check: `curl -s -X POST http://localhost:3000/users -H 'Content-Type: application/json' -d '{}' | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get('errors') else 1)"`
   - Criterion: `"WHEN finalize runs on a plan.json with schemaVersion != 4, THE system SHALL exit non-zero"` → Check: `python3 -c "import json,subprocess,sys; p=json.load(open('.design/plan.json')); p['schemaVersion']=99; open('/tmp/bad_plan.json','w').write(json.dumps(p)); r=subprocess.run(['python3','scripts/plan.py','finalize','/tmp/bad_plan.json'],capture_output=True); sys.exit(0 if r.returncode!=0 else 1)"`
   When uncertain whether EARS applies, ask: does this criterion describe what the system does in response to an event? If yes, use EARS. If it is a boundary-contract (external API response codes, file format guarantees) or a behavioral-invariant (system must always preserve X), EARS is the right format.

   **Check command authoring rules** (apply when writing `check` fields):
   - **AC gate pre-check**: Every structural AC must FAIL against the current codebase before execution and PASS after. If a check passes without changes, it verifies nothing — rewrite it to detect the actual before-state.
   - **Ban f-strings in inline Python**: `python3 -c "..."` check commands must NOT use f-strings — nested quotes and backslash escapes inside `"..."` cause `SyntaxError`. Use `.format()` or `%` formatting instead, or move complex logic to a script file.
   - **Prefer script files for complex checks**: When a check requires >1 logical step, write it to a temp file (`python3 /tmp/check_role.py`) instead of inlining with `-c`. Inline `-c` is limited to simple one-liners.
   - **Fail-fast required**: Every check must exit non-zero on failure with no fallback (`|| true`, `|| echo`) that masks the result.

   **Check command template library** — use these patterns, not custom one-offs:

   | Purpose | Template |
   |---|---|
   | File contains pattern (structural only, not sole check) | `grep -q "pattern" path/to/file` |
   | Python script parses JSON without error | `python3 -c "import json; json.load(open('file.json'))"` |
   | Python script validates field (use .format, not f-string) | `python3 -c "import json; d=json.load(open('f.json')); assert d['k']=='v', d['k']"` |
   | Complex Python check (multi-step) | Write to `/tmp/check_rolename.py`, then: `python3 /tmp/check_rolename.py` |
   | Command exits 0 (build/test) | `bun run build` or `python3 -m pytest tests/` |
   | Schema field exists and is non-empty | `python3 -c "import json,sys; d=json.load(open('f.json')); sys.exit(0 if d.get('field') else 1)"` |
   | Count lines/entries in output | `python3 -c "import json; d=json.load(open('f.json')); assert len(d['items'])>=3"` |
   | Shell script file is executable and exits 0 | `bash path/to/script.sh` |

9. **Constraint-to-AC coverage audit**: For each role, verify that every entry in `constraints[]` maps to at least one `acceptanceCriteria` check. If a constraint cannot be verified by a shell command (e.g., "use http:// not https://" or "preserve existing annotation"), mark it with the suffix `(manual-only)` in the constraint text so workers know it is not AC-checked. Constraints without AC checks become unverifiable obligations that workers may skip.
10. Add `auxiliaryRoles[]` (see Auxiliary Roles section).
10. Write to `.design/plan.json` (do NOT run finalize yet — that happens in Step 6).
11. **Draft plan review** (complex/high-stakes tier only): Display the draft plan to the user before finalization:
   ```
   Draft Plan ({roleCount} roles):
   - Role 0: {name} — {goal one-line} [{model}]
   - Role 1: {name} — {goal one-line} [{model}] [after: {dependencies}]
   ...
   Design decisions: {count}
   ```
   This is non-blocking — continue to finalization. If the user objects, adjust before finalizing. For trivial/standard tiers, skip this review.

**Validate acceptance criteria checks (MANDATORY blocking gate)**: Before running finalize, you MUST run `python3 $PLAN_CLI validate-checks .design/plan.json`. If errors are found, display them to the user with role name and criterion, then fix every check command in plan.json before proceeding. Do NOT call finalize until validate-checks reports zero errors. Apply the check command authoring rules above (ban f-strings, prefer script files for complex checks) when rewriting broken checks.

### 6. Generate Verification Specs

Verification specs are property-based tests workers must satisfy. They codify expert verificationProperties as executable tests without constraining implementation.

**When to generate**:

| Condition | Required? | Rationale |
|---|---|---|
| **4+ roles** | **MANDATORY** | Integration complexity requires property-based validation |
| **New skill creation** (new SKILL.md files) | **MANDATORY** | End-to-end workflow must be testable |
| **API integration** (external services, auth, rate limits) | **MANDATORY** | External contracts need verification |
| **1-3 roles** with simple scope | **OPTIONAL** | Acceptance criteria may suffice |
| **Docs-only** or **config-only** changes | **OPTIONAL** | Low integration risk |
| **Sparse verificationProperties** (experts provide <2 properties) | **OPTIONAL** | Insufficient property coverage |

Additional requirements for all cases: expert artifacts contain verificationProperties AND stack supports tests (context.testCommand/buildCommand exists).

**Authorship**: Simple goals (1-3 roles) → lead writes from expert verificationProperties. Complex goals (4+ roles) → spawn spec-writer Task agent with `Task(subagent_type: "general-purpose", model: "sonnet")` that reads expert artifacts + actual codebase, writes specs in `.design/specs/{role-name}.{ext}` using project's test framework or shell scripts, returns created paths.

**Spec generation**:
1. Read expert verificationProperties from all `.design/expert-*.json` files
2. For each role, extract relevant properties (filter by scope/goal alignment)
3. `mkdir -p .design/specs`
4. Write spec files: native tests (`.design/specs/spec-{role-name}.test.{ext}` using bun test/pytest/jest/cargo test/etc with property-based frameworks like fast-check/hypothesis/proptest) OR shell scripts (`.design/specs/spec-{role-name}.sh` with exit 0 = pass)
5. For each spec, add to plan.json's `verificationSpecs[]`: `{"role": "{role-name}", "path": ".design/specs/spec-{role}.{ext}", "runCommand": "{e.g., 'bun test .design/specs/spec-api.test.ts'}", "properties": ["brief descriptions"]}`

**Spec content**: Test WHAT (external behavior), not HOW (implementation). Include positive AND negative cases. Use property-based testing where possible. Test cross-role contracts. Specs must be independently runnable.

**Finalization**: `python3 $PLAN_CLI finalize .design/plan.json` validates structure, computes overlaps, computes SHA256 checksums for spec files (tamper detection).

**Security: no secrets in plan artifacts**: Plan.json, expert artifacts, and interface contracts are project files that may be committed. NEVER include plaintext credentials, API keys, tokens, or passwords in any `.design/` artifact. Reference credentials by env var name (e.g., "use RCI_USER from .env") — never by value. If the user provides credentials in the conversation, instruct workers to read them from .env, not from plan.json constraints.

**Role brief principles**:
- `goal`: Clear statement of what this role must achieve
- `scope.directories/patterns`: Where in the codebase this role operates (not specific files)
- `constraints`: Hard rules the worker must follow
- `acceptanceCriteria`: Goal-based success checks (not file existence checks)
- `expertContext`: References to expert artifacts with relevance notes
- `assumptions`: What must be true for the approach to work
- `rollbackTriggers`: When the worker should stop and report
- `fallback`: Alternative approach if primary fails (included in initial brief, not hidden until retry)
- **No `approach` field** — workers read the codebase and decide their own implementation strategy

**Role brief example**:
```json
{
  "name": "api-developer",
  "goal": "Implement rate limiting for all API routes using token-bucket algorithm",
  "model": "sonnet",
  "scope": {
    "directories": ["src/middleware/", "src/routes/"],
    "patterns": ["**/*.middleware.*"],
    "dependencies": []
  },
  "expertContext": [
    {
      "expert": "architect",
      "artifact": ".design/expert-architect.json",
      "relevance": "Middleware chain design, Express router structure"
    }
  ],
  "constraints": [
    "Use stdlib only, no Redis dependency",
    "Must not break existing route tests"
  ],
  "acceptanceCriteria": [
    { "criterion": "Rate limiting active on all /api/* routes", "check": "10 rapid requests to /api/health — last returns 429" },
    { "criterion": "Build succeeds", "check": "npm run build" },
    { "criterion": "Existing tests pass", "check": "npm test" }
  ],
  "assumptions": [
    { "text": "Express middleware pattern used", "severity": "non-blocking" }
  ],
  "rollbackTriggers": ["Existing tests fail"],
  "fallback": "If token-bucket too complex for stdlib, use simple sliding window counter"
}
```

### 7. Auxiliary Roles

Add auxiliary roles to `auxiliaryRoles[]` in plan.json. For all tiers: integration-verifier and memory-curator. Challenger and scout are NOT included — their functions are absorbed by `/do:reflect`, which runs between design and execute to review artifacts and fix issues with full conversation context.

```json
[
  {
    "name": "integration-verifier",
    "type": "post-execution",
    "goal": "Run full test suite. Check cross-role contracts. Validate all acceptanceCriteria. Test goal end-to-end.",
    "model": "sonnet",
    "trigger": "after-all-roles-complete"
  },
  {
    "name": "memory-curator",
    "type": "post-execution",
    "goal": "Distill design learnings: expert selection effectiveness, cross-review value, plan structure quality. Apply five quality gates before storing to .design/memory.jsonl.",
    "model": "haiku",
    "trigger": "after-all-roles-complete"
  }
]
```

### 8. Complete

1. Validate: `python3 $PLAN_CLI status .design/plan.json`. Stop if `ok: false`.
2. Summary: `python3 $PLAN_CLI summary .design/plan.json`. Display a rich end-of-run summary:

```
Design Complete: {goal}
Result: {roleCount} roles, max depth {maxDepth}

Roles:
| # | Name | Model | Dependencies | Goal |
|---|------|-------|-------------|------|
| 0 | {name} | {model} | — | {goal one-line} |
| 1 | {name} | {model} | after: {dep} | {goal one-line} |

Design Decisions:
| Conflict | Decision | Reasoning |
|----------|----------|-----------|
| {conflict} | {decision} | {one-line reasoning} |

Expert Highlights:
- {expert-name}: {key finding one-liner}

Acceptance Criteria: {total AC count across all roles}
| Role | Criteria | Key check |
|------|----------|-----------|
| {name} | {count} | {most important check command, abbreviated} |

Verification specs: {count or "none"}
Context: {stack}, Test: {testCommand}
Memories applied: {count or "none"}
```

3. **Trace** — Emit completion trace:

   ```bash
   python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event skill-complete --skill design --payload '{"outcome":"<completed|partial|failed|aborted>","roleCount":N,"expertsSpawned":N,"crossReviewPhases":["A"|"B"|"C"],"specsGenerated":N}' || true
   ```

4. **Next action** — Suggest the next steps. Always include `/do:reflect` first:

   ```
   Next: /do:reflect (review this design for gaps and missed opportunities)
   Then: /do:execute
   ```

**Fallback** (if finalize fails):
1. Fix validation errors and re-run finalize.
2. If structure is fundamentally broken: rebuild plan inline from expert findings, one role at a time.

---

## Contracts

### plan.json (schemaVersion 4)

**Top-level fields**: schemaVersion (4), goal, context {stack, conventions, testCommand, buildCommand, lsp}, expertArtifacts [{name, path, summary}], designDecisions [], verificationSpecs [] (optional), roles[], auxiliaryRoles[], progress {completedRoles: []}

**designDecisions fields**: conflict, experts (array), decision, reasoning. Documents lead's resolution of expert disagreements.

**verificationSpecs fields** (optional): Array of `{role, path, runCommand, properties, sha256}`. Maps roles to property-based test specs. SHA256 checksums computed by finalize for tamper detection. Workers fix code to pass specs, never modify specs.

**Role fields**: name, goal, model, scope {directories, patterns, dependencies}, expertContext [{expert, artifact, relevance}], constraints [], acceptanceCriteria [{criterion, check}], assumptions [{text, severity}], rollbackTriggers [], fallback. Status fields (status, result, attempts, directoryOverlaps) are initialized by finalize.

**Auxiliary role fields**: name, type (pre-execution|post-execution), goal, model, trigger. See Step 7 for examples.

### Interface Contracts (interfaces.json)

Produced during Step 4 Phase A when roles share domain boundaries. Array of `{boundary, producer, consumer, contract, negotiationNotes}`. Workers treat interface contracts as binding constraints.

### Analysis Artifacts

Preserved in `.design/` for execute workers:
- `expert-{name}.json` — per-expert findings (structured JSON)
- `interfaces.json` — agreed interface contracts (if produced in Step 4)

**Goal**: $ARGUMENTS
