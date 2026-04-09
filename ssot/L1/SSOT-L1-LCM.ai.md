# LCM — Lossless Context Management (Compressed)

**v0.7.0** | Plugin: @martian-engineering/lossless-claw | Status: Active (primary context engine) | DB: ~/.openclaw/lcm.db (SQLite) | Updated: 2026-04-09

## What It Does
DAG-based conversation summarization. Replaces sliding-window truncation. Raw messages persist in SQLite; summaries form a hierarchy; nothing is lost. Agents navigate via lcm_grep / lcm_describe / lcm_expand_query.

## Key Parameters (current live config)
| Parameter | Live Value | Description |
|-----------|-----------|-------------|
| incrementalMaxDepth | 2 | Condensation depth (must be bounded, never -1) |
| freshTailCount | 20 | Recent messages protected from compaction |
| contextThreshold | 0.75 | Context fill % that triggers compaction |
| ignoreSessionPatterns | agent:*:cron:** | Sessions excluded from LCM storage |

## Bounded Depth Rule
`incrementalMaxDepth` must be a positive integer or 0. Never -1 (unlimited). With -1, the DAG grows indefinitely and ALL summary nodes load into context_items → context window overflow. The Mar 2026 bloat produced 7,359 context_items and ~350K tokens.

## maxExpandTokens
Was in 0.5.2 schema, removed in 0.5.3 (caused validation failures), **re-added in 0.7.0**. Currently safe to set.

## New in 0.7.0
cacheAwareCompaction, dynamicLeafChunkTokens, circuitBreakerThreshold/CooldownMs, bootstrapMaxTokens, newSessionRetainDepth, largeFileSummaryModel/Provider, summaryTimeoutMs, fallbackProviders, timezone, pruneHeartbeatOk. Deps updated: @mariozechner/pi-agent-core, @mariozechner/pi-ai, @sinclair/typebox 0.34.48.

## Architecture
Messages → Leaf summaries (depth 0, ~800-1200 tokens) → Condensed (depth 1+, ~1500-2000 tokens) → higher. Context assembly: summaries + protected fresh tail (last 20 messages).

## Update History (recent)
- 0.7.0 (2026-04-09): Major release. maxExpandTokens restored. New: cache-aware compaction, circuit breaker, dynamic leaf chunks.
- 0.5.3 (2026-04-03): maxExpandTokens removed from schema.
- config (2026-03-27): incrementalMaxDepth -1 → 3 (bounded). freshTailCount 4 → 32.
