# R-Memory — Project SSoT (L2)

> High-fidelity compression + FIFO eviction + evolving narrative. Replaces OpenClaw's lossy compaction.

## Status: Production — V5.3.0

## Architecture

```
User message → AI response → agent_end fires
    ├→ Compression: archive raw blocks to disk
    └→ Narrative: update SESSION_THREAD.md (evolving working memory)

before_agent_start fires (every turn)
    ├→ Inject SESSION_THREAD.md via prependContext
    └→ Inject PLAN.md if exists (externalized task state)

Context reaches 36k → session_before_compact fires
    → R-Memory intercepts → rawWindow check (30k raw token budget)
    → compress oldest raw blocks until rawTokens ≤ rawWindow
    → Floor guard: retry if compression >65% (target+15%)
    → FIFO evict if compressed total > 80k
    → evicted blocks → memory/archive/ (searchable)
```

## Two Background Agents

| Agent | Model | Purpose | Cost |
|-------|-------|---------|------|
| Compression | `minimax/MiniMax-M2.5` | Compress conversation blocks (~50% target) | ~$0.01-0.03/day |
| Narrative | `minimax/MiniMax-M2.1` | Maintain evolving SESSION_THREAD.md | ~$0.01/day |

## Key Design Decisions

| Decision | Rationale |
|---|---|
| On-demand compression (not background) | Eliminates cache hash mismatches; compress at swap time |
| FIFO eviction (not "smart") | Deterministic > probabilistic |
| 50% compression target (not max) | Preserves reasoning chains, causal paths, WHY behind decisions |
| Floor guard with retry | Deterministic safety net when model over-compresses |
| M2.5 for compression | Good at structured tasks; hallucination issue is narrative-only |
| M2.1 for narrative | Less agentic training than M2.5; fewer hallucinated tool calls |
| Input sanitization | Removes [Tool: exec] patterns from conversation before narrative model sees them |
| Auto-injection via prependContext | SESSION_THREAD.md + PLAN.md mechanically in context every turn |
| Raw always on disk | Evicted ≠ deleted. Searchable via memory_search |
| Training data collection | Prepares for local fine-tuned model replacement |

## Token Budget

| Parameter | Value |
|---|---|
| Raw window | 30,000 tokens (always-live raw context) |
| FIFO eviction trigger | 80,000 tokens |
| Block size | 4,000 tokens |
| Min compress chars | 200 |
| Compression target | 50% reduction (configurable) |
| Floor guard threshold | target + 15% |

## Anti-Amnesia System

| Layer | Function |
|-------|----------|
| Rich compressed blocks | Micro view with reasoning chains preserved (50% not 87%) |
| SESSION_THREAD.md | Macro view of session arc/decisions (auto-injected) |
| PLAN.md | Task-level state (auto-injected if exists) |
| FIFO eviction | Predictable token budget |
| memory_search | Fallback for evicted content |

## Narrative Tracker

### Input Sanitization (V5.2.0)
Conversation messages (`recentExchanges`) are sanitized before reaching the narrative model:
- Removes `[Tool: exec]`, `[Tool: read]` patterns
- Removes `<minimax:tool_call>`, `<FunctionCallBegin>`, `[TOOL_CALL]` syntax
- Removes `<PRESERVE_VERBATIM>` blocks
- **Why:** M2.1 copies tool syntax from input → generates hallucinated tool calls

### Output Validation Gate
After model responds, output is checked for hallucination patterns:
- Rejects output containing tool-call syntax
- Rejects output < 100 chars (catches empty templates)
- If rejected: keeps previous SESSION_THREAD.md unchanged, logs warning

### Model History
| Model | Period | Result |
|-------|--------|--------|
| Opus 4.6 | Pre-Feb 2026 | Worked perfectly but expensive |
| MiniMax M2.5 | Mar 1-2 | Hallucinated tool calls (80.2% SWE-bench = heavy agentic training) |
| MiniMax M2.1 | Mar 2+ | Works with input sanitization; less agentic training |

## OpenClaw Integration

| Hook | What we do |
|---|---|
| `before_agent_start` | Inject SESSION_THREAD.md + PLAN.md via prependContext |
| `agent_start` | Init, load config, resolve API keys |
| `agent_end` | Archive blocks + update narrative |
| `session_before_compact` | Intercept compaction → compress on-demand → swap → FIFO evict |

**Critical:** R-Memory always provides its own compression or cancels. Never allows lossy fallback.

## Configuration

File: `r-memory/config.json`

```json
{
  "rawWindow": 30000,
  "evictTrigger": 80000,
  "blockSize": 4000,
  "minCompressChars": 200,
  "compressionModel": "minimax/MiniMax-M2.5",
  "narrativeModel": "minimax/MiniMax-M2.1",
  "maxParallelCompressions": 4,
  "enabled": true,
  "narrativeUseToolMode": false,
  "compressionTarget": 0.5
}
```

## Version History

| Version | Date | Key Changes |
|---|---|---|
| 4.6.3 | 2026-02-19 | Multi-provider, auto-model, usage tracking |
| 4.7.0 | 2026-02-20 | Narrative Tracker, SESSION_THREAD.md |
| 4.8.1 | 2026-02-20 | Camouflage routing, behavioral jitter |
| 5.0.0 | 2026-02-20 | Narrative redesign: evolving doc, structured format |
| 5.0.1 | 2026-02-20 | Narrative → Opus, training data collection |
| 5.1.0 | 2026-03-01 | Structured tool approach, configurable narrativeUseToolMode |
| 5.1.1 | 2026-03-02 | Compression target 50%, floor guard, evictTrigger 80K |
| 5.2.0 | 2026-03-02 | Input sanitization, auto-injection, PLAN.md, validation gate |
| 5.3.0 | 2026-03-03 | rawWindow (30k sliding raw context) replaces compressTrigger overflow logic |

## What's Next

1. **Narrative model stability** — M2.1 works but hallucination rate still ~5% with clean input
2. **Compression consistency** — Floor guard insufficient; model ignores 50% target on some blocks
3. **Collect training data** — Accumulate pairs for local fine-tuning
4. **Fine-tune local models** — Replace cloud calls with local 1-3B models

## Files

- L1 Architecture: `ssot/L1/SSOT-L1-R-MEMORY.md`
- Extension: `~/.openclaw/agents/main/agent/extensions/r-memory.js`
- Config: `r-memory/config.json`
- Training data: `r-memory/training-data/{compression,narrative}/pairs.jsonl`
- Narrative thread: `SESSION_THREAD.md`
- Log: `r-memory/r-memory.log`

## REFERENCES

- L4 Compression Strategy: `L4-2026-03-02-COMPRESSION-STRATEGY-REVISION.md`
- L4 Behavioral Issues: `L4-2026-03-02-BEHAVIORAL-AND-MEMORY-ISSUES.md`
- L4 Enforcement Architecture: `L4-2026-03-02-ENFORCEMENT-ARCHITECTURE.md`
