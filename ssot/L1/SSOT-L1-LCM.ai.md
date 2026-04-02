[AI-OPTIMIZED] ~800 tokens | src: SSOT-L1-LCM.md | Updated: 2026-03-28

## LCM — Lossless Context Management

**Version:** 0.5.2 | **Plugin:** @martian-engineering/lossless-claw | **DB:** ~/.openclaw/lcm.db (SQLite)

DAG-based summarization. Replaces sliding-window truncation with incremental compaction. Raw messages → leaf summaries → condensed summaries. Nothing lost. Context assembled from summaries + fresh tail (32 msgs protected).

## Architecture

Messages (SQLite) → leaf compaction (~20K tokens/chunk) → Leaf Summaries (~800-1200 tokens) → condensation (4-8 summaries) → Condensed (~1500-2000 tokens) → deeper levels.

Context assembly: summaries fill budget, last 32 raw messages always protected.

## Config Parameters

| Parameter | Default | Our Setting | Description |
|-----------|---------|-------------|-------------|
| contextThreshold | 0.75 | 0.75 | Context fill fraction triggering compaction |
| freshTailCount | 32 | 32 | Recent messages protected from compaction |
| incrementalMaxDepth | 0 | 3 | Condensation depth (-1=unlimited, 0=leaf only, N=N levels max) |
| leafChunkTokens | 20000 | default | Max source tokens per leaf chunk |
| leafTargetTokens | 1200 | default | Target tokens for leaf summaries |
| condensedTargetTokens | 2000 | default | Target tokens for condensed summaries |
| leafMinFanout | 8 | default | Min messages per leaf summary |
| condensedMinFanout | 4 | default | Min summaries per condensed node |
| maxExpandTokens | 4000 | default | Token cap for sub-agent expansion queries |

## Agent Tools

| Tool | Purpose |
|------|---------|
| lcm_grep | Search messages/summaries by regex/full-text (fast DB query) |
| lcm_describe | Inspect a specific summary or stored file |
| lcm_expand_query | Deep recall: sub-agent walks DAG, answers question (~30-120s) |
| lcm_expand | Low-level DAG walker (sub-agents only) |

Escalation: grep → describe → expand_query. Summary footers list what was compressed; use lcm_expand_query to recover.

## Key Rules

- **incrementalMaxDepth: 3** — must be bounded. Default (0) accumulates summaries at depth 0. Unlimited (-1) creates infinite DAG → all summary nodes load into context_items → context window bloat.
- **freshTailCount: 32** — protects 32 most recent messages. Lower risks losing continuity.
- **contextThreshold: 0.75** — triggers at 75% fill. Safe default.
- Large files >25K tokens intercepted, stored to ~/.openclaw/lcm-files/, replaced with compact reference.
- Three-level escalation for compaction failures: normal → aggressive → fallback deterministic truncation.

## Setup Agent Config

```json
"lossless-claw": {
  "enabled": true,
  "config": {
    "freshTailCount": 32,
    "contextThreshold": 0.75,
    "incrementalMaxDepth": 3
  }
}
```

## Update History

| Version | Date | Key Changes |
|---------|------|-------------|
| 0.1.4 | 2026-03-07 | Initial install |
| 0.4.0 | 2026-03-22 | LCM 0.4.0 release |
| 0.5.1 | 2026-03-24 | LCM 0.5.1 |
| 0.5.2 | 2026-03-26 | LCM 0.5.2 — critical: incrementalMaxDepth unbounded cascade |
| config | 2026-03-27 | incrementalMaxDepth: -1 → 3 (bounded). Context_items bloat fix (7,359 → 0). freshTailCount: 4 → 32. |
| schema | 2026-03-28 | Added maxExpandTokens (type:number, default:4000) to configSchema. |
