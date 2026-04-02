# Targeted commands to fully detect local OpenClaw instances (Windows)

Goal: collect *complete* install metadata for each local instance (service, user-mode, docker) without blind disk crawls.

## 0) Baseline: runtime identity
```powershell
$env:COMPUTERNAME
whoami
$PSVersionTable.PSVersion
node -v
```

## 1) PATH probe (user-mode installs)
```powershell
where.exe openclaw
Get-Command openclaw -ErrorAction SilentlyContinue | Format-List Path,Source,Version
```

## 2) Windows service probe (service installs)
```powershell
Get-CimInstance Win32_Service | Where-Object { $_.Name -match 'OpenClaw|openclaw' -or $_.DisplayName -match 'OpenClaw|openclaw' } |
  Select-Object Name,DisplayName,State,StartMode,ProcessId,PathName |
  Format-List
```

## 3) Process probe (all running instances)
```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -match 'OpenClaw|openclaw|node.exe|docker.exe' -and ($_.CommandLine -match 'openclaw' -or $_.CommandLine -match 'entry\.js' -or $_.CommandLine -match 'openclaw-gateway') } |
  Select-Object ProcessId,Name,CommandLine |
  Format-List
```

## 4) Docker probe (containerized instances)
```powershell
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
# For each candidate container:
docker inspect <name> --format "{{json .Mounts}}"
docker logs --tail 200 <name>
```

## 5) Targeted config probes (from discovered roots)
### Service install (ProgramData)
```powershell
$paths=@(
  'C:\\ProgramData\\OpenClaw\\Gateway\\config\\openclaw.json',
  'C:\\ProgramData\\OpenClaw\\Gateway\\.openclaw\\openclaw.json',
  'C:\\ProgramData\\openclaw\\openclaw.json',
  'C:\\ProgramData\\OpenClaw\\openclaw.json'
)
$paths | ForEach-Object { if(Test-Path $_){ "FOUND: $_" } }
```

### Docker Helm instance (compose + mounts)
```powershell
# Host-side (example path, adjust per instance):
Get-Content 'D:\\openclaw\\instances\\helm\\docker-compose.yml' -Raw
Get-Content 'D:\\openclaw\\instances\\helm\\secrets\\secrets.env' -Raw
# Container-side:
docker exec openclaw-helm bash -lc "ls -la /home/node/.openclaw; cat /home/node/.openclaw/openclaw.json | head -n 60"
```

## 6) Extract core fields needed by ResonantOS installer
From each instance config JSON:
- gateway port/bind (`gateway.port`, `gateway.bind`)
- auth mode (`gateway.auth.mode`)
- discord bot configured + allowed channels (`channels.discord.*`)
- workspace path (service may not have one)
- models/providers (for OAuth vs API-key distinctions)

PowerShell quick extract:
```powershell
$cfg='C:\\ProgramData\\OpenClaw\\Gateway\\config\\openclaw.json'
if(Test-Path $cfg){
  $j=Get-Content $cfg -Raw | ConvertFrom-Json
  $j.gateway | Format-List
  $j.channels.discord | ConvertTo-Json -Depth 6
}
```

## Notes from latest V3 run on this machine
- V3 ran under **SYSTEM** (service_account) and successfully detected multiple config hits under ProgramData.
- It also detected running gateway processes at ports **18790** and **18890**.
- The current blocker reported by the detector is: `openclaw_attach_fields_incomplete`.
