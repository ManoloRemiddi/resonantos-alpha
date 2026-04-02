"""System and memory routes."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, current_app, jsonify

from routes.config import OPENCLAW_CONFIG, OPENCLAW_HOME, R_AWARENESS_LOG, SSOT_ROOT, WORKSPACE
from routes.logging_config import get_logger
from routes.rmemory import (
    _rmem_config,
    _rmem_current_session_id,
    _rmem_gateway_session,
    _rmem_history_blocks,
    _rmem_parse_log,
    _scan_ssot_layer,
)
from routes.shared import get_gw_port, gw

system_bp = Blueprint("system", __name__)
logger = get_logger(__name__)

LCM_DB: Path = OPENCLAW_HOME / "lcm.db"


def _system_dashboard_health() -> dict[str, Any]:
    """Return the dashboard's local health snapshot."""
    from server_v2 import _get_version

    return {"status": "ok", "version": _get_version()}


def _system_shield_health() -> dict[str, Any]:
    """Probe the local Shield health endpoint."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:9999/health", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Shield health returned a non-object payload")
        raw_status = payload.get("status", "ok")
        if raw_status == "healthy":
            raw_status = "ok"
        elif raw_status == "unhealthy":
            raw_status = "error"
        return {**payload, "status": raw_status}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _system_logician_health() -> dict[str, Any]:
    """Check whether the Logician socket is present."""
    socket_exists = Path("/tmp/mangle.sock").exists()
    return {"status": "ok" if socket_exists else "error", "socket": socket_exists}


def _system_gateway_health() -> dict[str, Any]:
    """Return the shared gateway connection state."""
    connected = bool(gw.connected)
    payload: dict[str, Any] = {
        "status": "ok" if connected else "error",
        "connected": connected,
        "connId": gw.conn_id,
    }
    if not connected and gw.error:
        payload["error"] = gw.error
    return payload


def _system_lcm_health() -> dict[str, Any]:
    """Summarize LCM message and summary counts."""
    if not LCM_DB.exists():
        return {"status": "error", "messages": 0, "summaries": 0, "error": "LCM database not found"}

    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(str(LCM_DB), timeout=2)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM messages")
        messages = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM summaries")
        summaries = cur.fetchone()[0]
        return {"status": "ok", "messages": messages, "summaries": summaries}
    except Exception as e:
        return {"status": "error", "messages": 0, "summaries": 0, "error": str(e)}
    finally:
        if conn is not None:
            conn.close()


def _system_cron_health() -> dict[str, Any]:
    """Summarize cron job health from the OpenClaw CLI."""
    try:
        result = subprocess.run(
            ["openclaw", "cron", "list", "--json"], capture_output=True, text=True, timeout=2, check=False
        )
        if result.returncode != 0:
            error = result.stderr.strip() or result.stdout.strip() or "openclaw cron list failed"
            return {"status": "error", "total": 0, "errors": 0, "error": error}

        payload = json.loads(result.stdout or "{}")
        jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
        errors = 0
        for job in jobs:
            state = job.get("state", {}) if isinstance(job, dict) else {}
            if state.get("consecutiveErrors", 0) > 0 or state.get("lastStatus") == "error":
                errors += 1

        return {"status": "ok" if errors == 0 else "degraded", "total": len(jobs), "errors": errors}
    except Exception as e:
        return {"status": "error", "total": 0, "errors": 0, "error": str(e)}


def _system_disk_health() -> dict[str, Any]:
    """Report free disk space for the local machine."""
    try:
        stat = os.statvfs(str(Path.home()))
        free_bytes = stat.f_frsize * stat.f_bavail
        free_gb = round(free_bytes / (1024**3), 1)
        return {"status": "ok" if free_gb >= 5 else "warning", "free_gb": free_gb}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _system_overall_status(subsystems: dict[str, dict[str, Any]]) -> str:
    """Collapse subsystem statuses into one overall state."""
    statuses = [payload.get("status", "error") for payload in subsystems.values()]
    if all(status == "ok" for status in statuses):
        return "ok"
    if any(status == "error" for status in statuses):
        return "degraded"
    return "warning"


@system_bp.route("/api/modules")
def api_modules() -> Response:
    """Return the full dashboard module registry from application config."""
    registry = current_app.config.get("MODULE_REGISTRY", {})
    return jsonify(registry)


@system_bp.route("/api/modules/<module_id>/toggle", methods=["POST"])
def api_module_toggle(module_id: str) -> Response:
    """Toggle one dashboard module in ``modules.json`` and in memory.

    Load the persisted module registry, flip the ``enabled`` flag for the
    requested non-core module, write the updated JSON back to disk, and refresh
    the Flask app's cached module list.

    Args:
        module_id: Stable module identifier from ``modules.json``.

    Returns:
        Response: JSON response with the updated module state, or an error
        payload with HTTP 4xx/5xx when the toggle cannot be applied.
    """
    modules_file = Path(__file__).resolve().parent.parent / "modules.json"
    try:
        data = json.loads(modules_file.read_text())
    except Exception:
        return jsonify({"error": "Cannot read modules.json"}), 500

    toggled_module: dict[str, Any] | None = None
    for module in data.get("modules", []):
        if module.get("id") != module_id:
            continue
        if module.get("core", False):
            return jsonify({"error": "Cannot toggle core modules"}), 400
        module["enabled"] = not module.get("enabled", False)
        toggled_module = module
        break

    if toggled_module is None:
        return jsonify({"error": "Module not found"}), 404

    modules_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    current_app.config["MODULE_REGISTRY"] = data
    current_app.config["MODULES"] = data.get("modules", [])
    return jsonify({"ok": True, "module_id": module_id, "enabled": toggled_module["enabled"]})


@system_bp.route("/api/memory/health")
def api_memory_health() -> Response:
    """Assemble a composite health report for memory-related subsystems.

    Gather token usage, compression history, SSoT injection state, keyword
    matches, LCM summary data, and gateway session metrics into one dashboard
    payload. The route tolerates missing files and partial subsystem failures so
    the frontend still receives a best-effort health snapshot.

    Dependencies:
        R-Memory helpers from `routes.rmemory`, `WORKSPACE`, `SSOT_ROOT`,
        `R_AWARENESS_LOG`, `LCM_DB`, and the shared gateway client.

    Returns:
        Response: JSON object describing context-window usage and subsystem
        status for memory, compression, and injection features.
    """
    config = _rmem_config()
    compress_trigger = config.get("compressTrigger", 36000)
    evict_trigger = config.get("evictTrigger", 80000)

    cur_sid = _rmem_current_session_id()
    cur_blocks = _rmem_history_blocks(cur_sid) if cur_sid else []
    all_blocks = _rmem_history_blocks()

    stored_blocks_raw = sum(block.get("tokensRaw", 0) for block in cur_blocks)
    stored_blocks_comp = sum(block.get("tokensCompressed", 0) for block in cur_blocks)
    stored_blocks_count = len(cur_blocks)

    log_events = _rmem_parse_log()

    last_init = None
    last_compaction_done = None
    compaction_count = 0
    fifo_events = []
    cache_hits = 0
    cache_misses = 0

    for event in log_events:
        event_type = event.get("event", "")
        if event_type == "init":
            last_init = event
        elif event_type == "compaction_done":
            last_compaction_done = event
            compaction_count += 1
            cache_hits += event.get("cacheHits", 0)
            cache_misses += event.get("cacheMisses", 0)
        elif event_type == "fifo_evicted":
            fifo_events.append(event)

    blocks_count = stored_blocks_count
    blocks_comp = stored_blocks_comp
    blocks_raw = stored_blocks_raw
    if blocks_count == 0 and last_compaction_done:
        blocks_comp = last_compaction_done.get("compressed", 0) or last_compaction_done.get("contentTokens", 0) or 0
        blocks_raw = last_compaction_done.get("raw", 0) or 0
        blocks_count = last_compaction_done.get("blocksSwapped", 0) or last_compaction_done.get("historyBlocks", 0) or 0

    gw_session = _rmem_gateway_session()
    actual_total = gw_session.get("totalTokens", 0) if gw_session else 0
    max_tokens = gw_session.get("contextTokens", 200000) if gw_session else 200000
    model = gw_session.get("model") if gw_session else None

    workspace_tokens = 0
    for fname in ["AGENTS.md", "SOUL.md", "TOOLS.md", "USER.md", "MEMORY.md", "IDENTITY.md", "HEARTBEAT.md"]:
        fpath = WORKSPACE / fname
        if fpath.exists():
            try:
                workspace_tokens += len(fpath.read_text()) // 4
            except Exception:
                logger.debug("Failed to read workspace token source %s", fpath, exc_info=True)

    system_prompt_tokens = 12000

    ssot_tokens = 0
    ssot_count = 0
    ssot_injected_docs = []
    try:
        ra_log = WORKSPACE / "r-awareness" / "r-awareness.log"
        if ra_log.exists():
            lines = ra_log.read_text().splitlines()
            for line in reversed(lines):
                if "Injecting into system prompt" in line:
                    match = re.search(r'"docs":(\d+),"tokens":(\d+)', line)
                    if match:
                        ssot_count = int(match.group(1))
                        ssot_tokens = int(match.group(2))
                    break
            last_inject_idx = None
            for index in range(len(lines) - 1, -1, -1):
                if "Injecting into system prompt" in lines[index]:
                    last_inject_idx = index
                    break
            if last_inject_idx is not None:
                all_docs = set()
                prev_inject_idx = None
                for index in range(last_inject_idx - 1, -1, -1):
                    if "Injecting into system prompt" in lines[index]:
                        prev_inject_idx = index
                        break
                start = (prev_inject_idx + 1) if prev_inject_idx is not None else 0
                for index in range(start, last_inject_idx + 1):
                    match = re.search(r'"docs":\[([^\]]*)\]', lines[index])
                    if match and match.group(1):
                        for doc in match.group(1).split(","):
                            doc = doc.strip().strip('"')
                            if doc:
                                all_docs.add(doc)
                ssot_injected_docs = sorted(all_docs)[:ssot_count]
    except Exception:
        logger.debug("Failed to parse R-Awareness injection log", exc_info=True)
    if ssot_count == 0:
        try:
            docs = []
            for layer in ["L0", "L1", "L2", "L3", "L4"]:
                docs.extend(_scan_ssot_layer(SSOT_ROOT / layer, layer))
            ssot_count = len(docs)
            ssot_tokens = sum(doc.get("tokens", 0) for doc in docs)
        except Exception:
            logger.debug("Failed to scan SSoT layers for fallback token counts", exc_info=True)

    lcm_summary_tokens = 0
    try:
        if LCM_DB.exists():
            conn = sqlite3.connect(str(LCM_DB))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("""
                SELECT ci.conversation_id
                FROM context_items ci
                WHERE ci.conversation_id IN (
                    SELECT conversation_id FROM context_items
                    WHERE item_type = 'summary'
                    GROUP BY conversation_id
                )
                GROUP BY ci.conversation_id
                ORDER BY MAX(ci.created_at) DESC
                LIMIT 1
            """)
            row = cur.fetchone()
            if row:
                conv_id = row[0]
                cur.execute(
                    """
                    SELECT COALESCE(SUM(s.token_count), 0) as total_tokens
                    FROM context_items ci
                    JOIN summaries s ON ci.summary_id = s.summary_id
                    WHERE ci.conversation_id = ? AND ci.item_type = 'summary'
                """,
                    (conv_id,),
                )
                token_row = cur.fetchone()
                lcm_summary_tokens = token_row[0] if token_row else 0
            conn.close()
    except Exception:
        logger.debug("Failed to read LCM summary token data from %s", LCM_DB, exc_info=True)

    headers_tokens = 0
    header_files = []
    try:
        import glob

        header_files = glob.glob(os.path.expanduser("~/.openclaw/workspace/memory/headers/*.header.md"))
        for header_file in header_files:
            try:
                with open(header_file) as handle:
                    headers_tokens += len(handle.read()) // 4
            except Exception:
                logger.debug("Failed to read memory header file %s", header_file, exc_info=True)
    except Exception:
        logger.debug("Failed to enumerate memory header files", exc_info=True)

    conversation_tokens = max(
        0, actual_total - system_prompt_tokens - workspace_tokens - ssot_tokens - headers_tokens - lcm_summary_tokens
    )

    result = {
        "contextWindow": {
            "maxTokens": max_tokens,
            "actualTotalTokens": actual_total,
            "model": model,
            "lastInputTokens": gw_session.get("inputTokens", 0) if gw_session else 0,
            "lastOutputTokens": gw_session.get("outputTokens", 0) if gw_session else 0,
            "injectedSSoTs": ssot_count,
            "injectedSSoTDocs": ssot_injected_docs,
            "injectedHeaders": len(header_files),
            "segments": {
                "systemPrompt": system_prompt_tokens,
                "workspaceFiles": workspace_tokens,
                "ssotDocs": ssot_tokens,
                "conversation": conversation_tokens,
                "memoryHeaders": headers_tokens,
                "lcmSummaries": lcm_summary_tokens,
            },
            "status": "ok",
        },
        "subsystems": {},
        "lastTurn": None,
        "lastEventTs": None,
    }

    if actual_total > 0:
        ratio = actual_total / max_tokens
        if ratio < 0.5:
            result["contextWindow"]["status"] = "ok"
        elif ratio < 0.75:
            result["contextWindow"]["status"] = "warning"
        else:
            result["contextWindow"]["status"] = "critical"

    if last_init:
        cached = last_init.get("cachedBlocks", last_init.get("cachedTurns", 0))
        result["subsystems"]["plugin"] = {
            "label": "R-Memory Plugin",
            "status": "ok",
            "detail": f"V4.6.1 running, {cached} cached blocks, trigger: {compress_trigger}",
            "lastSeen": last_init.get("ts"),
        }
    else:
        result["subsystems"]["plugin"] = {
            "label": "R-Memory Plugin",
            "status": "error",
            "detail": "No init event found in log",
            "lastSeen": None,
        }

    if ssot_count > 0:
        result["subsystems"]["injection"] = {
            "label": "R-Awareness (Injection)",
            "status": "ok",
            "detail": f"{ssot_count} SSoT docs ({ssot_tokens} tok)",
            "lastSeen": last_init.get("ts") if last_init else None,
        }
    else:
        result["subsystems"]["injection"] = {
            "label": "R-Awareness (Injection)",
            "status": "idle",
            "detail": "No SSoT documents found",
            "lastSeen": None,
        }

    kw_events = []
    if R_AWARENESS_LOG.exists():
        try:
            ra_text = R_AWARENESS_LOG.read_text(errors="ignore")
            kw_re = re.compile(
                r"^\[(\d{4}-\d{2}-\d{2}T[\d:.]+Z)\]\s+\[INFO\]\s+Human keywords matched\s+(\{.*\})",
                re.MULTILINE,
            )
            for match in kw_re.finditer(ra_text):
                try:
                    payload = json.loads(match.group(2))
                    kw_events.append({"ts": match.group(1), "keywords": payload.get("keywords", [])})
                except Exception:
                    logger.debug("Failed to parse R-Awareness keyword payload", exc_info=True)
        except Exception:
            logger.debug("Failed to read keyword events from %s", R_AWARENESS_LOG, exc_info=True)
    if kw_events:
        last_kw = kw_events[-1]
        result["subsystems"]["keywords"] = {
            "label": "Keyword Detection",
            "status": "ok",
            "detail": f"Last: {', '.join(last_kw['keywords'][:6])}",
            "lastSeen": last_kw["ts"],
        }
    else:
        result["subsystems"]["keywords"] = {
            "label": "Keyword Detection",
            "status": "idle",
            "detail": "No keyword triggers yet",
            "lastSeen": None,
        }

    if last_compaction_done:
        saving = last_compaction_done.get("saving", "?")
        hit_rate = f"{cache_hits}/{cache_hits + cache_misses}" if (cache_hits + cache_misses) > 0 else "n/a"
        result["subsystems"]["compression"] = {
            "label": "Compression",
            "status": "ok",
            "detail": f"{blocks_count} blocks in context ({blocks_raw}→{blocks_comp} tok), saving: {saving}, cache: {hit_rate}",
            "lastSeen": last_compaction_done.get("ts"),
        }
    elif blocks_count > 0:
        ratio_str = f"{round(blocks_comp / blocks_raw * 100)}%" if blocks_raw > 0 else "?"
        result["subsystems"]["compression"] = {
            "label": "Compression",
            "status": "ok",
            "detail": f"{blocks_count} blocks ({blocks_raw}→{blocks_comp} tok, {ratio_str})",
            "lastSeen": None,
        }
    else:
        result["subsystems"]["compression"] = {
            "label": "Compression",
            "status": "idle",
            "detail": f"No compression yet (trigger: {compress_trigger} total context)",
            "lastSeen": None,
        }

    if fifo_events:
        last_fifo = fifo_events[-1]
        result["subsystems"]["eviction"] = {
            "label": "FIFO Eviction",
            "status": "ok",
            "detail": f"Last evicted block, {len(fifo_events)} total evictions",
            "lastSeen": last_fifo.get("ts"),
        }
    else:
        result["subsystems"]["eviction"] = {
            "label": "FIFO Eviction",
            "status": "idle",
            "detail": f"No evictions yet (trigger: {evict_trigger} compressed tok, current: {blocks_comp} tok)",
            "lastSeen": None,
        }

    if actual_total > 0:
        pct = min(100, round((actual_total / compress_trigger) * 100))
        result["conversationEstimate"] = {
            "tokens": actual_total,
            "trigger": compress_trigger,
            "percent": pct,
            "msgCount": None,
        }

    if log_events:
        result["lastEventTs"] = log_events[-1].get("ts")

    return jsonify(result)


@system_bp.route("/api/lcm/status")
def api_lcm_status() -> Response:
    """Summarize LCM database usage statistics.

    Open the local LCM SQLite database, count conversations, aggregate summary
    depths, and inspect the most recent conversation's context composition. The
    route returns a 404 when the database is absent and a 500 when queries fail.

    Dependencies:
        `LCM_DB`, `sqlite3`, and `jsonify()`.

    Returns:
        Response: JSON payload with LCM connectivity and summary statistics.
    """
    if not LCM_DB.exists():
        return jsonify({"connected": False, "message": "LCM database not found"}), 404

    try:
        db = sqlite3.connect(str(LCM_DB))
        db.row_factory = sqlite3.Row
        cur = db.cursor()

        cur.execute("SELECT COUNT(DISTINCT conversation_id) as cnt FROM messages")
        conversations = cur.fetchone()["cnt"]

        cur.execute("SELECT COUNT(*) as cnt FROM messages")
        total_messages = cur.fetchone()["cnt"]

        cur.execute("SELECT COUNT(*) as cnt FROM summaries")
        total_summaries = cur.fetchone()["cnt"]

        cur.execute("SELECT depth, COUNT(*) as cnt FROM summaries GROUP BY depth")
        summary_by_depth = {str(row["depth"]): row["cnt"] for row in cur.fetchall()}

        cur.execute("SELECT SUM(token_count) as total FROM summaries")
        total_summary_tokens = cur.fetchone()["total"] or 0

        cur.execute("""
            SELECT ci.conversation_id
            FROM context_items ci
            WHERE ci.conversation_id IN (
                SELECT conversation_id FROM context_items
                WHERE item_type = 'summary'
                GROUP BY conversation_id
            )
            GROUP BY ci.conversation_id
            ORDER BY MAX(ci.created_at) DESC
            LIMIT 1
        """)
        row = cur.fetchone()
        max_conv = row["conversation_id"] if row else None

        if max_conv:
            cur.execute(
                """
                SELECT
                    COUNT(*) as total_items,
                    SUM(CASE WHEN item_type = 'message' THEN 1 ELSE 0 END) as messages,
                    SUM(CASE WHEN item_type = 'summary' THEN 1 ELSE 0 END) as summaries
                FROM context_items
                WHERE conversation_id = ?
            """,
                (max_conv,),
            )
            row = cur.fetchone()
            total_items = row["total_items"] if row else 0
            msg_count = row["messages"] if row else 0
            sum_count = row["summaries"] if row else 0
        else:
            total_items = 0
            msg_count = 0
            sum_count = 0

        db_size_bytes = LCM_DB.stat().st_size
        db_size_mb = round(db_size_bytes / (1024 * 1024), 1)

        db.close()

        if total_items > 0:
            message_pct = (msg_count / total_items) * 100
            summary_pct = (sum_count / total_items) * 100
        else:
            message_pct = 0
            summary_pct = 0

        return jsonify(
            {
                "ok": True,
                "connected": True,
                "engineId": "lossless-claw",
                "conversations": conversations,
                "messages": total_messages,
                "summaries": total_summaries,
                "totalMessages": total_messages,
                "totalSummaries": total_summaries,
                "summaryByDepth": summary_by_depth,
                "contextComposition": {
                    "totalItems": total_items,
                    "messages": msg_count,
                    "summaries": sum_count,
                    "messagePct": round(message_pct, 1),
                    "summaryPct": round(summary_pct, 1),
                },
                "database": {
                    "path": str(LCM_DB),
                    "sizeBytes": db_size_bytes,
                    "sizeMb": db_size_mb,
                },
                "dbSizeMb": db_size_mb,
                "totalSummaryTokens": total_summary_tokens,
            }
        )
    except Exception as e:
        return jsonify({"connected": False, "error": str(e)}), 500


@system_bp.route("/api/system-keys")
def api_system_keys() -> Response:
    """Report which system provider keys are configured.

    Read the main agent auth profile file and translate the available provider
    tokens into a simplified provider-and-model list for the dashboard. Missing
    or unreadable auth data simply yields an empty provider set.

    Dependencies:
        `~/.openclaw/agents/main/agent/auth-profiles.json`, `json`, and
        `os.path.expanduser()`.

    Returns:
        Response: JSON object indicating whether any shared provider keys exist.
    """
    providers: list[dict[str, Any]] = []
    try:
        auth_path = os.path.expanduser("~/.openclaw/agents/main/agent/auth-profiles.json")
        with open(auth_path) as handle:
            auth = json.load(handle)
        profiles = auth.get("profiles", {})
        if "anthropic:manual" in profiles and profiles["anthropic:manual"].get("token"):
            providers.append(
                {
                    "id": "anthropic",
                    "name": "Anthropic",
                    "models": [
                        {"id": "claude-sonnet", "name": "Claude Sonnet"},
                        {"id": "claude-opus", "name": "Claude Opus"},
                        {"id": "claude-haiku", "name": "Claude Haiku"},
                    ],
                }
            )
        if "openai:manual" in profiles and profiles["openai:manual"].get("token"):
            providers.append(
                {
                    "id": "openai",
                    "name": "OpenAI",
                    "models": [
                        {"id": "gpt-4o", "name": "GPT-4o"},
                        {"id": "gpt-4", "name": "GPT-4"},
                    ],
                }
            )
    except Exception:
        logger.debug("Failed to load system provider keys", exc_info=True)
    return jsonify({"hasSystemKeys": len(providers) > 0, "providers": providers})


@system_bp.route("/api/system/health")
def api_system_health() -> Response:
    """Return a composite health snapshot across core local subsystems."""
    try:
        subsystems = {
            "dashboard": _system_dashboard_health(),
            "shield": _system_shield_health(),
            "logician": _system_logician_health(),
            "gateway": _system_gateway_health(),
            "lcm": _system_lcm_health(),
            "cron": _system_cron_health(),
            "disk": _system_disk_health(),
        }
        return jsonify({"status": _system_overall_status(subsystems), "subsystems": subsystems})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@system_bp.route("/api/system/status")
def api_system_status() -> Response:
    """Run the OpenClaw status command for the dashboard.

    Prefer the structured `openclaw status --json` output, then fall back to
    the plain-text status command if JSON output is unavailable. The route is a
    thin process wrapper and does not interpret the command's contents.

    Dependencies:
        `subprocess.run()` and the `openclaw` CLI on the local machine.

    Returns:
        Response: JSON-decoded CLI output, a raw fallback payload, or a 500
        error response.
    """
    try:
        result = subprocess.run(["openclaw", "status", "--json"], capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            return jsonify(json.loads(result.stdout))
        result2 = subprocess.run(["openclaw", "status"], capture_output=True, text=True, timeout=15)
        return jsonify({"raw": result2.stdout, "error": result2.stderr})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@system_bp.route("/api/system/restart", methods=["POST"])
def api_system_restart() -> Response:
    """Signal the OpenClaw gateway to restart.

    Find the process listening on the gateway port and send it `SIGUSR1`, which
    the local OpenClaw setup treats as a restart trigger. The route reports a
    404 when no gateway process is bound to the expected port.

    Dependencies:
        `subprocess.run()`, `lsof`, `os.kill()`, and `signal.SIGUSR1`.

    Returns:
        Response: JSON success message with the target pid or an error payload.
    """
    import signal

    try:
        gw_port = get_gw_port()
        result = subprocess.run(["lsof", "-ti", f"tcp:{gw_port}"], capture_output=True, text=True, timeout=10)
        pids = result.stdout.strip().split("\n")
        if not pids or not pids[0]:
            return jsonify({"ok": False, "error": f"Gateway process not found on port {gw_port}"}), 404
        pid = int(pids[0])
        os.kill(pid, signal.SIGUSR1)
        return jsonify({"ok": True, "message": f"SIGUSR1 sent to PID {pid} on port {gw_port}, restart initiated"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@system_bp.route("/api/config")
def api_config() -> Response:
    """Return the OpenClaw config with sensitive values masked.

    Load the main OpenClaw configuration file, redact the gateway auth token,
    and return the remaining structure for dashboard inspection. This endpoint
    only masks the specific gateway token field it knows about.

    Dependencies:
        `OPENCLAW_CONFIG`, `json`, and `jsonify()`.

    Returns:
        Response: JSON representation of the config or an error payload.
    """
    try:
        cfg = json.loads(OPENCLAW_CONFIG.read_text())
        if "gateway" in cfg and "auth" in cfg["gateway"]:
            cfg["gateway"]["auth"]["token"] = "***"
        return jsonify(cfg)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@system_bp.route("/api/models")
def api_models() -> Response:
    """Request the gateway's available model list.

    Forward the dashboard call directly to the shared gateway client's
    `models.list` RPC without reshaping the payload. This keeps model discovery
    behavior aligned with the gateway's own API contract.

    Dependencies:
        `gw.request("models.list")`.

    Returns:
        Response: JSON payload returned by the gateway model-list RPC.
    """
    return jsonify(gw.request("models.list"))


@system_bp.route("/api/cron/jobs")
def api_cron_jobs() -> Response:
    """Load configured cron jobs for dashboard display.

    Read the local cron jobs JSON file and flatten each job's schedule, state,
    and payload fields into a frontend-friendly summary object. Missing files
    return an empty job list with an explanatory error string.

    Dependencies:
        `~/.openclaw/cron/jobs.json`, `json`, `Path.home()`, and `os.path`.

    Returns:
        Response: JSON object containing normalized cron job entries or an
        error description.
    """
    jobs_file = os.path.join(str(Path.home()), ".openclaw", "cron", "jobs.json")
    try:
        with open(jobs_file) as handle:
            data = json.load(handle)
        jobs = data.get("jobs", [])
        result = []
        for job in jobs:
            sched = job.get("schedule", {})
            state = job.get("state", {})
            payload = job.get("payload", {})
            result.append(
                {
                    "id": job.get("id"),
                    "name": job.get("name", "Unnamed"),
                    "enabled": job.get("enabled", False),
                    "cronExpr": sched.get("expr", ""),
                    "tz": sched.get("tz", "UTC"),
                    "lastStatus": state.get("lastStatus", "unknown"),
                    "lastRunAtMs": state.get("lastRunAtMs"),
                    "nextRunAtMs": state.get("nextRunAtMs"),
                    "consecutiveErrors": state.get("consecutiveErrors", 0),
                    "model": payload.get("model", ""),
                }
            )
        return jsonify({"jobs": result})
    except FileNotFoundError:
        return jsonify({"jobs": [], "error": "jobs.json not found"})
    except Exception as e:
        return jsonify({"jobs": [], "error": str(e)})
