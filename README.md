# do

One skill and one command for collaborative sensemaking.

## What it does

`/do:work` is a unified skill for working on projects through four modes:

| Mode | What it does | When to use |
|------|-------------|-------------|
| Dialogue | Conversation about the project, update understanding | Clarifying intent, evaluating technology, surfacing constraints |
| Planning | Decompose work into testable tasks | Ready to implement something |
| Execution | Build the approved plan via TDD | Plan approved, ready to code |
| Analysis | Technical audit or product challenge | Want an honest assessment |

`/do:release` ships versions — bump, changelog, docs sync, commit, tag, push.

## Project files

The plugin maintains shared understanding in six files under `.do/`:

| File | Purpose | Question it answers |
|------|---------|-------------------|
| `spec.md` | Behaviors, constraints, data contracts | What should it do? |
| `reference.md` | External system models | How does the target system work? |
| `stack.md` | Runtime, frameworks, conventions | What are we building with? |
| `design.md` | Visual identity, aesthetic direction, UI patterns | What should it look like? |
| `decisions.md` | Decision log with rationale | Why did we choose this? |
| `pitfalls.md` | Debugging insights and gotchas | What breaks and how to avoid it? |

## Usage

### Start a new project
```
/do:work what problem are we solving?
```

### Continue working
```
/do:work
```
Reads project files, checks git diffs, picks up where you left off.

### Build something
```
/do:work implement the search feature
```
Plans in read-only mode, gets approval, executes via TDD.

### Audit the stack
```
/do:work audit
```
Technical evaluation against current best practices.

### Challenge assumptions
```
/do:work challenge the onboarding flow
```
Product review from PM perspective.

### Ship a version
```
/do:release minor
```

## How it works

The skill reads project files and git diffs to reconstruct current state, then enters whichever mode the request demands. Modes transition fluidly — discovering a gap during execution pauses into dialogue to propose a project file update, then resumes.

Direction is established in conversation; project files update as part of execution without re-confirming at write time. The only gate is: new direction (behaviors, scope, architecture) needs conversation first. All code changes require plan approval (or the quick-fix path for obvious fixes). The plan is the execution contract — self-sufficient for agents with no prior context.

Project files and code stay in sync bidirectionally. After execution, a sync gate requires enumerating each changed behavior and confirming spec coverage — or explicitly stating nothing drifted. After project file updates, implementation is verified to match. Neither can change without the other.

## Install

```
claude plugin add morphiax/do
```
