#!/usr/bin/env python3
"""
Shield File Guard — filesystem-level protection for core system files.

Cross-platform:
  - macOS: uses chflags uchg/nouchg (immutable flag)
  - Linux: uses chattr +i/-i (immutable attribute, requires root)
  - Fallback: chmod a-w / chmod u+w (any POSIX system)

Paths are auto-detected relative to the install location.
"""

import json
import os
import platform
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path detection — works regardless of install directory name
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent          # .../shield/
_PROJECT_ROOT = _SCRIPT_DIR.parent                      # .../resonantos-alpha/ (or whatever)
_HOME = Path.home()

def _project_rel(p: str) -> str:
    """Convert a project-relative path to absolute using detected root."""
    return str(_PROJECT_ROOT / p)

# Core files/dirs that make the agent run
GUARD_MANIFEST = {
    "agent_config": {
        "label": "Agent Configuration",
        "paths": [
            "~/.openclaw/agents/main/agent/auth-profiles.json",
        ],
        "category": "core",
        "include_data": True,
    },
    "agent_extensions": {
        "label": "Agent Extensions (backups, old versions)",
        "paths": ["~/.openclaw/agents/main/agent/extensions/"],
        "category": "core",
        "exclude_names": ["r-awareness.js", "r-memory.js"],
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
        "paths": [],  # populated at module load from _PROJECT_ROOT
        "category": "core",
    },
    "shield": {
        "label": "Shield",
        "paths": [],
        "category": "core",
    },
    "ssot_l0": {
        "label": "SSOT L0 — Foundation",
        "paths": [],
        "category": "ssot",
    },
    "ssot_l1": {
        "label": "SSOT L1 — Architecture",
        "paths": [],
        "category": "ssot",
    },
    "github_push": {
        "label": "GitHub Push Access",
        "paths": [],
        "category": "core",
        "hook_guard": True,
        "repos": [],
    },
}

# Populate project-relative paths at load time
GUARD_MANIFEST["dashboard"]["paths"] = [
    _project_rel("dashboard/server_v2.py"),
    _project_rel("dashboard/templates/"),
    _project_rel("dashboard/static/"),
]
GUARD_MANIFEST["shield"]["paths"] = [_project_rel("shield/")]
GUARD_MANIFEST["ssot_l0"]["paths"] = [_project_rel("ssot/L0/")] if (_PROJECT_ROOT / "ssot" / "L0").is_dir() else []
GUARD_MANIFEST["ssot_l1"]["paths"] = [_project_rel("ssot/L1/")] if (_PROJECT_ROOT / "ssot" / "L1").is_dir() else []
GUARD_MANIFEST["github_push"]["repos"] = [str(_PROJECT_ROOT)]

# Also check for ssot-template (alpha layout)
if not GUARD_MANIFEST["ssot_l0"]["paths"] and (_PROJECT_ROOT / "ssot-template" / "L0").is_dir():
    GUARD_MANIFEST["ssot_l0"]["paths"] = [_project_rel("ssot-template/L0/")]
if not GUARD_MANIFEST["ssot_l1"]["paths"] and (_PROJECT_ROOT / "ssot-template" / "L1").is_dir():
    GUARD_MANIFEST["ssot_l1"]["paths"] = [_project_rel("ssot-template/L1/")]


# These patterns inside guarded dirs should NOT be locked (working data)
EXCLUDE_PATTERNS = [
    "*.log",
    "*.json",
    "__pycache__",
    ".git",
    "alerts/",
    "r-memory.log",
]

# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------
_PLATFORM = platform.system()  # "Darwin", "Linux", "Windows"


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


def collect_files(paths: list, include_data: bool = False,
                   exclude_names: list = None) -> list:
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
    """Check if file has immutable flag set (cross-platform)."""
    try:
        if _PLATFORM == "Darwin":
            result = subprocess.run(
                ["ls", "-lO", str(filepath)],
                capture_output=True, text=True, timeout=5
            )
            return "uchg" in result.stdout
        elif _PLATFORM == "Linux":
            result = subprocess.run(
                ["lsattr", str(filepath)],
                capture_output=True, text=True, timeout=5
            )
            # lsattr output: "----i--------e-- filename"
            if result.returncode == 0 and result.stdout:
                attrs = result.stdout.split()[0] if result.stdout.strip() else ""
                return "i" in attrs
            # lsattr not available — fall back to write permission check
            return not os.access(str(filepath), os.W_OK)
        else:
            return not os.access(str(filepath), os.W_OK)
    except Exception:
        return False


def _lock_file_platform(filepath: str) -> None:
    """Lock a single file using platform-appropriate method."""
    if _PLATFORM == "Darwin":
        subprocess.run(["chflags", "uchg", filepath], check=True, timeout=5)
    elif _PLATFORM == "Linux":
        try:
            subprocess.run(["sudo", "chattr", "+i", filepath], check=True, timeout=5)
        except (subprocess.CalledProcessError, FileNotFoundError):
            # chattr unavailable or no sudo — fall back to chmod
            subprocess.run(["chmod", "a-w", filepath], check=True, timeout=5)
    else:
        subprocess.run(["chmod", "a-w", filepath], check=True, timeout=5)


def _unlock_file_platform(filepath: str) -> None:
    """Unlock a single file using platform-appropriate method."""
    if _PLATFORM == "Darwin":
        subprocess.run(["chflags", "nouchg", filepath], check=True, timeout=5)
    elif _PLATFORM == "Linux":
        try:
            subprocess.run(["sudo", "chattr", "-i", filepath], check=True, timeout=5)
        except (subprocess.CalledProcessError, FileNotFoundError):
            subprocess.run(["chmod", "u+w", filepath], check=True, timeout=5)
    else:
        subprocess.run(["chmod", "u+w", filepath], check=True, timeout=5)


def get_status() -> dict:
    """Return full status of all guarded file groups."""
    status = {}
    for group_id, group in GUARD_MANIFEST.items():
        if group.get("hook_guard"):
            repos = group.get("repos", [])
            file_status = []
            for r in repos:
                rp = expand_path(r)
                locked = is_hook_locked(rp)
                file_status.append({
                    "path": str(rp),
                    "short": str(rp).replace(str(_HOME), "~"),
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
                "short": str(f).replace(str(_HOME), "~"),
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


def lock_group(group_id: str) -> dict:
    """Lock all files in a group."""
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
        try:
            _lock_file_platform(str(f))
            results.append({"path": str(f), "locked": True})
        except subprocess.CalledProcessError as e:
            results.append({"path": str(f), "locked": False, "error": str(e)})
    return {"group": group_id, "results": results}


def unlock_group(group_id: str) -> dict:
    """Unlock all files in a group."""
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
        try:
            _unlock_file_platform(str(f))
            results.append({"path": str(f), "unlocked": True})
        except subprocess.CalledProcessError as e:
            results.append({"path": str(f), "unlocked": False, "error": str(e)})
    return {"group": group_id, "results": results}


PRE_PUSH_HOOK = """#!/bin/sh
# Shield File Guard — GitHub push lock
echo "⛔ Push blocked by Shield File Guard. Unlock github_push to push."
exit 1
"""


def is_hook_locked(repo_path: Path) -> bool:
    hook = repo_path / ".git" / "hooks" / "pre-push"
    if not hook.exists():
        return False
    try:
        return "Shield File Guard" in hook.read_text()
    except Exception:
        return False


def lock_hook(repo_path: Path) -> dict:
    hook = repo_path / ".git" / "hooks" / "pre-push"
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


def lock_file(filepath: str) -> dict:
    fp = expand_path(filepath)
    if not fp.exists():
        return {"error": f"File not found: {filepath}"}
    try:
        _lock_file_platform(str(fp))
        return {"path": str(fp), "locked": True}
    except subprocess.CalledProcessError as e:
        return {"error": str(e)}


def unlock_file(filepath: str) -> dict:
    fp = expand_path(filepath)
    if not fp.exists():
        return {"error": f"File not found: {filepath}"}
    try:
        _unlock_file_platform(str(fp))
        return {"path": str(fp), "unlocked": True}
    except subprocess.CalledProcessError as e:
        return {"error": str(e)}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: file_guard.py [status|lock|unlock] [group_id|file_path]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "status":
        print(json.dumps(get_status(), indent=2))
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
        print("Usage: file_guard.py [status|lock|unlock] [group_id|file_path]")
        sys.exit(1)
