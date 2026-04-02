[AI-OPTIMIZED] ~1800 tokens | src: openclaw/docs/concepts/memory.md
Updated: 2026-02-14

# Memory

OpenClaw memory: plain Markdown files = source of truth. Model remembers only what's written to disk. Memory search via active plugin (default: `memory-core`). Disable: `plugins.slots.memory = "none"`.

## Files

Default workspace layout:
- `memory/YYYY-MM-DD.md` — daily log (append-only); read today + yesterday at session start
- `MEMORY.md` (opt) — curated long-term; **main session only** (never group contexts)

Both under workspace root (`agents.defaults.workspace`, default `~/.openclaw/workspace`).

## Write Policy

- Decisions/preferences/facts → `MEMORY.md`
- Daily notes/context → `memory/YYYY-MM-DD.md`
- "Remember this" → write to file (not RAM)
- Ask bot to write if persistence needed

## Automatic Memory Flush (Pre-Compaction)

Silent agentic turn when context near compaction. Reminds model to store durable memory before context reset.

Config: `agents.defaults.compaction.memoryFlush`
```json5
{
  agents: {
    defaults: {
      compaction: {
        reserveTokensFloor: 20000,
        memoryFlush: {
          enabled: true,
          softThresholdTokens: 4000,
          systemPrompt: "Session nearing compaction. Store durable memories now.",
          prompt: "Write any lasting notes to memory/YYYY-MM-DD.md; reply NO_REPLY if nothing.",
        }
      }
    }
  }
}
```

Key points:
- **Soft threshold**: triggers @ `contextWindow - reserveTokensFloor - softThresholdTokens`
- **Silent**: `NO_REPLY` in prompt; nothing delivered to user
- **One per cycle**: tracked in `sessions.json`
- **RO workspaces**: flush skipped if `workspaceAccess: "ro"/"none"`

## Vector Memory Search

Semantic search over `MEMORY.md` + `memory/*.md` via small vector index. Find related notes despite wording differences.

**Defaults:**
- Enabled by default
- Watches memory files (debounced)
- Remote embeddings default; auto-selects provider in order:
  1. `local` (if `memorySearch.local.modelPath` exists)
  2. `openai` (if API key available)
  3. `gemini` (if API key available)
  4. `voyage` (if API key available)
  5. Disabled otherwise

**API Keys:** Resolve from auth profiles, `models.providers.*.apiKey`, or env vars. Codex OAuth covers chat/completions only; **not** embeddings. Gemini: `GEMINI_API_KEY` or `models.providers.google.apiKey`. Voyage: `VOYAGE_API_KEY` or `models.providers.voyage.apiKey`.

**Index storage:** per-agent SQLite @ `~/.openclaw/memory/<agentId>.sqlite` (cfg: `agents.defaults.memorySearch.store.path`, supports `{agentId}` token).

**Freshness:** watcher marks index dirty (debounce 1.5s). Sync on session start/search/interval (async). Sessions use delta thresholds. Index auto-resets if embedding provider/model/endpoint/chunking changes.

### QMD Backend (Experimental)

Set `memory.backend = "qmd"` → swap SQLite for [QMD](https://github.com/tobi/qmd) (local-first sidecar: BM25 + vectors + reranking). Markdown = source of truth; OpenClaw shells to QMD.

**Prereqs:**
- Opt-in: `memory.backend = "qmd"`
- Install QMD: `bun install -g https://github.com/tobi/qmd` or release binary
- SQLite w/ extensions: `brew install sqlite` (macOS)
- Bun + `node-llama-cpp` (auto-downloads GGUF models)
- Self-contained XDG home: `~/.openclaw/agents/<agentId>/qmd/`
- OS: macOS/Linux native; Windows via WSL2

**Operation:**
- Gateway writes QMD home under `~/.openclaw/agents/<agentId>/qmd/`
- Collections: rewrite from `memory.qmd.paths` + default workspace files → `index.yml`
- `qmd update` + `qmd embed` on boot + interval (`memory.qmd.update.interval`, default 5m)
- Searches: `qmd query --json`. Failure/missing binary → fallback to builtin SQLite
- **First search may be slow**: QMD auto-downloads GGUF models
- Warm pre-download:
  ```bash
  STATE_DIR="${OPENCLAW_STATE_DIR:-$HOME/.openclaw}"
  [ -d "$HOME/.moltbot" ] && [ ! -d "$HOME/.openclaw" ] && \
    STATE_DIR="$HOME/.moltbot"
  export XDG_CONFIG_HOME="$STATE_DIR/agents/main/qmd/xdg-config"
  export XDG_CACHE_HOME="$STATE_DIR/agents/main/qmd/xdg-cache"
  qmd update && qmd embed
  qmd query "test" -c memory-root --json >/dev/null 2>&1
  ```

**Config (`memory.qmd.*`):**
- `command` (default `qmd`) — executable override
- `includeDefaultMemory` (default true) — index `MEMORY.md` + `memory/**/*.md`
- `paths[]` — extra dirs/files: `path`, opt `pattern`, opt `name`
- `sessions` — session JSONL indexing: `enabled`, `retentionDays`, `exportDir`
- `update` — `interval`, `debounceMs`, `onBoot`, `embedInterval`
- `limits` — `maxResults`, `maxSnippetChars`, `maxInjectedChars`, `timeoutMs`
- `scope` — same schema as `session.sendPolicy`; default DM-only
- `citations` — `auto`/`on`/`off` (footer w/ path#line when on)

**Example:**
```json5
memory: {
  backend: "qmd",
  citations: "auto",
  qmd: {
    includeDefaultMemory: true,
    update: { interval: "5m", debounceMs: 15000 },
    limits: { maxResults: 6, timeoutMs: 4000 },
    scope: {
      default: "deny",
      rules: [{ action: "allow", match: { chatType: "direct" } }]
    },
    paths: [{ name: "docs", path: "~/notes", pattern: "**/*.md" }]
  }
}
```

**QMD results:** tagged `status().backend = "qmd"`. On failure, fallback to builtin provider until recovery.

### Extra Memory Paths

Index Markdown outside workspace:
```json5
agents: {
  defaults: {
    memorySearch: {
      extraPaths: ["../team-docs", "/srv/shared-notes/overview.md"]
    }
  }
}
```
Notes: absolute or relative paths; dirs scanned recursively; `.md` only; symlinks ignored.

### Gemini Embeddings

```json5
agents: {
  defaults: {
    memorySearch: {
      provider: "gemini",
      model: "gemini-embedding-001",
      remote: { apiKey: "YOUR_GEMINI_API_KEY" }
    }
  }
}
```

### OpenAI-Compatible Endpoint

```json5
agents: {
  defaults: {
    memorySearch: {
      provider: "openai",
      model: "text-embedding-3-small",
      remote: {
        baseUrl: "https://api.example.com/v1/",
        apiKey: "YOUR_API_KEY",
        headers: { "X-Custom-Header": "value" }
      }
    }
  }
}
```

**Fallback:** `memorySearch.fallback` = `openai`, `gemini`, `local`, `none`.

### Batch Indexing (OpenAI + Gemini)

Enabled by default. Config:
```json5
agents: {
  defaults: {
    memorySearch: {
      remote: {
        batch: {
          enabled: true,
          concurrency: 2,
          wait: <tune>,
          pollIntervalMs: <tune>,
          timeoutMinutes: <tune>
        }
      }
    }
  }
}
```

**Why fast+cheap:** async batch API = faster than sync + discounted pricing. See [OpenAI Batch API](https://platform.openai.com/docs/api-reference/batch).

### Memory Tools

- `memory_search` — semantic search Markdown (~400 tok target, 80 tok overlap) from `MEMORY.md` + `memory/**/*.md`. Returns: snippet (~700 chars), path, line range, score, provider/model, fallback indicator. **No full file payload.**
- `memory_get` — read memory file (workspace-relative), opt starting line + N lines. Rejects paths outside `MEMORY.md`/`memory/`.

Both enabled when `memorySearch.enabled` resolves true.

### What Gets Indexed

- **Files:** Markdown only (`MEMORY.md`, `memory/**/*.md`)
- **Storage:** per-agent SQLite @ `~/.openclaw/memory/<agentId>.sqlite`
- **Freshness:** watcher on `MEMORY.md` + `memory/` (debounce 1.5s). Sync: session start/search/interval (async). Session transcripts: delta thresholds.
- **Reindex triggers:** provider/model/endpoint fingerprint/chunking params stored. Change any → auto reset + reindex.

### Hybrid Search (BM25 + Vector)

Combine vector (semantic) + BM25 (keyword exact) retrieval.

**Why:** vectors handle paraphrases; BM25 handles IDs/symbols/error strings.

**Merge logic:**
1. Candidate pool: vector top `maxResults * candidateMultiplier` by cosine sim; BM25 top `maxResults * candidateMultiplier` by rank
2. BM25 → score: `textScore = 1 / (1 + max(0, bm25Rank))`
3. Union by chunk ID: `finalScore = vectorWeight * vectorScore + textWeight * textScore`

Notes: weights normalize to 1.0. If embeddings unavailable, BM25 only. If FTS5 unavailable, vector-only.

**Config:**
```json5
agents: {
  defaults: {
    memorySearch: {
      query: {
        hybrid: {
          enabled: true,
          vectorWeight: 0.7,
          textWeight: 0.3,
          candidateMultiplier: 4
        }
      }
    }
  }
}
```

### Embedding Cache

Cache chunk embeddings in SQLite to skip re-embedding unchanged text (esp. session transcripts).

```json5
agents: {
  defaults: {
    memorySearch: {
      cache: {
        enabled: true,
        maxEntries: 50000
      }
    }
  }
}
```

### Session Memory Search (Experimental)

Opt-in: index session transcripts + surface via `memory_search`.

```json5
agents: {
  defaults: {
    memorySearch: {
      experimental: { sessionMemory: true },
      sources: ["memory", "sessions"]
    }
  }
}
```

Notes: opt-in (default off); async debounced indexing (delta thresholds); never blocks; results = snippets only (no full file via `memory_get`); per-agent isolation; disk = trust boundary.

**Delta thresholds:**
```json5
agents: {
  defaults: {
    memorySearch: {
      sync: {
        sessions: {
          deltaBytes: 100000,   // ~100 KB
          deltaMessages: 50     // JSONL lines
        }
      }
    }
  }
}
```

### SQLite Vector Acceleration (sqlite-vec)

Use sqlite-vec extension for vector distance queries in DB (fast, no JS loading).

```json5
agents: {
  defaults: {
    memorySearch: {
      store: {
        vector: {
          enabled: true,
          extensionPath: "/path/to/sqlite-vec"
        }
      }
    }
  }
}
```

Notes: `enabled` default true. Missing extension → fall back to JS cosine. No hard failure.

### Local Embedding Auto-Download

**Default model:** `hf:ggml-org/embedding-gemma-300M-GGUF/embedding-gemma-300M-Q8_0.gguf` (~0.6 GB).

When `memorySearch.provider = "local"`: `node-llama-cpp` resolves `modelPath`; missing GGUF → auto-download to cache (or `local.modelCacheDir` if set), then load. Resume on retry.

**Native:** run `pnpm approve-builds`, pick `node-llama-cpp`, then `pnpm rebuild node-llama-cpp`.

**Fallback:** if local fails + `memorySearch.fallback = "openai"` → auto-switch to remote (`openai/text-embedding-3-small` default).
