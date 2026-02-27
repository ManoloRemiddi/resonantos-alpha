# PROTO-MODEL-SELECTION — Model Selection Protocol

> **Trigger keywords:** model, which model, subagent model, heartbeat model, cheap model
> **Level:** L1(P) — Protocol
> **Enforcement:** R-Awareness injection + Logician rules

---

## Model Hierarchy (Decision Order)

```
1. Can it be done without AI? (script, cron, deterministic)
   └─ YES → No model needed. Deterministic first.

2. Is it free?
   ├─ openai-codex/gpt-5.3-codex → Free via Pro subscription
   ├─ google/gemini-2.5-flash → Free tier (rate limited)
   ├─ ollama/* → Local, free (limited capability)
   └─ anthropic/claude-opus-4-6 → Included in subscription flat rate
   
3. Cost-aware selection:
   ├─ Heartbeat/routine checks → google/gemini-2.5-flash (free, fast)
   ├─ Background sub-agents → openai-codex/gpt-5.3-codex (free, capable)
   ├─ Compression → anthropic/claude-haiku-4-5 or openai/gpt-4o-mini
   ├─ Complex reasoning → anthropic/claude-opus-4-6 (main session only)
   └─ Coding → openai-codex/gpt-5.3-codex via Codex CLI
```

## Provider Constraints

| Provider | Auth | Route | Notes |
|----------|------|-------|-------|
| `anthropic` | API key (manual) | Direct API | Subscription flat rate — Opus for main session |
| `openai-codex` | OAuth (Pro subscription) | ChatGPT backend | Only gpt-5.3-codex resolves in OpenClaw heartbeat/agent model |
| `google` | API key (manual) | Gemini API | Free tier works for heartbeats |
| `ollama` | Needs OLLAMA_API_KEY env | Local | 1B-4B models, limited tool use |

## Known Limitation

OpenClaw's model resolver only supports `openai-codex/gpt-5.3-codex` via forward-compat. Other openai-codex models (gpt-4o-mini, gpt-4o) fail with "Unknown model." R-Memory bypasses this with its own fallback, but heartbeat/agents cannot.

## WHY This Protocol Exists

2026-02-24: Set heartbeat to openai-codex/gpt-4o-mini — failed because OpenClaw doesn't resolve it. Then tried anthropic/haiku — works but burns subscription. Correct answer was google/gemini-2.5-flash (free, capable, resolves correctly).
