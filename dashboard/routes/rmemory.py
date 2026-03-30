"""R-Memory compatibility helpers for dashboard routes.

R-Memory V1 retired, replaced by LCM (Lossless Context Management).
These helpers are retained because system.py, agents.py, and
token_savings_helpers.py depend on them.
Functions return safe defaults when backing data files don't exist.
"""

from __future__ import annotations

import glob
import json
import re
from pathlib import Path
from typing import Any

from routes.config import SSOT_ROOT, WORKSPACE
from routes.logging_config import get_logger
from routes.shared import gw

logger = get_logger(__name__)

_RMEMORY_DIR: Path = WORKSPACE / "r-memory"
_RMEMORY_CONFIG: Path = _RMEMORY_DIR / "config.json"
_RMEMORY_LOG: Path = _RMEMORY_DIR / "r-memory.log"


def _rmem_config() -> dict[str, Any]:
    """Read r-memory/config.json if it exists, otherwise return defaults."""
    try:
        if _RMEMORY_CONFIG.exists():
            return json.loads(_RMEMORY_CONFIG.read_text())
    except Exception:
        logger.debug("Could not read R-Memory config", exc_info=True)
    return {"compressTrigger": 36000, "evictTrigger": 80000, "blockSize": 4000}


def _rmem_effective_models() -> dict[str, Any]:
    """Resolve runtime models for compression and narrative."""
    cfg = _rmem_config()
    base_model = cfg.get("compressionModel", "anthropic/claude-haiku-4-5")
    narrative_model = cfg.get("narrativeModel") or base_model
    return {"compression": base_model, "narrative": narrative_model}


def _rmem_history_blocks(session_id: str | None = None) -> list[dict[str, Any]]:
    """Read compressed blocks from history-*.json files if they exist."""
    all_blocks: list[dict[str, Any]] = []
    if not _RMEMORY_DIR.exists():
        return all_blocks
    pattern = str(_RMEMORY_DIR / "history-*.json")
    for f in glob.glob(pattern):
        if session_id and session_id not in f:
            continue
        try:
            data = json.loads(Path(f).read_text())
            if isinstance(data, list):
                for b in data:
                    b["_file"] = Path(f).name
                    b["_source"] = "history"
                    all_blocks.append(b)
        except Exception:
            logger.debug("Failed to read history file %s", f, exc_info=True)
    return all_blocks


def _rmem_current_session_id() -> str | None:
    """Get the current main session ID from the most recent history file."""
    if not _RMEMORY_DIR.exists():
        return None
    pattern = str(_RMEMORY_DIR / "history-*.json")
    files = glob.glob(pattern)
    if not files:
        return None
    newest = max(files, key=lambda f: Path(f).stat().st_mtime)
    m = re.search(r"history-([a-f0-9]+)\.json", newest)
    return m.group(1) if m else None


def _rmem_parse_log() -> list[dict[str, Any]]:
    """Parse r-memory.log into structured events. Returns empty list if no log."""
    events: list[dict[str, Any]] = []
    if not _RMEMORY_LOG.exists():
        return events
    try:
        text = _RMEMORY_LOG.read_text(errors="ignore")
    except Exception:
        return events
    line_re = re.compile(
        r"^\[(\d{4}-\d{2}-\d{2}T[\d:.]+Z)\]\s+\[(\w+)\]\s+(.*)",
        re.MULTILINE,
    )
    for m in line_re.finditer(text):
        ts, level, body = m.group(1), m.group(2), m.group(3)
        evt: dict[str, Any] = {"ts": ts, "level": level, "raw": body, "event": "info"}
        payload: dict[str, Any] = {}
        json_match = re.search(r"\{.*\}", body)
        if json_match:
            try:
                payload = json.loads(json_match.group())
            except Exception:
                pass
        if "=== COMPACTION ===" in body:
            evt["event"] = "compaction_start"
        elif "=== DONE ===" in body:
            evt["event"] = "compaction_done"
        elif "Block compressed" in body:
            evt["event"] = "block_compressed"
        evt.update(payload)
        events.append(evt)
    return events


def _rmem_gateway_session() -> dict[str, Any] | None:
    """Get main session data from gateway or local sessions file."""
    sessions_path = (
        Path.home() / ".openclaw" / "agents" / "main" / "sessions" / "sessions.json"
    )
    try:
        if sessions_path.exists():
            data = json.loads(sessions_path.read_text())
            if isinstance(data, dict) and "agent:main:main" in data:
                return data["agent:main:main"]
            if isinstance(data, list):
                for s in data:
                    if s.get("key") == "agent:main:main":
                        return s
    except Exception:
        logger.debug("Failed to load session snapshot", exc_info=True)
    try:
        sess_result = gw.request("sessions.list", timeout=5)
        if sess_result.get("ok") and sess_result.get("payload"):
            for s in sess_result["payload"].get("sessions", []):
                if s.get("key") == "agent:main:main":
                    return s
    except Exception:
        logger.debug("Failed to query gateway for session data", exc_info=True)
    return None


def _scan_ssot_layer(layer_dir: Path, layer_name: str) -> list[dict[str, Any]]:
    """Scan a layer directory recursively for SSoT documents."""
    docs: list[dict[str, Any]] = []
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
            locked = bool(st.st_flags & (0x02 | 0x00020000))
        except AttributeError:
            pass
        raw_tokens = st.st_size // 4
        compressed_tokens = ai_path.stat().st_size // 4 if has_compressed else None
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
