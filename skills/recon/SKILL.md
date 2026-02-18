---
name: recon
description: "Investigate an area to identify high-leverage interventions using systems thinking."
argument-hint: "<area or question to investigate>"
---

# Recon

Investigate an area and produce a ranked list of interventions in `.design/recon.json` using adapted Meadows leverage point analysis. **This skill researches and ranks — it does NOT design or execute.**

**PROTOCOL REQUIREMENT: Do NOT answer the goal directly. Your FIRST action after reading the area MUST be the pre-flight check. Follow the Flow step-by-step.**

**CRITICAL BOUNDARY: Recon identifies WHAT to change and WHY. It does NOT determine HOW — that is `/do:design`'s job. Recon produces `.design/recon.json`, NOT `.design/plan.json`. If you start thinking about role decomposition or acceptance criteria, you have crossed into design territory — stop and refocus on leverage analysis.**

**Do NOT use `EnterPlanMode`** — this skill IS the plan.

**Lead boundaries**: Use only `TeamCreate`, `TeamDelete`, `TaskCreate`, `TaskUpdate`, `TaskList`, `SendMessage`, `Task`, `AskUserQuestion`, and `Bash` (for `python3 $PLAN_CLI`, cleanup, verification). Project metadata (CLAUDE.md, package.json, README) allowed via Bash. **Never use Read, Grep, Glob, Edit, Write, LSP, WebFetch, WebSearch, or MCP tools on project source files.** The lead orchestrates — researchers investigate.

**No polling**: Messages auto-deliver automatically. Never use `sleep`, loops, or Bash waits. When a teammate sends a message, it appears in your next turn.

---

## Clarification Protocol

| ASK (`AskUserQuestion`) when | SKIP when |
|---|---|
| Area is truly ambiguous (multiple unrelated systems) | Area maps to a clear codebase region or concern |
| Research scope would span entire codebase with no focus | Question is specific enough to guide research |
| User intent unclear (improve vs audit vs migrate) | Any reasonable interpretation leads to similar research |

Recon tolerates vague inputs better than design. "What should we improve?" is valid. "Make things better" with no project context is not.

### Script Setup

Resolve plugin root (containing `.claude-plugin/`). All script calls: `python3 $PLAN_CLI <command> [args]` via Bash. JSON output: `{"ok": true/false, ...}`.

```bash
PLAN_CLI={plugin_root}/skills/recon/scripts/plan.py
TEAM_NAME=$(python3 $PLAN_CLI team-name recon).teamName
SESSION_ID=$TEAM_NAME
```

### Trace Emission

After each agent lifecycle event: `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event {event} --skill recon [--agent "{name}"] || true`. Events: skill-start, skill-complete, spawn, completion, failure, respawn. Failures are non-blocking (`|| true`).

---

## Leverage Framework

Adapted from Meadows' leverage points with software-adjusted ranking weights. Internally 7 levels; user-facing output uses Abson 4 groups.

### 7-Level Internal Framework

| Level | Name | Software Analog | Ranking Weight | Examples |
|---|---|---|---|---|
| 1 | paradigm | Architecture/technology paradigm shifts | 5 | Monolith to microservices, REST to event-driven |
| 2 | goals | Success metrics, optimization targets | 4 | Redefine "fast" (p99 not p50), shift from feature count to adoption |
| 3 | rules | Standards, CI gates, type constraints, review policies | 6 | Required PR reviews, type safety at boundaries, linting rules |
| 4 | information flows | Logging, monitoring, observability, error reporting | 5 | Structured logging, tracing, runbooks, API documentation |
| 5 | feedback loops | CI/CD, test suites, health checks, alerting, perf budgets | 6 | Performance regression tests, automated rollback, canary deploys |
| 6 | structure | Data models, module boundaries, dependency graph, API contracts | 7 | Extract shared module, normalize database, split circular dependency |
| 7 | parameters | Config values, thresholds, buffer sizes, timeouts | 1 | Tune cache TTL, adjust rate limits, change batch sizes |

**Software-adjusted rationale**: Raw Meadows ordering underweights structural interventions. Empirical evidence (Tornhill hotspot analysis, architectural debt research) shows structure has outsized impact in codebases. Ranking uses software-adjusted weights, not raw level numbers.

### Abson 4-Group Mapping (User-Facing)

| Group | Levels | Description |
|---|---|---|
| **Intent** | 1-2 (paradigm, goals) | Highest leverage, requires human judgment. Frame as questions, not prescriptions. |
| **Design** | 3-4 (rules, information flows) | High leverage AND detectable. Standards, policies, observability. |
| **Feedbacks** | 5-6 (feedback loops, structure) | Empirically validated highest software impact. CI/CD, tests, architecture. |
| **Parameters** | 7 (parameters) | Low leverage regardless of domain. Config tuning. |

### Scoring Formula

Computed deterministically by `recon-validate`:

```
compositeScore = tier_weight * confidence_multiplier / effort_multiplier
```

Where:
- `tier_weight`: software-adjusted weight from the framework table (1-7)
- `confidence_multiplier`: high=1.0, medium=0.7, low=0.4
- `effort_multiplier`: trivial=0.5, small=1.0, medium=2.0, large=4.0, transformative=8.0

### Wrong-Direction Warnings

Meadows' key insight: people find leverage points but push them the wrong way. Each intervention at levels 1-5 MUST include a `wrongDirection` field describing what pushing this the wrong way looks like. Levels 6-7 may omit it.

Example: "Responding to slow tests by skipping tests rather than making them faster" (pushing feedback loops the wrong way).

---

## Flow

### 1. Pre-flight

1. **Lifecycle context**: Run `python3 $PLAN_CLI plan-health-summary .design` and display to user: "Previous session: {handoff summary}. Recent runs: {reflection summaries}." Skip if all fields empty. Then: `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event skill-start --skill recon || true`
2. **Check for ambiguity**: If the area has multiple valid interpretations per the Clarification Protocol, use `AskUserQuestion` before proceeding.
3. **Check existing recon**: `ls .design/recon.json`. If exists, ask user: "Existing recon output found. Overwrite?" If declined, stop.
5. **Archive stale artifacts**: `python3 $PLAN_CLI archive .design`

### 2. Scope Assessment

The lead assesses the area to investigate and determines research team composition.

1. Read the area/question. Scan project metadata (CLAUDE.md, package.json, README) via Bash to understand stack and context.
2. Determine research domains needed (codebase analysis, external research, domain-specific).
3. Select team — always spawn the full research team: 1 codebase-analyst + 1 external-researcher + 1 domain-specialist. Recon is inherently exploratory ("I don't know what I don't know") — external research is always valuable for grounding interventions in prior art and literature.
4. **Announce to user**: "Recon: investigating '{area}'. Spawning 3 researchers (codebase-analyst, external-researcher, domain-specialist)."

### 3. Research

Create the team and spawn researchers in parallel.

1. `TeamDelete(team_name: $TEAM_NAME)` (ignore errors), `TeamCreate(team_name: $TEAM_NAME)`. If TeamCreate fails, tell user Agent Teams is required and stop.
2. **TeamCreate health check**: Verify team is reachable. If verification fails, `TeamDelete`, then retry `TeamCreate` once. If retry fails, abort with clear error message.
3. **Memory injection**: Run `python3 $PLAN_CLI memory-search .design/memory.jsonl --goal "{area}" --keywords "{relevant keywords}"`. If `ok: false` or no memories, proceed without injection. Otherwise inject top 3-5 into researcher prompts. **Show user**: "Memory: injecting {count} past learnings — {keyword summaries}."
4. `TaskCreate` for each researcher.
5. Spawn researchers as teammates using the Task tool. For each researcher:
   - Before Task call: `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event spawn --skill recon --agent "{researcher-name}" || true`
   - Use Task with `team_name: $TEAM_NAME`, `name: "{researcher-name}"`, and `model: "sonnet"` (researchers require Read/Grep/Glob/Bash for codebase analysis and WebSearch/WebFetch for literature research).
   - Include the leverage framework reference table so researchers can classify findings.
   - Include scope bounds: "Focus your investigation on {directories/areas}. Do not explore unrelated areas."
   - Inject relevant memories if available.

**Researcher Prompts by Type**:

**Codebase Analyst** — Internal structure, patterns, debt, dependencies.
- **Tools granted**: Read, Grep, Glob, Bash (for git log, build/test commands, dependency analysis). Secondary: WebSearch, WebFetch (for clarifying code findings only).
- **Tools denied**: Edit, Write (researchers report findings, never modify code).
- Focus: hotspot analysis (git churn x complexity), change coupling, dependency analysis, architectural patterns, technical debt indicators.
- Git hotspot heuristic: `git log --format=format: --name-only --since=12.month | sort | uniq -c | sort -nr | head -20`
- Report what EXISTS — seek both failure signals AND working constraints. What breaks? What does the team NOT violate by convention?
- Describe root causes, not symptoms — "file X is slow" is a symptom; "file X is slow because it has no index" is a cause.
- **Invisible curriculum**: Surface tacit constraints you can infer from code evidence — patterns that appear consistently with no doc explanation, anti-patterns conspicuously absent, dependencies avoided despite obvious utility. Map these to `knowledgeGaps[]` in your findings. Do NOT speculate about team knowledge not evidenced in the codebase.

**External Researcher** — Literature, frameworks, best practices, prior art, ecosystem solutions.
- **Tools granted**: WebSearch, WebFetch, Read (for project context files only).
- **Tools denied**: Edit, Write, Grep, Glob (no codebase exploration — that is the analyst's job).
- Focus: prior art for the problem area, proven patterns from literature, ecosystem solutions, relevant standards.
- Cite sources with URLs. Note confidence and recency of sources.
- **Source priority** (highest to lowest — prefer higher tiers but don't discard high-quality lower-tier sources): (1) Production post-mortems and incident reports. (2) GitHub issues, RFCs, migration guides with real adoption data. (3) Deep-dive engineering blogs with benchmarks. (4) Official documentation and tutorials. (5) Community Q&A and discussions. Always state the source tier and recency.
- Cite specific precedent, not general best practice — name the exact source, version, and why it applies to this codebase, not just the recommendation.
- **Do NOT claim tacit knowledge about this codebase**; if literature documents a common undocumented pitfall, report it as unconfirmed for this codebase and place in `knowledgeGaps[]`.

**Domain Specialist** — Security, performance, UX, data, etc. (context-dependent).
- **Tools granted**: Read, Grep, Glob, WebSearch, WebFetch, Bash (for running project commands).
- **Tools denied**: Edit, Write (researchers report findings, never modify code).
- Focus: domain-specific analysis of the area under investigation.
- Apply your domain lens to THIS specific codebase, not in general — findings must reference concrete evidence from the code, not domain theory alone.
- **Invisible curriculum**: Identify assumed-but-unstated prerequisites visible in the codebase — domain-specific patterns the code follows implicitly, or anti-patterns conspicuously absent. Map to `knowledgeGaps[]` if lacking documentation confirmation.

**All researcher prompts MUST include**:

**Research quality guardrails (all researchers):**

| DO | DON'T |
|---|---|
| Seek failure signals AND working constraints | Report only failures or only successes |
| Cite version numbers/dates for technical claims | Assert recency without evidence |
| Label findings as proven vs inferred | Conflate hypothesis with observation |
| Surface what experts know but docs omit | Repeat what official docs already say |

- "Save your complete findings to `.design/expert-{name}.json` as structured JSON."
- "Then SendMessage to the lead with a summary."
- "For each finding include: area, observation, evidence, preliminary leverageLevel (1-7), leverageGroup (Intent/Design/Feedbacks/Parameters), effort estimate (trivial/small/medium/large/transformative), recommendation."
- "Include a confidence assessment (high/medium/low) with basis for each finding."

6. **Researcher liveness pipeline**: Track completion: (a) SendMessage received AND (b) artifact file exists (`ls .design/expert-{name}.json`). **Show user status**: "Researcher progress: {name} done ({M}/{N} complete)." On completion: `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event completion --skill recon --agent "{name}" || true`

| Rule | Action |
|---|---|
| Turn timeout (3 turns) | On re-spawn: `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event respawn --skill recon --agent "{name}" || true`. Re-spawn with same prompt (max 2 attempts). |
| Proceed with available | After 2 re-spawn attempts: `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event failure --skill recon --agent "{name}" || true`. Proceed with responsive researchers' artifacts. |

### 4. Synthesis

The lead combines researcher findings into leverage-ranked interventions.

**Announce to user**: "Synthesizing {N} researcher findings into leverage-ranked interventions."

1. Collect all researcher findings from messages and `.design/expert-*.json` files via Bash (`python3 -c "import json; ..."`).
2. **Contradiction detection**: Scan for findings from different researchers that recommend opposing actions on the same area. If found, add to `contradictions[]` in recon.json. Do NOT try to resolve via agent messaging — surface both positions for user decision.
3. **Delegation check**: If researchers produced >15 total findings across >3 domains, spawn a single synthesis Task agent via `Task(subagent_type: "general-purpose", model: "sonnet")` to perform ranking. Otherwise, lead synthesizes directly.
4. For each finding, assess:
   - Which of the 7 internal leverage levels (1-7)
   - Effort to implement (trivial/small/medium/large/transformative)
   - Confidence (high/medium/low)
   - Authority required (developer/team/org)
5. Group related findings into interventions (an intervention may combine multiple findings from different researchers).
6. For each intervention, write:
   - A concrete `designGoal` string ready for `/do:design` — if you cannot write a concrete goal, the intervention is too abstract. Demote or split it.
   - `constraints[]` — hard rules from research that design must respect.
   - `wrongDirection` — what pushing this the wrong way looks like (REQUIRED for levels 1-5, optional 6-7).
   - `evidence[]` — references to researcher findings that support this.
7. Rank interventions by composite score (computed by `recon-validate`).
8. **Cap interventions**: Max 5 interventions. Record `additionalFindings` count for transparency.
9. Add `knowledgeGaps[]` — areas where additional information would most improve the analysis. Tacit/inferred findings from codebase-analyst or domain-specialist that lack corroboration from a second researcher MUST go to `knowledgeGaps[]`, not `interventions[]`.
10. **Validate**: Run `python3 $PLAN_CLI recon-validate .design/recon.json`. Fix any validation errors.

### 5. Output

1. **Display to user** — Present ranked interventions:

```
Recon: {area}

Interventions (ranked by leverage):
| # | Intervention | Group | Effort | Confidence | Score |
|---|---|---|---|---|---|
| 1 | {title} | {Abson group} | {effort} | {confidence} | {compositeScore} |
| 2 | {title} | {Abson group} | {effort} | {confidence} | {compositeScore} |

Wrong-direction warnings:
- #{rank}: {wrongDirection}

Contradictions: {count or "none"}
Knowledge gaps: {count or "none"}
Additional findings not shown: {additionalFindings}

To design an intervention: /do:design {designGoal from chosen intervention}
```

2. If contradictions exist, display separately: "Contradiction in {area}: {positionA} vs {positionB}. {userDecisionNeeded}."
3. **Summary**: Run `python3 $PLAN_CLI recon-summary .design/recon.json` and display.

### 6. Reflection

1. Shut down teammates, delete team.
2. Clean up TaskList.
3. **Self-reflection** — Evaluate this recon run:

```bash
echo '{"researchQuality":"<assessment>","leverageAssessmentAccuracy":"<assessment>","scopeDiscipline":"<stayed focused|drifted>","researchersSpawned":N,"findingsCount":N,"interventionsProduced":N,"contradictionsFound":N,"whatWorked":["<item>"],"whatFailed":["<item>"],"doNextTime":["<item>"]}' | python3 $PLAN_CLI reflection-add .design/reflection.jsonl --skill recon --goal "<the investigated area>" --outcome "<completed|partial|failed|aborted>" --goal-achieved <true|false>
python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event skill-complete --skill recon || true
```

On failure: proceed (not blocking).

---

## Output Contract: recon.json (schemaVersion 1)

The lead writes `.design/recon.json` — this is NOT `.design/plan.json`. Recon output is structurally different from a plan (ranked interventions vs decomposed roles).

```json
{
  "schemaVersion": 1,
  "goal": "the investigated area/question",
  "scope": "directories or systems investigated",
  "sources": [
    {
      "name": "researcher-name",
      "artifact": ".design/expert-{name}.json",
      "summary": "what they investigated and key findings"
    }
  ],
  "interventions": [
    {
      "rank": 1,
      "title": "descriptive intervention name",
      "description": "what to change and why",
      "leverageLevel": 5,
      "leverageGroup": "Feedbacks",
      "leverageName": "feedback_loops",
      "designGoal": "ready-to-use goal string for /do:design",
      "evidence": ["finding references from researcher artifacts"],
      "constraints": ["hard rules from research"],
      "wrongDirection": "what pushing this the WRONG way looks like",
      "confidence": "high|medium|low",
      "effort": "trivial|small|medium|large|transformative",
      "authorityRequired": "developer|team|org"
    }
  ],
  "contradictions": [
    {
      "area": "the contested area",
      "positionA": {"researcher": "codebase-analyst", "claim": "what they found"},
      "positionB": {"researcher": "external-researcher", "claim": "what they recommend"},
      "userDecisionNeeded": "what the user must weigh"
    }
  ],
  "knowledgeGaps": ["areas where additional information would most improve the analysis"],
  "additionalFindings": 0,
  "timestamp": "ISO 8601"
}
```

**Required fields per intervention**: title, description, leverageLevel (1-7 int), leverageGroup (Intent|Design|Feedbacks|Parameters), leverageName (one of: paradigm, goals, rules, information_flows, feedback_loops, structure, parameters), designGoal (non-empty string), evidence (array), constraints (array), confidence, effort, authorityRequired.

**Conditionally required**: wrongDirection (required for leverageLevel 1-5, optional for 6-7).

### Analysis Artifacts

Preserved in `.design/` for reference:
- `expert-{name}.json` — per-researcher findings (structured JSON)
- `recon.json` — ranked interventions (archived on next design/recon run)

**Area**: $ARGUMENTS
