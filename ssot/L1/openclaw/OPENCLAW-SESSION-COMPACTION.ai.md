[AI-OPTIMIZED] ~1180 tokens | src: openclaw/docs/reference/session-management-compaction.md
Updated: 2026-02-14

---
summary: "Deep dive: session store + transcripts, lifecycle, and (auto)compaction internals"
read_when:
  - Debug session ids, transcript JSONL, or sessions.json fields
  - Changing auto-compaction behavior or "pre-compaction" housekeeping
  - Implementing memory flushes or silent system turns
title: "Session Management Deep Dive"
---

# Session Management & Compaction (Deep Dive)

**Overview:** Session routing → session store (`sessions.json`) → transcript persistence (`*.jsonl`) → transcript hygiene → context limits → compaction (manual + auto) → silent housekeeping.

For higher-level intro: [/concepts/session](/concepts/session), [/concepts/compaction](/concepts/compaction), [/concepts/session-pruning](/concepts/session-pruning), [/reference/transcript-hygiene](/reference/transcript-hygiene).

---

## Gateway authority

OpenClaw: single **Gateway process** owns session state. UIs query Gateway for session lists + token counts. Remote mode: session files on remote host.

---

## Persistence layers

1. **Session store (`sessions.json`)**
   - Key/value: `sessionKey → SessionEntry`
   - Small, mutable, safe to edit/delete
   - Tracks metadata, toggles, token counters

2. **Transcript (`<sessionId>.jsonl`)**
   - Append-only, tree structure (id + parentId)
   - Conversation, tool calls, compaction summaries
   - Rebuilds model context for future turns

---

## On-disk locations

- Store: `~/.openclaw/agents/<agentId>/sessions/sessions.json`
- Transcripts: `~/.openclaw/agents/<agentId>/sessions/<sessionId>.jsonl`
  - Telegram topics: `.../<sessionId>-topic-<threadId>.jsonl`

Config: `src/config/sessions.ts`

---

## Session keys (`sessionKey`)

Routing + isolation patterns:
- Main: `agent:<agentId>:<mainKey>` (default `main`)
- Group: `agent:<agentId>:<channel>:group:<id>`
- Channel: `agent:<agentId>:<channel>:channel:<id>` or `...:room:<id>`
- Cron: `cron:<job.id>`
- Webhook: `hook:<uuid>` (or overridden)

Details: [/concepts/session](/concepts/session)

---

## Session ids (`sessionId`)

Per `sessionKey`, points to current transcript file.

Rules:
- **Reset** (`/new`, `/reset`): new `sessionId` for that `sessionKey`
- **Daily reset** (default 4:00 AM local Gateway time): new `sessionId` on next msg after boundary
- **Idle expiry** (`session.reset.idleMinutes` or legacy `session.idleMinutes`): new `sessionId` after idle window. First to expire wins.

Implementation: `initSessionState()` in `src/auto-reply/reply/session.ts`

---

## Session store schema (`SessionEntry`, `src/config/sessions.ts`)

Key fields:
- `sessionId`: current transcript id
- `updatedAt`: last activity timestamp
- `sessionFile`: optional explicit transcript path override
- `chatType`: `direct | group | room`
- `provider`, `subject`, `room`, `space`, `displayName`: group/channel metadata
- Toggles: `thinkingLevel`, `verboseLevel`, `reasoningLevel`, `elevatedLevel`, `sendPolicy`
- Model: `providerOverride`, `modelOverride`, `authProfileOverride`
- Token counters: `inputTokens`, `outputTokens`, `totalTokens`, `contextTokens`
- `compactionCount`: auto-compaction completions
- `memoryFlushAt`: pre-compaction memory flush timestamp
- `memoryFlushCompactionCount`: compaction count at last flush

Store safe to edit; Gateway is authority (may rewrite/rehydrate).

---

## Transcript structure (`*.jsonl`)

Managed by `@mariozechner/pi-coding-agent`'s `SessionManager`. JSONL:

- Line 1: header (`type: "session"`, id, cwd, timestamp, optional `parentSession`)
- Rest: entries with `id` + `parentId` (tree)

Entry types:
- `message`: user/assistant/toolResult
- `custom_message`: extension-injected, enters context
- `custom`: extension state, skips context
- `compaction`: persisted summary (firstKeptEntryId, tokensBefore)
- `branch_summary`: summary when navigating branch

OpenClaw: no transcript fixup; uses `SessionManager` read/write.

---

## Context windows vs tracked tokens

**Model context window:** hard cap per model (visible to model).
**Session counters:** runtime estimates in `sessions.json` (for /status + dashboards).

- Context window: from catalog + override via config
- `contextTokens`: estimate; not strict guarantee

Details: [/token-use](/token-use)

---

## Compaction mechanics

Summarizes older conversation → persisted `compaction` entry. Future turns see:
- Compaction summary
- Messages after `firstKeptEntryId`

**Persistent** (unlike session pruning). See [/concepts/session-pruning](/concepts/session-pruning).

---

## Auto-compaction triggers (Pi runtime)

1. **Overflow recovery:** model returns context overflow → compact → retry
2. **Threshold maintenance:** after successful turn:
   ```
   contextTokens > contextWindow - reserveTokens
   ```
   - `contextWindow`: model context limit
   - `reserveTokens`: headroom for prompts + next output

Pi decides timing; OpenClaw consumes events.

---

## Compaction config (`reserveTokens`, `keepRecentTokens`)

Pi settings:
```json5
{
  compaction: {
    enabled: true,
    reserveTokens: 16384,
    keepRecentTokens: 20000,
  },
}
```

OpenClaw safety floor (embedded runs):
- If `compaction.reserveTokens < reserveTokensFloor` → bump it
- Default floor: `20000` tokens
- Disable: `agents.defaults.compaction.reserveTokensFloor: 0`
- Higher values: OpenClaw leaves alone

Rationale: headroom for multi-turn housekeeping (memory writes) before compaction forced.

Implementation: `ensurePiCompactionReserveTokens()` in `src/agents/pi-settings.ts` (called from `src/agents/pi-embedded-runner.ts`).

---

## User-facing surfaces

- `/status` (in chat)
- `openclaw status` (CLI)
- `openclaw sessions` / `sessions --json`
- Verbose: `🧹 Auto-compaction complete` + compaction count

---

## Silent housekeeping (`NO_REPLY`)

Assistant starts output with `NO_REPLY` → OpenClaw suppresses reply to user.

As of `2026.1.10`: suppresses draft/typing streaming when chunk starts with `NO_REPLY` (silent ops don't leak partial output).

---

## Pre-compaction memory flush (implemented)

Before auto-compaction: run silent agentic turn to write durable state (e.g. `memory/YYYY-MM-DD.md`) so compaction can't erase critical context.

**Pre-threshold flush approach:**
1. Monitor context usage
2. Cross "soft threshold" (below Pi threshold) → run silent "write memory" directive
3. Use `NO_REPLY` to suppress user visibility

Config (`agents.defaults.compaction.memoryFlush`):
- `enabled` (default: `true`)
- `softThresholdTokens` (default: `4000`)
- `prompt` (flush turn message)
- `systemPrompt` (extra system prompt, includes `NO_REPLY` hint)

Notes:
- Runs once per compaction cycle (tracked in `sessions.json`)
- Embedded Pi only (CLI backends skip)
- Skipped if workspace read-only (`workspaceAccess: "ro"` or `"none"`)
- See [Memory](/concepts/memory) for workspace layout + write patterns

Pi exposes `session_before_compact` hook in extension API; OpenClaw flush logic: Gateway-side.

---

## Troubleshooting

- Wrong session key? Check `sessionKey` in `/status` → [/concepts/session](/concepts/session)
- Store vs transcript mismatch? Confirm Gateway host + store path from `openclaw status`
- Compaction spam? Check:
  - Model context window (too small?)
  - Compaction settings (`reserveTokens` vs window)
  - Tool-result bloat: tune session pruning
- Silent turns leaking? Confirm reply starts with exact `NO_REPLY` + on build with streaming suppression fix
