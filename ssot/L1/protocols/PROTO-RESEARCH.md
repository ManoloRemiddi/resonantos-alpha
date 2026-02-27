# PROTO-RESEARCH — Research Protocol

> **Trigger keywords:** research, deep search, investigate, look into, find out, analyze this
> **Level:** L1(P) — Protocol
> **Enforcement:** R-Awareness injection + Shield Gate warning

---

## Decision Tree

```
User asks for research/analysis
│
├─ Simple factual lookup? (date, version, single fact)
│  └─ YES → web_search (Brave) is fine. STOP.
│
├─ Deep research? (compare options, analyze topic, multi-source)
│  └─ YES → MUST delegate to researcher agent. Continue below.
│
└─ Unsure?
   └─ If query needs >2 sources or >1 paragraph answer → researcher agent.
```

## Researcher Agent Procedure

1. **Spawn:** `sessions_spawn(agentId="researcher", task=<see template below>)`
2. **Task template:**
   ```
   Research prompt: <the question/topic>
   Mode: deep | regular
   Filename: <descriptive-name>
   ```
3. **Wait** for completion (push-based — it auto-announces).
4. **Read** the output from `research/outputs/<filename>.md`
5. **Synthesize** and present to Manolo.

## Mode Selection

| Scenario | Mode |
|----------|------|
| Broad topic analysis, comparison, state of the art | `deep` |
| Specific question with known answer shape | `regular` |
| Default when uncertain | `deep` |

## NEVER Do

- ❌ Use `web_search` for multi-source research and present results as comprehensive
- ❌ Use training data knowledge as "research" for current/evolving topics
- ❌ Answer "X doesn't exist" without verifying via Perplexity first
- ❌ Skip the researcher agent because "I probably know this"

## WHY This Protocol Exists

2026-02-24: Claimed "Gemini 3.1 Pro doesn't exist" based on web_search + training data. Wrong. Should have used Perplexity via researcher agent. Manolo's explicit instruction: serious research = Perplexity. No exceptions.
