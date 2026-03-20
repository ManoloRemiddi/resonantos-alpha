# R-Memory — High-Fidelity Compression Extension for OpenClaw

R-Memory replaces OpenClaw's built-in lossy compaction with **lossless compression**. Instead of summarizing your conversation (losing details), it compresses blocks while preserving all decisions, code, file paths, and reasoning.

## Features

- **Lossless compression**: 60-85% token savings without information loss
- **Narrative Tracker**: Writes `SESSION_THREAD.md` after each AI response — a ~200-word working memory that survives compaction
- **FIFO eviction**: When compressed history exceeds the evict trigger, oldest blocks are archived to `memory/archive/` (searchable via `memory_search`)
- **Multi-provider**: Auto-discovers API keys for Anthropic, OpenAI, and Google; picks the cheapest model
- **On-demand compression**: Compresses at compaction time only — no wasted background API calls

## Installation

1. Copy `r-memory.js` to your OpenClaw extensions directory:

```bash
cp r-memory.js ~/.openclaw/agents/main/agent/extensions/
```

2. Create the config directory:

```bash
mkdir -p ~/.openclaw/workspace/r-memory
```

3. (Optional) Create a config file `~/.openclaw/workspace/r-memory/config.json`:

```json
{
  "enabled": true,
  "compressTrigger": 36000,
  "evictTrigger": 80000,
  "blockSize": 4000,
  "compressionModel": "anthropic/claude-haiku-4-5",
  "narrativeModel": ""
}
```

4. Restart your gateway:

```bash
openclaw gateway restart
```

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `enabled` | `true` | Enable/disable the extension |
| `compressTrigger` | `36000` | Token count that triggers compaction |
| `evictTrigger` | `80000` | Token count that triggers FIFO eviction |
| `blockSize` | `4000` | Target tokens per compression block |
| `minSwapTokens` | `50` | Minimum block size to include in compaction (filters no-ops) |
| `compressionModel` | `anthropic/claude-haiku-4-5` | Model for compression (auto-selects if key unavailable) |
| `narrativeModel` | `""` | Model for narrative tracker (empty = use compressionModel) |
| `maxParallelCompressions` | `4` | Max concurrent compression API calls |

## How It Works

1. **agent_end**: After each AI response, conversation is grouped into ~4k token blocks and archived to disk
2. **Narrative update**: A small LLM call writes `SESSION_THREAD.md` with current task, decisions, pending items, and state
3. **session_before_compact**: When OpenClaw triggers compaction, R-Memory intercepts it and swaps oldest raw blocks with compressed versions — keeping recent conversation raw
4. **FIFO eviction**: When compressed history exceeds `evictTrigger`, oldest blocks are evicted to `memory/archive/` as searchable `.md` files

## Files Created

| File | Purpose |
|------|---------|
| `r-memory/config.json` | Extension configuration |
| `r-memory/block-cache.json` | Compression cache (hash → compressed text) |
| `r-memory/r-memory.log` | Diagnostic log |
| `r-memory/usage-stats.json` | API call tracking (compression + narrative) |
| `r-memory/history-*.json` | Per-session compaction history |
| `r-memory/archive/` | Raw block archive |
| `memory/archive/` | Evicted blocks (searchable) |
| `SESSION_THREAD.md` | Working memory (narrative tracker) |

## Requirements

- OpenClaw with extension support
- At least one LLM API key (Anthropic, OpenAI, or Google)

## License

See LICENSE in repository root.
