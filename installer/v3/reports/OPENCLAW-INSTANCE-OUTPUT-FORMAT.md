# OpenClaw Instance Output Format (Desired)

This document defines the **target human-readable output format** for the ResonantOS installer detector when reporting discovered OpenClaw instances.

## Target format (example)

The detector should print one block per instance, like this:

```
Openclaw Instance:
InstanceName: Atlas
RuntimeType: Windows Service
Config: C:\ProgramData\OpenClaw\Gateway\.openclaw\openclaw.json
Workspace: C:\Users\sambr\clawd
Gateway:18790 (200 OK)
ResonantOS: Installed
```

## Notes / constraints

- The **exact values** above are specific to the *Atlas* instance on this Windows host.
- The detector should also report additional instances (e.g. Docker-based, user-mode installs), but:
  - Their `RuntimeType`, `Config`, `Workspace`, `Gateway` port/health, and `ResonantOS` status will differ.
- When run in a **different environment**:
  - Inside Docker (e.g. Helm): paths will be Linux/container paths and runtime should reflect `docker_container`.
  - On VPS (e.g. Anvil): runtime should reflect Linux/systemd; paths will be `/home/openclaw/...`.

## Field semantics

- `InstanceName`: a stable, human-friendly name when it can be derived (e.g. from identity/config); otherwise `Unknown`.
- `RuntimeType`: one of (examples):
  - `Windows Service`
  - `Windows User`
  - `Docker Container`
  - `Linux systemd`
- `Config`: absolute path to the authoritative `openclaw.json` for the instance.
- `Workspace`: absolute path to the instance workspace if discoverable; otherwise `n/a`.
- `Gateway:<port> (<health>)`:
  - `<port>` is the gateway port the instance is bound to.
  - `<health>` is the result of an actual health probe (e.g. `200 OK`), or an error/timeout string.
- `ResonantOS`: `Installed` / `Not Installed` / `Unknown` (based on detectable signals).
