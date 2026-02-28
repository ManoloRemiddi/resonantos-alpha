# Deployment Lessons Log

Append new lessons after each deployment. Format:
`- <date>: <OS>: <what happened> → <fix/workaround>`

---

- 2026-02-28: Windows (BeeAMD): PowerShell bootstrap script had heredoc escaping issues → Use simple string concatenation, avoid heredocs in PowerShell
- 2026-02-28: Windows: `python3` command doesn't exist → install.js already handles fallback to `python`
- 2026-02-28: Windows: OpenSSH install hangs if already installed → Check `Get-WindowsCapability` first
- 2026-02-28: Windows: ssh-keygen `-N '""'` doesn't work → Use interactive passphrase or `-N ""`
- 2026-02-28: Windows: Gateway version mismatch (2025.2.25 vs 2026.2.26) → "device signature invalid". Fix: update both sides to same version BEFORE pairing
- 2026-02-28: Windows: Clock drift (2 min) on offline PC → "device signature expired". Fix: `w32tm /resync /force`
- 2026-02-28: Windows: Exec approvals default to deny → Set exec-approvals policy after pairing
- 2026-02-28: Windows: Unicode emoji crashes Python on CP1252 → Set PYTHONIOENCODING=utf-8
- 2026-02-28: Windows: Store App Execution Aliases intercept python → Disable in Settings
- 2026-02-28: Windows: `chflags`/`sudo` don't exist → file_guard.py now uses `icacls` on Windows
- 2026-02-28: Windows: ssot-validator.js regex `/\/L([0-4])\//` misses Windows backslash paths → Fixed to handle both separators
- 2026-02-28: General: install.js had `resonantos-augmentor` path hardcoded (private repo name) → Fixed to `resonantos-alpha`
- 2026-02-28: General: Setup Agent not deployed by install.js despite existing in repo → Added to install.js deployment step
