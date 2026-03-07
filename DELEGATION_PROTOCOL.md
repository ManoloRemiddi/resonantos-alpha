# DELEGATION_PROTOCOL.md — Orchestrator → Agent Handoff (V2)

**Version:** 2.0  
**Based on:** Research + Self-Debate (2026-03-07)  
**Read this before EVERY delegation to Codex or Perplexity.**

---

## Core Philosophy

Delegation is NOT "throw a task over the wall and hope." It's a structured handoff requiring the orchestrator to do the architectural work first, then guide the agent through Plan → Execute → Verify.

---

## The Two Checkpoints (Mandatory)

Every task MUST have these two checkpoints:

| Checkpoint | What Agent Does | Human Does |
|------------|----------------|-----------|
| **1. Plan** | Inspect files, confirm understanding, show implementation plan | Review plan, approve or correct |
| **2. Verify** | Run tests, verify no regressions, prove it works | Final approval |

**No task proceeds past Checkpoint 1 without human approval.**

---

## TASK.md Templates

### For Codex (Coding Tasks)

```markdown
# Task Overview
- Type: [bugfix / feature / refactor / docs]
- Goal: [single-sentence outcome]

# Problem Statement (WHY)
- What problem are we solving: [description]
- Why it matters: [business/technical reason]
- Success looks like: [what good outcome means]

# Context
- Codebase: ResonantOS (Python/Flask backend, JS frontend, OpenClaw, SQLite, Ollama)
- Relevant areas: [specific file paths - max 5 files]
- Architecture: [how this component works, any data flows]

# Current Behavior
- What happens now: [description with error messages/logs if bug]
- Expected behavior: [description]
- Reproduction steps (for bugs):
  1. [CLI/UI step]
  2. [...]

# Constraints
- Keep: [APIs/routes/DB schema that must remain compatible]
- Do NOT: [e.g., new dependencies, change existing behavior]
- Performance: [e.g., <200ms query time]
- Security: [rules from Logician]

# Checkpoints
## Checkpoint 1: Plan
- [ ] Inspect relevant files
- [ ] Confirm understanding of problem
- [ ] Show implementation plan:
  1. [first step]
  2. [second step]
  3. [third step]
- [ ] WAIT for human approval before proceeding

## Checkpoint 2: Verify
- [ ] Run existing tests: `COMMAND`
- [ ] Run new tests: `COMMAND`
- [ ] Manual verification: [UI/action to check]
- [ ] Show test output
- [ ] Confirm no regressions

# Acceptance Criteria
- [ ] Test `X` passes
- [ ] Test `Y` passes  
- [ ] Manual check: [specific UI behavior]
- [ ] No regressions in [existing tests]
```

### For Perplexity (Research Tasks)

```markdown
# Research Context
- Decision this informs: [what decision this research supports]
- Current status: [what we've already tried/implemented]
- Why we need this: [problem we're solving]

# Question
[Precise research question - one sentence]

# Scope
- Focus: [topic]
- Stack: [Python/Flask/OpenClaw/SQLite/Ollama]
- Timeframe: [e.g., as of 2026]
- Non-goals: [what to explicitly ignore]

# Evidence Rules
- Prefer: [official docs, technical blogs, academic papers]
- Min sources: [2 per major claim]
- Must cite: [each claim with source]

# Checkpoints
## Checkpoint 1: Plan
- [ ] Show search/coverage plan
- [ ] List sources to consult
- [ ] WAIT for human approval

## Checkpoint 2: Verify
- [ ] Summarize findings
- [ ] Show sources cited
- [ ] Address gaps/uncertainties

# Output Format
1) 5-7 bullet key takeaways
2) Table: Claim | Evidence | Source | Confidence
3) Best practices / patterns
4) Open questions
```

---

## Tier System (Unchanged)

| Tier | Scope | Checkpoints |
|------|-------|-------------|
| Small | ≤3 files, ≤100 lines | 2 (Plan + Verify) |
| Mid | >3 files OR >100 lines | 2 (Plan + Verify) |
| Large | New system/architecture | 2 + more detailed Plan |

---

## Pre-Delegation Checklist

Before spawning the agent, complete ALL of these:

### 1. Understand (5-10 min)
- [ ] Read the relevant source code (not just grep)
- [ ] Trace data flow (input → processing → output → UI)
- [ ] Identify root cause with evidence
- [ ] Read relevant SSoT docs

### 2. Specify (5 min)
- [ ] Write Problem Statement (why this matters)
- [ ] Document exact fix approach
- [ ] List files + line numbers
- [ ] Define acceptance criteria

### 3. Prepare TASK.md
- [ ] Use the template above
- [ ] Include exact commands for testing
- [ ] Set Checkpoint 1: Plan phase
- [ ] Set Checkpoint 2: Verify phase

### 4. Verify (Post-Delegation)
- [ ] Review Checkpoint 1 plan before approving
- [ ] Run test commands yourself after Checkpoint 2
- [ ] Never tell human "done" without running verification

---

## Anti-Patterns (Auto-Blocked)

| ❌ Bad | ✅ Good |
|--------|---------|
| "Investigate and fix" | Do investigation yourself, specify exact fix |
| "Likely cause" | 1 confirmed cause + evidence |
| No checkpoints | Plan → Verify always |
| Codex reports "done" without test output | Must show test results |
| Missing "why" | Problem Statement section |

---

## Vague Language Detection

Blocked phrases:
- "investigate and fix"
- "likely cause" / "probably"
- "might be" / "should be fixed"
- "try to fix" / "not sure"
- "somehow" / "maybe"

---

## Enforcement

These rules are enforced by Logician:
- `coder_rules.mg` - Codex behavior rules
- `preparation_rules.mg` - Pre-delegation requirements
- Violations block delegation until fixed
