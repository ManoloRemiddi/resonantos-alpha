[AI-OPTIMIZED] ~850 tokens | src: openclaw/docs/concepts/session.md
Updated: 2026-02-14

---
title: "Session Management"
---

# Session Management

OpenClaw treats **one direct-chat session per agent** as primary. Direct chats → `agent:<agentId>:<mainKey>` (default `main`). Groups/channels get own keys. `session.mainKey` honored.

## DM Scoping (session.dmScope)

- `main` (default): all DMs share main session (continuity)
- `per-peer`: isolate by sender id across channels
- `per-channel-peer`: isolate by channel + sender (recommended multi-user inboxes)
- `per-account-channel-peer`: isolate account + channel + sender (recommended multi-account inboxes)

Use `session.identityLinks` to map provider-prefixed peer ids to canonical identity → same person shares DM session across channels.

## Secure DM Mode (Required Multi-User Setups)

**Risk:** Without isolation, all users share same context → leak private info between users.

**Fix:** Set `dmScope: "per-channel-peer"` (or `per-account-channel-peer` for multi-account)

```json5
{
  session: { dmScope: "per-channel-peer" }
}
```

**Enable when:**
- Multiple pairing approvals
- Multi-entry DM allowlist
- `dmPolicy: "open"`
- Multiple phone numbers/accounts can message

**Verify:** `openclaw security audit`

## Gateway as Source of Truth

All session state owned by gateway. UI clients query gateway for sessions/token counts, not local files.

- Remote mode: session store on remote gateway host
- Token counts from gateway store: `inputTokens`, `outputTokens`, `totalTokens`, `contextTokens`

## State Locations

**Gateway host:**
- Store: `~/.openclaw/agents/<agentId>/sessions/sessions.json` (per agent)
- Transcripts: `~/.openclaw/agents/<agentId>/sessions/<SessionId>.jsonl`
- Telegram topics: `.../<SessionId>-topic-<threadId>.jsonl`
- Store map: `sessionKey → {sessionId, updatedAt, ...}`
- Group entries: `displayName`, `channel`, `subject`, `room`, `space`
- Session entries: `origin` metadata (label + routing)

Not read: legacy Pi/Tau session folders.

## Session Pruning & Compaction

- OpenClaw trims old tool results from in-memory context pre-LLM (doesn't rewrite JSONL)
- See [/concepts/session-pruning](/concepts/session-pruning)
- Pre-compaction: silent memory flush turn writes durable notes when workspace writable
- See [Memory](/concepts/memory), [Compaction](/concepts/compaction)

## Session Key Mapping

**Direct chats (follow session.dmScope):**
- `main`: `agent:<agentId>:<mainKey>` (default, cross-device/channel continuity)
- `per-peer`: `agent:<agentId>:dm:<peerId>`
- `per-channel-peer`: `agent:<agentId>:<channel>:dm:<peerId>`
- `per-account-channel-peer`: `agent:<agentId>:<channel>:<accountId>:dm:<peerId>` (accountId defaults `default`)
- `session.identityLinks` replaces `<peerId>` for canonical multi-channel sharing

**Group chats (isolated):**
- `agent:<agentId>:<channel>:group:<id>`
- Rooms/channels: `agent:<agentId>:<channel>:channel:<id>`
- Telegram topics: append `:topic:<threadId>`
- Legacy `group:<id>` still recognized

**Other sources:**
- Cron: `cron:<job.id>`
- Webhooks: `hook:<uuid>` (or explicitly set)
- Node runs: `node-<nodeId>`

## Lifecycle & Reset Policy

Reuse until expiry; expiry evaluated next inbound message.

**Daily reset** (default): 4:00 AM gateway local time. Session stale if last update before most recent reset.

**Idle reset** (optional): `idleMinutes` sliding window. When both set, **whichever expires first** wins.

**Legacy idle-only:** set `session.idleMinutes` w/o `session.reset`/`resetByType` → backward-compat idle-only mode.

**Per-type overrides:** `resetByType` for `dm`, `group`, `thread` (thread = Slack/Discord/Telegram topics/Matrix threads)

**Per-channel overrides:** `resetByChannel` for channel-specific policy (precedence over `reset`/`resetByType`)

**Manual triggers:**
- `/new` or `/reset`: fresh sessionId, pass remainder of message
- `/new <model>`: model alias, `provider/model`, or provider name (fuzzy) → set session model
- `/new` or `/reset` alone → short "hello" greeting confirms reset
- Delete keys from store or JSONL transcript → recreated next message
- Isolated cron always mints fresh `sessionId` per run

## Send Policy (Optional)

Block delivery by session type without listing ids:

```json5
{
  session: {
    sendPolicy: {
      rules: [
        { action: "deny", match: { channel: "discord", chatType: "group" } },
        { action: "deny", match: { keyPrefix: "cron:" } },
      ],
      default: "allow",
    },
  },
}
```

**Runtime override (owner):**
- `/send on` → allow
- `/send off` → deny
- `/send inherit` → clear override, use config rules
(Send as standalone)

## Configuration Example

```json5
{
  session: {
    scope: "per-sender",
    dmScope: "main",
    identityLinks: {
      alice: ["telegram:123456789", "discord:987654321012345678"],
    },
    reset: { mode: "daily", atHour: 4, idleMinutes: 120 },
    resetByType: {
      thread: { mode: "daily", atHour: 4 },
      dm: { mode: "idle", idleMinutes: 240 },
      group: { mode: "idle", idleMinutes: 120 },
    },
    resetByChannel: { discord: { mode: "idle", idleMinutes: 10080 } },
    resetTriggers: ["/new", "/reset"],
    store: "~/.openclaw/agents/{agentId}/sessions/sessions.json",
    mainKey: "main",
  },
}
```

## Inspecting Sessions

- `openclaw status` — store path, recent sessions
- `openclaw sessions --json` — dump all (filter `--active <minutes>`)
- `openclaw gateway call sessions.list --params '{}'` — fetch from running gateway (`--url`/`--token` for remote)
- `/status` (chat) — agent reachability, context usage, thinking/verbose toggles, WhatsApp cred refresh time
- `/context list|detail` (chat) — system prompt, injected files, contributors
- `/stop` (chat) — abort current run, clear queued followups, stop sub-agents (report count)
- `/compact` (chat) — summarize older context, free window space; see [/concepts/compaction](/concepts/compaction)
- JSONL transcripts open directly for full turn review

## Tips

- Keep primary key for 1:1 traffic; let groups keep own keys
- Cleanup: delete individual keys, not whole store (preserves context elsewhere)

## Session Origin Metadata

Each session records inbound source (best-effort) in `origin`:
- `label`: human label (from conversation/group subject/channel)
- `provider`: normalized channel id (inc. extensions)
- `from`/`to`: raw routing ids (inbound envelope)
- `accountId`: provider account id (multi-account)
- `threadId`: thread/topic id (when supported)

Connectors: send `ConversationLabel`, `GroupSubject`, `GroupChannel`, `GroupSpace`, `SenderName` in inbound context + call `recordSessionMetaFromInbound` or `updateLastRoute` to populate explainer metadata.
