# SSOT-L1-PROTO-TOL — Think-Out-Loud Protocol
Updated: {{GENERATED_DATE}}

## Purpose
The Think-Out-Loud (TOL) protocol enables transparent reasoning for complex, ambiguous, or high-stakes decisions.

## When to Use

### Required
- Strategic decisions with >2 viable paths
- Ethical dilemmas or value conflicts
- Novel problems without established patterns
- High-stakes actions (financial, security, public)

### Optional
- Complex technical debugging
- Creative exploration
- Teaching moments (user learning about agent reasoning)

### Never
- Routine operations
- Well-established patterns
- Time-sensitive actions requiring speed

## Protocol Steps

### 1. Frame the Problem
State what you're trying to decide and why it matters.

**Template:**
```
**Decision:** [What needs to be decided]
**Stakes:** [Why this matters / what's at risk]
**Constraints:** [Time, resources, other limits]
```

### 2. List Options
Generate 3-5 distinct approaches.

**Template:**
```
**Option A:** [Description]
- Pros: [Benefits]
- Cons: [Drawbacks]
- Confidence: [Low/Medium/High]

**Option B:** [Description]
- Pros: [Benefits]
- Cons: [Drawbacks]
- Confidence: [Low/Medium/High]

[Continue for all options]
```

### 3. Evaluate Trade-offs
Analyze each option against relevant criteria.

**Template:**
```
**Evaluation criteria:**
1. [Criterion 1]: Which option wins and why?
2. [Criterion 2]: Which option wins and why?
3. [Criterion 3]: Which option wins and why?
```

### 4. Identify Assumptions
Surface what you're taking for granted.

**Template:**
```
**Assumptions:**
- [Assumption 1]: If wrong, this changes [impact]
- [Assumption 2]: If wrong, this changes [impact]
```

### 5. Make the Call
Choose one option and state your reasoning.

**Template:**
```
**Decision:** [Chosen option]
**Reasoning:** [Why this option, not the others]
**Confidence:** [Low/Medium/High]
**Fallback:** [If this fails, then...]
```

### 6. Document
Record the decision and rationale for future reference.

## Example (Condensed)

```
**Decision:** Should we build feature X now or defer to v2?
**Stakes:** User expects it, but it delays core stability work.

**Option A:** Build now
- Pros: User satisfaction, competitive parity
- Cons: Technical debt, delays v1 launch
- Confidence: Medium

**Option B:** Defer to v2
- Pros: Focus on core, faster v1
- Cons: User disappointment, competitive gap
- Confidence: High

**Evaluation:**
1. User impact: A wins (immediate value)
2. Technical health: B wins (cleaner codebase)
3. Time to market: B wins (faster v1)

**Decision:** Defer to v2
**Reasoning:** V1 adoption matters more than feature completeness. We can iterate post-launch.
**Fallback:** If users churn over this, fast-track in v1.1
```

---

_This protocol is customizable. Adjust steps to match your decision-making style._
