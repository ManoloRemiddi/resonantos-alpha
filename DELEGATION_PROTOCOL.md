# DELEGATION_PROTOCOL.md — Orchestrator → Coder Handoff

**Read this before EVERY delegation to Codex or any coding agent.**

## The Failure Mode (Why This Exists)

On 2026-02-24, the orchestrator delegated a dashboard fix to Codex twice. Both times:
- TASK.md was vague on data formats and architecture
- No SSoT docs were referenced or included
- No data flow analysis was done before delegation
- Codex made 341 lines of speculative changes, broke the feature worse
- The orchestrator treated delegation as "throw task over the wall"

**Root cause:** Orchestrator was lazy. Delegation is not "write a TASK.md and hope." It's a structured handoff requiring the orchestrator to do the architectural work first.

## Task Tiers

Every delegation uses TASK.md. The required sections scale with task scope:

| Tier | Scope | Required Sections |
|---|---|---|
| **Small** | ≤3 files, ≤100 lines, simple fix | Root Cause, Fix, Files to Modify, Test Command (4 sections) |
| **Mid** | >3 files OR >100 lines | Small + Acceptance Criteria, Out of Scope, Data Context, Preferences, Escalation Triggers (9 sections) |
| **Large/Design** | New system, protocol, architecture, new extension | Mid + Constraints, Context (11 sections) |

**Tier detection is automatic.** The Delegation Gate reads TASK.md and detects scope from:
1. Explicit declaration: `## Scope: mid` (highest priority)
2. Keywords in title: "new system", "architecture", "new protocol" → large
3. File count in Files to Modify: >3 files → mid
4. Line count hints: >100 lines mentioned → mid

**Default on ambiguity: mid** (safer to over-validate than under-validate).

## Mandatory Pre-Delegation Checklist

Before spawning Codex, complete ALL of these:

### 1. UNDERSTAND THE SYSTEM (5-10 min)
- [ ] Read the relevant source code (not just grep — read the function)
- [ ] Trace the complete data flow (input → processing → output → UI)
- [ ] Identify the root cause with evidence (not assumption)
- [ ] Read the relevant SSoT doc (L1 for architecture, L2 for project context)

### 2. SPECIFY THE FIX (5 min)
- [ ] Document the exact root cause (not symptoms)
- [ ] Specify the exact fix approach (not "investigate and fix")
- [ ] List the exact files to modify and what changes are needed
- [ ] Define acceptance criteria with testable commands
- [ ] Include sample data (actual values, not descriptions)

### 3. PREPARE THE CONTEXT (5 min)
- [ ] Write TASK.md in the working directory with all required sections for the tier
- [ ] If the fix needs data format knowledge, include actual data samples
- [ ] If the fix touches config, include the current config values
- [ ] Reference specific line numbers in source files
- [ ] Include the test command that validates the fix

### 4. SCOPE CONTROL
- [ ] Task changes ≤3 files for small tier (if more, it's mid or break into subtasks)
- [ ] Task adds/modifies ≤100 lines for small tier (if more, it's mid)
- [ ] No architectural decisions delegated (those stay with orchestrator)
- [ ] No speculative "improvements" — fix exactly what's broken

## TASK.md Templates

### Small Tier (≤3 files, ≤100 lines)

```markdown
# TASK: [Brief title]

## Root Cause
[Exact technical explanation of why it's broken, with evidence]

## Fix
[Exact description of what to change]

## Files to Modify
- `path/to/file.py` line ~N: [what to change]

## Test Command
\`\`\`bash
[Exact command that validates the fix]
\`\`\`
```

### Mid Tier (>3 files OR >100 lines)

```markdown
# TASK: [Brief title]

## Root Cause
[Exact technical explanation with evidence]

## Fix
[Exact description of what to change]

## Files to Modify
- `path/to/file1.py` line ~N: [what to change]
- `path/to/file2.py` line ~N: [what to change]
- `path/to/file3.py` line ~N: [what to change]
- `path/to/file4.py` line ~N: [what to change]

## Data Context
[Actual data samples, config values, API response examples — real values, not descriptions.
The coding agent should be able to understand the data format without reading source files.]

## Test Command
\`\`\`bash
[Exact command that validates the fix]
\`\`\`

## Acceptance Criteria
1. [Specific, testable condition]
2. [Specific, testable condition]
3. [Specific, testable condition]

## Preferences
- [When multiple valid approaches exist, which to favour and why]
- [Performance vs readability trade-off preference]
- [Library vs custom implementation preference]

## Escalation Triggers
- Stop and report back if: [you find more than 1 possible root cause]
- Stop and report back if: [changes would exceed the scoped files]
- Stop and report back if: [tests fail in unexpected ways]

## Out of Scope
- [Things NOT to touch]
- [Existing features to preserve]
```

### Large/Design Tier (new system, protocol, architecture)

```markdown
# TASK: [Brief title]
## Scope: large

## Root Cause
[Exact technical explanation with evidence]

## Context
[Architecture overview, data flow, environment details, relevant SSoT references.
Must be self-contained — the coding agent should not need to ask clarifying questions.]

## Fix
[Exact description of what to change]

## Data Context
[Actual data samples, config values, API response examples — real values, not descriptions.
Include current state AND expected state after fix.]

## Files to Modify
- `path/to/file1.py` line ~N: [what to change]
- `path/to/file2.py` line ~N: [what to change]

## Test Command
\`\`\`bash
[Exact command that validates the fix]
\`\`\`

## Acceptance Criteria
1. [Specific, testable condition]
2. [Specific, testable condition]
3. [Specific, testable condition]

## Preferences
- [When multiple valid approaches exist, which to favour and why]
- [Architectural style preferences (functional vs OOP, etc.)]
- [Performance vs readability vs maintainability hierarchy]

## Escalation Triggers
- Stop and report back if: [you discover the root cause differs from what's specified]
- Stop and report back if: [changes would exceed the scoped files]
- Stop and report back if: [you need to modify shared infrastructure]
- Stop and report back if: [tests fail in unexpected ways]

## Constraints
- [Must-not rules — hard boundaries]
- [Performance limits — max response time, max memory]
- [Compatibility requirements — what must not break]

## Out of Scope
- [Things NOT to touch]
- [Architectural decisions NOT to make]
```

## Section Requirements (Enforced by Delegation Gate)

| Section | Tier | Min Chars | What It Must Contain |
|---|---|---|---|
| Root Cause | all | 50 | Technical explanation with evidence, not symptoms |
| Fix | all | 30 | Exact change description, not "investigate and fix" |
| Files to Modify | all | 10 | Explicit file list, max 5 files |
| Test Command | all | 20 | Runnable command in code block |
| Acceptance Criteria | mid+ | 30 | ≥3 verifiable conditions |
| Out of Scope | mid+ | 15 | Explicit exclusions |
| Data Context | mid+ | 40 | Real data samples, config values, API responses |
| Preferences | mid+ | 20 | Approach priority when multiple valid options exist |
| Escalation Triggers | mid+ | 20 | Conditions to stop and report back |
| Constraints | large | 20 | Hard limits and must-not rules |
| Context | large | 50 | Self-contained architecture/environment description |

## Anti-Patterns (What NOT to Do)

| Anti-Pattern | Correct Approach |
|---|---|
| "Investigate and fix" | Do the investigation yourself, specify the fix |
| "Likely root causes to investigate" | Find the root cause, document it |
| "The numbers should be stable" | "Bug: `usage-stats.json` is cumulative (693 calls), not windowed. Fix: filter `pairs.jsonl` by timestamp" |
| TASK.md with 5 possible causes | TASK.md with 1 confirmed cause + exact fix |
| 4-file, 300-line change scope | Break into 2-3 focused tasks |
| "Don't break existing functionality" | "Run this test command to verify no regressions" |
| Missing Out of Scope for mid task | Explicitly list what to preserve |
| No Constraints for large task | Define hard limits before the agent starts |

## Vague Language Detection (Enforced by Gate)

The following phrases in Root Cause are auto-blocked:
- "investigate and fix"
- "likely cause" / "probably the"
- "might be caused" / "should be fixed"
- "look into" / "check if"
- "try to fix" / "not sure"
- "somehow" / "maybe"

## Post-Delegation

1. Monitor Codex output (first 2 minutes)
2. If it starts exploring files it shouldn't → steer or kill
3. When it reports done → verify test output independently
4. Never forward "done" to Manolo without running the test yourself

## Logician Enforcement

These rules are defined in `logician/rules/coder_rules.mg` and `preparation_rules.mg`.
The orchestrator must satisfy `preparation_rules.mg` before the coder is invoked.
Violations: delegating without root cause analysis, delegating without test criteria, claiming "fixed" without running tests.
