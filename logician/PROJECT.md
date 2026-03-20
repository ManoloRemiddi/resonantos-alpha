# Project: The Logician (Mangle Integration)

**Status:** Planning  
**Priority:** High  
**Started:** 2026-02-03  
**Goal:** Add verifiable deductive reasoning to ResonantOS

---

## What This Is

The Logician is the "second brain" of ResonantOS — a deductive reasoning engine that can **prove** things, not just guess them.

**Current state (Oracle only):**
- Claude generates responses
- No verification — we trust the output
- Can hallucinate, be inconsistent, violate rules without knowing

**Future state (Oracle + Logician):**
- Claude generates responses
- Mangle verifies against rules and facts
- Contradictions caught, rules enforced, reasoning traceable

---

## The Technology

**Google Mangle** — open source deductive database
- GitHub: https://github.com/google/mangle
- Datalog-based logic programming
- Go library with gRPC service option
- Nanosecond-to-millisecond query times

---

## Architecture Vision

```
User Request
     ↓
┌─────────────────┐
│ Oracle (Claude) │ ← Creative, probabilistic
│   Generates     │
│   Reasons       │
│   Hypothesizes  │
└────────┬────────┘
         ↓
┌─────────────────┐
│ Semantic Bridge │ ← Translates NL ↔ Logic
│   NL → Facts    │
│   NL → Queries  │
└────────┬────────┘
         ↓
┌─────────────────┐
│    Logician     │ ← Deterministic, provable
│    (Mangle)     │
│   Verifies      │
│   Deduces       │
│   Proves        │
└────────┬────────┘
         ↓
    Verified Response
```

---

## Use Cases

### 1. Constitutional Checks (Shield)

**Before:** Shield scans for patterns (regex) — can miss novel attacks
**After:** Shield has logical rules that are provably enforced

```datalog
% Rule: Actions requiring verification
must_verify(Action) :- 
    action_type(Action, send_email),
    recipient_external(Action).

% Rule: Detect unauthorized actions  
unauthorized(Action) :- 
    must_verify(Action), 
    NOT verified(Action).
```

**Result:** "This action would send external email without verification — BLOCKED"

### 2. Memory Consistency

**Before:** Agent can hold contradictory facts without knowing
**After:** Contradictions are automatically detected

```datalog
% Facts
user_location(user1, rome).
user_location(user1, milan).  % Added later by mistake

% Rule: Detect contradiction
contradiction(user_location, User) :-
    user_location(User, L1),
    user_location(User, L2),
    L1 != L2.
```

**Result:** "Contradiction detected: user1 can't be in Rome AND Milan"

### 3. Agent Permissions

**Before:** Permissions checked by code, can have bugs
**After:** Permissions are logical rules, provably correct

```datalog
% Facts
agent(strategist).
agent(coder).
allowlist(strategist, coder).

% Rule
can_spawn(A, B) :- agent(A), agent(B), allowlist(A, B).

% Query: Can strategist spawn coder?
?- can_spawn(strategist, coder).  % YES, provably
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1)
- [ ] Set up mangle-service (Docker)
- [ ] Create Python gRPC client
- [ ] Test basic queries
- [ ] Document setup process

### Phase 2: Semantic Bridge (Week 2)
- [ ] Design fact schema for ResonantOS
- [ ] Build NL → Mangle translator (Claude-assisted)
- [ ] Test with simple examples

### Phase 3: Integration (Week 3-4)
- [ ] Connect to Shield for constitutional checks
- [ ] Connect to Memory for consistency checks
- [ ] Create agent verification rules

### Phase 4: Production (Week 5+)
- [ ] Performance tuning
- [ ] Error handling
- [ ] Monitoring and logging
- [ ] Documentation

---

## Success Criteria

**We know it's working when:**

1. Shield can PROVE an action violates rules (not just pattern match)
2. Memory contradictions are automatically detected
3. Agent permissions are verifiable
4. Every "blocked" action has a logical explanation
5. Query times < 100ms for typical checks

---

## Files & Resources

- **Deep Research:** `$HOME/clawd/research/MANGLE_DEEP_RESEARCH.md`
- **Mangle Repo:** https://github.com/google/mangle
- **gRPC Service:** https://github.com/burakemir/mangle-service
- **Docs:** https://mangle.readthedocs.io

---

## Questions to Resolve

1. What facts do we store? (user info, agent state, conversation history?)
2. What rules do we enforce? (constitution, permissions, consistency?)
3. How often do we verify? (every action? only risky ones?)
4. Where does Mangle run? (local Docker? separate service?)

---

## Session Log

### 2026-02-03
- Identified Google Mangle as the technology
- Completed deep research (43KB document)
- Documented architecture vision
- Next: Explain expected outcome, then proof-of-concept
