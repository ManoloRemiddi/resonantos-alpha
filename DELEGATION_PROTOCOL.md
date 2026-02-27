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
- [ ] Write TASK.md in the working directory with all of the above
- [ ] If the fix needs data format knowledge, include actual data samples
- [ ] If the fix touches config, include the current config values
- [ ] Reference specific line numbers in source files
- [ ] Include the test command that validates the fix

### 4. SCOPE CONTROL
- [ ] Task changes ≤3 files (if more, break into subtasks)
- [ ] Task adds/modifies ≤100 lines (if more, escalate to Manolo)
- [ ] No architectural decisions delegated (those stay with orchestrator)
- [ ] No speculative "improvements" — fix exactly what's broken

## TASK.md Template

```markdown
# TASK: [Brief title]

## Root Cause
[Exact technical explanation of why it's broken, with evidence]

## Fix
[Exact description of what to change]

## Files to Modify
- `path/to/file.py` line ~N: [what to change]
- `path/to/template.html` line ~N: [what to change]

## Data Context
[Include actual data samples, current config values, API response examples]

## Test Command
```bash
[Exact command that validates the fix — must show different output before/after]
```

## Acceptance Criteria
1. [Specific, testable condition]
2. [Specific, testable condition]

## Out of Scope
- [Things NOT to touch]
```

## Anti-Patterns (What NOT to Do)

| Anti-Pattern | Correct Approach |
|---|---|
| "Investigate and fix" | Do the investigation yourself, specify the fix |
| "Likely root causes to investigate" | Find the root cause, document it |
| "The numbers should be stable" | "Bug: `usage-stats.json` is cumulative (693 calls), not windowed. Fix: filter `pairs.jsonl` by timestamp" |
| TASK.md with 5 possible causes | TASK.md with 1 confirmed cause + exact fix |
| 4-file, 300-line change scope | Break into 2-3 focused tasks |
| "Don't break existing functionality" | "Run this test command to verify no regressions" |

## Post-Delegation

1. Monitor Codex output (first 2 minutes)
2. If it starts exploring files it shouldn't → steer or kill
3. When it reports done → verify test output independently
4. Never forward "done" to Manolo without running the test yourself

## Logician Enforcement

These rules are defined in `logician/rules/coder_rules.mg` and `preparation_rules.mg`.
The orchestrator must satisfy `preparation_rules.mg` before the coder is invoked.
Violations: delegating without root cause analysis, delegating without test criteria, claiming "fixed" without running tests.
