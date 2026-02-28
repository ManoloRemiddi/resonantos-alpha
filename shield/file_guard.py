#!/usr/bin/env python3
"""
Shield File Guard — filesystem-level protection for core system files.
Cross-platform: macOS (chflags schg/noschg), Linux (chattr +i/-i), Windows (icacls).
Requires root/admin to modify. The AI agent CANNOT unlock files without the password.
"""

import json
import platform
import os
import subprocess
import sys
from pathlib import Path

IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SSOT_ROOT = _REPO_ROOT / "ssot"
if not _SSOT_ROOT.exists():
    _SSOT_ROOT = _REPO_ROOT / "ssot-template"

# Core files/dirs that make the agent run
GUARD_MANIFEST = {
    "agent_config": {
        "label": "Agent Configuration",
        "paths": [
            "~/.openclaw/agents/main/agent/auth-profiles.json",
        ],
        "category": "core",
        "include_data": True,  # override exclude for .json
    },
    "agent_extensions": {
        "label": "Agent Extensions (backups, old versions)",
        "paths": ["~/.openclaw/agents/main/agent/extensions/"],
        "category": "core",
        "exclude_names": ["r-awareness.js", "r-memory.js"],  # Active extensions — must stay writable
    },
    "identity": {
        "label": "Identity Files",
        "paths": [
            "~/.openclaw/workspace/SOUL.md",
            "~/.openclaw/workspace/AGENTS.md",
            "~/.openclaw/workspace/USER.md",
            "~/.openclaw/workspace/IDENTITY.md",
            "~/.openclaw/workspace/TOOLS.md",
        ],
        "category": "core",
    },
    "dashboard": {
        "label": "Dashboard",
        "paths": [
            str(_REPO_ROOT / "dashboard" / "server_v2.py"),
            str(_REPO_ROOT / "dashboard" / "templates"),
            str(_REPO_ROOT / "dashboard" / "static"),
        ],
        "category": "core",
    },
    "shield": {
        "label": "Shield",
        "paths": [str(_REPO_ROOT / "shield")],
        "category": "core",
    },
    "ssot_l0": {
        "label": "SSOT L0 — Foundation",
        "paths": [str(_SSOT_ROOT / "L0")],
        "category": "ssot",
    },
    "ssot_l1": {
        "label": "SSOT L1 — Architecture",
        "paths": [str(_SSOT_ROOT / "L1")],
        "category": "ssot",
    },
    "github_push": {
        "label": "GitHub Push Access",
        "paths": [],  # No filesystem paths — uses git hook mechanism
        "category": "core",
        "hook_guard": True,  # Special: manages pre-push hook instead of chflags
        "repos": [
            str(_REPO_ROOT),
        ],
    },
}

# These patterns inside guarded dirs should NOT be locked (working data)
EXCLUDE_PATTERNS = [
    "*.log",
    "*.json",  # history/cache data files
    "__pycache__",
    ".git",
    "alerts/",
    "r-memory.log",
]


def expand_path(p: str) -> Path:
    return Path(os.path.expanduser(p)).resolve()


def should_exclude(filepath: Path) -> bool:
    name = filepath.name
    parts = str(filepath)
    for pat in EXCLUDE_PATTERNS:
        if pat.endswith("/") and pat.rstrip("/") in parts:
            return True
        if pat.startswith("*") and name.endswith(pat[1:]):
            return True
        if name == pat:
            return True
    return False


def collect_files(paths, include_data=False, exclude_names=None):
    """Collect all files from paths (expanding dirs recursively)."""
    result = []
    _excl = set(exclude_names or [])
    for p in paths:
        fp = expand_path(p)
        if fp.is_file():
            if fp.name not in _excl and (include_data or not should_exclude(fp)):
                result.append(fp)
        elif fp.is_dir():
            for f in fp.rglob("*"):
                if f.is_file() and f.name not in _excl and (include_data or not should_exclude(f)):
                    result.append(f)
    return sorted(set(result))


def is_locked(filepath: Path) -> bool:
    """Check if file has schg or uchg flag set (either counts as locked)."""
    if IS_WINDOWS:
        try:
            result = subprocess.run(
                ["icacls", str(filepath)],
                capture_output=True, text=True, timeout=5
            )
            return "(DENY)" in result.stdout and "(W)" in result.stdout
        except Exception:
            return False
    if IS_LINUX:
        try:
            result = subprocess.run(
                ["lsattr", str(filepath)],
                capture_output=True, text=True, timeout=5
            )
            # lsattr output: "----i---------e------- /path/to/file"
            attrs = result.stdout.split()[0] if result.stdout.strip() else ""
            return "i" in attrs
        except Exception:
            return False
    try:
        result = subprocess.run(
            ["ls", "-lO", str(filepath)],
            capture_output=True, text=True, timeout=5
        )
        return "schg" in result.stdout or "uchg" in result.stdout
    except Exception:
        return False


def get_status() -> dict:
    """Return full status of all guarded file groups."""
    status = {}
    for group_id, group in GUARD_MANIFEST.items():
        if group.get("hook_guard"):
            # Hook-based guard (e.g., git pre-push)
            repos = group.get("repos", [])
            file_status = []
            for r in repos:
                rp = expand_path(r)
                locked = is_hook_locked(rp)
                file_status.append({
                    "path": str(rp),
                    "short": str(rp).replace(str(Path.home()), "~"),
                    "locked": locked,
                    "size": 0,
                })
            all_locked = len(file_status) > 0 and all(f["locked"] for f in file_status)
            any_locked = any(f["locked"] for f in file_status)
            status[group_id] = {
                "label": group["label"],
                "category": group["category"],
                "status": "locked" if all_locked else ("partial" if any_locked else "unlocked"),
                "total": len(file_status),
                "locked_count": sum(1 for f in file_status if f["locked"]),
                "files": file_status,
            }
            continue
        files = collect_files(group["paths"], include_data=group.get("include_data", False),
                              exclude_names=group.get("exclude_names"))
        file_status = []
        for f in files:
            locked = is_locked(f)
            file_status.append({
                "path": str(f),
                "short": str(f).replace(str(Path.home()), "~"),
                "locked": locked,
                "size": f.stat().st_size if f.exists() else 0,
            })
        all_locked = len(file_status) > 0 and all(f["locked"] for f in file_status)
        any_locked = any(f["locked"] for f in file_status)
        status[group_id] = {
            "label": group["label"],
            "category": group["category"],
            "status": "locked" if all_locked else ("partial" if any_locked else "unlocked"),
            "total": len(file_status),
            "locked_count": sum(1 for f in file_status if f["locked"]),
            "files": file_status,
        }
    return status


def _sudo_chflags(flag: str, filepath: str, password: str = None) -> bool:
    """Run sudo chflags with optional password via stdin. Returns True on success."""
    cmd = ["sudo", "-S", "chflags", flag, filepath] if password else ["sudo", "chflags", flag, filepath]
    stdin_data = (password + "\n") if password else None
    result = subprocess.run(cmd, input=stdin_data, capture_output=True, text=True, timeout=10)
    return result.returncode == 0


def _platform_lock(filepath: str, password: str = None) -> bool:
    if IS_WINDOWS:
        try:
            result = subprocess.run(
                ["icacls", filepath, "/deny", "Everyone:(W)"],
                capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False
    if IS_LINUX:
        cmd = ["sudo", "-S", "chattr", "+i", filepath] if password else ["sudo", "chattr", "+i", filepath]
        stdin_data = (password + "\n") if password else None
        result = subprocess.run(cmd, input=stdin_data, capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    return _sudo_chflags("schg", filepath, password)


def _platform_unlock(filepath: str, password: str = None) -> bool:
    if IS_WINDOWS:
        try:
            result = subprocess.run(
                ["icacls", filepath, "/remove:d", "Everyone"],
                capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False
    if IS_LINUX:
        cmd = ["sudo", "-S", "chattr", "-i", filepath] if password else ["sudo", "chattr", "-i", filepath]
        stdin_data = (password + "\n") if password else None
        result = subprocess.run(cmd, input=stdin_data, capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    return _sudo_chflags("noschg", filepath, password)


def lock_group(group_id: str, password: str = None) -> dict:
    """Lock all files in a group using sudo chflags schg (system immutable, root-only)."""
    if group_id not in GUARD_MANIFEST:
        return {"error": f"Unknown group: {group_id}"}
    group = GUARD_MANIFEST[group_id]
    if group.get("hook_guard"):
        results = []
        for r in group.get("repos", []):
            rp = expand_path(r)
            results.append(lock_hook(rp))
        return {"group": group_id, "results": results}
    files = collect_files(group["paths"], include_data=group.get("include_data", False),
                          exclude_names=group.get("exclude_names"))
    results = []
    for f in files:
        ok = _platform_lock(str(f), password)
        results.append({"path": str(f), "locked": ok, **({"error": "sudo failed"} if not ok else {})})
    return {"group": group_id, "results": results}


def unlock_group(group_id: str, password: str = None) -> dict:
    """Unlock all files in a group using sudo chflags noschg (requires root)."""
    if group_id not in GUARD_MANIFEST:
        return {"error": f"Unknown group: {group_id}"}
    group = GUARD_MANIFEST[group_id]
    if group.get("hook_guard"):
        results = []
        for r in group.get("repos", []):
            rp = expand_path(r)
            results.append(unlock_hook(rp))
        return {"group": group_id, "results": results}
    files = collect_files(group["paths"], include_data=group.get("include_data", False),
                          exclude_names=group.get("exclude_names"))
    results = []
    for f in files:
        ok = _platform_unlock(str(f), password)
        results.append({"path": str(f), "unlocked": ok, **({"error": "sudo failed"} if not ok else {})})
    return {"group": group_id, "results": results}


PRE_PUSH_HOOK = """#!/bin/sh
# Shield File Guard — GitHub push lock
echo "⛔ Push blocked by Shield File Guard. Unlock github_push to push."
exit 1
"""


def is_hook_locked(repo_path: Path) -> bool:
    hook = repo_path / ".git" / "hooks" / "pre-push"
    return hook.exists() and "Shield File Guard" in hook.read_text()


def lock_hook(repo_path: Path) -> dict:
    hook = repo_path / ".git" / "hooks" / "pre-push"
    # Back up existing hook if present and not ours
    if hook.exists() and "Shield File Guard" not in hook.read_text():
        hook.rename(hook.with_suffix(".pre-shield-backup"))
    hook.write_text(PRE_PUSH_HOOK)
    if not IS_WINDOWS:
        hook.chmod(0o755)
    return {"path": str(hook), "locked": True}


def unlock_hook(repo_path: Path) -> dict:
    hook = repo_path / ".git" / "hooks" / "pre-push"
    backup = hook.with_suffix(".pre-shield-backup")
    if hook.exists() and "Shield File Guard" in hook.read_text():
        hook.unlink()
        if backup.exists():
            backup.rename(hook)
    return {"path": str(hook), "unlocked": True}


def lock_file(filepath: str, password: str = None) -> dict:
    fp = expand_path(filepath)
    if not fp.exists():
        return {"error": f"File not found: {filepath}"}
    ok = _platform_lock(str(fp), password)
    return {"path": str(fp), "locked": ok} if ok else {"error": "sudo failed — root required"}


def unlock_file(filepath: str, password: str = None) -> dict:
    fp = expand_path(filepath)
    if not fp.exists():
        return {"error": f"File not found: {filepath}"}
    ok = _platform_unlock(str(fp), password)
    return {"path": str(fp), "unlocked": ok} if ok else {"error": "sudo failed — root required"}


def migrate_uchg_to_schg() -> dict:
    """Migrate all guarded files from uchg (user) to schg (system) immutable.
    Requires root. Run: sudo python3 file_guard.py migrate
    """
    results = []
    for group_id, group in GUARD_MANIFEST.items():
        if group.get("hook_guard"):
            continue
        files = collect_files(group["paths"], include_data=group.get("include_data", False),
                              exclude_names=group.get("exclude_names"))
        for f in files:
            try:
                # Check current state
                check = subprocess.run(["ls", "-lO", str(f)], capture_output=True, text=True, timeout=5)
                had_uchg = "uchg" in check.stdout and "schg" not in check.stdout
                had_schg = "schg" in check.stdout

                if had_schg:
                    results.append({"path": str(f), "action": "already_schg"})
                    continue

                if had_uchg:
                    # Remove uchg first, then apply schg
                    subprocess.run(["chflags", "nouchg", str(f)], check=True, timeout=5)

                subprocess.run(["chflags", "schg", str(f)], check=True, timeout=5)
                results.append({"path": str(f), "action": "migrated" if had_uchg else "locked_new"})
            except subprocess.CalledProcessError as e:
                results.append({"path": str(f), "action": "error", "error": str(e)})
    return {"migrated": sum(1 for r in results if r["action"] == "migrated"),
            "already": sum(1 for r in results if r["action"] == "already_schg"),
            "new": sum(1 for r in results if r["action"] == "locked_new"),
            "errors": sum(1 for r in results if r["action"] == "error"),
            "details": results}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: file_guard.py [status|lock|unlock|migrate] [group_id|file_path]")
        print("  migrate — Convert all uchg flags to schg (requires: sudo)")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "status":
        print(json.dumps(get_status(), indent=2))
    elif cmd == "migrate":
        print(json.dumps(migrate_uchg_to_schg(), indent=2))
    elif cmd == "lock" and len(sys.argv) > 2:
        target = sys.argv[2]
        if target in GUARD_MANIFEST:
            print(json.dumps(lock_group(target), indent=2))
        else:
            print(json.dumps(lock_file(target), indent=2))
    elif cmd == "unlock" and len(sys.argv) > 2:
        target = sys.argv[2]
        if target in GUARD_MANIFEST:
            print(json.dumps(unlock_group(target), indent=2))
        else:
            print(json.dumps(unlock_file(target), indent=2))
    else:
        print("Usage: file_guard.py [status|lock|unlock|migrate] [group_id|file_path]")
        sys.exit(1)
