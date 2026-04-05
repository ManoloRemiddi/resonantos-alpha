"""Knowledge routes."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, jsonify, request

from routes.config import OPENCLAW_CONFIG, OPENCLAW_HOME, SSOT_ACCESS_FILE, SSOT_ROOT
from routes.shared import _load_ssot_access_store

knowledge_bp = Blueprint("knowledge", __name__)


def _read_ssot_access(agent_id: str, levels: tuple[str, ...] = ("L0", "L1", "L2")) -> dict[str, bool]:
    """Read SSoT access for an agent.
    Compute a normalized helper value for the routes in this module. Keeping the shared
    logic here avoids duplicating fallback behavior and data-shape cleanup across
    handlers.

    Args:
        agent_id (str): Value supplied by the caller.
        levels (tuple[str, ...]): Value supplied by the caller. Optional.
    Returns:
        dict[str, bool]: Structured mapping assembled from config files, runtime state,
        or parsed content.
    Dependencies:
        Module-level constants and standard-library helpers imported by this module.
    Called by:
        `api_knowledge_ssot`, `api_knowledge_ssot_access`.
    Side effects:
        None."""
    normalized = {level: False for level in levels}
    if not agent_id:
        return normalized

    store = _load_ssot_access_store()
    access = store.get(agent_id, {})
    if not isinstance(access, dict):
        return normalized

    for level in levels:
        normalized[level] = bool(access.get(level, normalized[level]))
    return normalized


def _write_ssot_access(agent_id: str, access: dict[str, Any], levels: tuple[str, ...] = ("L0", "L1", "L2")) -> None:
    """Write SSoT access for an agent.
    Parse raw files, paths, or structured text into a predictable shape for downstream
    callers. Centralizing the parsing rules here keeps the route handlers focused on
    request validation and response formatting.

    Args:
        agent_id (str): Value supplied by the caller.
        access (dict[str, Any]): Value supplied by the caller.
        levels (tuple[str, ...]): Value supplied by the caller. Optional.
    Returns:
        None: This helper updates state in place and does not return a value.
    Dependencies:
        SSOT_ACCESS_FILE and json.
    Called by:
        `api_knowledge_ssot_access`.
    Side effects:
        Creates parent directories when required by the requested operation. Raises a
        validation error when required identifiers are missing. Writes dashboard-managed
        JSON or text files on disk."""
    if not agent_id:
        raise ValueError("agent_id is required")

    normalized = {level: False for level in levels}
    if isinstance(access, dict):
        for level in levels:
            normalized[level] = bool(access.get(level, normalized[level]))

    store = _load_ssot_access_store()
    store[agent_id] = normalized
    SSOT_ACCESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SSOT_ACCESS_FILE.write_text(json.dumps(store, indent=2))


@knowledge_bp.route("/api/knowledge/base")
def api_knowledge_base() -> Response:
    """Return knowledge base structure and indexed status.
    Validate request input, gather the requested dashboard data from backing files or
    runtime state, and return it as JSON. Keeping the lookup flow in this handler
    preserves a single API contract for the dashboard UI.

    Returns:
        Response: JSON response payload returned to the dashboard client.
    Dependencies:
        OPENCLAW_CONFIG, OPENCLAW_HOME, Path, json, and jsonify.
    Side effects:
        Reads request and filesystem state without mutating module-level globals."""
    kb_root = OPENCLAW_HOME / "knowledge"
    common_dir = kb_root / "common"
    common_dir_resolved = common_dir.resolve()

    def _ordered_unique(values: list[str]) -> list[str]:
        """Return ordered unique values.
        Compute a normalized helper value for the routes in this module. Keeping the
        shared logic here avoids duplicating fallback behavior and data-shape cleanup
        across handlers.

        Args:
            values (list[str]): Value supplied by the caller.
        Returns:
            list[str]: Ordered collection assembled from the backing dashboard data
            sources.
        Dependencies:
            Module-level constants and standard-library helpers imported by this module.
        Called by:
            `api_knowledge_base`.
        Side effects:
            None."""
        out = []
        seen = set()
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            out.append(value)
        return out

    def _normalize_path(path_str: str) -> str:
        """Normalize a filesystem path.
        Parse raw files, paths, or structured text into a predictable shape for
        downstream callers. Centralizing the parsing rules here keeps the route handlers
        focused on request validation and response formatting.

        Args:
            path_str (str): Value supplied by the caller.
        Returns:
            str: Normalized string value prepared for downstream callers.
        Dependencies:
            Path.
        Called by:
            `api_knowledge_base`.
        Side effects:
            None."""
        try:
            return str(Path(path_str).expanduser().resolve())
        except Exception:
            return str(Path(path_str).expanduser())

    def _list_agent_ids(cfg: dict[str, Any]) -> list[str]:
        """List configured agent ids.
        Compute a normalized helper value for the routes in this module. Keeping the
        shared logic here avoids duplicating fallback behavior and data-shape cleanup
        across handlers.

        Args:
            cfg (dict[str, Any]): Value supplied by the caller.
        Returns:
            list[str]: Ordered collection assembled from the backing dashboard data
            sources.
        Dependencies:
            Module-level constants and standard-library helpers imported by this module.
        Called by:
            `api_knowledge_base`.
        Side effects:
            None."""
        agents_cfg = cfg.get("agents", {}) if isinstance(cfg, dict) else {}
        discovered = []
        if isinstance(agents_cfg.get("list"), list):
            for item in agents_cfg.get("list", []):
                if isinstance(item, dict):
                    aid = str(item.get("id", "")).strip()
                    if aid:
                        discovered.append(aid)
        for key, value in agents_cfg.items():
            if key in {"defaults", "list"}:
                continue
            if isinstance(value, dict):
                discovered.append(key)

        preferred = ["main", "foreman", "setup"]
        ordered = [aid for aid in preferred if aid in discovered]
        ordered.extend([aid for aid in discovered if aid not in preferred])
        return _ordered_unique(ordered)

    def _agent_extra_paths(cfg: dict[str, Any], agent_id: str) -> list[str]:
        """Return extra knowledge paths for an agent.
        Compute a normalized helper value for the routes in this module. Keeping the
        shared logic here avoids duplicating fallback behavior and data-shape cleanup
        across handlers.

        Args:
            cfg (dict[str, Any]): Value supplied by the caller.
            agent_id (str): Value supplied by the caller.
        Returns:
            list[str]: Ordered collection assembled from the backing dashboard data
            sources.
        Dependencies:
            Module-level constants and standard-library helpers imported by this module.
        Called by:
            `api_knowledge_base`.
        Side effects:
            None."""
        agents_cfg = cfg.get("agents", {}) if isinstance(cfg, dict) else {}
        defaults = agents_cfg.get("defaults", {}).get("memorySearch", {}).get("extraPaths", [])
        out = list(defaults) if isinstance(defaults, list) else []

        legacy_cfg = agents_cfg.get(agent_id, {})
        if isinstance(legacy_cfg, dict):
            legacy_paths = legacy_cfg.get("memorySearch", {}).get("extraPaths")
            if isinstance(legacy_paths, list):
                out = list(legacy_paths)

        for item in agents_cfg.get("list", []):
            if not isinstance(item, dict) or item.get("id") != agent_id:
                continue
            list_paths = item.get("memorySearch", {}).get("extraPaths")
            if isinstance(list_paths, list):
                out = list(list_paths)
            break

        return [str(p) for p in out]

    try:
        config = json.loads(OPENCLAW_CONFIG.read_text()) if OPENCLAW_CONFIG.exists() else {}
    except Exception:
        config = {}

    agent_ids = _list_agent_ids(config)
    common_access = {}
    extra_paths = {}
    for aid in agent_ids:
        paths = _agent_extra_paths(config, aid)
        normalized = {_normalize_path(p) for p in paths}
        extra_paths[aid] = paths
        common_access[aid] = str(common_dir_resolved) in normalized

    folders = {}
    if kb_root.exists():
        for folder in sorted(kb_root.iterdir(), key=lambda p: p.name.lower()):
            if not folder.is_dir():
                continue
            files = []
            for f in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
                if not f.is_file():
                    continue
                try:
                    st = f.stat()
                    files.append(
                        {
                            "name": f.name,
                            "size": st.st_size,
                            "modified": int(st.st_mtime * 1000),
                            "path": str(f.relative_to(kb_root)),
                        }
                    )
                except Exception:
                    continue
            folders[folder.name] = {
                "path": str(folder),
                "fileCount": len(files),
                "files": files,
                "totalFiles": len(files),
            }

    return jsonify(
        {
            "folders": folders,
            "extraPaths": extra_paths,
            "commonAccess": common_access,
            "agentOrder": agent_ids,
            "kbRoot": str(kb_root),
            "commonFolder": "common",
        }
    )


@knowledge_bp.route("/api/knowledge/common-access", methods=["POST"])
def api_knowledge_common_access() -> Response:
    """Enable/disable common knowledge folder access per agent.
    Validate request input, update the backing file or local system state when needed,
    and return JSON describing the result. Keeping the mutation flow in this handler
    preserves a single API contract for the dashboard UI.

    Returns:
        Response: JSON response payload returned to the dashboard client.
    Dependencies:
        OPENCLAW_CONFIG, OPENCLAW_HOME, Path, json, jsonify, and request.
    Side effects:
        Writes dashboard-managed JSON or text files on disk."""
    data: dict[str, Any] = request.get_json(silent=True) or {}
    agent_id = str(data.get("agentId", "")).strip()
    enabled = bool(data.get("enabled"))
    if not agent_id:
        return jsonify({"error": "agentId required"}), 400

    kb_root = OPENCLAW_HOME / "knowledge"
    common_dir = (kb_root / "common").resolve()

    try:
        cfg = json.loads(OPENCLAW_CONFIG.read_text()) if OPENCLAW_CONFIG.exists() else {}
    except Exception as e:
        return jsonify({"error": f"Failed to read config: {e}"}), 500

    if "agents" not in cfg or not isinstance(cfg["agents"], dict):
        cfg["agents"] = {}
    agents_cfg = cfg["agents"]
    if "list" not in agents_cfg or not isinstance(agents_cfg["list"], list):
        agents_cfg["list"] = []

    entry = None
    for item in agents_cfg["list"]:
        if isinstance(item, dict) and item.get("id") == agent_id:
            entry = item
            break
    if entry is None:
        entry = {"id": agent_id}
        agents_cfg["list"].append(entry)

    if "memorySearch" not in entry or not isinstance(entry["memorySearch"], dict):
        entry["memorySearch"] = {}
    current_paths = entry["memorySearch"].get("extraPaths", [])
    if not isinstance(current_paths, list):
        current_paths = []

    normalized_paths = []
    seen = set()
    for path_value in current_paths:
        p = str(path_value)
        if p in seen:
            continue
        seen.add(p)
        normalized_paths.append(p)

    common_path = str(common_dir)
    present = False
    for p in normalized_paths:
        try:
            if Path(p).expanduser().resolve() == common_dir:
                present = True
                break
        except Exception:
            continue

    if enabled and not present:
        normalized_paths.append(common_path)
    if not enabled:
        filtered = []
        for p in normalized_paths:
            try:
                if Path(p).expanduser().resolve() == common_dir:
                    continue
            except Exception:
                pass
            filtered.append(p)
        normalized_paths = filtered

    entry["memorySearch"]["extraPaths"] = normalized_paths

    try:
        OPENCLAW_CONFIG.write_text(json.dumps(cfg, indent=2))
    except Exception as e:
        return jsonify({"error": f"Failed to write config: {e}"}), 500

    return jsonify(
        {
            "ok": True,
            "agentId": agent_id,
            "enabled": enabled,
            "commonPath": common_path,
            "extraPaths": normalized_paths,
        }
    )


@knowledge_bp.route("/api/knowledge/ssot")
def api_knowledge_ssot() -> Response:
    """Return SSoT folders and per-agent level access config.
    Validate request input, gather the requested dashboard data from backing files or
    runtime state, and return it as JSON. Keeping the lookup flow in this handler
    preserves a single API contract for the dashboard UI.

    Returns:
        Response: JSON response payload returned to the dashboard client.
    Dependencies:
        OPENCLAW_CONFIG, Path, json, and jsonify.
    Side effects:
        Reads request and filesystem state without mutating module-level globals."""
    ssot_root = SSOT_ROOT
    levels = ("L0", "L1", "L2")

    def _ordered_unique(values: list[str]) -> list[str]:
        """Return ordered unique values.
        Compute a normalized helper value for the routes in this module. Keeping the
        shared logic here avoids duplicating fallback behavior and data-shape cleanup
        across handlers.

        Args:
            values (list[str]): Value supplied by the caller.
        Returns:
            list[str]: Ordered collection assembled from the backing dashboard data
            sources.
        Dependencies:
            Module-level constants and standard-library helpers imported by this module.
        Called by:
            `api_knowledge_ssot`.
        Side effects:
            None."""
        out = []
        seen = set()
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            out.append(value)
        return out

    def _list_agent_ids(cfg: dict[str, Any]) -> list[str]:
        """List configured agent ids.
        Compute a normalized helper value for the routes in this module. Keeping the
        shared logic here avoids duplicating fallback behavior and data-shape cleanup
        across handlers.

        Args:
            cfg (dict[str, Any]): Value supplied by the caller.
        Returns:
            list[str]: Ordered collection assembled from the backing dashboard data
            sources.
        Dependencies:
            Module-level constants and standard-library helpers imported by this module.
        Called by:
            `api_knowledge_ssot`.
        Side effects:
            None."""
        agents_cfg = cfg.get("agents", {}) if isinstance(cfg, dict) else {}
        discovered = []
        if isinstance(agents_cfg.get("list"), list):
            for item in agents_cfg.get("list", []):
                if isinstance(item, dict):
                    aid = str(item.get("id", "")).strip()
                    if aid:
                        discovered.append(aid)
        for key, value in agents_cfg.items():
            if key in {"defaults", "list"}:
                continue
            if isinstance(value, dict):
                discovered.append(key)

        preferred = ["main", "foreman", "setup"]
        ordered = [aid for aid in preferred if aid in discovered]
        ordered.extend([aid for aid in discovered if aid not in preferred])
        return _ordered_unique(ordered)

    try:
        config = json.loads(OPENCLAW_CONFIG.read_text()) if OPENCLAW_CONFIG.exists() else {}
    except Exception:
        config = {}

    agent_ids = _list_agent_ids(config)
    if not agent_ids:
        agent_ids = ["main", "foreman", "setup"]

    level_info = {}
    for level in levels:
        level_dir = ssot_root / level
        exists = level_dir.exists() and level_dir.is_dir()
        file_count = 0
        markdown_count = 0
        if exists:
            for item in level_dir.rglob("*"):
                if not item.is_file() or item.name.startswith("."):
                    continue
                file_count += 1
                if item.suffix.lower() == ".md":
                    markdown_count += 1
        level_info[level] = {
            "path": str(level_dir),
            "exists": exists,
            "fileCount": file_count,
            "markdownCount": markdown_count,
        }

    ssot_access = {agent_id: _read_ssot_access(agent_id, levels) for agent_id in agent_ids}

    return jsonify(
        {
            "ssotRoot": str(ssot_root),
            "levels": level_info,
            "agentOrder": agent_ids,
            "ssotAccess": ssot_access,
        }
    )


@knowledge_bp.route("/api/knowledge/ssot-access", methods=["POST"])
def api_knowledge_ssot_access() -> Response:
    """Enable/disable access to a single SSoT level per agent.
    Validate request input, gather the requested dashboard data from backing files or
    runtime state, and return it as JSON. Keeping the lookup flow in this handler
    preserves a single API contract for the dashboard UI.

    Returns:
        Response: JSON response payload returned to the dashboard client.
    Dependencies:
        Path, jsonify, and request.
    Side effects:
        Reads request and filesystem state without mutating module-level globals."""
    data: dict[str, Any] = request.get_json(silent=True) or {}
    agent_id = str(data.get("agentId", "")).strip()
    level = str(data.get("level", "")).strip().upper()
    enabled = bool(data.get("enabled"))
    valid_levels = {"L0", "L1", "L2"}

    if not agent_id:
        return jsonify({"error": "agentId required"}), 400
    if level not in valid_levels:
        return jsonify({"error": "level must be one of L0, L1, L2"}), 400

    try:
        normalized_access = _read_ssot_access(agent_id)
    except Exception as e:
        return jsonify({"error": f"Failed to read SSoT access: {e}"}), 500

    normalized_access[level] = enabled

    try:
        _write_ssot_access(agent_id, normalized_access)
    except Exception as e:
        return jsonify({"error": f"Failed to write SSoT access: {e}"}), 500

    level_path = str(SSOT_ROOT / level)
    return jsonify(
        {
            "ok": True,
            "agentId": agent_id,
            "level": level,
            "enabled": enabled,
            "levelPath": level_path,
            "ssotAccess": normalized_access,
        }
    )


@knowledge_bp.route("/api/knowledge/file")
def api_knowledge_file() -> Response:
    """Read content of a knowledge file.
    Validate request input, gather the requested dashboard data from backing files or
    runtime state, and return it as JSON. Keeping the lookup flow in this handler
    preserves a single API contract for the dashboard UI.

    Returns:
        Response: JSON response payload returned to the dashboard client.
    Dependencies:
        OPENCLAW_HOME, Path, jsonify, and request.
    Side effects:
        Reads request and filesystem state without mutating module-level globals."""
    kb_root = (OPENCLAW_HOME / "knowledge").resolve()
    raw_path = request.args.get("path", "").strip()
    if not raw_path:
        return jsonify({"error": "path required"}), 400

    candidate = Path(raw_path)
    filepath = candidate if candidate.is_absolute() else kb_root / candidate
    try:
        resolved = filepath.expanduser().resolve()
    except Exception:
        return jsonify({"error": "Invalid path"}), 400

    if not resolved.is_relative_to(kb_root):
        return jsonify({"error": "Access denied"}), 403
    if not resolved.exists():
        return jsonify({"error": "File not found"}), 404
    if not resolved.is_file():
        return jsonify({"error": "Not a file"}), 400

    try:
        raw = resolved.read_bytes()
        content = raw.decode("utf-8", errors="replace")
        st = resolved.stat()
        return jsonify(
            {
                "path": str(resolved.relative_to(kb_root)),
                "name": resolved.name,
                "content": content,
                "size": st.st_size,
                "modified": int(st.st_mtime * 1000),
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@knowledge_bp.route("/api/knowledge/file", methods=["DELETE"])
def api_knowledge_file_delete() -> Response:
    """Delete a knowledge file.
    Validate request input, update the backing file or local system state when needed,
    and return JSON describing the result. Keeping the mutation flow in this handler
    preserves a single API contract for the dashboard UI.

    Returns:
        Response: JSON response payload returned to the dashboard client.
    Dependencies:
        OPENCLAW_HOME, Path, jsonify, and request.
    Side effects:
        Deletes files from disk when the request is authorized."""
    kb_root = (OPENCLAW_HOME / "knowledge").resolve()
    data: dict[str, Any] = request.get_json() or {}
    raw_path = data.get("path", "").strip()
    if not raw_path:
        return jsonify({"error": "path required"}), 400

    candidate = Path(raw_path)
    filepath = candidate if candidate.is_absolute() else kb_root / candidate
    try:
        resolved = filepath.expanduser().resolve()
    except Exception:
        return jsonify({"error": "Invalid path"}), 400

    if not resolved.is_relative_to(kb_root):
        return jsonify({"error": "Access denied"}), 403
    if not resolved.exists():
        return jsonify({"error": "File not found"}), 404

    try:
        resolved.unlink()
        return jsonify({"ok": True, "path": str(resolved.relative_to(kb_root))})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@knowledge_bp.route("/api/knowledge/upload", methods=["POST"])
def api_knowledge_upload() -> Response:
    """Upload a file to a knowledge folder.
    Validate request input, update the backing file or local system state when needed,
    and return JSON describing the result. Keeping the mutation flow in this handler
    preserves a single API contract for the dashboard UI.

    Returns:
        Response: JSON response payload returned to the dashboard client.
    Dependencies:
        OPENCLAW_HOME, Path, jsonify, re, request, and time.
    Side effects:
        Creates parent directories when required by the requested operation. Persists
        uploaded file content to the knowledge store."""
    kb_root = (OPENCLAW_HOME / "knowledge").resolve()
    folder_raw = (request.form.get("folder") or request.form.get("target") or "").strip()
    if not folder_raw:
        return jsonify({"error": "folder required"}), 400

    folder_path = Path(folder_raw)
    if folder_path.is_absolute() or ".." in folder_path.parts:
        return jsonify({"error": "Invalid folder"}), 400

    file = request.files.get("file")
    if file is None or not file.filename:
        return jsonify({"error": "file required"}), 400

    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(file.filename).name).strip("._")
    if not safe_name:
        return jsonify({"error": "Invalid filename"}), 400

    target_dir = (kb_root / folder_path).resolve()
    if not target_dir.is_relative_to(kb_root):
        return jsonify({"error": "Access denied"}), 403
    target_dir.mkdir(parents=True, exist_ok=True)

    target_file = target_dir / safe_name
    if target_file.exists():
        stem, suffix = target_file.stem, target_file.suffix
        target_file = target_dir / f"{stem}_{int(time.time())}{suffix}"

    try:
        file.save(str(target_file))
        st = target_file.stat()
        return jsonify(
            {
                "ok": True,
                "folder": str(target_dir.relative_to(kb_root)),
                "name": target_file.name,
                "path": str(target_file.relative_to(kb_root)),
                "size": st.st_size,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@knowledge_bp.route("/api/knowledge/index", methods=["POST"])
def api_knowledge_index() -> Response:
    """Trigger re-indexing of knowledge folders.
    Validate request input, gather the requested dashboard data from backing files or
    runtime state, and return it as JSON. Keeping the lookup flow in this handler
    preserves a single API contract for the dashboard UI.

    Returns:
        Response: JSON response payload returned to the dashboard client.
    Dependencies:
        jsonify.
    Side effects:
        Reads request and filesystem state without mutating module-level globals."""
    return jsonify({"status": "triggered", "message": "Knowledge folders will be re-indexed on next file change"})
