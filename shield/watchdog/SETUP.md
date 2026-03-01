# Watchdog Setup — Emergency Recovery System

## Architecture

```
┌─────────────────────────────────────┐
│     Mac Mini (Orchestrator)         │
│     Health Sensors (9 checks)       │
│     Watchdog Handler (SSH target)   │
│     watchdog user (no shell)        │
├─────────────────────────────────────┤
│         ↕ Direct Ethernet           │
├─────────────────────────────────────┤
│     BeeAMD (Watchdog Node)          │
│     Watchdog Client (5-min cycle)   │
│     Checks → Restarts → Alerts     │
└─────────────────────────────────────┘
```

## Security Model

| Control | Implementation |
|---------|---------------|
| SSH access | `restrict,command=,from=10.0.0.1` — single script, single IP |
| User | `watchdog` — no shell, no home dir access to augmentor |
| sudoers | ONLY `launchctl bootstrap/bootout` for OpenClaw services |
| Data access | ZERO — cannot read wallet, config, memory, or any user files |
| Blast radius | Full BeeAMD compromise = can restart OpenClaw gateway. That's it. |

## Mac Mini Setup (requires sudo)

Run these commands on the Mac Mini:

### 1. Create watchdog user
```bash
# Create user with no shell access
sudo dscl . -create /Users/watchdog
sudo dscl . -create /Users/watchdog UserShell /usr/bin/false
sudo dscl . -create /Users/watchdog UniqueID 599
sudo dscl . -create /Users/watchdog PrimaryGroupID 20
sudo dscl . -create /Users/watchdog NFSHomeDirectory /var/empty

# Create .ssh dir owned by root (prevents the user from modifying authorized_keys)
sudo mkdir -p /var/empty/.ssh
sudo chmod 700 /var/empty/.ssh
sudo chown root:wheel /var/empty/.ssh
```

### 2. Generate SSH key on BeeAMD
```powershell
# Run this on BeeAMD (Windows)
ssh-keygen -t ed25519 -N "" -C "watchdog@BeeAMD" -f "$env:USERPROFILE\.ssh\watchdog_ed25519"
# Display public key
Get-Content "$env:USERPROFILE\.ssh\watchdog_ed25519.pub"
```

### 3. Add restricted key to Mac Mini
```bash
# Replace <PUBKEY> with the output from step 2
HANDLER_PATH="/Users/augmentor/resonantos-augmentor/shield/watchdog/watchdog-handler.sh"

sudo bash -c "echo 'restrict,command=\"${HANDLER_PATH}\",from=\"10.0.0.2\" <PUBKEY>' > /var/empty/.ssh/authorized_keys"
sudo chmod 600 /var/empty/.ssh/authorized_keys
sudo chown root:wheel /var/empty/.ssh/authorized_keys
```

### 4. Configure sudoers for watchdog
```bash
# Allow watchdog to restart OpenClaw services (and NOTHING else)
sudo bash -c 'cat > /etc/sudoers.d/watchdog << EOF
# Watchdog user — can only restart OpenClaw launchd services
watchdog ALL=(augmentor) NOPASSWD: /bin/launchctl bootout gui/*/ai.openclaw.gateway
watchdog ALL=(augmentor) NOPASSWD: /bin/launchctl bootstrap gui/* /Users/augmentor/Library/LaunchAgents/ai.openclaw.gateway.plist
watchdog ALL=(augmentor) NOPASSWD: /bin/launchctl bootout gui/*/ai.openclaw.node
watchdog ALL=(augmentor) NOPASSWD: /bin/launchctl bootstrap gui/* /Users/augmentor/Library/LaunchAgents/ai.openclaw.node.plist
EOF'
sudo chmod 440 /etc/sudoers.d/watchdog
sudo visudo -cf /etc/sudoers.d/watchdog  # Validate syntax
```

### 5. Configure sshd for watchdog access
```bash
# Add to /etc/ssh/sshd_config (or sshd_config.d/ if supported)
sudo bash -c 'cat >> /etc/ssh/sshd_config << EOF

# Watchdog user — restricted SSH access for health monitoring
Match User watchdog
    AuthorizedKeysFile /var/empty/.ssh/authorized_keys
    ForceCommand /Users/augmentor/resonantos-augmentor/shield/watchdog/watchdog-handler.sh
    AllowTcpForwarding no
    X11Forwarding no
    PermitTTY no
    AllowAgentForwarding no
EOF'
# Restart sshd
sudo launchctl stop com.openssh.sshd
sudo launchctl start com.openssh.sshd
```

### 6. Test from BeeAMD
```powershell
# Should return health JSON
ssh -i "$env:USERPROFILE\.ssh\watchdog_ed25519" -o BatchMode=yes watchdog@10.0.0.1 health

# Should return version info
ssh -i "$env:USERPROFILE\.ssh\watchdog_ed25519" -o BatchMode=yes watchdog@10.0.0.1 version

# Should be BLOCKED (no shell access)
ssh -i "$env:USERPROFILE\.ssh\watchdog_ed25519" -o BatchMode=yes watchdog@10.0.0.1 "cat /etc/passwd"
```

## BeeAMD Setup (Windows)

### 1. Copy watchdog client
```powershell
# Create watchdog directory
New-Item -ItemType Directory -Path "$env:USERPROFILE\watchdog" -Force

# Copy the script (from Mac Mini or download from alpha repo)
# The script should already be at shield/watchdog/watchdog-client.ps1
```

### 2. Configure Telegram alerts (optional)
Create `$env:USERPROFILE\watchdog\config.json`:
```json
{
    "orchestratorIP": "10.0.0.1",
    "sshUser": "watchdog",
    "sshKey": "C:\\Users\\danze\\.ssh\\watchdog_ed25519",
    "telegramBotToken": "<YOUR_BOT_TOKEN>",
    "telegramChatId": "<YOUR_CHAT_ID>",
    "maxRestartAttempts": 3
}
```

### 3. Create Scheduled Task
```powershell
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$env:USERPROFILE\watchdog\watchdog-client.ps1`""
$trigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Minutes 5) -Once -At (Get-Date)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "OpenClaw-Watchdog" -Action $action -Trigger $trigger -Settings $settings -Description "Monitors OpenClaw orchestrator health"
```

### 4. Verify
```powershell
# Manual run
powershell.exe -File "$env:USERPROFILE\watchdog\watchdog-client.ps1"

# Check scheduled task
Get-ScheduledTask -TaskName "OpenClaw-Watchdog" | Format-List
```

## Sensor Reference

| Sensor | Checks | Critical When |
|--------|--------|---------------|
| gateway_process | `openclaw-gateway` process exists | Process not running |
| gateway_http | HTTP 200 on /api/health | Connection refused/timeout |
| launchagent | LaunchAgent loaded | Service not registered |
| disk_space | Available GB on / | < 5 GB free |
| memory | System-wide free % | < 10% free |
| network | DNS + HTTPS to api.anthropic.com | DNS resolution fails |
| node_tunnel | BeeAMD reachable + SSH tunnel | (informational only) |
| openclaw_config | JSON validity of openclaw.json | Invalid JSON |
| extensions | Syntax check all .js extensions | (informational only) |

## Watchdog Actions

| Overall Status | Action |
|----------------|--------|
| ok | Log, reset counters |
| degraded | Log warnings, monitor (no restart) |
| critical (gateway) | Attempt restart (up to 3x), then alert |
| critical (other) | Alert immediately |
| unreachable | Alert after 6 consecutive failures |

## Files

| File | Location | Purpose |
|------|----------|---------|
| health-sensors.sh | Mac Mini: shield/watchdog/ | 9 diagnostic sensors (JSON/human) |
| watchdog-handler.sh | Mac Mini: shield/watchdog/ | SSH forced-command handler |
| watchdog-client.ps1 | BeeAMD: ~/watchdog/ | Monitoring client (PowerShell) |
| SETUP.md | shield/watchdog/ | This file |
