[AI-OPTIMIZED] ~850 tokens | src: SSOT-L1-R-MEMORY.md | Updated: 2026-03-15

# R-Memory — Conversation Compression

**V4.6.3 | Active (Production) | Extension:** `~/.openclaw/agents/main/agent/extensions/r-memory.js`

## What

OpenClaw extension replacing built-in lossy compaction with high-fidelity compression. Old conversation blocks compressed via Haiku preserving all decisions, code, paths, facts. Conversations run indefinitely with minimal info loss.

> Compression, not summarization. Lossless where possible, high-fidelity where not. Never let OpenClaw's lossy fallback run.

## Three-Phase Pipeline

**Phase 1 — Background Compression (every turn):** After AI response, group msgs into ~4k blocks, compress via Haiku, cache to disk by content hash. Silent, non-blocking.

**Phase 2 — Compaction Swap (at 36k context):** OpenClaw triggers compaction → R-Memory intercepts via `session_before_compact` → swaps oldest raw blocks with cached compressed versions. Recent conversation stays raw.

**Phase 3 — FIFO Eviction (at 80k compressed):** Compressed total >80k → oldest compressed blocks evicted from context. Remain on disk in archive.

```
Turn 1-N: normal conversation
→ agent_end: group→compress→cache
→ context≥36k: session_before_compact fires
→ R-Memory swaps oldest raw→compressed
→ compressed total>80k: FIFO evicts oldest
```

## Hooks

| Hook | When | Action |
|------|------|--------|
| `agent_start` | Agent begins | Init extension, reset block counter |
| `agent_end` | After AI response | Group msgs→blocks, compress new blocks in background |
| `session_before_compact` | Compaction triggered | Intercept: swap raw→compressed OR cancel. **Never allows lossy fallback.** |

### Compaction Handler Returns
- `{ compaction: { summary, firstKeptEntryId } }` — custom compressed content
- `{ cancel: true }` — cancel compaction (prevents data loss)
- Never returns `undefined` (would allow lossy default)

## Block System

**Block:** ~4k token group of conversation messages. Msgs grouped into turns (human+AI responses), split at msg boundaries if >4k. Large AI responses (100k) → ~25 blocks.

**Lifecycle:** Messages → turns → ~4k blocks → hash → compress via Haiku → cache → swap at compaction → FIFO evict when >80k → archive raw on disk

**Compression rules:** Preserve ALL decisions/facts/params/code/paths/errors/speaker labels. Redact secrets. Tables > prose. Remove filler/pleasantries/redundancy/reasoning (keep conclusions). `<PRESERVE_VERBATIM>` content kept exactly. Typical savings: 75-92%.

## Token Budget

| Parameter | Value | Config Key |
|-----------|-------|-----------|
| Compaction trigger | 36,000 tok total context | `compressTrigger` |
| FIFO eviction | 80,000 tok compressed total | `evictTrigger` |
| Block size | 4,000 tok | `blockSize` |
| Min compress chars | 200 | `minCompressChars` |
| Max parallel compressions | 4 | `maxParallelCompressions` |

**36k trigger:** OpenClaw `reserveTokens`=164k in 200k window → compaction at ~36k. Total = system prompt (~4k) + workspace (~6k) + SSoTs + compressed history + raw conversation. R-Memory doesn't control when — only what happens.

**80k eviction:** Applies ONLY to compressed blocks total. Not raw, not system prompt, not SSoT.

## AI Context View (post-compaction)

```
# R-Memory: Compressed Conversation History
_N blocks | ~X tokens (was ~Y raw)_
## Block 1 [timestamp]
[compressed oldest]
## Block 2 [timestamp]
[compressed next]
---
[raw recent messages]
```

Compressed blocks = `compactionSummary` entry at conversation start, then recent raw msgs.

## Files

| File | Path |
|------|------|
| Extension | `~/.openclaw/agents/main/agent/extensions/r-memory.js` |
| Config | `~/.openclaw/workspace/r-memory/config.json` |
| Block cache | `~/.openclaw/workspace/r-memory/block-cache.json` |
| Session history | `~/.openclaw/workspace/r-memory/history-{sessionId}.json` |
| Archive | `~/.openclaw/workspace/r-memory/archive/{hash}.md` |
| Log | `~/.openclaw/workspace/r-memory/r-memory.log` |

**block-cache.json** = pre-compressed blocks waiting for swap (NOT in AI context). **history-{sessionId}.json** = compressed blocks currently in AI context.

## Config — `~/.openclaw/workspace/r-memory/config.json`

```json
{ "evictTrigger": 80000, "compressTrigger": 36000, "blockSize": 4000,
  "minCompressChars": 200, "compressionModel": "anthropic/claude-haiku-4-5",
  "maxParallelCompressions": 4, "enabled": true }
```

| Key | Type | Default | Desc |
|-----|------|---------|------|
| `evictTrigger` | number | 80000 | FIFO threshold (compressed total) |
| `compressTrigger` | number | 36000 | Context size triggering compaction |
| `blockSize` | number | 4000 | Target block size (tokens) |
| `minCompressChars` | number | 200 | Min text length to compress |
| `compressionModel` | string | `anthropic/claude-haiku-4-5` | Compression model |
| `maxParallelCompressions` | number | 4 | Concurrent Haiku calls |
| `enabled` | bool | true | Master switch |

## Relationship to R-Awareness

Independent. R-Memory = conversation length (compression+eviction). R-Awareness = project knowledge (SSoT injection). Different hooks, installable independently.

## Diagnostics

```bash
tail -20 ~/.openclaw/workspace/r-memory/r-memory.log
```

Log: `R-Memory V4.6.x init`, `Queued blocks`, `Block compressed` (w/ savings%), `=== COMPACTION ===` (tokensBefore, block count), `Swap plan`, `=== DONE ===` (full stats).

Stats: `grep "=== DONE ===" ...log | tail -5` → blocksSwapped, raw/compressed tokens, saving%, cache hits/misses.

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Cannot compress — CANCELLING` | No API key | Check ANTHROPIC_API_KEY or auth-profiles.json |
| `Cannot swap without removing all blocks` | Only 1 block after compaction | Normal — needs ≥2 blocks; wait for next human msg |
| 100% cache misses | Hash mismatch bg vs compaction | Known limitation — on-demand handles misses; no quality impact |
| `No blocks found — cancelling` | Compaction after previous compaction | Normal — no new blocks yet |

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Cancel over lossy fallback | Data loss permanent; cancelled compaction = context stays large until next trigger |
| Haiku for compression | Fast/cheap/sufficient; saves Opus for main conversation |
| Block size 4k | Meaningful compression + granular swapping |
| FIFO eviction | Deterministic/predictable — no AI deciding importance |
| Cache to disk | Survives gateway restarts; no re-compression |
| Archive raw blocks | Evicted ≠ deleted. Raw always recoverable |
| Background + on-demand | Background prepares cache; on-demand handles misses |
