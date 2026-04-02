"""Shield routes."""

from __future__ import annotations

import json
import os
import subprocess
import urllib.request
from typing import Any

from flask import Blueprint, Response, jsonify, request

shield_bp = Blueprint("shield", __name__)


def _shield_daemon_health() -> tuple[bool, dict[str, Any] | None, str | None]:
    """Probe the local Shield daemon health endpoint.

    Call the localhost health URL and decode the daemon's JSON payload to
    determine whether Shield is reporting a healthy state. Failures are
    normalized into a `(False, None, error)` tuple for the route layer.

    Called by:
        `api_shield_status()` when building the overall Shield status payload.

    Side effects:
        Performs an HTTP request to `http://localhost:9999/health`.

    Returns:
        tuple[bool, dict[str, Any] | None, str | None]: Health flag, optional
        payload, and optional error message.
    """
    try:
        with urllib.request.urlopen("http://localhost:9999/health", timeout=2) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        if payload.get("status") == "healthy":
            return True, payload, None
        return False, payload, f"Unexpected daemon status: {payload.get('status')}"
    except Exception as e:
        return False, None, str(e)


@shield_bp.route("/api/shield/status")
def api_shield_status() -> Response:
    """Combine daemon and file-guard status into one summary.

    Start with the Shield daemon probe, then attempt to load the file guard
    module and fold its lock counts into the response. This gives the frontend
    a single status object even when only one of the backing subsystems is
    available.

    Dependencies:
        `_shield_daemon_health()`, dynamic import of `shield/file_guard.py`,
        and `jsonify()`.

    Returns:
        Response: JSON object describing daemon availability and file-guard
        totals.
    """
    healthy, payload, error = _shield_daemon_health()
    result = {
        "active": healthy,
        "available": healthy,
        "mode": "daemon" if healthy else "off",
    }
    if healthy:
        result["uptime_seconds"] = payload.get("uptime_seconds")
    else:
        result["error"] = error
    # Add file guard data
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "file_guard",
            os.path.join(os.path.dirname(__file__), "..", "..", "shield", "file_guard.py"),
        )
        fg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fg)
        guard_status = fg.get_status()
        total_files = sum(g["total"] for g in guard_status.values())
        locked_files = sum(g["locked_count"] for g in guard_status.values())
        result["active"] = healthy or locked_files > 0
        result["file_guard"] = {
            "total_files": total_files,
            "locked_files": locked_files,
            "groups": guard_status,
        }
    except Exception:
        pass
    return jsonify(result)


@shield_bp.route("/api/shield/guard/status")
def api_shield_guard_status() -> Response:
    """Return full file-guard status for every group.

    Dynamically load the Shield file-guard module and delegate directly to its
    `get_status()` helper. The response preserves the full per-group data,
    including file lists, for detailed frontend inspection.

    Dependencies:
        Dynamic import of `shield/file_guard.py` and its `get_status()` helper.

    Returns:
        Response: JSON mapping of guard groups or a 500 error payload.
    """
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "file_guard",
            os.path.join(os.path.dirname(__file__), "..", "..", "shield", "file_guard.py"),
        )
        fg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fg)
        return jsonify(fg.get_status())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@shield_bp.route("/api/shield/guard/summary")
def api_shield_guard_summary() -> Response:
    """Summarize file-guard groups without file-level detail.

    Load the full file-guard status and strip each group down to the fields the
    summary cards need for fast rendering. This avoids sending the potentially
    large file lists used by the detailed view.

    Dependencies:
        Dynamic import of `shield/file_guard.py` and its `get_status()` helper.

    Returns:
        Response: JSON mapping of compact per-group summaries or a 500 error.
    """
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "file_guard",
            os.path.join(os.path.dirname(__file__), "..", "..", "shield", "file_guard.py"),
        )
        fg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fg)
        full = fg.get_status()
        summary = {}
        for k, v in full.items():
            summary[k] = {
                "label": v.get("label", k),
                "category": v.get("category", ""),
                "status": v.get("status", "unknown"),
                "total": v.get("total", 0),
                "locked_count": v.get("locked_count", 0),
            }
        return jsonify(summary)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@shield_bp.route("/api/shield/guard/group/<group_key>")
def api_shield_guard_group(group_key: str) -> Response:
    """Return one lazily loaded file-guard group.

    Load the full file-guard state and extract only the requested group so the
    frontend can expand individual sections on demand. Unknown groups return a
    404 rather than an empty object.

    Dependencies:
        Dynamic import of `shield/file_guard.py`, `group_key`, and
        `jsonify()`.

    Returns:
        Response: JSON object for the requested guard group or an error
        response.
    """
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "file_guard",
            os.path.join(os.path.dirname(__file__), "..", "..", "shield", "file_guard.py"),
        )
        fg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fg)
        full = fg.get_status()
        if group_key not in full:
            return jsonify({"error": "Group not found"}), 404
        return jsonify(full[group_key])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@shield_bp.route("/api/shield/guard/lock", methods=["POST"])
def api_shield_guard_lock() -> Response:
    """Lock a guarded file group or a single file.

    Validate the submitted sudo password first, then dispatch to the Shield
    file-guard helper for either group-level or file-level locking. The route
    accepts the same body shape the frontend uses for manual guard actions.

    Dependencies:
        request JSON payload, `subprocess.run()` for sudo validation, and the
        dynamically imported `shield/file_guard.py` module.

    Returns:
        Response: JSON result from the file-guard helper or a validation/error
        response.
    """
    data = request.get_json(silent=True) or {}
    password = data.get("password", "")
    if not password:
        return jsonify({"error": "Password required — schg needs root"}), 403
    # Validate password
    check = subprocess.run(
        ["sudo", "-S", "echo", "ok"],
        input=password + "\n",
        capture_output=True,
        text=True,
        timeout=10,
    )
    if check.returncode != 0:
        return jsonify({"error": "Invalid password"}), 403
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "file_guard",
            os.path.join(os.path.dirname(__file__), "..", "..", "shield", "file_guard.py"),
        )
        fg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fg)
        if "group" in data:
            return jsonify(fg.lock_group(data["group"], password=password))
        elif "file" in data:
            return jsonify(fg.lock_file(data["file"], password=password))
        return jsonify({"error": "Provide 'group' or 'file'"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@shield_bp.route("/api/shield/guard/unlock", methods=["POST"])
def api_shield_guard_unlock() -> Response:
    """Unlock a guarded file group or a single file.

    Reuse the sudo-password validation flow before dispatching to the file
    guard's unlock helpers. The route mirrors the lock endpoint but calls the
    inverse file-guard operations.

    Dependencies:
        request JSON payload, `subprocess.run()` for sudo validation, and the
        dynamically imported `shield/file_guard.py` module.

    Returns:
        Response: JSON result from the unlock helper or a validation/error
        response.
    """
    data = request.get_json(silent=True) or {}
    password = data.get("password", "")
    if not password:
        return jsonify({"error": "Password required to unlock"}), 403
    # Validate password by attempting sudo -S with it
    check = subprocess.run(
        ["sudo", "-S", "echo", "ok"],
        input=password + "\n",
        capture_output=True,
        text=True,
        timeout=10,
    )
    if check.returncode != 0:
        return jsonify({"error": "Invalid password"}), 403
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "file_guard",
            os.path.join(os.path.dirname(__file__), "..", "..", "shield", "file_guard.py"),
        )
        fg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fg)
        if "group" in data:
            return jsonify(fg.unlock_group(data["group"], password=password))
        elif "file" in data:
            return jsonify(fg.unlock_file(data["file"], password=password))
        return jsonify({"error": "Provide 'group' or 'file'"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@shield_bp.route("/api/shield/doorman/status")
def api_shield_doorman_status() -> Response:
    """Inspect workspace sanitizer process and log state.

    Query launchd for the workspace sanitizer process, then read the recent log tail
    from `/tmp/workspace-sanitizer.log` when it exists. The response is intentionally
    lightweight and geared toward the Shield dashboard card.

    Dependencies:
        `subprocess.run()`, `launchctl`, `os.path.exists()`, and local log file
        reads.

    Returns:
        Response: JSON object with runtime flags, pid, and recent log entries.
    """
    import subprocess

    result = {
        "running": False,
        "pid": None,
        "recent_log": [],
        "categories": 10,
        "watched_paths": 2,
    }
    try:
        out = subprocess.run(["launchctl", "list"], capture_output=True, text=True, timeout=5)
        for line in out.stdout.splitlines():
            if "workspace-sanitizer" in line:
                parts = line.split()
                if parts[0] != "-":
                    result["running"] = True
                    result["pid"] = int(parts[0])
                elif parts[1] == "0":
                    result["running"] = True
                break
    except Exception:
        pass
    try:
        log_path = "/tmp/workspace-sanitizer.log"
        if os.path.exists(log_path):
            with open(log_path) as f:
                lines = f.readlines()
            result["recent_log"] = [l.strip() for l in lines[-10:]]
            result["total_sanitized"] = sum(1 for l in lines if "CLEANED" in l)
    except Exception:
        pass
    return jsonify(result)
