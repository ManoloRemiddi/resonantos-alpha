"""Legacy helpers retained for dashboard compatibility — R-Memory system replaced by LCM.

R-Memory routes.
"""

from __future__ import annotations

import glob
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, jsonify, request

from routes.config import RMEMORY_CONFIG, RMEMORY_DIR, RMEMORY_LOG, SSOT_ROOT, WORKSPACE
from routes.logging_config import get_logger
from routes.shared import gw

rmemory_bp = Blueprint("rmemory", __name__)
logger = get_logger(__name__)

SSOT_KEYWORDS_FILE: Path = SSOT_ROOT / ".ssot-keywords.json"
R_AWARENESS_KEYWORDS_FILE: Path = WORKSPACE / "r-awareness" / "keywords.json"


def _rmem_config() -> dict[str, Any]:
    """Read r-memory/config.json.
    Parse raw files, paths, or structured text into a predictable shape for downstream
    callers. Centralizing the parsing rules here keeps the route handlers focused on
    request validation and response formatting.

    Returns:
        dict[str, Any]: Structured mapping assembled from config files, runtime state,
        or parsed content.
    Dependencies:
        RMEMORY_CONFIG and json.
    Called by:
        `_rmem_effective_models`, `api_rmemory_config`.
    Side effects:
        None."""
    try:
        return json.loads(RMEMORY_CONFIG.read_text())
    except Exception:
        return {"compressTrigger": 36000, "evictTrigger": 80000, "blockSize": 4000}


def _rmem_camouflage() -> dict[str, Any]:
    """Read r-memory/camouflage.json.
    Parse raw files, paths, or structured text into a predictable shape for downstream
    callers. Centralizing the parsing rules here keeps the route handlers focused on
    request validation and response formatting.

    Returns:
        dict[str, Any]: Structured mapping assembled from config files, runtime state,
        or parsed content.
    Dependencies:
        RMEMORY_DIR and json.
    Called by:
        `_rmem_effective_models`.
    Side effects:
        None."""
    try:
        return json.loads((RMEMORY_DIR / "camouflage.json").read_text())
    except Exception:
        return {"enabled": False}


def _rmem_effective_models() -> dict[str, Any]:
    """Resolve the actual runtime models for compression and narrative.
    Compute a normalized helper value for the routes in this module. Keeping the shared
    logic here avoids duplicating fallback behavior and data-shape cleanup across
    handlers.

    Returns:
        dict[str, Any]: Structured mapping assembled from config files, runtime state,
        or parsed content.
    Dependencies:
        Module-level constants and standard-library helpers imported by this module.
    Called by:
        `api_rmemory_effective_models`.
    Side effects:
        None."""
    cfg = _rmem_config()
    camo = _rmem_camouflage()
    base_model = cfg.get("compressionModel", "anthropic/claude-haiku-4-5")

    narrative_override = cfg.get("narrativeModel")

    if camo.get("enabled") and camo.get("elements", {}).get("trafficSegregation"):
        pref = camo.get("preferredBackgroundProvider", "openai")
        bg_models = camo.get("backgroundModels", {})
        compression_model = bg_models.get(pref, base_model) if camo.get("routeCompressionOffAnthro") else base_model
        narrative_model = narrative_override or (
            bg_models.get(f"{pref}-narrative", bg_models.get(pref, base_model))
            if camo.get("routeNarrativeOffAnthro")
            else base_model
        )
    else:
        compression_model = base_model
        narrative_model = narrative_override or base_model

    warning = None
    if narrative_model and "minimax-m2.5" in narrative_model.lower():
        warning = "MiniMax M2.5 is incompatible with the narrative tracker (hallucinates tool calls). Defaulting to M2.1 at runtime."

    result = {
        "compression": compression_model,
        "narrative": narrative_model,
    }
    if warning:
        result["warning"] = warning
    return result


def _rmem_history_blocks(session_id: str | None = None) -> list[dict[str, Any]]:
    """Read compressed blocks from history-{sessionId}.json files AND block-cache.json.
    Parse raw files, paths, or structured text into a predictable shape for downstream
    callers. Centralizing the parsing rules here keeps the route handlers focused on
    request validation and response formatting.

    Args:
        session_id (str | None): Value supplied by the caller. Optional.
    Returns:
        list[dict[str, Any]]: Ordered collection assembled from the backing dashboard
        data sources.
    Dependencies:
        Path, RMEMORY_DIR, glob, and json.
    Called by:
        `api_rmemory_stats`.
    Side effects:
        None."""
    all_blocks = []
    history_hashes = set()

    pattern = str(RMEMORY_DIR / "history-*.json")
    files = glob.glob(pattern)
    for f in files:
        if session_id and session_id not in f:
            continue
        try:
            data = json.loads(Path(f).read_text())
            if isinstance(data, list):
                for b in data:
                    b["_file"] = Path(f).name
                    b["_source"] = "history"
                    all_blocks.append(b)
                    if "hash" in b:
                        history_hashes.add(b["hash"])
        except Exception:
            logger.debug("Failed to read R-Memory history file %s", f, exc_info=True)

    if not session_id:
        cache_file = RMEMORY_DIR / "block-cache.json"
        if cache_file.exists():
            try:
                cache_data = json.loads(cache_file.read_text())
                if isinstance(cache_data, dict):
                    for cache_hash, entry in cache_data.items():
                        if str(cache_hash) in history_hashes:
                            continue
                        if not isinstance(entry, dict):
                            continue
                        raw_tokens = int(entry.get("tokensRaw", 0) or 0)
                        comp_tokens = int(entry.get("tokensCompressed", 0) or 0)
                        if raw_tokens <= 0 and comp_tokens <= 0:
                            continue
                        cache_block = {
                            "tokensRaw": raw_tokens,
                            "tokensCompressed": comp_tokens,
                            "compressed": entry.get("compressed", ""),
                            "hash": str(cache_hash),
                            "_file": "block-cache.json",
                            "_source": "cache",
                        }
                        all_blocks.append(cache_block)
            except Exception:
                logger.debug("Failed to read R-Memory block cache from %s", cache_file, exc_info=True)

    return all_blocks


def _rmem_current_session_id() -> str | None:
    """Get the current main session ID (short hash) from the most recently modified history file.
    Parse raw files, paths, or structured text into a predictable shape for downstream
    callers. Centralizing the parsing rules here keeps the route handlers focused on
    request validation and response formatting.

    Returns:
        str | None: Value described by `Get the current main session ID (short hash)
        from the most recently modified history file`.
    Dependencies:
        Path, RMEMORY_DIR, glob, and re.
    Called by:
        `api_rmemory_stats`.
    Side effects:
        None."""
    pattern = str(RMEMORY_DIR / "history-*.json")
    files = glob.glob(pattern)
    if not files:
        return None
    newest = max(files, key=lambda f: Path(f).stat().st_mtime)
    m = re.search(r"history-([a-f0-9]+)\.json", newest)
    return m.group(1) if m else None


def _rmem_parse_log() -> list[dict[str, Any]]:
    """Parse r-memory.log (text format) into structured events.
    Parse raw files, paths, or structured text into a predictable shape for downstream
    callers. Centralizing the parsing rules here keeps the route handlers focused on
    request validation and response formatting.

    Returns:
        list[dict[str, Any]]: Ordered collection assembled from the backing dashboard
        data sources.
    Dependencies:
        RMEMORY_LOG, json, and re.
    Called by:
        `api_rmemory_stats`.
    Side effects:
        None."""
    events = []
    if not RMEMORY_LOG.exists():
        return events
    try:
        text = RMEMORY_LOG.read_text(errors="ignore")
    except Exception:
        logger.warning("Failed to read R-Memory log from %s", RMEMORY_LOG, exc_info=True)
        return events

    line_re = re.compile(r"^\[(\d{4}-\d{2}-\d{2}T[\d:.]+Z)\]\s+\[(\w+)\]\s+(.*)", re.MULTILINE)
    for m in line_re.finditer(text):
        ts, level, body = m.group(1), m.group(2), m.group(3)
        evt = {"ts": ts, "level": level, "raw": body}

        json_match = re.search(r"\{.*\}", body)
        payload = {}
        if json_match:
            try:
                payload = json.loads(json_match.group())
            except Exception:
                logger.debug("Failed to parse R-Memory log payload: %s", body, exc_info=True)

        if "=== COMPACTION ===" in body:
            evt["event"] = "compaction_start"
            evt.update(payload)
        elif "=== DONE ===" in body:
            evt["event"] = "compaction_done"
            evt.update(payload)
        elif "Swap plan" in body:
            evt["event"] = "swap_plan"
            evt.update(payload)
        elif "Block compressed" in body:
            evt["event"] = "block_compressed"
            evt.update(payload)
        elif "FIFO evicted" in body:
            evt["event"] = "fifo_evicted"
            evt.update(payload)
        elif "FIFO done" in body:
            evt["event"] = "fifo_done"
            evt.update(payload)
        elif body.startswith("Session "):
            evt["event"] = "session"
            evt.update(payload)
        elif "init" in body and ("R-Memory" in body or "r-memory" in body.lower()):
            evt["event"] = "init"
            evt.update(payload)
        elif "Config loaded" in body:
            evt["event"] = "config_loaded"
            evt.update(payload)
        else:
            evt["event"] = "info"

        events.append(evt)
    return events


def _rmem_gateway_session() -> dict[str, Any] | None:
    """Get main session data from sessions.json file directly.
    Parse raw files, paths, or structured text into a predictable shape for downstream
    callers. Centralizing the parsing rules here keeps the route handlers focused on
    request validation and response formatting.

    Returns:
        dict[str, Any] | None: Structured mapping assembled from config files, runtime
        state, or parsed content.
    Dependencies:
        Path, gw, and json.
    Called by:
        No in-module callers currently reference this helper.
    Side effects:
        None."""
    sessions_path = Path.home() / ".openclaw" / "agents" / "main" / "sessions" / "sessions.json"
    try:
        data = json.loads(sessions_path.read_text())
        if isinstance(data, dict) and "agent:main:main" in data:
            return data["agent:main:main"]
        if isinstance(data, list):
            for s in data:
                if s.get("key") == "agent:main:main":
                    return s
    except Exception:
        logger.debug("Failed to load R-Memory session snapshot from %s", sessions_path, exc_info=True)
    try:
        sess_result = gw.request("sessions.list", timeout=5)
        if sess_result.get("ok") and sess_result.get("payload"):
            sessions = sess_result["payload"].get("sessions", [])
            for s in sessions:
                if s.get("key") == "agent:main:main":
                    return s
    except Exception:
        logger.debug("Failed to query gateway for R-Memory session data", exc_info=True)
    return None


def _scan_ssot_layer(layer_dir: Path, layer_name: str) -> list[dict[str, Any]]:
    """Scan a layer directory (recursively) for SSoT documents.
    Parse raw files, paths, or structured text into a predictable shape for downstream
    callers. Centralizing the parsing rules here keeps the route handlers focused on
    request validation and response formatting.

    Args:
        layer_dir (Path): Value supplied by the caller.
        layer_name (str): Value supplied by the caller.
    Returns:
        list[dict[str, Any]]: Ordered collection assembled from the backing dashboard
        data sources.
    Dependencies:
        Path and SSOT_ROOT.
    Called by:
        `api_rmemory_documents`.
    Side effects:
        None."""
    docs = []
    if not layer_dir.exists():
        return docs

    for f in sorted(layer_dir.rglob("*.md")):
        if f.name.startswith("."):
            continue
        if f.name.endswith(".ai.md"):
            full_version = f.parent / (f.name[: -len(".ai.md")] + ".md")
            if full_version.exists():
                continue

        st = f.stat()
        ai_path = f.with_suffix(".ai.md")
        has_compressed = ai_path.exists()

        locked = False
        try:
            flags = st.st_flags
            locked = bool(flags & (0x02 | 0x00020000))
        except AttributeError:
            logger.debug("Filesystem flags unavailable for %s", f)

        raw_tokens = st.st_size // 4
        compressed_tokens = None
        if has_compressed:
            compressed_tokens = ai_path.stat().st_size // 4

        docs.append(
            {
                "path": str(f.relative_to(SSOT_ROOT)),
                "name": f.stem,
                "layer": layer_name,
                "size": st.st_size,
                "rawTokens": raw_tokens,
                "compressedTokens": compressed_tokens,
                "hasCompressed": has_compressed,
                "locked": locked,
                "modified": st.st_mtime,
            }
        )

    return docs


@rmemory_bp.route("/api/r-memory/documents")
def api_rmemory_documents() -> Response:
    """List all SSoT documents across layers.
    Validate request input, gather the requested dashboard data from backing files or
    runtime state, and return it as JSON. Keeping the lookup flow in this handler
    preserves a single API contract for the dashboard UI.

    Returns:
        Response: JSON response payload returned to the dashboard client.
    Dependencies:
        SSOT_ROOT and jsonify.
    Side effects:
        Reads request and filesystem state without mutating module-level globals."""
    all_docs = []
    for layer in ["L0", "L1", "L2", "L3", "L4"]:
        layer_dir = SSOT_ROOT / layer
        all_docs.extend(_scan_ssot_layer(layer_dir, layer))
    return jsonify(all_docs)


@rmemory_bp.route("/api/r-memory/document", methods=["GET"])
def api_rmemory_document() -> Response:
    """Read a single SSoT document. ?path=L1/FOO.md&compressed=true
    Validate request input, gather the requested dashboard data from backing files or
    runtime state, and return it as JSON. Keeping the lookup flow in this handler
    preserves a single API contract for the dashboard UI.

    Returns:
        Response: JSON response payload returned to the dashboard client.
    Dependencies:
        SSOT_ROOT, jsonify, and request.
    Side effects:
        Reads request and filesystem state without mutating module-level globals."""
    rel_path = request.args.get("path", "")
    use_compressed = request.args.get("compressed", "false").lower() == "true"

    if not rel_path or ".." in rel_path:
        return jsonify({"error": "invalid path"}), 400

    doc_path = SSOT_ROOT / rel_path
    if use_compressed:
        ai_path = doc_path.with_suffix(".ai.md")
        if ai_path.exists():
            doc_path = ai_path

    if not doc_path.exists():
        return jsonify({"error": "not found"}), 404

    return jsonify(
        {
            "path": rel_path,
            "content": doc_path.read_text(),
            "size": doc_path.stat().st_size,
        }
    )


@rmemory_bp.route("/api/r-memory/available-models", methods=["GET"])
def api_rmemory_available_models() -> Response:
    """Return compression model options based on user's configured providers.
    Validate request input, gather the requested dashboard data from backing files or
    runtime state, and return it as JSON. Keeping the lookup flow in this handler
    preserves a single API contract for the dashboard UI.

    Returns:
        Response: JSON response payload returned to the dashboard client.
    Dependencies:
        Path, json, and jsonify.
    Side effects:
        Reads request and filesystem state without mutating module-level globals."""
    cheap_models = {
        "anthropic": {"model": "anthropic/claude-haiku-4-5", "label": "Claude Haiku 4.5 (cheap)"},
        "openai": {"model": "openai/gpt-4o-mini", "label": "GPT-4o Mini (cheap)"},
        "google": {"model": "google/gemini-2.0-flash", "label": "Gemini 2.0 Flash (cheap)"},
        "minimax": {"model": "minimax/MiniMax-M2.5-Lightning", "label": "MiniMax M2.5 Lightning"},
    }
    full_models = {
        "anthropic": [
            {"model": "anthropic/claude-haiku-4-5", "label": "Claude Haiku 4.5 (cheap)"},
            {"model": "anthropic/claude-sonnet-4-5", "label": "Claude Sonnet 4.5"},
            {"model": "anthropic/claude-opus-4-6", "label": "Claude Opus 4.6"},
        ],
        "openai": [
            {"model": "openai/gpt-4o-mini", "label": "GPT-4o Mini (cheap)"},
            {"model": "openai/gpt-4o", "label": "GPT-4o"},
        ],
        "google": [
            {"model": "google/gemini-2.0-flash", "label": "Gemini 2.0 Flash (cheap)"},
        ],
        "minimax": [
            {"model": "minimax/MiniMax-M2.5-Lightning", "label": "MiniMax M2.5 Lightning"},
            {"model": "minimax/MiniMax-M2.5", "label": "MiniMax M2.5"},
            {"model": "minimax/MiniMax-M2.1", "label": "MiniMax M2.1"},
        ],
    }
    available = []
    try:
        auth_path = Path.home() / ".openclaw" / "agents" / "main" / "agent" / "auth-profiles.json"
        if auth_path.exists():
            data = json.loads(auth_path.read_text())
            seen_providers = set()
            for key, profile in data.get("profiles", {}).items():
                if profile.get("token"):
                    prov = profile.get("provider") or key.split(":")[0]
                    if prov not in seen_providers:
                        seen_providers.add(prov)
                        available.extend(full_models.get(prov, [{"model": f"{prov}/default", "label": prov}]))
    except Exception:
        logger.debug("Failed to load auth profiles for R-Memory model discovery", exc_info=True)
    if not available:
        available = [{"model": "anthropic/claude-haiku-4-5", "label": "Claude Haiku 4.5 (default)"}]
    return jsonify({"models": available})


@rmemory_bp.route("/api/r-memory/config", methods=["GET", "PUT"])
def api_rmemory_config() -> Response:
    """Read or update R-Memory config (including compressionModel).
    Validate request input, update the backing file or local system state when needed,
    and return JSON describing the result. Keeping the mutation flow in this handler
    preserves a single API contract for the dashboard UI.

    Returns:
        Response: JSON response payload returned to the dashboard client.
    Dependencies:
        RMEMORY_CONFIG, json, jsonify, and request.
    Side effects:
        Writes dashboard-managed JSON or text files on disk."""
    if request.method == "GET":
        return jsonify(_rmem_config())
    patch = request.get_json(force=True) or {}
    cfg = _rmem_config()
    cfg.update(patch)
    try:
        RMEMORY_CONFIG.write_text(json.dumps(cfg, indent=2))
        return jsonify({"ok": True, "config": cfg})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@rmemory_bp.route("/api/r-memory/effective-models", methods=["GET"])
def api_rmemory_effective_models() -> Response:
    """Return the actual runtime models.
    Validate request input, gather the requested dashboard data from backing files or
    runtime state, and return it as JSON. Keeping the lookup flow in this handler
    preserves a single API contract for the dashboard UI.

    Returns:
        Response: JSON response payload returned to the dashboard client.
    Dependencies:
        jsonify.
    Side effects:
        Reads request and filesystem state without mutating module-level globals."""
    return jsonify(_rmem_effective_models())


@rmemory_bp.route("/api/r-memory/narrative-model", methods=["PUT"])
def api_rmemory_narrative_model() -> Response:
    """Update the narrative tracker model in camouflage.json.
    Validate request input, update the backing file or local system state when needed,
    and return JSON describing the result. Keeping the mutation flow in this handler
    preserves a single API contract for the dashboard UI.

    Returns:
        Response: JSON response payload returned to the dashboard client.
    Dependencies:
        RMEMORY_DIR, json, jsonify, and request.
    Side effects:
        Writes dashboard-managed JSON or text files on disk."""
    patch: dict[str, Any] = request.get_json(force=True) or {}
    model = patch.get("model")
    if not model:
        return jsonify({"error": "model required"}), 400
    camo_path = RMEMORY_DIR / "camouflage.json"
    try:
        camo = json.loads(camo_path.read_text()) if camo_path.exists() else {}
        pref = camo.get("preferredBackgroundProvider", "openai")
        bg = camo.get("backgroundModels", {})
        bg[f"{pref}-narrative"] = model
        camo["backgroundModels"] = bg
        camo_path.write_text(json.dumps(camo, indent=2))
        return jsonify({"ok": True, "narrativeModel": model})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@rmemory_bp.route("/api/r-memory/open-log", methods=["POST"])
def api_rmemory_open_log() -> Response:
    """Open R-Memory log in Terminal.app.
    Validate request input, update the backing file or local system state when needed,
    and return JSON describing the result. Keeping the mutation flow in this handler
    preserves a single API contract for the dashboard UI.

    Returns:
        Response: JSON response payload returned to the dashboard client.
    Dependencies:
        jsonify and subprocess.
    Side effects:
        Invokes local subprocesses to inspect or mutate system state."""
    cmd = "tail -f ~/.openclaw/workspace/r-memory/r-memory.log"
    subprocess.Popen(["osascript", "-e", f'tell application "Terminal" to do script "{cmd}"'])
    return jsonify({"ok": True})


@rmemory_bp.route("/api/r-memory/stats")
def api_rmemory_stats() -> Response:
    """R-Memory runtime stats: blocks from history files, log events.
    Validate request input, gather the requested dashboard data from backing files or
    runtime state, and return it as JSON. Keeping the lookup flow in this handler
    preserves a single API contract for the dashboard UI.

    Returns:
        Response: JSON response payload returned to the dashboard client.
    Dependencies:
        RMEMORY_LOG and jsonify.
    Side effects:
        Reads request and filesystem state without mutating module-level globals."""
    all_blocks = _rmem_history_blocks()
    total_raw = sum(b.get("tokensRaw", 0) for b in all_blocks)
    total_comp = sum(b.get("tokensCompressed", 0) for b in all_blocks)

    cur_sid = _rmem_current_session_id()
    cur_blocks = [b for b in all_blocks if cur_sid and cur_sid in b.get("_file", "")]

    log_events = _rmem_parse_log()

    last_compaction = None
    for ev in log_events:
        if ev.get("event") == "compaction_done":
            last_compaction = ev

    in_context_blocks = last_compaction.get("historyBlocks", 0) if last_compaction else 0
    in_context_tokens = last_compaction.get("contentTokens", 0) if last_compaction else 0

    stats = {
        "blockCount": in_context_blocks,
        "contentTokens": in_context_tokens,
        "totalRawTokens": sum(b.get("tokensRaw", 0) for b in cur_blocks),
        "totalCompressedTokens": sum(b.get("tokensCompressed", 0) for b in cur_blocks),
        "compressionRatio": None,
        "storedBlockCount": len(cur_blocks),
        "allSessionsBlockCount": len(all_blocks),
        "allSessionsRawTokens": total_raw,
        "allSessionsCompressedTokens": total_comp,
        "currentSessionId": cur_sid,
        "logsExist": RMEMORY_LOG.exists(),
        "recentEvents": [],
    }

    if stats["totalRawTokens"] > 0:
        stats["compressionRatio"] = round(stats["totalCompressedTokens"] / stats["totalRawTokens"], 3)

    stats["recentEvents"] = log_events[-30:]

    return jsonify(stats)


@rmemory_bp.route("/api/r-memory/lock/<path:doc_path>", methods=["POST"])
def api_rmemory_lock(doc_path: str) -> Response:
    """Lock a document with chflags schg (requires sudo password).
    Validate request input, update the backing file or local system state when needed,
    and return JSON describing the result. Keeping the mutation flow in this handler
    preserves a single API contract for the dashboard UI.

    Args:
        doc_path (str): Value supplied by the caller.
    Returns:
        Response: JSON response payload returned to the dashboard client.
    Dependencies:
        SSOT_ROOT, jsonify, request, and subprocess.
    Side effects:
        Invokes local subprocesses to inspect or mutate system state."""
    full_path = SSOT_ROOT / doc_path
    if not full_path.exists():
        return jsonify({"error": "not found"}), 404
    body: dict[str, Any] = request.get_json(force=True) or {}
    password = body.get("password", "")
    if not password:
        return jsonify({"error": "password required — schg needs root"}), 403
    try:
        proc = subprocess.run(
            ["sudo", "-S", "chflags", "schg", str(full_path)],
            input=password.encode() + b"\n",
            capture_output=True,
            timeout=10,
        )
        if proc.returncode == 0:
            return jsonify({"ok": True, "locked": True})
        else:
            return jsonify({"ok": False, "error": "lock failed (wrong password?)"}), 403
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@rmemory_bp.route("/api/r-memory/unlock/<path:doc_path>", methods=["POST"])
def api_rmemory_unlock(doc_path: str) -> Response:
    """Unlock a document. Requires sudo password in body.
    Validate request input, update the backing file or local system state when needed,
    and return JSON describing the result. Keeping the mutation flow in this handler
    preserves a single API contract for the dashboard UI.

    Args:
        doc_path (str): Value supplied by the caller.
    Returns:
        Response: JSON response payload returned to the dashboard client.
    Dependencies:
        SSOT_ROOT, jsonify, request, and subprocess.
    Side effects:
        Invokes local subprocesses to inspect or mutate system state."""
    full_path = SSOT_ROOT / doc_path
    if not full_path.exists():
        return jsonify({"error": "not found"}), 404

    body: dict[str, Any] = request.get_json(force=True) or {}
    password = body.get("password", "")
    if not password:
        return jsonify({"error": "password required"}), 400

    try:
        proc = subprocess.run(
            ["sudo", "-S", "chflags", "noschg", str(full_path)],
            input=password.encode() + b"\n",
            capture_output=True,
            timeout=10,
        )
        if proc.returncode == 0:
            return jsonify({"ok": True, "locked": False})
        else:
            return jsonify({"ok": False, "error": "unlock failed (wrong password?)"}), 403
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@rmemory_bp.route("/api/r-memory/document", methods=["PUT"])
def api_rmemory_document_save() -> Response:
    """Save/update a SSoT document.
    Validate request input, update the backing file or local system state when needed,
    and return JSON describing the result. Keeping the mutation flow in this handler
    preserves a single API contract for the dashboard UI.

    Returns:
        Response: JSON response payload returned to the dashboard client.
    Dependencies:
        SSOT_ROOT, jsonify, and request.
    Side effects:
        Writes dashboard-managed JSON or text files on disk."""
    body: dict[str, Any] = request.get_json(force=True) or {}
    rel_path = body.get("path", "")
    content = body.get("content", "")
    if not rel_path or ".." in rel_path:
        return jsonify({"ok": False, "error": "invalid path"}), 400
    full_path = SSOT_ROOT / rel_path
    if not full_path.exists():
        return jsonify({"ok": False, "error": "not found"}), 404
    try:
        if hasattr(full_path.stat(), "st_flags") and full_path.stat().st_flags & 0x02:
            return jsonify({"ok": False, "error": "document is locked"}), 403
    except Exception:
        logger.debug("Failed to inspect document lock flags for %s", full_path, exc_info=True)
    try:
        full_path.write_text(content)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def _load_keywords() -> dict[str, list[str]]:
    """Load dashboard keywords {docPath: [kw1, kw2, ...]}.
    Parse raw files, paths, or structured text into a predictable shape for downstream
    callers. Centralizing the parsing rules here keeps the route handlers focused on
    request validation and response formatting.

    Returns:
        dict[str, list[str]]: Structured mapping assembled from config files, runtime
        state, or parsed content.
    Dependencies:
        json.
    Called by:
        `api_ssot_keywords_get`, `api_ssot_keywords_put`.
    Side effects:
        None."""
    try:
        return json.loads(SSOT_KEYWORDS_FILE.read_text())
    except Exception:
        return {}


def _load_r_awareness_keywords() -> dict[str, list[str]]:
    """Load R-Awareness keywords {keyword: docPath} and invert to dashboard format.
    Parse raw files, paths, or structured text into a predictable shape for downstream
    callers. Centralizing the parsing rules here keeps the route handlers focused on
    request validation and response formatting.

    Returns:
        dict[str, list[str]]: Structured mapping assembled from config files, runtime
        state, or parsed content.
    Dependencies:
        json.
    Called by:
        No in-module callers currently reference this helper.
    Side effects:
        None."""
    try:
        ra = json.loads(R_AWARENESS_KEYWORDS_FILE.read_text())
        result = {}
        for kw, path in ra.items():
            result.setdefault(path, []).append(kw)
        return result
    except Exception:
        return {}


def _sync_to_r_awareness(data: dict[str, list[str]]) -> None:
    """Write inverted keyword map to R-Awareness keywords.json. {docPath: [kws]} → {kw: docPath}.
    Parse raw files, paths, or structured text into a predictable shape for downstream
    callers. Centralizing the parsing rules here keeps the route handlers focused on
    request validation and response formatting.

    Args:
        data (dict[str, list[str]]): Value supplied by the caller.
    Returns:
        None: This helper updates state in place and does not return a value.
    Dependencies:
        SSOT_ROOT and json.
    Called by:
        `_save_keywords`.
    Side effects:
        Creates parent directories when required by the requested operation. Writes
        dashboard-managed JSON or text files on disk."""
    inverted = {}
    for doc_path, kws in data.items():
        ra_path = doc_path
        if doc_path.endswith(".md") and not doc_path.endswith(".ai.md"):
            ai_candidate = doc_path[:-3] + ".ai.md"
            if (SSOT_ROOT / ai_candidate).exists():
                ra_path = ai_candidate
        for kw in kws:
            inverted[kw.strip().lower()] = ra_path
    try:
        R_AWARENESS_KEYWORDS_FILE.parent.mkdir(parents=True, exist_ok=True)
        R_AWARENESS_KEYWORDS_FILE.write_text(json.dumps(inverted, indent=2))
    except Exception:
        logger.warning(
            "Failed to sync dashboard keywords to R-Awareness file %s",
            R_AWARENESS_KEYWORDS_FILE,
            exc_info=True,
        )


def _save_keywords(data: dict[str, list[str]]) -> None:
    """Save dashboard keywords.
    Parse raw files, paths, or structured text into a predictable shape for downstream
    callers. Centralizing the parsing rules here keeps the route handlers focused on
    request validation and response formatting.

    Args:
        data (dict[str, list[str]]): Value supplied by the caller.
    Returns:
        None: This helper updates state in place and does not return a value.
    Dependencies:
        json.
    Called by:
        `api_ssot_keywords_put`.
    Side effects:
        Writes dashboard-managed JSON or text files on disk."""
    SSOT_KEYWORDS_FILE.write_text(json.dumps(data, indent=2))
    _sync_to_r_awareness(data)


@rmemory_bp.route("/api/ssot/keywords", methods=["GET"])
@rmemory_bp.route("/api/r-memory/keywords", methods=["GET"])
def api_ssot_keywords_get() -> Response:
    """Return dashboard keywords.
    Validate request input, gather the requested dashboard data from backing files or
    runtime state, and return it as JSON. Keeping the lookup flow in this handler
    preserves a single API contract for the dashboard UI.

    Returns:
        Response: JSON response payload returned to the dashboard client.
    Dependencies:
        jsonify.
    Side effects:
        Reads request and filesystem state without mutating module-level globals."""
    return jsonify(_load_keywords())


@rmemory_bp.route("/api/ssot/keywords", methods=["PUT"])
@rmemory_bp.route("/api/r-memory/keywords", methods=["PUT"])
def api_ssot_keywords_put() -> Response:
    """Update dashboard keywords.
    Validate request input, gather the requested dashboard data from backing files or
    runtime state, and return it as JSON. Keeping the lookup flow in this handler
    preserves a single API contract for the dashboard UI.

    Returns:
        Response: JSON response payload returned to the dashboard client.
    Dependencies:
        jsonify and request.
    Side effects:
        Reads request and filesystem state without mutating module-level globals."""
    body: dict[str, Any] = request.get_json(force=True) or {}
    path = body.get("path", "")
    keywords = body.get("keywords", [])
    if not path:
        return jsonify({"ok": False, "error": "path required"}), 400
    data = _load_keywords()
    if keywords:
        data[path] = keywords
    else:
        data.pop(path, None)
    _save_keywords(data)
    return jsonify({"ok": True})


@rmemory_bp.route("/api/r-memory/lock-layer/<layer>", methods=["POST"])
def api_rmemory_lock_layer(layer: str) -> Response:
    """Lock all documents in a layer.
    Validate request input, update the backing file or local system state when needed,
    and return JSON describing the result. Keeping the mutation flow in this handler
    preserves a single API contract for the dashboard UI.

    Args:
        layer (str): Value supplied by the caller.
    Returns:
        Response: JSON response payload returned to the dashboard client.
    Dependencies:
        SSOT_ROOT, jsonify, request, and subprocess.
    Side effects:
        Invokes local subprocesses to inspect or mutate system state."""
    layer_dir = SSOT_ROOT / layer
    if not layer_dir.exists():
        return jsonify({"ok": False, "error": "layer not found"}), 404
    body: dict[str, Any] = request.get_json(force=True) or {}
    password = body.get("password", "")
    if not password:
        return jsonify({"ok": False, "error": "password required — schg needs root"}), 403
    count = 0
    errors = []
    for f in layer_dir.rglob("*.md"):
        if f.name.startswith("."):
            continue
        try:
            proc = subprocess.run(
                ["sudo", "-S", "chflags", "schg", str(f)],
                input=password.encode() + b"\n",
                capture_output=True,
                timeout=10,
            )
            if proc.returncode == 0:
                count += 1
            else:
                errors.append(f"{f.name}: lock failed")
        except Exception as e:
            errors.append(f"{f.name}: {e}")
    if errors and count == 0:
        return jsonify({"ok": False, "error": "lock failed (wrong password?)", "errors": errors}), 403
    return jsonify({"ok": True, "count": count, "errors": errors})


@rmemory_bp.route("/api/r-memory/unlock-layer/<layer>", methods=["POST"])
def api_rmemory_unlock_layer(layer: str) -> Response:
    """Unlock all documents in a layer. Requires password.
    Validate request input, update the backing file or local system state when needed,
    and return JSON describing the result. Keeping the mutation flow in this handler
    preserves a single API contract for the dashboard UI.

    Args:
        layer (str): Value supplied by the caller.
    Returns:
        Response: JSON response payload returned to the dashboard client.
    Dependencies:
        SSOT_ROOT, jsonify, request, and subprocess.
    Side effects:
        Invokes local subprocesses to inspect or mutate system state."""
    layer_dir = SSOT_ROOT / layer
    if not layer_dir.exists():
        return jsonify({"ok": False, "error": "layer not found"}), 404
    body: dict[str, Any] = request.get_json(force=True) or {}
    password = body.get("password", "")
    if not password:
        return jsonify({"ok": False, "error": "password required"}), 400
    count = 0
    errors = []
    for f in layer_dir.rglob("*.md"):
        if f.name.startswith("."):
            continue
        try:
            proc = subprocess.run(
                ["sudo", "-S", "chflags", "noschg", str(f)],
                input=password.encode() + b"\n",
                capture_output=True,
                timeout=10,
            )
            if proc.returncode == 0:
                count += 1
            else:
                errors.append(f"{f.name}: unlock failed")
        except Exception as e:
            errors.append(f"{f.name}: {e}")
    if errors and count == 0:
        return jsonify({"ok": False, "error": "unlock failed (wrong password?)", "errors": errors}), 403
    return jsonify({"ok": True, "count": count, "errors": errors})
