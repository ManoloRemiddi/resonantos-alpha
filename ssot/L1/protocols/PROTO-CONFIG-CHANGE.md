# PROTO-CONFIG-CHANGE — Configuration Change Protocol

> **Trigger keywords:** config, openclaw.json, heartbeat model, provider, auth-profiles
> **Level:** L1(P) — Protocol
> **Enforcement:** R-Awareness injection + Shield Gate HARD BLOCK

---

## Rules (ABSOLUTE)

1. **NEVER edit `openclaw.json` directly** — not via python3, not via node, not via sed, not via any exec command. The file is protected.
2. **ALWAYS use `gateway config.patch`** for config changes. If it rejects the change, the change is invalid. Do not bypass validation.
3. **NEVER edit `auth-profiles.json` directly** — use `openclaw configure` or the proper CLI.
4. **If config.patch rejects a change:** STOP. Investigate why. The schema is telling you something. Do not work around it.

## Config Change Procedure

```
1. Read current config:     gateway config.get
2. Plan the change:         Identify exact JSON path and value
3. Apply via patch:         gateway config.patch with the change
4. If rejected:             STOP. Read the error. Ask Manolo if unclear.
5. If accepted:             Gateway auto-restarts. Verify with config.get.
6. Test:                    Verify the change works (e.g., trigger heartbeat)
```

## Model Registration

To add a new model to OpenClaw:
- Add it to `agents.defaults.models` via `gateway config.patch`
- If the provider needs auth, use `openclaw configure` for credentials
- NEVER assume a provider supports arbitrary models — check forward-compat first

## Heartbeat Model Constraints

| Provider | Allowed for heartbeat? | Reason |
|----------|----------------------|--------|
| `anthropic/*` | NO | Burns subscription tokens |
| `openai-codex/gpt-5.3-codex` | YES (but expensive for heartbeat) | Free via Pro |
| `google/gemini-*` | YES | Free tier / cheap |
| `ollama/*` | YES (if capable) | Local, free |

## WHY This Protocol Exists

2026-02-24: Bypassed config.patch validation by writing openclaw.json directly via python3. Crashed the gateway. Used anthropic/haiku for heartbeat, burning subscription tokens. Both were avoidable.
