# R-Memory — Conversation Compression

| Field | Value |
|-------|-------|
| Version | 4.6.3 (Alpha) |
| Date | 2026-02-18 |
| Level | L1 (Architecture) |
| Type | OpenClaw Extension |

---

## What Is R-Memory

An OpenClaw extension that replaces the built-in lossy compaction with high-fidelity compression. Old conversation blocks are compressed via a cheap model (Haiku) while preserving all decisions, code, paths, and facts. Conversations can run indefinitely with minimal information loss.

> Compression, not summarization. Lossless where possible, high-fidelity where not.

---

## Three-Phase Pipeline

### Phase 1 — Background Compression (every turn)
After each AI response, messages are grouped into ~4k token blocks and compressed via Haiku in the background. Results are cached to disk by content hash. Silent and non-blocking.

### Phase 2 — Compaction Swap (at context threshold)
When OpenClaw triggers compaction (context too large), R-Memory intercepts and swaps the oldest raw conversation blocks with their pre-compressed versions. Recent conversation stays raw and uncompressed.

### Phase 3 — FIFO Eviction (at compressed limit)
When compressed blocks exceed the eviction threshold, the oldest compressed blocks are removed from context. They remain on disk in the archive — evicted ≠ deleted.

```
Turn 1-N: normal conversation
→ After AI response: group → compress → cache
→ Context too large: swap oldest raw → compressed
→ Compressed total too large: evict oldest blocks
```

---

## How It Looks to the AI

After compaction, the AI sees:

```
# R-Memory: Compressed Conversation History
_N blocks | ~X tokens (was ~Y raw)_

## Block 1 [timestamp]
[compressed oldest conversation]

## Block 2 [timestamp]
[compressed next block]

---
[raw recent messages continue normally]
```

---

## Configuration

Config file: `~/.openclaw/workspace/r-memory/config.json`

```json
{
  "enabled": true,
  "evictTrigger": 80000,
  "compressTrigger": 36000,
  "blockSize": 4000,
  "minCompressChars": 200,
  "compressionModel": "anthropic/claude-haiku-4-5",
  "maxParallelCompressions": 4
}
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `enabled` | true | Master switch |
| `evictTrigger` | 80000 | FIFO threshold (compressed tokens) |
| `compressTrigger` | 36000 | Context size triggering compaction |
| `blockSize` | 4000 | Target block size (tokens) |
| `compressionModel` | claude-haiku-4-5 | Model used for compression |
| `maxParallelCompressions` | 4 | Concurrent compression calls |

---

## Compression Rules

- Preserve ALL decisions, facts, parameters, code, paths, errors, speaker labels
- Tables over prose
- Remove filler, pleasantries, redundancy, reasoning chains (keep conclusions)
- Content marked `<PRESERVE_VERBATIM>` is kept exactly as-is
- Redact secrets (API keys, tokens)
- Typical savings: 75-92%

---

## Files

| File | Purpose |
|------|---------|
| `r-memory/config.json` | Configuration |
| `r-memory/block-cache.json` | Pre-compressed blocks waiting for swap |
| `r-memory/history-{sessionId}.json` | Compressed blocks in current AI context |
| `r-memory/archive/{hash}.md` | Archived raw blocks (recoverable) |
| `r-memory/r-memory.log` | Diagnostic log |

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Cancel over lossy fallback | Data loss is permanent; better to keep context large |
| Haiku for compression | Fast, cheap, sufficient quality |
| Block size 4k | Meaningful compression + granular swapping |
| FIFO eviction | Deterministic — no AI deciding what's important |
| Cache to disk | Survives gateway restarts |
| Archive raw blocks | Evicted ≠ deleted; always recoverable |

---

## Relationship to R-Awareness

Independent. R-Memory handles **conversation length** (compression + eviction). R-Awareness handles **project knowledge** (SSoT injection). Different hooks, installable independently.

---

## Diagnostics

```bash
tail -20 ~/.openclaw/workspace/r-memory/r-memory.log
```

| Symptom | Fix |
|---------|-----|
| "Cannot compress — CANCELLING" | Check API key / auth credentials |
| 100% cache misses | Normal on first compaction; on-demand handles misses |
| "No blocks found — cancelling" | No new blocks since last compaction; wait |
