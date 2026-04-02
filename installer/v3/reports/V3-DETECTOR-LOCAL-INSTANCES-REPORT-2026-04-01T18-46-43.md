# V3 Detector — Local Instances Report (2026-04-01T18-46-43)

## Goal
Produce stable, targeted instance detection (3 local instances) without broad disk crawls; output in a consistent per-instance block format suitable for ResonantOS installer guidance.

## Environment
- Host: DESKTOP-VE5AREB
- OS: Windows
- Node: v24.11.1
- Docker: 29.2.1

## Issues encountered
- V2 tester (`v2/tester/run-detector-tests.js`) intermittently hung with no output on Windows when Docker engine was unhealthy/unresponsive (blocking docker probe; no timeout).
- V3 detector output originally over-counted instances by listing multiple ProgramData config variants/backups as separate instances (needs de-dupe by canonical config root).
- BackupGateway: process probe found a running gateway (`node ... entry.js gateway --port 18890`) but did not discover config path without additional logic.

## Patches / mitigations applied
1) Deterministic Windows run: ran detector with Docker removed from PATH to fast-fail Docker checks when needed.
2) Added bounded resolver helper (script) to map a gateway process command line → nearby openclaw.json candidates.
   - Script: `v3/scripts/resolve-openclaw-config-from-process.js`
   - Tested: resolves `D:\\openclaw-backup\\gateway\\.openclaw\\openclaw.json` using only 30 candidate checks.

## Current instance findings
`	ext
Openclaw Instance:
InstanceName: Atlas
RuntimeType: Windows Service
Config: C:\ProgramData\OpenClaw\Gateway\config\openclaw.json
Workspace: C:\Users\sambr\clawd
Gateway:18790 (200 OK)
ResonantOS: Installed (repo present; dashboard :19200 returns 200)

Openclaw Instance:
InstanceName: Helm
RuntimeType: Docker Container (openclaw-helm)
Config: D:\openclaw\instances\helm\state\openclaw.json (mounted to /home/node/.openclaw/openclaw.json)
Workspace: D:\openclaw\instances\helm\workspace
Gateway:18810 (200 OK)
ResonantOS: Unknown (not inferred for container yet)

Openclaw Instance:
InstanceName: BackupGateway
RuntimeType: Windows User (node.exe)
Config: D:\openclaw-backup\gateway\.openclaw\openclaw.json
Workspace: n/a (derive from config once parsed)
Gateway:18890 (200 OK)
ResonantOS: Unknown
`

## Next patches
- Integrate the resolver directly into 3/detector-cli.js so BackupGateway config is auto-resolved.
- Add hard timeouts to docker probes to prevent hangs.
- Improve de-dupe logic (canonicalize ProgramData config variants).
