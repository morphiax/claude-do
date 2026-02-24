---
name: research
description: Investigate a topic — decompose into sub-questions, gather evidence from multiple sources, synthesize structured findings.
argument-hint: "<topic> — research question or knowledge gap to investigate"
context: fork
agent: general-purpose
allowed-tools: Read,Glob,Grep,Bash,Task,WebSearch,WebFetch,mcp__sequential-thinking__sequentialthinking
model: claude-sonnet-4-6
satisfies:
  [
    RC-1,
    RC-2,
    RC-3,
    RC-4,
    RC-5,
    RC-6,
    RC-7,
    RC-8,
    RC-9,
    IE-8,
    IE-9,
    IE-13,
    IE-15,
    IE-16,
    VC-1,
    VC-2,
    VC-3,
    VC-4,
    VC-5,
  ]
---

## CLI Setup

Resolve the helper script path at skill start. `scripts/do.py` is a symlink that resolves to `shared/do.py` in the plugin root.

Use the Glob tool to find `scripts/do.py` relative to this SKILL.md, then resolve its absolute path:

```bash
DO=$(python3 -c "import os; print(os.path.realpath('<absolute-path-to-scripts/do.py>'))" )
```

All commands: `python3 $DO <domain> <command> --root .do`


# LOAD STATE [IE-8, IE-9] — deterministic

Execute all loads before any investigation:

1. `python3 $DO memory search --root .do --keyword <topic>` — prior learnings on this topic
2. `python3 $DO research search --root .do --keyword <topic>` — existing research artifacts [RC-6]
3. `python3 $DO reflection list --root .do --lens product` — product observations that may inform research
4. `python3 $DO reflection list --root .do --lens process` — process observations with relevant patterns
5. Read `.do/conventions.md` if exists — project context for scoping investigation
6. `python3 $DO trace add --root .do --json '{"event":"research_start","topic":"<topic>"}'`

Assess existing coverage: if prior research already answers the question with sufficient confidence, report findings and skip investigation. Do not duplicate work.

---

# DECOMPOSITION [RC-7] — creative

Break the topic into discrete sub-questions:

1. Use `mcp__sequential-thinking__sequentialthinking` to decompose:
   - What specific facts are needed?
   - What are the boundaries of the investigation?
   - What would change the recommendation depending on the answer?
   - Which sub-questions have the highest uncertainty?

2. Prioritize sub-questions by:
   - **Impact**: how much does the answer change the recommendation?
   - **Uncertainty**: how confident are we without investigation?
   - **Dependency**: does answering X unlock answering Y?

3. Identify knowledge gaps that cannot be answered from the codebase alone — these require external sources.

---

# HYPOTHESIS GENERATION [RC-8] — creative

BEFORE investigating, generate competing hypotheses:

1. For each high-uncertainty sub-question, state ≥2 plausible answers.
2. For each hypothesis, identify what evidence would confirm or refute it.
3. Record hypotheses — investigation must actively seek disconfirming evidence, not just confirmation.

This prevents anchoring bias: investigating with a conclusion already in mind.

---

# INVESTIGATION [RC-5, RC-6, RC-9] — creative

Three source types, in priority order:

**a) Internal sources** — codebase and project artifacts:

- `Grep` / `Glob` for patterns, implementations, prior decisions
- Read relevant source files, configs, test suites
- Check `.do/` for prior research, memory, reflections

**b) Foundational knowledge** — established patterns and principles:

- Apply known architectural patterns, design principles, failure modes
- Reference industry standards and well-established practices
- Use `mcp__sequential-thinking__sequentialthinking` for structured reasoning about tradeoffs

**c) External sources** — when internal + foundational are insufficient:

- `WebSearch` for documentation, benchmarks, known issues, community consensus
- `WebFetch` for specific pages with detailed technical content
- Prioritize: official documentation > reputable technical sources > community discussions

For EVERY sub-question [RC-9]:

- Seek evidence that DISCONFIRMS the leading hypothesis, not just confirms it
- Record the strongest counter-argument found
- If no disconfirming evidence found, note that explicitly — absence of counter-evidence is itself a data point, not proof

Prior art check [RC-6]: before recommending any approach, search for existing solutions in the codebase and in prior research artifacts. Do not reinvent.

---

# SYNTHESIS [RC-1, RC-2] — creative

Structure findings into a research artifact with these sections:

**Prerequisites**: what must be true for the findings to apply. Runtime versions, dependencies, environmental assumptions.

**Mental models**: core abstractions the reader needs. How does this technology/pattern conceptually work? What are the key invariants?

**Usage patterns**: concrete examples of correct usage. Code patterns, configuration templates, integration approaches. Include the SIMPLEST correct approach, not the most comprehensive.

**Failure patterns**: how this goes wrong. Common misconfigurations, performance traps, security pitfalls, subtle bugs. For each: trigger condition, symptom, fix.

**Production readiness**: maturity, maintenance status, known limitations, scaling characteristics. Is this battle-tested or experimental?

**Confidence levels** [RC-2]:

For each finding, assign confidence:

- `high` — multiple corroborating sources, tested, well-documented
- `medium` — single authoritative source or logical inference from established principles
- `low` — limited evidence, extrapolation, or conflicting sources

Track evidence evolution: if initial hypothesis was wrong, document what changed and why. This prevents repeating the same investigation.

**Recommendation**: direct answer to the original topic. State the recommended approach, alternatives considered, and conditions under which the recommendation would change.

---

# PERSIST [RC-3, IE-8, IE-9] — deterministic

1. **Research store** [RC-3] — persist structured findings:

   ```
   python3 $DO research store --root .do --json RESEARCH_JSON
   ```

   RESEARCH_JSON keys: topic, findings (structured text), confidence (high/medium/low), prerequisites=[], recommendation.

2. **Trace** — record research_complete:

   ```
   python3 $DO trace add --root .do --json TRACE_JSON
   ```

   TRACE_JSON keys: event=research_complete, topic, sub_questions=N, sources_consulted=N.

3. **Reflection** — research process assessment. Required fields: type, outcome, lens=process, urgency=deferred, failures=[], fix_proposals=[]:

   ```
   python3 $DO reflection add --root .do --json REFLECTION_JSON
   ```

   REFLECTION_JSON keys: type=research, outcome=summary, lens=process, urgency=deferred, failures=[], fix_proposals=[].

4. **Memory** — record key learnings for future reuse. Required fields: category=research, keywords, content, source=do-research, importance (3–10):

   ```
   python3 $DO memory add --root .do --json MEMORY_JSON
   ```

   MEMORY_JSON keys: category=research, keywords=[...], content=key-finding, source=do-research, importance=6.

5. **Handoff format**: findings must be consumable by do-design without re-investigation. The research artifact is the handoff — design reads it via `python3 $DO research search`.

6. **Propose updates** [XC-16]:
   - Conventions: note any technical standards discovered
   - Flag topics that need deeper investigation as deferred reflections

---

# VERSION CONTROL [VC-2, VC-3, VC-5]

Commit all changes produced by this research run. Working tree must be clean afterward.

1. Check working tree status: `git status --porcelain`
2. Resolve untracked files:
   - Research artifacts, `.do/` state files → `git add`
   - Generated/environment-specific files → add to `.gitignore`, then `git add .gitignore`
   - Scratch output that should not persist → delete
3. Stage all changes: `git add` relevant files
4. Commit: message summarizing research output (topic, key findings)
5. Verify clean: `git status --porcelain` — must produce no output

If no changes were produced [VC-4]: skip commit.

---

# PROHIBITIONS

- `[RC-4]` MUST NOT produce execution plans — research informs design, does not replace it
- MUST NOT modify source code, configurations, or project artifacts — research is read-only
- MUST NOT satisfy or author spec contracts — that is design's responsibility
