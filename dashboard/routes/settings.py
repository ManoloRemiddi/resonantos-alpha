"""Settings routes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, jsonify, request

from routes.config import EXTENSIONS_DIR, OPENCLAW_CONFIG
from routes.settings_helpers import (
    DASHBOARD_REPO_DIR,
    _UPDATE_INTERVAL_OPTIONS,
    _MEMORY_CRON_IDS,
    _discover_settings_skills,
    _get_agent_skill_allow,
    _list_skill_agents,
    _memory_log_state,
    _perform_update_check_logic,
    _read_openclaw_config,
    _read_updates_config,
    _set_agent_skill_allow,
    _write_openclaw_config,
    _write_updates_config,
)

settings_bp = Blueprint("settings", __name__)

_DASHBOARD_SETTINGS_FILE: Path = Path(__file__).resolve().parent.parent / "data" / "dashboard-settings.json"


def _default_dashboard_settings() -> dict[str, Any]:
    """Return the default dashboard UI preferences payload.

    Build the exact settings structure expected by `settings.html` when no
    persisted preferences file exists. The payload is constructed in memory on
    each call so callers can mutate the result without sharing nested state.

    Dependencies:
        None.

    Called by:
        api_get_settings()
        api_post_settings()
    Side effects:
        None.

    Returns:
        A new dictionary containing theme, refresh, and permissions defaults.
    """
    return {
        "theme": "dark",
        "autoRefresh": True,
        "refreshInterval": 30,
        "permissions": {
            "browserAccess": True,
            "shellCommands": True,
            "fileWrite": True,
            "externalMessaging": True,
            "toolInstallation": True,
        },
    }


@settings_bp.route("/api/settings")
def api_get_settings() -> Response:
    """Return the persisted dashboard UI preferences.

    Read `dashboard/data/dashboard-settings.json` when it exists and deserialize
    the stored JSON payload for the settings page. If the file is missing,
    unreadable, or does not contain an object, return the required in-memory
    defaults so the shared frontend settings loader always receives valid data.

    Dependencies:
        Uses `_DASHBOARD_SETTINGS_FILE`, filesystem reads, and `json.loads`.

    Returns:
        A JSON response containing dashboard UI preferences with status 200.
    """
    defaults = _default_dashboard_settings()
    if not _DASHBOARD_SETTINGS_FILE.exists():
        return jsonify(defaults)

    try:
        payload = json.loads(_DASHBOARD_SETTINGS_FILE.read_text())
    except Exception:
        return jsonify(defaults)

    if not isinstance(payload, dict):
        return jsonify(defaults)

    permissions = payload.get("permissions")
    if not isinstance(permissions, dict):
        permissions = {}

    return jsonify(
        {
            "theme": payload.get("theme", defaults["theme"]),
            "autoRefresh": payload.get("autoRefresh", defaults["autoRefresh"]),
            "refreshInterval": payload.get("refreshInterval", defaults["refreshInterval"]),
            "permissions": {
                "browserAccess": permissions.get("browserAccess", defaults["permissions"]["browserAccess"]),
                "shellCommands": permissions.get("shellCommands", defaults["permissions"]["shellCommands"]),
                "fileWrite": permissions.get("fileWrite", defaults["permissions"]["fileWrite"]),
                "externalMessaging": permissions.get("externalMessaging", defaults["permissions"]["externalMessaging"]),
                "toolInstallation": permissions.get("toolInstallation", defaults["permissions"]["toolInstallation"]),
            },
        }
    )


@settings_bp.route("/api/settings", methods=["POST"])
def api_post_settings() -> Response:
    """Persist dashboard UI preferences for the settings page.

    Parse the JSON request body, extract the supported settings keys, and write
    the normalized payload to `dashboard/data/dashboard-settings.json`. The
    route creates the data directory when needed and responds with a simple
    acknowledgement after the write succeeds.

    Dependencies:
        Uses `request.get_json()`, `_DASHBOARD_SETTINGS_FILE`, filesystem writes, and `json.dumps`.

    Returns:
        A JSON response containing `{"ok": true}` on success, or a 400 error for invalid JSON bodies.
    """
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "Invalid JSON body"}), 400

    defaults = _default_dashboard_settings()
    permissions = body.get("permissions")
    if not isinstance(permissions, dict):
        permissions = {}

    payload = {
        "theme": body.get("theme", defaults["theme"]),
        "autoRefresh": body.get("autoRefresh", defaults["autoRefresh"]),
        "refreshInterval": body.get("refreshInterval", defaults["refreshInterval"]),
        "permissions": {
            "browserAccess": permissions.get("browserAccess", defaults["permissions"]["browserAccess"]),
            "shellCommands": permissions.get("shellCommands", defaults["permissions"]["shellCommands"]),
            "fileWrite": permissions.get("fileWrite", defaults["permissions"]["fileWrite"]),
            "externalMessaging": permissions.get("externalMessaging", defaults["permissions"]["externalMessaging"]),
            "toolInstallation": permissions.get("toolInstallation", defaults["permissions"]["toolInstallation"]),
        },
    }

    _DASHBOARD_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _DASHBOARD_SETTINGS_FILE.write_text(json.dumps(payload, indent=2))
    return jsonify({"ok": True})


@settings_bp.route("/api/settings/update-config")
def api_get_update_config() -> Response:
    """Return the persisted dashboard update settings.

    Load the current update-check configuration from disk and expose it directly
    to the settings UI. This route is read-only and does not transform the
    stored values beyond JSON serialization.

    Dependencies:
        Uses _read_updates_config() from routes.settings_helpers.

    Returns:
        A JSON response containing the current update configuration.
    """
    return jsonify(_read_updates_config())


@settings_bp.route("/api/settings/update-config", methods=["PUT"])
def api_put_update_config() -> Response:
    """Update the persisted dashboard update settings.

    Validate the incoming JSON body field by field, then merge supported values
    into the existing update configuration before writing it back to disk. The
    response returns the saved configuration so the frontend can refresh its state.

    Dependencies:
        Uses request JSON plus _read_updates_config() and _write_updates_config().

    Returns:
        A JSON response with the saved configuration, or a validation error response.
    """
    body: dict[str, Any] = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"error": "Invalid JSON body"}), 400

    updates = _read_updates_config()

    if "autoCheck" in body:
        if not isinstance(body["autoCheck"], bool):
            return jsonify({"error": "autoCheck must be a boolean"}), 400
        updates["autoCheck"] = body["autoCheck"]

    if "autoApply" in body:
        if not isinstance(body["autoApply"], bool):
            return jsonify({"error": "autoApply must be a boolean"}), 400
        updates["autoApply"] = body["autoApply"]

    if "notifyOnUpdate" in body:
        if not isinstance(body["notifyOnUpdate"], bool):
            return jsonify({"error": "notifyOnUpdate must be a boolean"}), 400
        updates["notifyOnUpdate"] = body["notifyOnUpdate"]

    if "autoCheckIntervalHours" in body:
        try:
            interval = int(body["autoCheckIntervalHours"])
        except Exception:
            return jsonify({"error": "autoCheckIntervalHours must be an integer"}), 400
        if interval not in _UPDATE_INTERVAL_OPTIONS:
            return jsonify({"error": "autoCheckIntervalHours must be one of: 1, 2, 4, 6, 12, 24"}), 400
        updates["autoCheckIntervalHours"] = interval

    saved = _write_updates_config(updates)
    return jsonify(saved)


@settings_bp.route("/api/settings/memory-logs")
def api_memory_logs_get() -> Response:
    """Return the current memory log scheduler state.

    Query the helper that inspects the configured memory-related cron jobs and
    expose that state to the settings page. The route simply forwards the helper
    payload as JSON for the frontend controls.

    Dependencies:
        Uses _memory_log_state() from routes.settings_helpers.

    Returns:
        A JSON response describing memory log enablement and model configuration.
    """
    return jsonify(_memory_log_state())


@settings_bp.route("/api/settings/memory-logs", methods=["PUT"])
def api_memory_logs_put() -> Response:
    """Update memory log scheduler settings.

    Apply enable or disable requests to each managed cron job and optionally
    rewrite the model used by those jobs through the `openclaw cron` CLI. The
    response returns the refreshed scheduler state plus any command errors collected.

    Dependencies:
        Uses request JSON, subprocess calls to `openclaw cron`, _MEMORY_CRON_IDS, and _memory_log_state().

    Returns:
        A JSON response with the updated memory log state and any non-fatal errors.
    """
    import subprocess

    body: dict[str, Any] = request.get_json(force=True)
    errors = []
    for key, cron_id in _MEMORY_CRON_IDS.items():
        sub = body.get(key)
        if isinstance(sub, dict) and "enabled" in sub:
            cmd = "enable" if sub["enabled"] else "disable"
            try:
                subprocess.run(["openclaw", "cron", cmd, cron_id], capture_output=True, text=True, timeout=15)
            except Exception as e:
                errors.append(f"{key} toggle: {e}")
    model = body.get("model")
    if model:
        for key, cron_id in _MEMORY_CRON_IDS.items():
            try:
                subprocess.run(
                    ["openclaw", "cron", "edit", cron_id, "--model", model], capture_output=True, text=True, timeout=15
                )
            except Exception as e:
                errors.append(f"{key} model: {e}")
    result = _memory_log_state()
    if errors:
        result["errors"] = errors
    return jsonify(result)


@settings_bp.route("/api/settings/skills")
def api_settings_skills_get() -> Response:
    """Return the skills assignment matrix for settings.

    Read the OpenClaw configuration, discover available skills, and compute each
    agent's effective allowed-skill list for the settings UI. Agents without an
    explicit allow list are expanded to all known skills in the response.

    Dependencies:
        Uses OpenClaw config helpers plus skill discovery and agent listing helpers.

    Returns:
        A JSON response containing available skills, agents, and current assignments.
    """
    try:
        cfg = _read_openclaw_config()
    except Exception as e:
        return jsonify({"error": f"Failed to read openclaw.json: {e}"}), 500

    skills = _discover_settings_skills()
    skill_names = [skill["name"] for skill in skills]
    skill_name_set = set(skill_names)
    agents = _list_skill_agents(cfg)
    assignments = {}

    for agent in agents:
        allow = _get_agent_skill_allow(cfg, agent["name"])
        if allow is None:
            assignments[agent["name"]] = list(skill_names)
            continue
        seen = set()
        assignments[agent["name"]] = [
            skill_name
            for skill_name in allow
            if skill_name in skill_name_set and skill_name not in seen and not seen.add(skill_name)
        ]

    return jsonify(
        {
            "skills": skills,
            "agents": agents,
            "assignments": assignments,
        }
    )


@settings_bp.route("/api/settings/skills", methods=["PUT"])
def api_settings_skills_put() -> Response:
    """Update the allowed skills for a specific agent.

    Validate the requested agent and skill list against discovered skills, then
    persist the agent's allow-list configuration to `openclaw.json`. A complete
    skill selection is normalized back to the implicit "all skills allowed" state.

    Dependencies:
        Uses request JSON, skill discovery helpers, and OpenClaw config read/write helpers.

    Returns:
        A JSON response containing the agent name and effective allowed skills, or an error response.
    """
    body: dict[str, Any] = request.get_json(silent=True) or {}
    agent_name = str(body.get("agent", "")).strip()
    requested_skills = body.get("skills")

    if not agent_name:
        return jsonify({"error": "agent is required"}), 400
    if not isinstance(requested_skills, list):
        return jsonify({"error": "skills must be an array"}), 400

    available_skills = _discover_settings_skills()
    available_names = [skill["name"] for skill in available_skills]
    available_name_set = set(available_names)
    requested_set = []
    seen = set()
    for skill_name in requested_skills:
        normalized = str(skill_name).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        requested_set.append(normalized)

    unknown = [skill_name for skill_name in requested_set if skill_name not in available_name_set]
    if unknown:
        return jsonify({"error": f"Unknown skills: {', '.join(unknown)}"}), 400

    allowed_skills = [name for name in available_names if name in seen]
    if len(allowed_skills) == len(available_names):
        allowed_skills = None

    try:
        cfg = _read_openclaw_config()
        _set_agent_skill_allow(cfg, agent_name, allowed_skills)
        _write_openclaw_config(cfg)
    except Exception as e:
        return jsonify({"error": f"Failed to write openclaw.json: {e}"}), 500

    return jsonify(
        {
            "agent": agent_name,
            "skills": allowed_skills if allowed_skills is not None else available_names,
        }
    )


@settings_bp.route("/api/settings/plugins")
def api_settings_plugins() -> Response:
    """Return plugin metadata from config and extension directories.

    Combine the OpenClaw plugin configuration with manifests found in the stock
    and custom extension folders to build the settings page inventory. The route
    annotates each plugin with source, enablement, and allow-list state for display.

    Dependencies:
        Uses OPENCLAW_CONFIG, EXTENSIONS_DIR, filesystem reads, and JSON manifest loading.

    Returns:
        A JSON response containing plugin entries, allow-list data, and plugin totals.
    """
    import json as _json

    plugins = []
    cfg = {}
    config_entries = {}
    plugins_allow = []

    try:
        with open(OPENCLAW_CONFIG) as f:
            cfg = _json.load(f)
        plugins_cfg = cfg.get("plugins", {}) if isinstance(cfg, dict) else {}
        entries = plugins_cfg.get("entries", {}) if isinstance(plugins_cfg, dict) else {}
        allow = plugins_cfg.get("allow", []) if isinstance(plugins_cfg, dict) else []
        config_entries = entries if isinstance(entries, dict) else {}
        if isinstance(allow, list):
            plugins_allow = [str(item).strip() for item in allow if str(item).strip()]
    except Exception:
        pass

    ext_dirs = [
        (Path("/opt/homebrew/lib/node_modules/openclaw/extensions"), "stock"),
        (EXTENSIONS_DIR, "custom"),
    ]

    for ext_dir, source in ext_dirs:
        if not ext_dir.is_dir():
            continue
        try:
            entries = sorted(ext_dir.iterdir(), key=lambda item: item.name.lower())
        except Exception:
            continue

        for entry in entries:
            if not entry.is_dir():
                continue
            name = entry.name
            if name.startswith("."):
                continue

            plugin_id = name[:-9] if name.endswith(".DISABLED") else name
            config_entry = config_entries.get(name)
            if config_entry is None:
                config_entry = config_entries.get(plugin_id)

            plugin = {
                "id": plugin_id,
                "source": source,
                "path": str(entry),
                "name": name,
                "description": "",
                "version": "",
                "enabled": False,
                "configuredInEntries": name in config_entries or plugin_id in config_entries,
                "inAllowList": name in plugins_allow or plugin_id in plugins_allow,
            }

            manifest = entry / "openclaw.plugin.json"
            if manifest.exists():
                try:
                    with open(manifest) as f:
                        manifest_data = _json.load(f)
                    plugin["name"] = manifest_data.get("name", name)
                    plugin["description"] = manifest_data.get("description", "")
                    plugin["version"] = manifest_data.get("version", "")
                except Exception:
                    pass

            pkg = entry / "package.json"
            if pkg.exists() and not plugin["description"]:
                try:
                    with open(pkg) as f:
                        package_data = _json.load(f)
                    if not plugin["name"] or plugin["name"] == name:
                        plugin["name"] = package_data.get("name", name)
                    plugin["description"] = package_data.get("description", "")
                    plugin["version"] = package_data.get("version", plugin["version"])
                except Exception:
                    pass

            if name.endswith(".DISABLED"):
                plugin["note"] = "Retired — replaced by LCM (Lossless Context Management)"
                plugin["retired"] = True
                plugin["enabled"] = False
            elif isinstance(config_entry, dict):
                plugin["enabled"] = config_entry.get("enabled", True)
            elif config_entry is not None:
                plugin["enabled"] = True
            elif source == "stock":
                plugin["enabled"] = None

            plugins.append(plugin)

    return jsonify(
        {
            "plugins": plugins,
            "allow": plugins_allow,
            "contextEngineSlot": ((cfg.get("plugins", {}) or {}).get("slots", {}) or {}).get("contextEngine", ""),
            "totalCustom": sum(1 for plugin in plugins if plugin["source"] == "custom"),
            "totalStock": sum(1 for plugin in plugins if plugin["source"] == "stock"),
        }
    )


@settings_bp.route("/api/skills/setup-request", methods=["POST"])
def api_skills_setup_request() -> Response:
    """Queue a skill setup request placeholder response.

    Validate that the requested skill exists in the discovered skill catalog and
    return the acknowledgement payload expected by the settings UI. The route
    currently confirms the request without persisting any setup job details.

    Dependencies:
        Uses request JSON and _discover_settings_skills().

    Returns:
        A JSON acknowledgement response, or a validation error response.
    """
    body: dict[str, Any] = request.get_json(silent=True) or {}
    skill_name = str(body.get("skill", "")).strip()

    if not skill_name:
        return jsonify({"error": "skill is required"}), 400

    available_skills = {skill["name"] for skill in _discover_settings_skills()}
    if skill_name not in available_skills:
        return jsonify({"error": f"Unknown skill: {skill_name}"}), 400

    return jsonify({"message": "Setup request queued"})


@settings_bp.route("/api/settings/check-update")
def api_check_update() -> Response:
    """Check whether the dashboard is behind `origin/main`.

    Fetch the remote main branch, compare the local HEAD against `origin/main`,
    and report whether an update is available along with short commit hashes and
    the current branch name. Timeout handling is explicit because the route shells out to git.

    Dependencies:
        Uses subprocess git commands executed inside DASHBOARD_REPO_DIR.

    Returns:
        A JSON response describing update availability, or an error response if git commands fail.
    """
    import subprocess

    try:
        fetch_result = subprocess.run(
            ["git", "fetch", "origin", "main"], cwd=DASHBOARD_REPO_DIR, capture_output=True, text=True, timeout=30
        )
        if fetch_result.returncode != 0:
            return jsonify({"error": f"git fetch failed: {fetch_result.stderr.strip()}"}), 500

        local = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=DASHBOARD_REPO_DIR, capture_output=True, text=True, timeout=10
        ).stdout.strip()

        remote = subprocess.run(
            ["git", "rev-parse", "origin/main"], cwd=DASHBOARD_REPO_DIR, capture_output=True, text=True, timeout=10
        ).stdout.strip()

        behind_result = subprocess.run(
            ["git", "rev-list", "--count", f"HEAD..origin/main"],
            cwd=DASHBOARD_REPO_DIR,
            capture_output=True,
            text=True,
            timeout=10,
        )
        behind = int(behind_result.stdout.strip()) if behind_result.returncode == 0 else 0

        branch_result = subprocess.run(
            ["git", "branch", "--show-current"], cwd=DASHBOARD_REPO_DIR, capture_output=True, text=True, timeout=10
        )
        branch = branch_result.stdout.strip()

        return jsonify(
            {
                "available": behind > 0,
                "behind": behind,
                "local": local[:12],
                "remote": remote[:12],
                "branch": branch,
            }
        )
    except subprocess.TimeoutExpired:
        return jsonify({"error": "git command timed out"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@settings_bp.route("/api/settings/update", methods=["POST"])
def api_apply_update() -> Response:
    """Apply a fast-forward update from `origin/main`.

    Run `git pull --ff-only` in the dashboard repository so the settings UI can
    trigger a safe update without creating merge commits. The response includes
    command output and a user-facing message describing success or failure.

    Dependencies:
        Uses subprocess git commands executed inside DASHBOARD_REPO_DIR.

    Returns:
        A JSON response containing update status, command output, and any error text.
    """
    import subprocess

    try:
        pull_result = subprocess.run(
            ["git", "pull", "--ff-only", "origin", "main"],
            cwd=DASHBOARD_REPO_DIR,
            capture_output=True,
            text=True,
            timeout=60,
        )

        success = pull_result.returncode == 0
        output = pull_result.stdout.strip()
        error = pull_result.stderr.strip()

        return jsonify(
            {
                "success": success,
                "output": output,
                "error": error if not success else None,
                "message": "Update applied successfully. Restart the dashboard to load changes."
                if success
                else f"Update failed: {error}",
            }
        ), 200 if success else 500
    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "error": "git pull timed out", "message": "Update timed out after 60s"}), 504
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "message": f"Update error: {e}"}), 500
