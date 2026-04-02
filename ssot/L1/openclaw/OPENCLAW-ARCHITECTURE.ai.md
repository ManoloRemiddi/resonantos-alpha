[AI-OPTIMIZED] ~350 tokens | src: openclaw/docs/concepts/architecture.md
Updated: 2026-02-14

# Gateway Architecture

**Last updated:** 2026-01-22

## Overview

- Single **Gateway** daemon owns all messaging (WhatsApp/Baileys, Telegram/grammY, Slack, Discord, Signal, iMessage, WebChat)
- Control clients (macOS app, CLI, web UI, automations) → WS on `127.0.0.1:18789` (default)
- **Nodes** (macOS/iOS/Android/headless) → same WS, declare `role: node` + caps/commands
- One Gateway/host; only place opening WhatsApp session
- Canvas host: `18793` (agent-editable HTML, A2UI)

## Components & Flows

### Gateway (daemon)
- Maintains provider connections
- Typed WS API: requests, responses, server-push events
- Schema validation (JSON Schema)
- Emits: `agent`, `chat`, `presence`, `health`, `heartbeat`, `cron`

### Clients (app/CLI/web)
- 1 WS conn/client
- Req: `health`, `status`, `send`, `agent`, `system-presence`
- Sub: `tick`, `agent`, `presence`, `shutdown`

### Nodes (macOS/iOS/Android/headless)
- Same WS, `role: node`
- Device identity in `connect`; device-based pairing (approval in pairing store)
- Commands: `canvas.*`, `camera.*`, `screen.record`, `location.get`
- [Protocol: Gateway protocol](/gateway/protocol)

### WebChat
- Static UI consuming WS API (chat history, sends)
- SSH/Tailscale tunnel in remote setups

## Connection Lifecycle (Single Client)

```
Client                    Gateway
  |------- req:connect ----->|
  |<------ res (ok) ---------|  (or error + close)
  |   (payload=hello-ok: snapshot with presence + health)
  |<------ event:presence ----|
  |<------ event:tick --------|
  |------- req:agent -------->|
  |<------ res:agent ---------|  (ack: {runId, status:"accepted"})
  |<------ event:agent -------|  (streaming)
  |<------ res:agent ---------|  (final: {runId, status, summary})
```

## Wire Protocol

- **Transport:** WS, text frames, JSON payloads
- **First frame:** must be `connect`
- **Format:**
  - Req: `{type:"req", id, method, params}` → `{type:"res", id, ok, payload|error}`
  - Event: `{type:"event", event, payload, seq?, stateVersion?}`
- **Auth:** `OPENCLAW_GATEWAY_TOKEN` (env/--token) → verify `connect.params.auth.token` or close
- **Idempotency:** required for side-effects (`send`, `agent`); server caches short-lived dedupe
- **Nodes:** include `role:"node"` + caps/commands/permissions in `connect`

## Pairing & Local Trust

- All WS clients → device identity on `connect`
- New device IDs → pairing approval + **device token** issued
- **Local** (loopback/tailnet address) → auto-approved for UX
- **Non-local** → sign `connect.challenge` nonce + explicit approval
- Gateway auth (`gateway.auth.*`) applies to all, local or remote
- [Details: Protocol](/gateway/protocol), [Pairing](/start/pairing), [Security](/gateway/security)

## Protocol Typing & Codegen

- TypeBox schemas → JSON Schema → Swift models

## Remote Access

- **Preferred:** Tailscale/VPN
- **Alt:** SSH tunnel: `ssh -N -L 18789:127.0.0.1:18789 user@host`
- Handshake + auth token apply over tunnel
- TLS + pinning available

## Operations

- **Start:** `openclaw gateway` (foreground, stdout)
- **Health:** WS `health` (in `hello-ok`)
- **Supervision:** launchd/systemd auto-restart

## Invariants

- 1 Gateway = 1 Baileys session/host
- Mandatory handshake; non-JSON/non-connect first frame = hard close
- Events not replayed; clients refresh on gaps
