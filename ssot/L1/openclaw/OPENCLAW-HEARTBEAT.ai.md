[AI-OPTIMIZED] ~950 tokens | src: openclaw/docs/gateway/heartbeat.md
Updated: 2026-02-14

# Heartbeat (Gateway)

Periodic agent turns in main session to surface needs without spam. See [Cron vs Heartbeat](/automation/cron-vs-heartbeat) for task scheduling guidance.

## Quick Start

1. Enable heartbeats (default: `30m`, or `1h` for OAuth/setup-token)
2. Create optional `HEARTBEAT.md` checklist in workspace
3. Set delivery target (`target: "last"` default)
4. Optional: enable reasoning delivery & active hours

Config:
```json5
{
  agents: {
    defaults: {
      heartbeat: {
        every: "30m",
        target: "last",
        // activeHours: { start: "08:00", end: "24:00" },
        // includeReasoning: true,
      },
    },
  },
}
```

## Defaults

- **Interval**: `30m` (or `1h` w/ OAuth). Set via `agents.defaults.heartbeat.every` or per-agent `agents.list[].heartbeat.every`; `0m` = disabled
- **Prompt** (default):
  ```
  Read HEARTBEAT.md if it exists (workspace context). Follow it strictly. Do not infer or repeat old tasks from prior chats. If nothing needs attention, reply HEARTBEAT_OK.
  ```
- Prompt sent verbatim; system prompt includes "Heartbeat" section & internal flag
- Active hours checked in configured timezone; outside window, skipped until next tick

## Purpose

- **Background tasks**: nudges agent to review inbox, calendar, reminders, queued work; surface urgent items
- **Check-in**: lightweight "anything you need?" during daytime; avoids night spam via local timezone
- **Custom prompt**: set `agents.defaults.heartbeat.prompt` or `agents.list[].heartbeat.prompt` for specific tasks (e.g. "check Gmail stats", "verify gateway health")

## Response Contract

- **No action needed**: reply `HEARTBEAT_OK`
- During heartbeat, `HEARTBEAT_OK` at **start or end** is ack'd; stripped & dropped if remaining ≤ `ackMaxChars` (default: 300)
- **Middle of reply**: not treated specially
- **Alerts**: return only alert text; do NOT include `HEARTBEAT_OK`
- Outside heartbeat: stray `HEARTBEAT_OK` stripped & logged; message-only `HEARTBEAT_OK` dropped

## Config Reference

```json5
{
  agents: {
    defaults: {
      heartbeat: {
        every: "30m", // duration: 0m disables
        model: "anthropic/claude-opus-4-6", // optional override
        includeReasoning: false, // deliver separate Reasoning: message
        target: "last", // last | none | channel id (telegram, whatsapp, etc.)
        to: "+15551234567", // optional channel-specific recipient
        accountId: "ops-bot", // multi-account channels
        prompt: "...", // custom prompt (not merged)
        ackMaxChars: 300,
      },
    },
  },
}
```

### Scope & Precedence

- `agents.defaults.heartbeat`: global behavior
- `agents.list[].heartbeat`: merges on top; if present, **only those agents** run heartbeats
- `channels.defaults.heartbeat`: channel visibility defaults
- `channels.<channel>.heartbeat`: channel override
- `channels.<channel>.accounts.<id>.heartbeat`: multi-account override

### Per-Agent Example

Two agents; only second runs heartbeats:
```json5
{
  agents: {
    defaults: { heartbeat: { every: "30m", target: "last" } },
    list: [
      { id: "main", default: true },
      {
        id: "ops",
        heartbeat: {
          every: "1h",
          target: "whatsapp",
          to: "+15551234567",
          prompt: "Read HEARTBEAT.md...",
        },
      },
    ],
  },
}
```

### Active Hours Example

Business hours in specific timezone:
```json5
{
  agents: {
    defaults: {
      heartbeat: {
        every: "30m",
        target: "last",
        activeHours: {
          start: "09:00",
          end: "22:00",
          timezone: "America/New_York", // optional; falls back to userTimezone or host tz
        },
      },
    },
  },
}
```

Outside window (before 9am or after 10pm ET), heartbeats skipped; next tick in window runs normally.

### Multi-Account Example

Target specific account (Telegram, etc.):
```json5
{
  agents: {
    list: [
      {
        id: "ops",
        heartbeat: {
          every: "1h",
          target: "telegram",
          to: "12345678",
          accountId: "ops-bot",
        },
      },
    ],
  },
  channels: {
    telegram: {
      accounts: {
        "ops-bot": { botToken: "YOUR_TELEGRAM_BOT_TOKEN" },
      },
    },
  },
}
```

### Field Reference

| Field | Notes |
|-------|-------|
| `every` | Duration string (default unit: min); `0m` disables |
| `model` | Optional override (`provider/model`) |
| `includeReasoning` | Deliver separate `Reasoning:` message when available |
| `session` | Session key for heartbeat runs: `main` (default), or explicit key (see [Sessions](/concepts/session)) |
| `target` | `last` (default), explicit channel (`whatsapp`/`telegram`/`discord`/etc.), or `none` (run but don't deliver) |
| `to` | Optional recipient (channel-specific id: E.164 for WhatsApp, chat id for Telegram, etc.) |
| `accountId` | Multi-account channel account id; applies if target resolves to that channel; ignored if unmatched |
| `prompt` | Override default prompt body (not merged) |
| `ackMaxChars` | Max chars after `HEARTBEAT_OK` before delivery (default: 300) |
| `activeHours` | Time window: `start` (HH:MM inclusive), `end` (HH:MM exclusive; `24:00` allowed), `timezone` (optional: IANA id, `"user"`, `"local"`) |

Timezone resolution:
- Omitted/`"user"`: `agents.defaults.userTimezone` if set, else host tz
- `"local"`: host system tz
- IANA id (e.g. `America/New_York`): used directly; invalid → fallback to `"user"`

## Delivery

- Runs in agent's main session by default (`agent:<id>:<mainKey>`) or `global` if `session.scope = "global"`
- `session` affects run context; `target` + `to` control delivery
- With `target: "last"`, uses last external channel for that session
- If main queue busy, heartbeat skipped & retried
- If `target` resolves to no destination, run happens but no outbound message
- Heartbeat-only replies don't keep session alive; `updatedAt` restored for normal idle expiry

## Visibility Controls

```yaml
channels:
  defaults:
    heartbeat:
      showOk: false # Hide HEARTBEAT_OK (default)
      showAlerts: true # Show alerts (default)
      useIndicator: true # Emit indicator events (default)
  telegram:
    heartbeat:
      showOk: true # Show OKs on Telegram
  whatsapp:
    accounts:
      work:
        heartbeat:
          showAlerts: false # Suppress alerts for this account
```

**Precedence**: per-account → per-channel → channel defaults → built-in

| Flag | Effect |
|------|--------|
| `showOk` | Send `HEARTBEAT_OK` acknowledgment for OK-only replies |
| `showAlerts` | Send alert content for non-OK replies |
| `useIndicator` | Emit indicator events for UI status |

If all three false, heartbeat run skipped (no model call).

### Common Patterns

| Goal | Config |
|------|--------|
| Default (silent OKs, alerts on) | _(no config)_ |
| Fully silent (no messages/indicator) | `channels.defaults.heartbeat: { showOk: false, showAlerts: false, useIndicator: false }` |
| Indicator-only | `channels.defaults.heartbeat: { showOk: false, showAlerts: false, useIndicator: true }` |
| OKs in one channel only | `channels.telegram.heartbeat: { showOk: true }` |

## HEARTBEAT.md (Optional)

- Agent reads it if present; acts as "heartbeat checklist"
- Small, stable, safe for ~30m intervals
- If effectively empty (blank lines + headers only), heartbeat skipped to save API calls
- Missing file: heartbeat runs; model decides action

Example:
```md
# Heartbeat checklist

- Scan: anything urgent in inboxes?
- Daytime: lightweight check-in if nothing pending
- Blocked tasks: note what's missing; ask Peter next time
```

### Agent Updates HEARTBEAT.md

Yes — normal file in workspace. Tell agent in chat:
- "Update `HEARTBEAT.md` to add daily calendar check"
- "Rewrite `HEARTBEAT.md` shorter, focused on inbox follow-ups"

Or include in custom prompt: "If checklist becomes stale, update HEARTBEAT.md with better one."

**⚠️ No secrets** (API keys, phone numbers, tokens) in `HEARTBEAT.md` — becomes prompt context.

## Manual Wake

Trigger immediate heartbeat:
```bash
openclaw system event --text "Check for urgent follow-ups" --mode now
```

If multiple agents have `heartbeat` configured, all run immediately.

Use `--mode next-heartbeat` to wait for next scheduled tick.

## Reasoning Delivery

Default: final "answer" payload only.

Enable transparency:
- `agents.defaults.heartbeat.includeReasoning: true`

Delivers separate `Reasoning:` message (same format as `/reasoning on`). Useful for multi-session/codex debugging; can leak internal detail in group chats. Keep off in shared contexts.

## Cost Awareness

- Full agent turns; shorter intervals burn more tokens
- Keep `HEARTBEAT.md` small
- Consider cheaper `model` or `target: "none"` for internal-only updates
