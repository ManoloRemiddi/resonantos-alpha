#!/usr/bin/env python3
"""
Shield File Guard — filesystem-level protection for core system files.
Uses platform-specific immutable file flags:
  - macOS: sudo chflags schg/noschg (system immutable — requires root)
  - Linux: sudo chattr +i/-i (EXT4/XFS immutable — requires root)
This means the AI agent CANNOT unlock files; only a human with sudo can.
"""

import json
import os
import platform
import subprocess
import sys
from pathlib import Path

# Core files/dirs that make the agent run
GUARD_MANIFEST = {
    # agent_config REMOVED (2026-02-26): auth-profiles.json MUST stay writable.
    # OpenClaw writes token refresh + usage stats to it. Locking causes EPERM → "agent failed before replying".
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
            "~/resonantos-alpha/dashboard/server_v2.py",
            "~/resonantos-alpha/dashboard/templates/",
            "~/resonantos-alpha/dashboard/static/",
        ],
        "category": "core",
    },
    "shield": {
        "label": "Shield",
        "paths": ["~/resonantos-alpha/shield/"],
        "category": "core",
    },
    "ssot_l0": {
        "label": "SSOT L0 — Foundation",
        "paths": ["~/resonantos-alpha/ssot/L0/"],
        "category": "ssot",
    },
    "ssot_l1": {
        "label": "SSOT L1 — Architecture",
        "paths": ["~/resonantos-alpha/ssot/L1/"],
        "category": "ssot",
    },
    "github_push": {
        "label": "GitHub Push Access",
        "paths": [],  # No filesystem paths — uses git hook mechanism
        "category": "core",
        "hook_guard": True,  # Special: manages pre-push hook instead of chflags
        "repos": [
            "~/resonantos-alpha",
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


def collect_files(paths: list[str], include_data: bool = False,
                   exclude_names: list[str] | None = None) -> list[Path]:
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
    """Check if file has immutable flag set (platform-specific check)."""
    system = platform.system()
    try:
        if system == "Darwin":
            import stat
            st = os.stat(str(filepath))
            flags = st.st_flags
            return bool(flags & (0x00000002 | 0x00020000))
        elif system == "Linux":
            result = subprocess.run(
                ["lsattr", "-d", str(filepath)],
                capture_output=True, text=True, timeout=5
            )
            return "+i" in result.stdout
    except Exception:
        pass
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
    """Run sudo with platform-specific immutable flag command. Returns True on success."""
    system = platform.system()
    if system == "Darwin":
        cmd = ["sudo", "-S", "chflags", flag, filepath]
    elif system == "Linux":
        if flag == "schg":
            cmd = ["sudo", "-S", "chattr", "+i", filepath]
        elif flag == "noschg":
            cmd = ["sudo", "-S", "chattr", "-i", filepath]
        else:
            return False
    else:
        return False
    stdin_data = (password + "\n") if password else None
    result = subprocess.run(cmd, input=stdin_data, capture_output=True, text=True, timeout=10)
    return result.returncode == 0


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
        ok = _sudo_chflags("schg", str(f), password)
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
        ok = _sudo_chflags("noschg", str(f), password)
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
    ok = _sudo_chflags("schg", str(fp), password)
    return {"path": str(fp), "locked": ok} if ok else {"error": "sudo failed — root required"}


def unlock_file(filepath: str, password: str = None) -> dict:
    fp = expand_path(filepath)
    if not fp.exists():
        return {"error": f"File not found: {filepath}"}
    ok = _sudo_chflags("noschg", str(fp), password)
    return {"path": str(fp), "unlocked": ok} if ok else {"error": "sudo failed — root required"}


def migrate_uchg_to_schg() -> dict:
    """Migrate all guarded files from uchg to schg (macOS) or check chattr (Linux).
    Requires root. Run: sudo python3 file_guard.py migrate
    """
    system = platform.system()
    results = []
    for group_id, group in GUARD_MANIFEST.items():
        if group.get("hook_guard"):
            continue
        files = collect_files(group["paths"], include_data=group.get("include_data", False),
                              exclude_names=group.get("exclude_names"))
        for f in files:
            try:
                if system == "Darwin":
                    check = subprocess.run(["ls", "-lO", str(f)], capture_output=True, text=True, timeout=5)
                    had_uchg = "uchg" in check.stdout and "schg" not in check.stdout
                    had_schg = "schg" in check.stdout

                    if had_schg:
                        results.append({"path": str(f), "action": "already_schg"})
                        continue

                    if had_uchg:
                        subprocess.run(["chflags", "nouchg", str(f)], check=True, timeout=5)

                    subprocess.run(["chflags", "schg", str(f)], check=True, timeout=5)
                    results.append({"path": str(f), "action": "migrated" if had_uchg else "locked_new"})
                elif system == "Linux":
                    check = subprocess.run(["lsattr", "-d", str(f)], capture_output=True, text=True, timeout=5)
                    had_i = "+i" in check.stdout

                    if had_i:
                        results.append({"path": str(f), "action": "already_immutable"})
                        continue

                    subprocess.run(["chattr", "+i", str(f)], check=True, timeout=5)
                    results.append({"path": str(f), "action": "locked_linux"})
            except subprocess.CalledProcessError as e:
                results.append({"path": str(f), "action": "error", "error": str(e)})
    return {"migrated": sum(1 for r in results if r["action"] in ("migrated", "locked_new", "locked_linux")),
            "already": sum(1 for r in results if r["action"] in ("already_schg", "already_immutable")),
            "new": sum(1 for r in results if r["action"] in ("migrated", "locked_new", "locked_linux")),
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
