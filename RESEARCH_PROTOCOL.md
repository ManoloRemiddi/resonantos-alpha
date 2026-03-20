# RESEARCH_PROTOCOL.md — Orchestrator → Perplexity Handoff

**Version:** 1.0  
**Created:** 2026-03-07

---

## How It Works

| Step | What Happens |
|------|--------------|
| 1. I give you research prompt | You provide a structured research question |
| 2. You run research | Perplexity in **Deep Search** mode by default |
| 3. Results | I verify output format, then deliver to you |
| 4. If Perplexity fails | I immediately report to orchestrator (Manolo) |

---

## Research Prompt Template

```markdown
# Research Context
- Decision this informs: [what decision this supports]
- Why we need this: [the problem we're solving]

# Question
[Precise research question - one sentence]

# Scope
- Focus: [topic]
- Stack: [relevant tech - Python, Flask, OpenClaw, etc.]
- Timeframe: [e.g., as of 2026]
- Non-goals: [what to ignore]

# Evidence Rules
- Prefer: official docs, technical blogs, academic papers
- Min sources: [2 per major claim]
- Must cite each claim with source

# Output Format
1) 5-7 bullet key takeaways
2) Table: Claim | Evidence | Source | Confidence
3) Best practices / patterns
4) Open questions
```

---

## Rules

### 1. Deep Search Default
- Always use **Deep Search** mode unless explicitly asked for "quick" or "standard"
- Deep Search = more sources, better synthesis

### 2. Perplexity Unavailable
If Perplexity fails (not logged in, auth error, rate limit, etc.):
- **DO NOT** try alternative methods yourself
- **IMMEDIATELY** report to orchestrator:
  - What failed (exact error message)
  - Why it failed
  - Ask: "Should I try again, or can you fix the Perplexity access?"

### 3. No Manual Research
- Don't search the web yourself using web_search
- Always use Perplexity for research tasks
- Only exception: quick factual lookup (dictionary, weather, etc.)

### 4. Verify Output
- Check that output matches the required format
- If output is poor quality, ask Perplexity to improve

---

## Example

**Me → You:**
```
Research: What are best practices for Flask security headers?
```

**You → Perplexity:**
```
You are helping me research Flask security headers.

Question: What are the best practices for implementing security headers in Flask applications?

Scope:
- Focus: HTTP security headers (CSP, HSTS, X-Frame-Options, etc.)
- Stack: Python/Flask
- Timeframe: as of 2026

Evidence Rules:
- Prefer: official Flask docs, security blogs, OWASP
- Min 2 sources per claim

Output:
1) 5-7 bullet key takeaways
2) Table: Header | Purpose | Recommended Value | Source
3) Code examples if available
```

---

## Perplexity Down Protocol

If Perplexity returns error:
```
❌ Perplexity failed: [error message]

Should I:
1) Try again?
2) Use standard search mode instead?
3) Wait for you to fix the access?
```

---

## Anti-Patterns

| ❌ Bad | ✅ Good |
|--------|---------|
| "Research X quickly" (shallow) | Use Deep Search by default |
| Try web_search yourself | Always use Perplexity |
| Tell human "done" without sources | Cite sources for each claim |
| Skip output format | Follow template structure |
