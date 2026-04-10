# LCM — Lossless Context Management (Compressed)

**v0.8.0** | Plugin: @martian-engineering/lossless-claw | Status: Active (primary context engine) | DB: ~/.openclaw/lcm.db (SQLite) | Updated: 2026-04-10

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

## New in 0.8.0
`/lossless doctor clean apply` — backup-first cleanup of high-confidence junk, preserves NULL-key subagent rows. `lcm_expand_query(allConversations: true)` — bounded cross-conversation synthesis. FTS5 query guidance: shorter queries, natural-language in prompt. CJK/emoji budget fix. Malformed `summaries_fts` recovery on startup.

## Architecture
Messages → Leaf summaries (depth 0, ~800-1200 tokens) → Condensed (depth 1+, ~1500-2000 tokens) → higher. Context assembly: summaries + protected fresh tail (last 20 messages).

## Update History (recent)
- 0.8.0 (2026-04-10): `/lossless doctor clean apply`, cross-conversation expand, FTS5 guidance, CJK fix, summaries_fts recovery.
- 0.7.0 (2026-04-09): maxExpandTokens restored. New: cache-aware compaction, circuit breaker, dynamic leaf chunks.
- 0.5.3 (2026-04-03): maxExpandTokens removed from schema.
