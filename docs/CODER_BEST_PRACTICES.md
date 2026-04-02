# AI Coder Best Practices
## Research Summary (Feb 2026)

Sources: Anthropic Engineering, Addy Osmani, community practitioners

---

## The Core Workflow: Plan → Act → Reflect

### 1. PLAN (Before Any Code)

**Why:** LLMs that dive straight into code produce "jumbled messes" — like 10 devs working without talking to each other.

**How:**
- Brainstorm requirements with clarifying questions
- Create a spec or plan document
- Break into small, logical tasks
- Identify what could go wrong (pre-mortem)

> "It's like doing waterfall in 15 minutes — a rapid structured planning phase that makes coding much smoother." — Addy Osmani

### 2. ACT (Small Iterative Chunks)

**Why:** LLMs do best with focused prompts. Large monolithic tasks lead to confusion and inconsistency.

**How:**
- One feature/function at a time
- Commit after each working piece
- Test before moving to next chunk
- Keep environment in "clean state" (mergeable code)

> "Avoid huge leaps. By iterating in small loops, we reduce chance of catastrophic errors and can course-correct quickly."

### 3. REFLECT (Check Your Work)

**Why:** Agents tend to declare "done" prematurely without proper verification.

**How:**
- Summarize what was done and why
- Run end-to-end tests (not just unit tests)
- Ask: "Does this actually work from user perspective?"
- Document what worked, what didn't, what's next

---

## Blindspot Prevention Techniques

### Pre-Mortem
Before implementing, ask:
- What could go wrong?
- What assumptions am I making?
- What edge cases exist?
- What dependencies might break?

### Feature Checklist
Anthropic's approach: explicit pass/fail for each feature
```json
{
  "description": "User can reset password",
  "steps": ["Click forgot password", "Enter email", "Receive link"],
  "passes": false
}
```
Only mark `passes: true` after end-to-end verification.

### Rubber Duck / Explain Step
Before coding, explain your approach as if to someone else:
- What am I building?
- Why this approach?
- What's the expected behavior?
- How will I know it works?

### Context Verification
Before starting, verify you have:
- [ ] Clear problem statement (WHY)
- [ ] Concrete deliverables (WHAT)
- [ ] Relevant code context
- [ ] Known constraints/pitfalls
- [ ] Success criteria

---

## Common Failure Modes (Avoid These)

| Failure | Symptom | Prevention |
|---------|---------|------------|
| One-shotting | Tries to build everything at once | Break into small tasks |
| Premature completion | Declares "done" without testing | End-to-end verification |
| Context loss | Forgets what was decided/built | Commit frequently, document progress |
| Assumption drift | Guesses intent instead of asking | Context verification protocol |
| Over-engineering | Adds complexity not requested | Stay focused on spec |
| Silent breaking | Changes break other features | Run full test suite |

---

## The Protocol (Checklist)

### Before Coding
```
□ Do I understand the WHY? (problem being solved)
□ Do I know the WHAT? (deliverables)
□ Have I seen the HOW? (if approach was discussed)
□ Do I have CONTEXT? (related code, constraints)
□ Can I explain the plan? (rubber duck test)
□ What could go wrong? (pre-mortem)
```

### During Coding
```
□ One feature at a time
□ Test each piece before moving on
□ Commit frequently with clear messages
□ Keep code in mergeable state
□ Document non-obvious decisions
```

### After Coding
```
□ Does it actually work? (end-to-end test)
□ Did I break anything else? (regression check)
□ Is the code clean and documented?
□ What did I learn? (reflection)
□ What's next? (handoff notes)
```

---

## Testing Requirements

**Critical insight from Anthropic:**
> "Claude tended to make code changes and do testing with unit tests, but would fail to recognize that the feature didn't work end-to-end."

**Rules:**
1. Unit tests are necessary but not sufficient
2. Test as a user would (end-to-end)
3. Verify the happy path works completely
4. Check error handling and edge cases
5. Don't mark "done" until you've seen it work

---

## Context Management

### What to Include
- Relevant source files
- API docs for libraries being used
- Constraints and known pitfalls
- Examples of desired patterns
- What NOT to do (anti-patterns to avoid)

### What to Exclude
- Unrelated code (wastes tokens)
- Outdated documentation
- Irrelevant history

> "Don't make the AI operate on partial information. If a bug fix requires understanding four modules, show it those four modules."

---

## Version Control Discipline

1. **Commit small and often** — each working piece
2. **Descriptive messages** — explain what and why
3. **Tag AI branches** — e.g., `agent/feature-name`
4. **Never commit broken state** — keep main stable
5. **Review before merge** — human oversight always

---

## Key Quotes

> "The difference between chaos and clarity lies in how you direct your agent, not just what you ask it to do."

> "Treat the agent as a capable junior developer — efficient, but always in need of supervision and validation."

> "AI coding assistants are not replacing developers; they are amplifying human capability."

> "The clearer your structure and communication, the better your agent performs."

---

## References

- [Anthropic: Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [Addy Osmani: My LLM Coding Workflow](https://addyosmani.com/blog/ai-coding-workflow/)
- [Plan-Act-Reflect Framework](https://medium.com/@elisheba.t.anderson/building-with-ai-coding-agents-best-practices-for-agent-workflows-be1d7095901b)
