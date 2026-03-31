# SSOT-L1-PROTO-RESEARCH — Deep Research Protocol
Updated: {{GENERATED_DATE}}

## Purpose
For deep, multi-source research that exceeds quick web_search capacity, spawn a dedicated research sub-agent with access to premium search tools.

## When to Use

### Use This Protocol When:
- Research requires >3 distinct queries
- Need academic/technical depth
- Cross-referencing multiple sources
- Building comprehensive understanding of a topic
- Preparing for major decisions

### Use web_search Instead When:
- Quick fact-checking
- Single, straightforward question
- Time-sensitive lookups

## Protocol Steps

### 1. Frame the Research Question
Define what you need to know and why.

**Template:**
```
**Question:** [What are we trying to learn?]
**Context:** [Why does this matter?]
**Scope:** [Boundaries — what's in/out]
**Deliverable:** [Format of the answer]
```

### 2. Spawn Research Sub-Agent
Create an isolated session with research tools.

**Command:**
```bash
sessions_spawn(
  task="Research: [your question]. Deliverable: [format]",
  agentId="{{RESEARCH_AGENT_ID}}",
  model="{{RESEARCH_MODEL}}",
  mode="run",
  runTimeoutSeconds=600
)
```

### 3. Sub-Agent Research Process
The research agent should:
1. Break the question into sub-questions
2. Query each sub-question independently
3. Cross-reference sources
4. Synthesize findings
5. Cite sources

### 4. Review & Integrate
When the sub-agent returns:
1. Verify findings against known context
2. Flag any contradictions
3. Extract actionable insights
4. Document in appropriate SSoT

## Configuration

### Research Agent
- **Agent ID:** {{RESEARCH_AGENT_ID}}
- **Model:** {{RESEARCH_MODEL}}
- **Search Provider:** {{RESEARCH_SEARCH_PROVIDER}}

### Timeout
- **Default:** 600s (10 minutes)
- **Deep research:** 1200s (20 minutes)

## Example

```markdown
**Question:** What are the best practices for Solana PDA (Program-Derived Address) security in 2026?

**Context:** We're implementing Symbiotic Wallet and need to ensure the PDA architecture is secure.

**Scope:**
- In: Recent Solana security advisories, PDA best practices, multi-sig patterns
- Out: General blockchain security (focus on Solana-specific)

**Deliverable:** Markdown summary with:
- Top 5 security practices
- Known vulnerabilities to avoid
- Code examples where applicable
- Citations
```

**Spawn command:**
```python
sessions_spawn(
  task="Research Solana PDA security best practices (2026). Focus on: recent advisories, multi-sig patterns, known vulnerabilities. Deliverable: Markdown with top 5 practices + code examples + citations.",
  agentId="researcher",
  model="{{RESEARCH_MODEL}}",
  mode="run",
  runTimeoutSeconds=600
)
```

---

_This protocol is customizable. Adjust agent configuration to match your research needs._
