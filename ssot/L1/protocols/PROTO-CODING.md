# PROTO-CODING — Code Implementation Protocol

> **Trigger keywords:** code, implement, build, fix bug, refactor, create feature, write code
> **Level:** L1(P) — Protocol
> **Enforcement:** R-Awareness injection

---

## Rule (ABSOLUTE)

**Delegate ALL implementation to OpenAI Codex CLI.** You are the orchestrator, not the coder.

## Decision Tree

```
Task involves code changes?
│
├─ Trivial one-liner? (single sed, one config value, rename)
│  └─ YES → Do it directly. STOP.
│
├─ Anything else (routes, templates, integrations, multi-file, logic)
│  └─ MUST delegate to Codex. Continue below.
│
└─ "I'll just quickly..."
   └─ NO. Delegate. You need to stay free for Manolo.
```

## Delegation Procedure

1. **Write TASK.md** in the target repo with:
   - What to build/fix
   - Acceptance criteria
   - Files likely involved
   - Constraints (don't touch X, must work with Y)
2. **Spawn Codex:** Use coding-agent skill
3. **Review output** when complete
4. **Test** before reporting (Verification Protocol)

## NEVER Do

- ❌ Write routes, templates, or integration code yourself
- ❌ Use Opus-based coder sub-agents (Codex produces better results)
- ❌ Get buried in implementation (you become unreachable to Manolo)
- ❌ Claim "fixed" without testing

## WHY This Protocol Exists

2026-02-21: Did a chatbot UI audit myself instead of delegating. Got buried in code, couldn't respond to Manolo. The orchestrator must stay free.
