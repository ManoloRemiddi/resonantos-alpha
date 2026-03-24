Updated: 2026-03-24 (version 2026.3.22)
# OpenClaw Manual (Compressed) — L1 Reference

> Load this for full OpenClaw awareness. ~2,500 tokens vs ~15,000+ raw.

## 1. Architecture

| Component | Role |
|-----------|------|
| Gateway | Single daemon, owns all channels (Telegram/WhatsApp/Discord/Slack/Signal/iMessage/WebChat), WS API on 127.0.0.1:18789 |
| Agent Runtime | Embedded pi-mono derivative. OpenClaw owns sessions/discovery/tool-wiring |
| Workspace | `~/.openclaw/workspace` — agent's cwd, bootstrap files injected into context |
| State Dir | `~/.openclaw/` — config, credentials, sessions (NOT in workspace) |
| Sessions | JSONL at `~/.openclaw/agents/<agentId>/sessions/<SessionId>.jsonl` |
| Canvas Host | Port 18793, serves agent-editable HTML/A2UI |
| Nodes | macOS/iOS/Android connect via WS with `role:node`, expose camera/screen/location |

**Wire Protocol:** WS text frames, JSON. First frame must be `connect`. Req/res + server-push events. Auth via `OPENCLAW_GATEWAY_TOKEN`.

**Remote Access:** Tailscale/VPN preferred, SSH tunnel alternative.

## 2. Sessions

| Concept | Detail |
|---------|--------|
| Main session | `agent:<agentId>:<mainKey>` (default `main`), all DMs collapse here |
| Group sessions | `agent:<agentId>:<channel>:group:<id>` (isolated) |
| DM scope | `main` (default) / `per-peer` / `per-channel-peer` / `per-account-channel-peer` |
| Reset | Daily 4AM local (default) + optional idle minutes. `/new` or `/reset` forces fresh session |
| Store | `sessions.json` — map of sessionKey → metadata. Delete-safe, recreated on demand |
| Pruning | Trims old tool results in-memory before LLM call (not on disk). Mode: `cache-ttl` |
| Identity links | Map cross-channel peer IDs to canonical identity |

**Lifecycle:** Sessions reused until expired. Evaluated on next inbound message.

## 3. Context Window

**What model sees per run:**
1. System prompt (OpenClaw-built): tools, skills list, time, runtime, injected workspace files
2. Conversation history
3. Tool calls/results + attachments
4. Compaction summaries

**System prompt sections:** Tooling → Safety → Skills (names only) → Self-Update → Workspace → Docs → Time → Reply Tags → Heartbeats → Runtime → Reasoning

**Bootstrap files injected:** AGENTS.md, SOUL.md, TOOLS.md, IDENTITY.md, USER.md, HEARTBEAT.md, BOOTSTRAP.md. Max 20k chars/file, truncated with marker.

**Prompt modes:** `full` (main) / `minimal` (sub-agents: omits skills, memory recall, heartbeats, etc.) / `none`

**Inspect:** `/status`, `/context list`, `/context detail`, `/usage tokens`

## 4. Compaction

| Setting | Detail |
|---------|--------|
| Trigger | Auto when session nears context window limit |
| Action | Summarizes older conversation → compact summary entry, keeps recent messages |
| Persistence | Summary stored in JSONL history |
| Memory flush | Silent pre-compaction turn reminds model to write durable notes to disk |
| Manual | `/compact [instructions]` |
| Config | `agents.defaults.compaction.reserveTokensFloor` (20k default), `memoryFlush.softThresholdTokens` (4k) |

**Compaction ≠ Pruning:** Compaction summarizes+persists. Pruning trims tool results in-memory only.

## 5. Memory

**Philosophy:** Plain Markdown in workspace = source of truth. Model only "remembers" what's on disk.

| File | Purpose | Load When |
|------|---------|-----------|
| `memory/YYYY-MM-DD.md` | Daily log (append-only) | Today + yesterday at session start |
| `MEMORY.md` | Curated long-term | Main session only (never in groups) |

**Memory Search (vector):**
- Indexes `MEMORY.md` + `memory/*.md` via embeddings (OpenAI/Gemini/Voyage/local)
- Hybrid search: BM25 (keyword) + vector (semantic), weights configurable
- Tools: `memory_search` (returns snippets+path+lines), `memory_get` (read by path)
- Storage: per-agent SQLite at `~/.openclaw/memory/<agentId>.sqlite`
- Auto-watches for changes, debounced reindex
- Extra paths configurable via `memorySearch.extraPaths`

**QMD backend (experimental):** Local BM25+vector+reranking sidecar. Opt-in via `memory.backend = "qmd"`.

**Session memory search (experimental):** Opt-in indexing of session transcripts.

## 6. Sub-Agents

| Property | Detail |
|----------|--------|
| Session | `agent:<agentId>:subagent:<uuid>` (isolated) |
| Model | Inherits caller unless `subagents.model` set |
| Context | Only AGENTS.md + TOOLS.md injected (no SOUL/IDENTITY/USER) |
| Tools | All except session tools (sessions_list/history/send/spawn) |
| Announce | Result posted back to requester chat. `ANNOUNCE_SKIP` suppresses |
| Concurrency | `maxConcurrent: 8` default |
| Nesting | Cannot spawn sub-sub-agents |
| Cleanup | `keep` (default) or `delete`. Auto-archive after 60min |
| Timeout | `runTimeoutSeconds` (0 = no limit) |

**Tool:** `sessions_spawn(task, label?, model?, thinking?, runTimeoutSeconds?, cleanup?)`

## 7. Multi-Agent

- Multiple isolated agents per gateway: separate workspace + agentDir + sessions
- Auth profiles per-agent (`~/.openclaw/agents/<agentId>/agent/auth-profiles.json`)
- Routing via `bindings`: deterministic, most-specific wins (peer > guild > account > channel > default)
- Per-agent sandbox + tool restrictions possible
- `agents_list` shows allowed spawn targets

## 8. Workspace Files

| File | Purpose |
|------|---------|
| `AGENTS.md` | Operating instructions, memory guidance |
| `SOUL.md` | Persona, tone, boundaries |
| `TOOLS.md` | Local tool notes (does NOT control availability) |
| `IDENTITY.md` | Name, vibe, emoji |
| `USER.md` | User profile |
| `HEARTBEAT.md` | Optional periodic task checklist |
| `BOOT.md` | Optional startup checklist on gateway restart |
| `BOOTSTRAP.md` | One-time first-run ritual |

**NOT in workspace:** config (`openclaw.json`), credentials, sessions, managed skills.

## 9. Key Config Paths

```
~/.openclaw/openclaw.json          # Main config
~/.openclaw/workspace/             # Agent workspace (cwd)
~/.openclaw/agents/<id>/sessions/  # Session transcripts + store
~/.openclaw/agents/<id>/agent/     # Per-agent auth + state
~/.openclaw/skills/                # Managed/shared skills
~/.openclaw/memory/<id>.sqlite     # Memory search index
```

## 10. Slash Commands (Key)

`/status` `/context list|detail` `/compact [instructions]` `/new [model]` `/reset` `/stop` `/send on|off|inherit` `/subagents list|stop|log|info|send` `/usage tokens` `/think` `/verbose` `/reasoning` `/elevated` `/model` `/queue`

## 11. Model Configuration

- Format: `provider/model` (e.g., `anthropic/claude-opus-4-6`)
- Provider split on first `/`
- Per-session override: `/model provider/model` or `/new provider/model`
- Sub-agent model: `agents.defaults.subagents.model`
- Heartbeat model: `agents.defaults.heartbeat.model`

## 12. Session Pruning (cache-ttl)

- Trims old `toolResult` messages in-memory when last Anthropic call > TTL (default 5min)
- Soft-trim: head+tail with `...` for oversized results
- Hard-clear: replaces with placeholder
- Protects last 3 assistant messages
- Skips image blocks
- Improves Anthropic prompt cache efficiency

## 13. R-Memory Integration Points

**OpenClaw memory is file-based Markdown.** Any enhancement must:
1. Write to `MEMORY.md` / `memory/*.md` (source of truth)
2. Use `memory_search` / `memory_get` tools (vector search)
3. Respect pre-compaction memory flush cycle
4. Not fight compaction (summaries replace old context)
5. Work within workspace cwd (no external state stores)

**Integration surfaces:**
- Pre-compaction flush hook (write before summarize)
- Memory file watcher (auto-reindex on change)
- Extra paths for additional indexed content
- Sub-agents for background processing (stateless, cheap model)
- Cron for scheduled maintenance
