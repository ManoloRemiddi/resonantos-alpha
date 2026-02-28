# Pre-Flight Checks

Run ALL four categories before attempting installation. Each check must PASS.

## 1. OS-Specific Issues

| OS | Check | Known Issue | Fix |
|----|-------|-------------|-----|
| Windows | `python3` command | Doesn't exist — only `python` | Use `python` or create alias |
| Windows | PowerShell ExecutionPolicy | Scripts blocked by default | `Set-ExecutionPolicy Bypass -Scope Process` |
| Windows | Store App Aliases | Intercept `python`/`python3` | Disable in Settings → Apps → App Execution Aliases |
| Windows | Unicode in Python | CP1252 crashes on emoji | Set `PYTHONIOENCODING=utf-8` |
| Windows | `chflags`/`sudo` | Don't exist | Skip file locking or use `icacls` |
| Linux | Python package manager | `pip3` may not be installed | `apt install python3-pip` |
| Linux | Node.js version | Distro default may be old | Use NodeSource or nvm |

### Detection Script (run via node exec)

**Windows:**
```powershell
$ErrorActionPreference = 'SilentlyContinue'
Write-Host "OS: Windows"
Write-Host "Python: $(python --version 2>&1)"
Write-Host "Node: $(node --version 2>&1)"
Write-Host "Git: $(git --version 2>&1)"
Write-Host "Pip: $(pip --version 2>&1)"
Write-Host "Encoding: $([System.Text.Encoding]::Default.EncodingName)"
Write-Host "ExecPolicy: $(Get-ExecutionPolicy)"
```

**Linux:**
```bash
echo "OS: $(cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2)"
echo "Python: $(python3 --version 2>&1 || echo MISSING)"
echo "Node: $(node --version 2>&1 || echo MISSING)"
echo "Git: $(git --version 2>&1 || echo MISSING)"
echo "Pip: $(pip3 --version 2>&1 || echo MISSING)"
echo "RAM: $(free -h | awk '/Mem:/{print $2}')"
echo "Disk: $(df -h / | awk 'NR==2{print $4}')"
```

## 2. Network/Trust

| Check | How | Failure Mode |
|-------|-----|-------------|
| Clock sync | Compare node time vs orchestrator time | >60s drift = signature validation fails |
| Gateway version | `openclaw --version` on both sides | Version mismatch = "device signature invalid" |
| Connectivity | Node can reach gateway IP:port | Firewall, NAT, or tunnel issue |
| DNS resolution | `nslookup github.com` | Needed for git clone |

**Clock sync fix:**
- Windows: `w32tm /resync /force`
- Linux: `sudo timedatectl set-ntp true && sudo systemctl restart systemd-timesyncd`

**Gateway version fix:** Update OpenClaw on whichever side is older:
```bash
npm install -g openclaw@latest
```

## 3. Missing Prerequisites

Check BEFORE running install.js:

| Prerequisite | Required | Check Command |
|-------------|----------|---------------|
| Node.js 18+ | Yes | `node --version` |
| Python 3 | Yes | `python3 --version` or `python --version` |
| Git | Yes | `git --version` |
| pip3/pip | Yes | `pip3 --version` or `pip --version` |
| OpenClaw | Yes | `openclaw --version` |
| Internet access | Yes (for git clone + pip install) | `curl -s https://github.com` |

### Auto-Install Prerequisites

**Windows (PowerShell as Admin):**
```powershell
winget install OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements
winget install Python.Python.3.12 --accept-source-agreements --accept-package-agreements
winget install Git.Git --accept-source-agreements --accept-package-agreements
# Refresh PATH
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
npm install -g openclaw
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update && sudo apt install -y nodejs npm python3 python3-pip git
# If Node.js < 18:
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
sudo npm install -g openclaw
```

## 4. Config Drift

| Check | What to verify |
|-------|---------------|
| SSoT root path | Should be `resonantos-alpha/ssot`, NOT `resonantos-augmentor/ssot` |
| Dashboard port | Default 19100 — check nothing else uses it |
| Gateway port | Default 18789 — check for conflicts |
| R-Awareness keywords.json | Must reference existing SSoT doc paths |
| R-Memory config.json | Model references must be available on this node's provider |

Run after install.js completes:
```bash
grep -r "resonantos-augmentor" ~/resonantos-alpha/ && echo "FAIL: private repo ref found" || echo "PASS: no private refs"
node -e "JSON.parse(require('fs').readFileSync('$HOME/.openclaw/agents/main/agent/extensions/r-awareness/keywords.json'))" && echo "PASS" || echo "FAIL: invalid JSON"
```
