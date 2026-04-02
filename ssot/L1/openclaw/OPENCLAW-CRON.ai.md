[AI-OPTIMIZED] ~2100 tokens | src: openclaw/docs/automation/cron-jobs.md
Updated: 2026-02-14

# Cron Jobs (Gateway scheduler)

**Cron vs Heartbeat:** See cron-vs-heartbeat guide for when to use each.

Cron is Gateway's built-in scheduler. Persists jobs, wakes agent at right time, optionally delivers output to chat.

Use: _"run this every morning"_ or _"poke the agent in 20 minutes"_

## Overview

- Runs inside Gateway (not inside model)
- Jobs persist at `~/.openclaw/cron/jobs.json`; restarts preserve schedules
- **Two execution styles:**
  - **Main session**: enqueue system event, run on next heartbeat
  - **Isolated**: dedicated agent turn in `cron:<jobId>`, w/ delivery (announce default or none)
- Wakeups first-class: job can request "wake now" vs "next heartbeat"

## Quick Start

One-shot reminder:
```bash
openclaw cron add \
  --name "Reminder" --at "2026-02-01T16:00:00Z" \
  --session main --system-event "Reminder: check cron docs" \
  --wake now --delete-after-run
openclaw cron list
openclaw cron run <job-id>
openclaw cron runs --id <job-id>
```

Recurring isolated job w/ delivery:
```bash
openclaw cron add \
  --name "Morning brief" --cron "0 7 * * *" --tz "America/Los_Angeles" \
  --session isolated --message "Summarize overnight updates." \
  --announce --channel slack --to "channel:C1234567890"
```

## Job Storage

`~/.openclaw/cron/jobs.json` (Gateway-managed). Manual edits only safe when Gateway stopped; use CLI/tool API instead.

## Concepts

### Jobs
- **schedule**: when to run
- **payload**: what to do
- **delivery**: announce or none (opt.)
- **agentId**: run under specific agent; fallback to default if missing (opt.)

Identified by stable `jobId`. One-shot jobs (`schedule.kind = "at"`) auto-delete after success (set `deleteAfterRun: false` to keep).

### Schedules (3 kinds)

- **at**: one-shot ISO 8601 timestamp (no tz → UTC)
- **every**: fixed interval (ms)
- **cron**: 5-field cron expr + opt. IANA tz (uses `croner`; omitted tz → Gateway host local tz)

### Execution Modes

#### Main Session (system events)
- `payload.kind = "systemEvent"` only
- `wakeMode: "now"` (default): event triggers immediate heartbeat
- `wakeMode: "next-heartbeat"`: event waits for next scheduled heartbeat
- Best fit for normal heartbeat prompt + main-session context

#### Isolated Sessions (dedicated cron runs)
- Run in session `cron:<jobId>` (fresh session id, no prior carry-over)
- Prompt prefixed: `[cron:<jobId> <job name>]`
- Default: `delivery.mode = "announce"` (if omitted)
- `delivery.mode`:
  - **announce**: summary to target channel + brief summary to main session
  - **none**: internal only (no delivery, no main-session summary)
- `wakeMode` (when main-session summary posts):
  - **now**: immediate heartbeat
  - **next-heartbeat**: waits for next scheduled heartbeat
- Use for noisy/frequent background chores that shouldn't spam main history

### Payload Shapes

**systemEvent** (main-only):
```json
{ "kind": "systemEvent", "text": "..." }
```

**agentTurn** (isolated-only):
- `message`: required text prompt
- `model`: opt. override (e.g., `anthropic/claude-sonnet-4-20250514` or alias `opus`)
- `thinking`: opt. override (off, minimal, low, medium, high, xhigh; GPT-5.2 + Codex only)
- `timeoutSeconds`: opt. timeout override

### Delivery Config (isolated jobs only)

```json
{
  "mode": "none" | "announce",
  "channel": "last | whatsapp | telegram | discord | slack | mattermost | signal | imessage",
  "to": "channel-specific target",
  "bestEffort": true
}
```

- **Announce flow**: uses isolated run's outbound payloads (text/media) w/ normal chunking & channel formatting
- **HEARTBEAT_OK skip**: heartbeat-only responses not delivered
- **Duplicate skip**: if isolated run already sent to same target via message tool, skip delivery
- **Invalid targets**: fail job unless `delivery.bestEffort = true`
- **Main-session summary**: posted only when `delivery.mode = "announce"`, respects `wakeMode`

### Model & Thinking Overrides

Isolated jobs can override:
- `model`: provider/model string or alias (e.g., `opus`)
- `thinking`: level (off, minimal, low, medium, high, xhigh; GPT-5.2 + Codex only)

Priority: job payload override > hook-specific defaults > agent config default

Note: Can set `model` on main-session jobs, but changes shared main session model; recommend overrides only for isolated jobs.

### Delivery Targets

- Slack/Discord/Mattermost: use prefixes (e.g. `channel:<id>`, `user:<id>`)
- Telegram topics: `-1001234567890:topic:123` (preferred explicit) or `-1001234567890:123` (shorthand)
- Also accept: `telegram:group:-1001234567890:topic:123`

## JSON Schema (Tool Calls)

### cron.add

One-shot, main session (system event):
```json
{
  "name": "Reminder",
  "schedule": { "kind": "at", "at": "2026-02-01T16:00:00Z" },
  "sessionTarget": "main",
  "wakeMode": "now",
  "payload": { "kind": "systemEvent", "text": "..." },
  "deleteAfterRun": true
}
```

Recurring, isolated w/ delivery:
```json
{
  "name": "Morning brief",
  "schedule": { "kind": "cron", "expr": "0 7 * * *", "tz": "America/Los_Angeles" },
  "sessionTarget": "isolated",
  "wakeMode": "next-heartbeat",
  "payload": { "kind": "agentTurn", "message": "..." },
  "delivery": {
    "mode": "announce",
    "channel": "slack",
    "to": "channel:C1234567890",
    "bestEffort": true
  }
}
```

**Notes:**
- `schedule.kind`: `at` (→ `at`), `every` (→ `everyMs`), or `cron` (→ `expr`, opt. `tz`)
- `schedule.at` ISO 8601; tz omitted → UTC
- `everyMs` milliseconds
- `sessionTarget`: "main" or "isolated"; must match `payload.kind`
- Opt. fields: `agentId`, `description`, `enabled`, `deleteAfterRun` (default true for `at`), `delivery`
- `wakeMode` defaults "now" when omitted

### cron.update

```json
{
  "jobId": "job-123",
  "patch": {
    "enabled": false,
    "schedule": { "kind": "every", "everyMs": 3600000 }
  }
}
```

Notes: `jobId` canonical; `id` accepted for compat. Use `agentId: null` to clear binding.

### cron.run & cron.remove

```json
{ "jobId": "job-123", "mode": "force" }
{ "jobId": "job-123" }
```

## CLI Examples

One-shot (UTC ISO, auto-delete):
```bash
openclaw cron add \
  --name "Send reminder" --at "2026-01-12T18:00:00Z" \
  --session main --system-event "Reminder: submit expense report." \
  --wake now --delete-after-run
```

One-shot relative time:
```bash
openclaw cron add \
  --name "Calendar check" --at "20m" \
  --session main --system-event "Next heartbeat: check calendar." \
  --wake now
```

Recurring isolated → WhatsApp:
```bash
openclaw cron add \
  --name "Morning status" --cron "0 7 * * *" --tz "America/Los_Angeles" \
  --session isolated --message "Summarize inbox + calendar for today." \
  --announce --channel whatsapp --to "+15551234567"
```

Recurring isolated → Telegram topic:
```bash
openclaw cron add \
  --name "Nightly summary (topic)" --cron "0 22 * * *" --tz "America/Los_Angeles" \
  --session isolated --message "Summarize today; send to nightly topic." \
  --announce --channel telegram --to "-1001234567890:topic:123"
```

Model & thinking override:
```bash
openclaw cron add \
  --name "Deep analysis" --cron "0 6 * * 1" --tz "America/Los_Angeles" \
  --session isolated --message "Weekly deep analysis of project progress." \
  --model "opus" --thinking high \
  --announce --channel whatsapp --to "+15551234567"
```

Agent selection (multi-agent):
```bash
openclaw cron add --name "Ops sweep" --cron "0 6 * * *" --session isolated --message "Check ops queue" --agent ops
openclaw cron edit <jobId> --agent ops
openclaw cron edit <jobId> --clear-agent
```

Manual run:
```bash
openclaw cron run <jobId>
openclaw cron run <jobId> --due
```

Edit job (patch):
```bash
openclaw cron edit <jobId> \
  --message "Updated prompt" --model "opus" --thinking low
```

Run history:
```bash
openclaw cron runs --id <jobId> --limit 50
```

Immediate system event (no job):
```bash
openclaw system event --mode now --text "Next heartbeat: check battery."
```

## Storage & History

- Job store: `~/.openclaw/cron/jobs.json` (Gateway-managed JSON)
- Run history: `~/.openclaw/cron/runs/<jobId>.jsonl` (JSONL, auto-pruned)
- Override: `cron.store` in config

## Configuration

```json5
{
  cron: {
    enabled: true,
    store: "~/.openclaw/cron/jobs.json",
    maxConcurrentRuns: 1,
  },
}
```

Disable: `cron.enabled: false` (config) or `OPENCLAW_SKIP_CRON=1` (env)

## Gateway API

- `cron.list`, `cron.status`, `cron.add`, `cron.update`, `cron.remove`
- `cron.run` (force or due), `cron.runs`

## Troubleshooting

**"Nothing runs"**
- Check enabled: `cron.enabled` + `OPENCLAW_SKIP_CRON`
- Gateway must run continuously
- Cron schedules: confirm `--tz` vs host timezone

**Telegram wrong destination**
- Use `-100…:topic:<id>` for forum topics (explicit, unambiguous)
- `telegram:...` prefixes in logs normal; cron parses correctly
