---
name: research
description: "Research a technology, pattern, or area and produce a structured knowledge artifact with actionable recommendations."
argument-hint: "<topic or question to research>"
---

# Research

Investigate a topic and produce a knowledge artifact in `.design/research.json` with structured knowledge sections and actionable recommendations. **This skill researches and synthesizes — it does NOT design or execute.**

**PROTOCOL REQUIREMENT: Do NOT answer the goal directly. Your FIRST action after reading the topic MUST be the pre-flight check. Follow the Flow step-by-step.**

**CRITICAL BOUNDARY: Research captures WHAT is known and WHY it matters. It does NOT determine HOW to implement — that is `/do:design`'s job. Research produces `.design/research.json`, NOT `.design/plan.json`. If you start thinking about role decomposition or acceptance criteria, you have crossed into design territory — stop and refocus on knowledge synthesis.**

**Do NOT use `EnterPlanMode`** — this skill IS the plan.

**Lead boundaries**: Use only `TeamCreate`, `TeamDelete`, `TaskCreate`, `TaskUpdate`, `TaskList`, `SendMessage`, `Task`, `AskUserQuestion`, and `Bash` (for `python3 $PLAN_CLI`, cleanup, verification). Project metadata (CLAUDE.md, package.json, README) allowed via Bash. **Never use Read, Grep, Glob, Edit, Write, LSP, WebFetch, WebSearch, or MCP tools on project source files.** The lead orchestrates — researchers investigate.

**No polling**: Messages auto-deliver automatically. Never use `sleep`, loops, or Bash waits.

---

## Clarification Protocol

| ASK (`AskUserQuestion`) when | SKIP when |
|---|---|
| Topic spans multiple unrelated technologies | Topic maps to a clear domain or concern |
| Research scope is unbounded with no focus | Question is specific enough to guide research |
| User intent unclear (evaluate vs audit vs migrate) | Any reasonable interpretation leads to similar research |

Research tolerates vague inputs better than design. "Should we adopt GraphQL?" is valid. "Research things" with no context is not.

### Script Setup

Resolve plugin root (containing `.claude-plugin/`). All script calls: `python3 $PLAN_CLI <command> [args]` via Bash. JSON output: `{"ok": true/false, ...}`.

```bash
PLAN_CLI={plugin_root}/skills/research/scripts/plan.py
TEAM_NAME=$(python3 $PLAN_CLI team-name research | python3 -c "import sys,json;print(json.load(sys.stdin)['teamName'])")
SESSION_ID=$TEAM_NAME
```

### Trace Emission

After each agent lifecycle event: `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event {event} --skill research [--agent "{name}"] || true`. Events: skill-start, skill-complete, spawn, completion, failure, respawn. Failures are non-blocking (`|| true`).

---

## Knowledge Sections

Five structured knowledge domains that together constitute a complete research artifact:

| Section | What it captures | Design handoff |
|---|---|---|
| `prerequisites` | What must be true before adopting this. Technical, organizational, invisible curriculum. Concept dependency graph ("understand A before B before C"). | role `constraints[]` |
| `mentalModels` | Conceptual framework for thinking correctly. Corrects misconceptions. | `context.conventions[]` |
| `usagePatterns` | Proven patterns that work. What "good" looks like in practice. Evolution paths ("start with X, refactor to Y as you scale"). | `expertContext[]` for workers |
| `failurePatterns` | How this breaks in production. Anti-patterns, post-mortem sourced where possible. | `constraints[]` and `rollbackTriggers[]` |
| `productionReadiness` | Operational concerns: observability, scaling, security, operational overhead. Team adoption factors: learning timeline, doc quality, community support. | `acceptanceCriteria[]` checks |

Researchers tag each finding with which section(s) it informs. Lead assembles pre-tagged findings during synthesis — no reclassification needed.

---

## Flow

### 1. Pre-flight

1. **Lifecycle context**: Run `python3 $PLAN_CLI plan-health-summary .design` and display to user: "Recent runs: {reflection summaries}." Skip if all fields empty. Then: `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event skill-start --skill research || true`
2. **Check for ambiguity**: If the topic has multiple valid interpretations per the Clarification Protocol, use `AskUserQuestion` before proceeding.
3. **Check existing research**: `ls .design/research.json`. If exists, ask user: "Existing research output found. Overwrite?" If declined, stop.
4. **Archive stale artifacts**: `python3 $PLAN_CLI archive .design`

### 2. Scope Assessment

1. Read the topic. Scan project metadata (CLAUDE.md, package.json, README) via Bash to understand stack and context.
2. Set research depth: surface (quick scan, high-confidence findings only), standard (thorough, default), or deep (exhaustive + production signals). Infer from user phrasing or ask if unclear.
3. Select team — always spawn the full research team: 1 codebase-analyst + 1 external-researcher + 1 domain-specialist. Research is inherently exploratory — external research is always valuable for grounding knowledge in prior art and production reality.
4. **Announce to user**: "Research: investigating '{topic}'. Depth: {depth}. Spawning 3 researchers (codebase-analyst, external-researcher, domain-specialist)."

### 3. Research

Create the team and spawn researchers in parallel.

1. `TeamDelete(team_name: $TEAM_NAME)` (ignore errors), `TeamCreate(team_name: $TEAM_NAME)`. If TeamCreate fails, tell user Agent Teams is required and stop.
2. **TeamCreate health check**: Verify team is reachable. If verification fails, `TeamDelete`, then retry `TeamCreate` once. If retry fails, abort with clear error message.
3. **Memory injection**: Run `python3 $PLAN_CLI memory-search .design/memory.jsonl --goal "{topic}" --keywords "{relevant keywords}"`. If `ok: false` or no memories, proceed without injection. Otherwise inject top 3-5 into researcher prompts. **Show user**: "Memory: injecting {count} past learnings — {keyword summaries}."
4. `TaskCreate` for each researcher.
5. Spawn researchers as teammates using the Task tool. For each researcher:
   - Before Task call: `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event spawn --skill research --agent "{researcher-name}" || true`
   - Use Task with `team_name: $TEAM_NAME`, `name: "{researcher-name}"`, and `model: "sonnet"`.
   - Include scope bounds: "Focus your investigation on {directories/areas}. Do not explore unrelated areas."
   - Inject relevant memories if available.

**Researcher Prompts by Type**:

**Codebase Analyst** — Internal structure, patterns, debt, dependencies.
- **Tools granted**: Read, Grep, Glob, Bash (for git log, build/test commands, dependency analysis).
- **Tools denied**: Edit, Write, WebSearch, WebFetch (no external research — that is the external-researcher's job).
- Focus: hotspot analysis (git churn x complexity), change coupling, dependency analysis, architectural patterns, technical debt indicators.
- Git hotspot heuristic: `git log --format=format: --name-only --since=12.month | sort | uniq -c | sort -nr | head -20`
- Report what EXISTS — seek both failure signals AND working constraints. What breaks? What does the team NOT violate by convention?
- Describe root causes, not symptoms — "file X is slow" is a symptom; "file X is slow because it has no index" is a cause.
- **Invisible curriculum**: Surface tacit constraints you can infer from code evidence — patterns that appear consistently with no doc explanation, anti-patterns conspicuously absent, dependencies avoided despite obvious utility. Map to researchGaps if lacking corroboration. Do NOT speculate about team knowledge not evidenced in the codebase.
- **Calibration** — Bad: "The auth module has complex code. Section: failurePatterns. Evidence: it is hard to understand." Good: "auth.js has 340 churn commits in 12 months (git log) with 0 test coverage. Unhandled error on line 87 silently swallows JWT validation failures. Section: failurePatterns. Evidence: `git log --since=12.month auth.js | wc -l = 340`; no test files match `auth*.test.js`."
- Tag each finding with sections[] from: prerequisites, mentalModels, usagePatterns, failurePatterns, productionReadiness.

**External Researcher** — Literature, frameworks, best practices, post-mortems, ecosystem solutions.
- **Tools granted**: WebSearch, WebFetch, Read (for project context files only).
- **Tools denied**: Edit, Write, Grep, Glob (no codebase exploration — that is the analyst's job).
- Focus: production signals, post-mortem sourcing, ecosystem reality, proven patterns from literature. Explicitly seek "intended use case vs how people actually use it" — the gap between marketing/docs and production reality.
- Cite sources with URLs. Note confidence and recency of sources.
- **Source priority** (highest to lowest): (1) Production post-mortems and incident reports. (2) GitHub issues, RFCs, migration guides with real adoption data. (3) Deep-dive engineering blogs with benchmarks. (4) Official documentation and tutorials. (5) Community Q&A and discussions. Always state the source tier and recency.
- Cite specific precedent, not general best practice — name the exact source, version, and why it applies, not just the recommendation.
- **Do NOT claim tacit knowledge about this codebase**; if literature documents a common undocumented pitfall, report it as unconfirmed for this codebase and place in researchGaps.
- **Calibration** — Bad: "React Query is good for server state. Section: usagePatterns. Source: React Query docs." Good: "Vercel engineering post-mortem (2023) identified stale-time misconfiguration as primary cause of 40% cache invalidation overhead. Correct default: staleTime=0 causes excessive refetch; staleTime=Infinity causes stale UIs. Section: failurePatterns. Source: vercel.com/blog/... (tier 1 — production incident report, 2023)."
- **Calibration (prerequisites)** — Bad: "You need to know JavaScript and async patterns." Good: "Critical prerequisite: JavaScript event loop fundamentals — understanding why `setTimeout(() => console.log('B'), 0)` executes after synchronous code. If this surprises you, study the event loop before proceeding. Common failure: developers skip understanding promises and write `async function getData() { fetch(url); return data }` wondering why `data` is undefined. Root cause: missing `await` because promises are lazy. Section: prerequisites."
- Tag each finding with sections[] from: prerequisites, mentalModels, usagePatterns, failurePatterns, productionReadiness.

**Domain Specialist** — Security, performance, UX, data, or other domain lens (context-dependent).
- **Tools granted**: Read, Grep, Glob, WebSearch, WebFetch, Bash (for running project commands).
- **Tools denied**: Edit, Write (researchers report findings, never modify code).
- Focus: domain-specific analysis of the topic under investigation. Apply your domain lens to THIS specific codebase, not in general — findings must reference concrete evidence from the code or production, not domain theory alone.
- **Invisible curriculum**: Identify assumed-but-unstated prerequisites visible in the codebase — domain-specific patterns the code follows implicitly, or anti-patterns conspicuously absent. Map to researchGaps if lacking documentation confirmation.
- **Calibration** — Bad: "The system should use rate limiting for security. Section: productionReadiness. Evidence: general best practice." Good: "API routes in routes/api/ lack per-user rate limiting — only global IP-based throttling exists (express-rate-limit with windowMs: 15m). OWASP API Security Top 10 (2023) lists broken object-level authorization as #1 risk; per-user limits are the mitigation. Section: productionReadiness. Evidence: `grep -r 'rateLimit' routes/` shows single global middleware with no user-scoped limits."
- Tag each finding with sections[] from: prerequisites, mentalModels, usagePatterns, failurePatterns, productionReadiness.

**All researcher prompts MUST include**:

**Minimum research thresholds** (enforced during synthesis — researchers should aim to exceed):
- At least 3 production post-mortems, "lessons learned," or migration-away stories for failure patterns
- At least 5 common beginner mistakes identified across all researchers combined
- Performance claims must include real numbers (latency in ms, throughput in req/s, memory in MB) — "fast" or "scalable" without numbers is not a finding

**Research quality guardrails (all researchers):**

| DO | DON'T |
|---|---|
| Cite production post-mortems for failure patterns (minimum 3 across team) | Infer failure modes from documentation alone |
| State source tier and date for every technical claim | Assert recency without evidence |
| Surface what experts know but docs omit (invisible curriculum) | Repeat what official docs already say |
| Separate confirmed-in-this-codebase from literature findings | Conflate external best practice with local reality |
| Tag each finding with which knowledge sections it informs | Produce untagged findings lists for the lead to classify |
| Preserve worked examples, concrete demonstrations, and prompt patterns VERBATIM | Summarize examples into abstract descriptions |
| Include the actual content that makes a technique reproducible | Describe what something does without showing how |
| Quantify performance claims with real numbers (ms, req/s, MB, %) | Say "fast", "scalable", or "performant" without measurements |
| Document "intended use" vs "how people actually use it" gaps | Present marketing claims as production reality |

**Verbatim preservation rule**: When reference materials, prompts, agent definitions, or documentation contain worked examples, concrete demonstrations, structural templates, process steps, or prompt engineering patterns — include them VERBATIM in your findings as a `verbatim` field. These are the materials that make the difference between understanding a concept abstractly and being able to reproduce it. Summarizing "there are 3 examples of cascades" loses the teaching value; including the actual examples preserves it. This applies to: example inputs/outputs, step-by-step processes, decision tables, prompt structures, configuration templates, schema patterns, and any content where the specific wording or structure IS the value.

- "Save your complete findings to `.design/expert-{name}.json` as structured JSON."
- "Then SendMessage to the lead with a summary."
- "For each finding include: area, observation, evidence, sections (array from: prerequisites/mentalModels/usagePatterns/failurePatterns/productionReadiness), confidence (high/medium/low), effort (trivial/small/medium/large/transformative). If the finding contains worked examples, templates, process steps, or prompt patterns from reference materials, include a `verbatim` field with the actual content."

6. **Researcher liveness pipeline**: Track completion: (a) SendMessage received AND (b) artifact file exists (`ls .design/expert-{name}.json`). **Show user status**: "Researcher progress: {name} done ({M}/{N} complete)." On completion: `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event completion --skill research --agent "{name}" || true`

| Rule | Action |
|---|---|
| Turn timeout (3 turns) | On re-spawn: `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event respawn --skill research --agent "{name}" || true`. Re-spawn with same prompt (max 2 attempts). |
| Proceed with available | After 2 re-spawn attempts: `python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event failure --skill research --agent "{name}" || true`. Proceed with responsive researchers' artifacts. |

### 4. Synthesis

The lead assembles pre-tagged findings into knowledge sections and writes recommendations.

**Announce to user**: "Synthesizing {N} researcher findings into knowledge sections and recommendations."

1. Collect all researcher findings from messages and `.design/expert-*.json` files via Bash (`python3 -c "import json; ..."`).
2. **Delegation check**: If researchers produced >15 total findings across >3 domains, spawn a single synthesis Task agent via `Task(subagent_type: "general-purpose", model: "sonnet")` to perform assembly. Otherwise, lead synthesizes directly.
3. **Assemble sections**: Group findings by their section[] tags into the 5 knowledge sections. For each section, merge corroborating findings, surface contradictions, note gaps.
4. **Contradiction detection**: Scan for findings from different researchers that recommend opposing positions on the same area. If found, add to `contradictions[]` in research.json. Do NOT resolve via agent messaging — surface both positions for user decision.
5. **Write recommendations**: Synthesize all sections into `recommendations[]`. Each recommendation has an `action` (adopt|adapt|investigate|defer|reject) and a concrete `designGoal` for `/do:design` (required when action is adopt or adapt).
6. **Minimum threshold check**: Verify combined findings meet minimums: >=3 production post-mortems/lessons-learned in failurePatterns, >=5 beginner mistakes across all sections. If thresholds not met, add specific gaps to `researchGaps[]` (e.g., "Need 2 more production post-mortems for failure patterns"). Non-blocking — proceed with available findings.
7. **Research gaps**: Tacit or inferred findings lacking corroboration from a second researcher go to `researchGaps[]`, not sections.
8. **Design handoff**: Extract concrete, actionable building blocks from expert artifacts into `designHandoff[]`. This is CRITICAL — design should be able to read research.json alone without re-reading expert artifacts. For each building block, include: `source` (reference-material|codebase-analysis|expert-finding|literature), `element` (what it is — e.g., "symptom table", "expert prompt template", "schema pattern"), `material` (the actual content — verbatim excerpts, structured data, concrete patterns), `usage` (how /do:design should use it — e.g., "inject into expert prompts", "use as acceptance criteria template", "adopt as team composition"). Prioritize: concrete patterns/templates over abstract summaries, verbatim reference material over paraphrased, structural schemas over prose descriptions.

   **Completeness check**: Before finalizing designHandoff, verify against source material:
   - For each reference material mentioned in the user's goal: are worked examples, process steps, decision tables, and prompt patterns preserved verbatim (not just summarized)?
   - For each tool/skill/agent analyzed: is the actual prompt structure or configuration captured (not just a description of what it does)?
   - For each technique recommended for adoption: is there enough concrete material that /do:design could implement it without going back to the original source?
   If any of these checks fail, go back to the expert artifacts' `verbatim` fields or re-read the source to fill the gap.
9. **Validate**: Run `python3 $PLAN_CLI research-validate .design/research.json`. Fix any validation errors.

### 5. Output

1. **Display to user** — Present knowledge sections and recommendations:

```
Research: {topic}
Depth: {depth}

Knowledge Sections:
| Section | Entries | Key insight |
|---|---|---|
| Prerequisites | N | {one-line summary} |
| Mental Models | N | {one-line summary} |
| Usage Patterns | N | {one-line summary} |
| Failure Patterns | N | {one-line summary} |
| Production Readiness | N | {one-line summary} |

Recommendations:
| Action | Scope | Confidence | Effort | Design Goal |
|---|---|---|---|---|
| adopt | {scope} | high | small | {designGoal} |

Contradictions: {count or "none"}
Research gaps: {count or "none"}
Design handoff: {count} building blocks

To act on this research: /do:design {designGoal from primary adopt/adapt recommendation}
```

2. If contradictions exist, display separately: "Contradiction in {area}: {positionA} vs {positionB}. {userDecisionNeeded}."
3. **Summary**: Run `python3 $PLAN_CLI research-summary .design/research.json` and display.

### 6. Reflection

1. Shut down teammates, delete team.
2. Clean up TaskList.
3. **Self-reflection** — Evaluate this research run:

```bash
echo '{"researchQuality":"<assessment>","sectionCoverage":"<complete|partial>","scopeDiscipline":"<stayed focused|drifted>","researchersSpawned":N,"findingsCount":N,"recommendationsProduced":N,"contradictionsFound":N,"whatWorked":["<item>"],"whatFailed":["<item>"],"doNextTime":["<item>"]}' | python3 $PLAN_CLI reflection-add .design/reflection.jsonl --skill research --goal "<the investigated topic>" --outcome "<completed|partial|failed|aborted>" --goal-achieved <true|false>
python3 $PLAN_CLI trace-add .design/trace.jsonl --session-id $SESSION_ID --event skill-complete --skill research || true
```

On failure: proceed (not blocking).

---

## Output Contract: research.json (schemaVersion 1)

The lead writes `.design/research.json` — this is NOT `.design/plan.json`. Research output is structurally different from a plan (knowledge sections + recommendations vs decomposed roles).

```json
{
  "schemaVersion": 1,
  "goal": "the investigated topic/question",
  "scope": "directories or systems investigated",
  "researchDepth": "surface|standard|deep",
  "sources": [
    {
      "name": "researcher-name",
      "artifact": ".design/expert-{name}.json",
      "summary": "what they investigated and key findings"
    }
  ],
  "sections": {
    "prerequisites": {
      "summary": "What must be true before adopting this",
      "technical": ["specific technical prerequisites with version constraints"],
      "organizational": ["team/process prerequisites"],
      "invisibleCurriculum": ["unstated prerequisites experts know but docs omit"],
      "conceptDependencyGraph": ["understand A before B before C — ordered learning path"]
    },
    "mentalModels": {
      "summary": "Conceptual framework for thinking correctly about this",
      "keyPrinciples": ["core principle statements"],
      "tradeoffs": ["explicit tradeoffs the technology acknowledges"],
      "commonMisconceptions": ["what people get wrong"]
    },
    "usagePatterns": {
      "summary": "Proven patterns that work in practice",
      "patterns": [
        {
          "name": "pattern name",
          "description": "what the pattern does",
          "evidence": "source or codebase evidence",
          "confidence": "high|medium|low"
        }
      ],
      "evolutionPaths": [
        {
          "stage": "start|scale|mature",
          "pattern": "pattern name at this stage",
          "trigger": "what signals the transition to next stage"
        }
      ]
    },
    "failurePatterns": {
      "summary": "How this commonly breaks in production",
      "patterns": [
        {
          "name": "pattern name",
          "description": "what goes wrong",
          "trigger": "what causes it",
          "evidence": "source or evidence type",
          "mitigation": "how to prevent or recover",
          "source": "post-mortem|github-issue|docs|inference"
        }
      ]
    },
    "productionReadiness": {
      "summary": "Operational concerns for production deployment",
      "observability": ["what to instrument and how"],
      "operationalPatterns": ["proven operational patterns"],
      "scalingConsiderations": ["scaling-specific concerns"],
      "securityConsiderations": ["security-specific concerns"],
      "teamAdoption": {
        "learningTimeline": "realistic ramp-up: hours for hello world → days for competency → weeks for mastery",
        "documentationQuality": "completeness, accuracy, real-world examples assessment",
        "communitySupport": "response time, answer quality, tribal knowledge availability"
      }
    }
  },
  "recommendations": [
    {
      "action": "adopt|adapt|investigate|defer|reject",
      "scope": "what this recommendation applies to",
      "designGoal": "ready-to-use goal string for /do:design (required if action is adopt or adapt)",
      "reasoning": "why this action",
      "confidence": "high|medium|low",
      "effort": "trivial|small|medium|large|transformative",
      "prerequisites": ["what must be true first"],
      "risks": ["key risks to mitigate"],
      "bestFit": ["use this when you have X, Y, Z requirements"],
      "wrongFit": ["don't use this if you have A, B, C constraints"]
    }
  ],
  "contradictions": [
    {
      "area": "the contested area",
      "positionA": {"researcher": "researcher-name", "claim": "their finding"},
      "positionB": {"researcher": "researcher-name", "claim": "their finding"},
      "userDecisionNeeded": "what the user must weigh"
    }
  ],
  "researchGaps": ["areas where additional research would most improve confidence"],
  "designHandoff": [
    {
      "source": "reference-material|codebase-analysis|expert-finding|literature",
      "element": "what this building block is (e.g., 'symptom table', 'schema pattern', 'expert prompt template')",
      "material": "the actual content — verbatim excerpts, structured data, concrete patterns. Can be string, array, or object.",
      "usage": "how /do:design should use this (e.g., 'inject into expert prompts', 'use as team composition template')"
    }
  ],
  "timestamp": "ISO 8601"
}
```

**Required top-level fields**: schemaVersion (1), goal, sections, recommendations, contradictions.

**Optional top-level fields**: designHandoff (array of building blocks for /do:design consumption).

**Recommendation required fields**: action (adopt|adapt|investigate|defer|reject), scope, reasoning, confidence, effort. designGoal required when action is adopt or adapt. bestFit and wrongFit optional but encouraged for adopt/adapt recommendations.

**Design handoff fields**: source (reference-material|codebase-analysis|expert-finding|literature), element, material, usage. All required per entry.

**Sections**: All 5 section keys should be present. Each section may be sparsely populated for narrow research topics.

### Analysis Artifacts

Preserved in `.design/` for reference:
- `expert-{name}.json` — per-researcher findings (structured JSON)
- `research.json` — knowledge sections and recommendations (archived on next research run)

**Topic**: $ARGUMENTS
