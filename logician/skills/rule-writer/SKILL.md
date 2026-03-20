# Rule Writer Skill — Logician Rule Engineering

> Transform natural-language policy intentions into provable Mangle/Datalog rules.

## When to Use This Skill

- User wants to add a policy rule ("I don't want my agent to...")
- User has a broken rule that needs fixing
- User wants to audit existing rules for quality
- Converting behavioral guidelines into enforceable rules

## The Protocol: 5 Phases

### Phase 0: Intent Recovery (The Pre-Gate)

Before writing any rule, recover **what it's trying to protect against.**

Ask these questions:
1. **What does this rule want to prevent?** (The threat, the risk)
2. **Is that intent still valid?** (If no → delete)
3. **What's the actual attack surface?** (What concretely happens without this rule)
4. **What's the smallest measurable signal?** (The deterministic skeleton)

**Example:**
- Bad rule: `sensitive_pattern(/seed_phrase, "abandon")`
- Recovered intent: "Prevent crypto wallet seed phrases from leaking"
- Attack surface: 12/24 BIP39 words appearing in output
- Measurable signal: 8+ consecutive words from the BIP39 wordlist
- New rule: Full wordlist scanner (deterministic, zero false positives on normal text)

The intent is the invariant. The implementation is replaceable.

### Phase 1: Decomposition

Extract the deterministic skeleton from natural language:

- **Subject**: Which agent/entity?
- **Action**: What operation?
- **Object**: What resource/target?
- **Condition**: Under what circumstances?

If any part requires "understanding" or "judgment" → it's NOT a Logician rule.
Put it in the agent's system prompt (SOUL.md) instead.

### Phase 2: Three-Gate Validation

Every rule MUST pass all three gates. No exceptions.

**Gate 1: Measurable**
Can a machine evaluate this without AI reasoning?
- ✅ `injection_pattern("ignore previous instructions")` — string matching
- ❌ "Block manipulative prompts" — requires understanding

**Gate 2: Binary**  
Does it produce exactly YES or NO?
- ✅ `spawn_allowed(/coder, /orchestrator)` — true or false
- ❌ "Agent is somewhat trusted" — not binary

**Gate 3: Falsifiable**
Can you write a test that SHOULD fail?
- ✅ `can_spawn(/tester, /coder)` → query should return empty
- ❌ A rule that matches everything isn't protecting anything

If a gate fails: explain WHY, suggest a rewrite, or redirect to system prompt.

### Phase 3: Synthesis

Generate valid Mangle syntax + mandatory test pair:

```mangle
# Rule
blocked_model_task(/opus, /heartbeat).

# Test (MUST include both pass and fail)
# PASS: blocked_model_task(/opus, /heartbeat)     → TRUE  ✅
# FAIL: blocked_model_task(/opus, /architecture)   → FALSE ✅  
# FAIL: blocked_model_task(/haiku, /heartbeat)     → FALSE ✅
```

Classify the rule type:
| Type | Pattern | Example |
|------|---------|---------|
| Fact | `predicate(constant).` | `agent(/coder).` |
| Permission | `can_X(agent, resource).` | `can_spawn(/main, /coder).` |
| Block | `blocked_X(agent, resource).` | `blocked_spawn(/coder, /main).` |
| Derived | `result(X) :- condition(X), ...` | `spawn_allowed(F, T) :- ...` |
| Pattern | `type_pattern(category, string).` | `injection_pattern("jailbreak").` |
| Threshold | `limit(resource, number).` | `token_yearly_cap(/rct, 10000).` |

### Phase 4: Integration

1. Check for predicate name conflicts with existing rules
2. Check that all referenced predicates exist
3. Test against the live Logician service:
   ```bash
   ./scripts/logician_ctl.sh query 'your_new_rule(X)'
   ```
4. Add to the appropriate `.mg` file

## Mangle Quick Reference

### Syntax

```mangle
# Facts (ground truth)
agent(/coder).
trust_level(/coder, 3).

# Rules (derived from facts)
spawn_allowed(From, To) :- can_spawn(From, To), !blocked_spawn(From, To).

# Negation (closed-world assumption)
!blocked_spawn(From, To)    # "not blocked" — true if no blocking fact exists

# Variables start with uppercase
agent(X)                     # X matches any agent

# Constants start with /
agent(/coder)                # /coder is a specific value

# Numbers
trust_level(Agent, Level), Level >= 3
```

### Operators
- `,` = AND
- `!` = NOT (negation-as-failure)
- `>=`, `<=`, `>`, `<` = numeric comparison
- `:-` = "if" (head :- body means "head is true if body is true")

### Common Patterns

```mangle
# Authorization chain
can_do(Agent, Action) :-
  has_permission(Agent, Action),
  !is_blocked(Agent, Action),
  trust_level(Agent, Level),
  Level >= required_trust(Action).

# Category-based blocking  
blocked_in_category(Item) :- 
  item_category(Item, Cat),
  blocked_category(Cat).

# Transitive closure (reachability)
reachable(A, B) :- edge(A, B).
reachable(A, C) :- edge(A, B), reachable(B, C).
```

## What This Skill Does NOT Do

- Write system prompt guidelines (different domain — those go in SOUL.md/AGENTS.md)
- Evaluate whether a rule is *strategically* correct (that's the human's job)
- Auto-deploy rules to production (human approval required)
- Modify Shield Gate code (that's implementation, not rule writing)
