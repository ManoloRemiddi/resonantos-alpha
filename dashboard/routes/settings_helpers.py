"""Settings route helpers."""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from routes.config import (
    BUILTIN_SKILLS_DIR,
    CUSTOM_SKILLS_DIR,
    DASHBOARD_DIR,
    EXTENSIONS_DIR,
    OPENCLAW_CONFIG,
    REPO_DIR,
)

_CONFIG_FILE = DASHBOARD_DIR / "config.json"
DASHBOARD_REPO_DIR = str(REPO_DIR)
_UPDATE_CONFIG_LOCK = threading.Lock()
_UPDATE_CHECKER_STARTED = False
_UPDATE_DEFAULTS: dict[str, Any] = {
    "autoCheck": True,
    "autoCheckIntervalHours": 6,
    "autoApply": False,
    "notifyOnUpdate": True,
    "lastCheck": None,
    "lastCheckResult": None,
}
_UPDATE_INTERVAL_OPTIONS: set[int] = {1, 2, 4, 6, 12, 24}

_MEMORY_CRON_IDS: dict[str, str] = {
    "daily": "cc9b58f8-9039-4f68-95ca-25148bd34be5",
    "intraday": "3c4fc129-c78d-476f-a45b-e04ee07ebe73",
}


def _utc_now_iso() -> str:
    """Return the current UTC timestamp.
    Compute a normalized helper value for the routes in this module. Keeping the shared
    logic here avoids duplicating fallback behavior and data-shape cleanup across
    handlers.

    Returns:
        str: Normalized string value prepared for downstream callers.
    Dependencies:
        datetime and timezone.
    Called by:
        No in-module callers currently reference this helper.
    Side effects:
        None."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso_utc(ts: Any) -> datetime | None:
    """Parse a UTC timestamp.
    Compute a normalized helper value for the routes in this module. Keeping the shared
    logic here avoids duplicating fallback behavior and data-shape cleanup across
    handlers.

    Args:
        ts (Any): Value supplied by the caller.
    Returns:
        datetime | None: Parsed UTC timestamp when the input is valid, otherwise `None`.
    Dependencies:
        datetime and timezone.
    Called by:
        No in-module callers currently reference this helper.
    Side effects:
        None."""
    if not ts or not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _normalize_updates_config(raw: Any) -> dict[str, Any]:
    """Normalize update config values.
    Compute a normalized helper value for the routes in this module. Keeping the shared
    logic here avoids duplicating fallback behavior and data-shape cleanup across
    handlers.

    Args:
        raw (Any): Value supplied by the caller.
    Returns:
        dict[str, Any]: Structured mapping assembled from config files, runtime state,
        or parsed content.
    Dependencies:
        Module-level constants and standard-library helpers imported by this module.
    Called by:
        `_read_updates_config`, `_write_updates_config`.
    Side effects:
        None."""
    out = dict(_UPDATE_DEFAULTS)
    if isinstance(raw, dict):
        if isinstance(raw.get("autoCheck"), bool):
            out["autoCheck"] = raw["autoCheck"]
        if isinstance(raw.get("autoApply"), bool):
            out["autoApply"] = raw["autoApply"]
        if isinstance(raw.get("notifyOnUpdate"), bool):
            out["notifyOnUpdate"] = raw["notifyOnUpdate"]
        try:
            interval = int(raw.get("autoCheckIntervalHours", _UPDATE_DEFAULTS["autoCheckIntervalHours"]))
            if interval in _UPDATE_INTERVAL_OPTIONS:
                out["autoCheckIntervalHours"] = interval
        except Exception:
            pass
        if isinstance(raw.get("lastCheck"), str):
            out["lastCheck"] = raw["lastCheck"]
        if isinstance(raw.get("lastCheckResult"), dict):
            out["lastCheckResult"] = raw["lastCheckResult"]
    return out


def _load_dashboard_config_for_updates() -> dict[str, Any]:
    """Load dashboard config for updates.
    Parse raw files, paths, or structured text into a predictable shape for downstream
    callers. Centralizing the parsing rules here keeps the route handlers focused on
    request validation and response formatting.

    Returns:
        dict[str, Any]: Structured mapping assembled from config files, runtime state,
        or parsed content.
    Dependencies:
        json.
    Called by:
        `_read_updates_config`, `_write_updates_config`.
    Side effects:
        None."""
    try:
        cfg = json.loads(_CONFIG_FILE.read_text())
        if isinstance(cfg, dict):
            return cfg
    except Exception:
        pass
    return {}


def _read_updates_config() -> dict[str, Any]:
    """Read update config.
    Compute a normalized helper value for the routes in this module. Keeping the shared
    logic here avoids duplicating fallback behavior and data-shape cleanup across
    handlers.

    Returns:
        dict[str, Any]: Structured mapping assembled from config files, runtime state,
        or parsed content.
    Dependencies:
        Module-level constants and standard-library helpers imported by this module.
    Called by:
        No in-module callers currently reference this helper.
    Side effects:
        None."""
    with _UPDATE_CONFIG_LOCK:
        cfg = _load_dashboard_config_for_updates()
        return _normalize_updates_config(cfg.get("updates"))


def _write_updates_config(updates: dict[str, Any]) -> dict[str, Any]:
    """Write update config.
    Parse raw files, paths, or structured text into a predictable shape for downstream
    callers. Centralizing the parsing rules here keeps the route handlers focused on
    request validation and response formatting.

    Args:
        updates (dict[str, Any]): Value supplied by the caller.
    Returns:
        dict[str, Any]: Structured mapping assembled from config files, runtime state,
        or parsed content.
    Dependencies:
        json.
    Called by:
        No in-module callers currently reference this helper.
    Side effects:
        Writes dashboard-managed JSON or text files on disk."""
    normalized = _normalize_updates_config(updates)
    with _UPDATE_CONFIG_LOCK:
        cfg = _load_dashboard_config_for_updates()
        cfg["updates"] = normalized
        _CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
    return normalized


def _perform_update_check_logic() -> tuple[dict[str, Any] | None, str | None]:
    """Run update check logic.
    Wrap local command execution and normalize the result for the route handlers that
    use it. Keeping subprocess details here prevents the HTTP layer from duplicating
    command, timeout, and parsing behavior.

    Returns:
        tuple[dict[str, Any] | None, str | None]: Value described by `Run update check
        logic`.
    Dependencies:
        subprocess.
    Called by:
        No in-module callers currently reference this helper.
    Side effects:
        Invokes local subprocesses to inspect or mutate system state."""
    try:
        fetch_result = subprocess.run(
            ["git", "fetch", "origin", "main"], cwd=DASHBOARD_REPO_DIR, capture_output=True, text=True, timeout=30
        )
        if fetch_result.returncode != 0:
            return None, f"git fetch failed: {fetch_result.stderr.strip()}"

        local = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=DASHBOARD_REPO_DIR, capture_output=True, text=True, timeout=10
        ).stdout.strip()

        remote = subprocess.run(
            ["git", "rev-parse", "origin/main"], cwd=DASHBOARD_REPO_DIR, capture_output=True, text=True, timeout=10
        ).stdout.strip()

        behind_result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD..origin/main"],
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

        return {
            "available": behind > 0,
            "behind": behind,
            "local": local[:12],
            "remote": remote[:12],
            "branch": branch,
        }, None
    except subprocess.TimeoutExpired:
        return None, "git command timed out"
    except Exception as e:
        return None, str(e)


def _read_openclaw_config() -> dict[str, Any]:
    """Read openclaw config.
    Parse raw files, paths, or structured text into a predictable shape for downstream
    callers. Centralizing the parsing rules here keeps the route handlers focused on
    request validation and response formatting.

    Returns:
        dict[str, Any]: Structured mapping assembled from config files, runtime state,
        or parsed content.
    Dependencies:
        OPENCLAW_CONFIG and json.
    Called by:
        No in-module callers currently reference this helper.
    Side effects:
        None."""
    if not OPENCLAW_CONFIG.exists():
        return {}
    return json.loads(OPENCLAW_CONFIG.read_text())


def _write_openclaw_config(cfg: dict[str, Any]) -> None:
    """Write openclaw config.
    Parse raw files, paths, or structured text into a predictable shape for downstream
    callers. Centralizing the parsing rules here keeps the route handlers focused on
    request validation and response formatting.

    Args:
        cfg (dict[str, Any]): Value supplied by the caller.
    Returns:
        None: This helper updates state in place and does not return a value.
    Dependencies:
        OPENCLAW_CONFIG and json.
    Called by:
        No in-module callers currently reference this helper.
    Side effects:
        Creates parent directories when required by the requested operation. Writes
        dashboard-managed JSON or text files on disk."""
    OPENCLAW_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    OPENCLAW_CONFIG.write_text(json.dumps(cfg, indent=2))


def _parse_cron_json() -> dict[str, Any]:
    """Parse cron JSON output.
    Wrap local command execution and normalize the result for the route handlers that
    use it. Keeping subprocess details here prevents the HTTP layer from duplicating
    command, timeout, and parsing behavior.

    Returns:
        dict[str, Any]: Structured mapping assembled from config files, runtime state,
        or parsed content.
    Dependencies:
        json and subprocess.
    Called by:
        `_memory_log_state`.
    Side effects:
        Invokes local subprocesses to inspect or mutate system state."""
    try:
        res = subprocess.run(
            ["openclaw", "cron", "list", "--all", "--json"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        raw = res.stdout
        idx = raw.find("{")
        if idx == -1:
            return {}
        payload = json.loads(raw[idx:])
        return {j["id"]: j for j in payload.get("jobs", [])}
    except Exception:
        return {}


def _get_orchestrator_model() -> str:
    """Return the orchestrator model.
    Parse raw files, paths, or structured text into a predictable shape for downstream
    callers. Centralizing the parsing rules here keeps the route handlers focused on
    request validation and response formatting.

    Returns:
        str: Normalized string value prepared for downstream callers.
    Dependencies:
        OPENCLAW_CONFIG and json.
    Called by:
        `_memory_log_state`.
    Side effects:
        None."""
    try:
        cfg = json.loads(OPENCLAW_CONFIG.read_text())
        return cfg.get("defaultModel", "anthropic/claude-opus-4-6")
    except Exception:
        return "anthropic/claude-opus-4-6"


def _memory_log_state() -> dict[str, Any]:
    """Return memory log state.
    Compute a normalized helper value for the routes in this module. Keeping the shared
    logic here avoids duplicating fallback behavior and data-shape cleanup across
    handlers.

    Returns:
        dict[str, Any]: Structured mapping assembled from config files, runtime state,
        or parsed content.
    Dependencies:
        datetime and timezone.
    Called by:
        No in-module callers currently reference this helper.
    Side effects:
        None."""
    jobs = _parse_cron_json()
    result = {"orchestratorModel": _get_orchestrator_model()}
    for key, cron_id in _MEMORY_CRON_IDS.items():
        job = jobs.get(cron_id)
        if job:
            state = job.get("state", {})
            last_ms = state.get("lastRunAtMs")
            result[key] = {
                "enabled": job.get("enabled", False),
                "model": (job.get("payload") or {}).get("model", ""),
                "lastRun": datetime.fromtimestamp(last_ms / 1000, tz=timezone.utc).isoformat() if last_ms else None,
                "lastStatus": state.get("lastStatus", "idle"),
                "schedule": (job.get("schedule") or {}).get("expr", ""),
            }
        else:
            result[key] = {"enabled": False, "model": "", "lastRun": None, "lastStatus": "idle", "schedule": ""}
    return result


def _normalize_skill_location(path_obj: Path) -> str:
    """Normalize a skill path.
    Parse raw files, paths, or structured text into a predictable shape for downstream
    callers. Centralizing the parsing rules here keeps the route handlers focused on
    request validation and response formatting.

    Args:
        path_obj (Path): Value supplied by the caller.
    Returns:
        str: Normalized string value prepared for downstream callers.
    Dependencies:
        Path.
    Called by:
        `_discover_settings_skills`.
    Side effects:
        None."""
    path_str = str(path_obj)
    home_prefix = str(Path.home())
    if path_str.startswith(home_prefix):
        return "~" + path_str[len(home_prefix) :]
    return path_str


def _split_skill_frontmatter(text: str) -> tuple[str, str]:
    """Split skill frontmatter from body.
    Compute a normalized helper value for the routes in this module. Keeping the shared
    logic here avoids duplicating fallback behavior and data-shape cleanup across
    handlers.

    Args:
        text (str): Value supplied by the caller.
    Returns:
        tuple[str, str]: Value described by `Split skill frontmatter from body`.
    Dependencies:
        Module-level constants and standard-library helpers imported by this module.
    Called by:
        `_extract_skill_description`, `_extract_skill_setup_metadata`.
    Side effects:
        None."""
    if not text.startswith("---"):
        return "", text

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text

    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            return "\n".join(lines[1:idx]), "\n".join(lines[idx + 1 :])

    return "", text


def _extract_frontmatter_value(frontmatter: str, key: str) -> str:
    """Extract a frontmatter value.
    Compute a normalized helper value for the routes in this module. Keeping the shared
    logic here avoids duplicating fallback behavior and data-shape cleanup across
    handlers.

    Args:
        frontmatter (str): Value supplied by the caller.
        key (str): Value supplied by the caller.
    Returns:
        str: Normalized string value prepared for downstream callers.
    Dependencies:
        Module-level constants and standard-library helpers imported by this module.
    Called by:
        `_parse_skill_frontmatter_metadata`.
    Side effects:
        None."""
    lines = frontmatter.splitlines()
    key_prefix = f"{key}:"

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or line[:1].isspace() or not stripped.startswith(key_prefix):
            continue

        raw_value = stripped.split(":", 1)[1].strip()
        if raw_value:
            return raw_value

        block = []
        next_idx = idx + 1
        while next_idx < len(lines):
            candidate = lines[next_idx]
            if not candidate.strip():
                block.append(candidate)
                next_idx += 1
                continue
            if candidate[:1].isspace():
                block.append(candidate)
                next_idx += 1
                continue
            break
        return "\n".join(block).strip()

    return ""


def _parse_skill_frontmatter_metadata(frontmatter: str) -> dict[str, Any]:
    """Parse skill frontmatter metadata.
    Parse raw files, paths, or structured text into a predictable shape for downstream
    callers. Centralizing the parsing rules here keeps the route handlers focused on
    request validation and response formatting.

    Args:
        frontmatter (str): Value supplied by the caller.
    Returns:
        dict[str, Any]: Structured mapping assembled from config files, runtime state,
        or parsed content.
    Dependencies:
        ast.
    Called by:
        `_extract_skill_setup_metadata`.
    Side effects:
        None."""
    metadata_raw = _extract_frontmatter_value(frontmatter, "metadata")
    if not metadata_raw:
        return {}

    try:
        parsed = ast.literal_eval(metadata_raw)
    except (SyntaxError, ValueError):
        return {}

    return parsed if isinstance(parsed, dict) else {}


def _normalize_skill_string_list(value: Any) -> list[str]:
    """Normalize a skill string list.
    Compute a normalized helper value for the routes in this module. Keeping the shared
    logic here avoids duplicating fallback behavior and data-shape cleanup across
    handlers.

    Args:
        value (Any): Value supplied by the caller.
    Returns:
        list[str]: Ordered collection assembled from the backing dashboard data sources.
    Dependencies:
        Module-level constants and standard-library helpers imported by this module.
    Called by:
        `_extract_skill_setup_metadata`.
    Side effects:
        None."""
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    normalized = []
    for item in value:
        item_str = str(item).strip()
        if item_str:
            normalized.append(item_str)
    return normalized


def _extract_skill_setup_metadata(skill_file: Path) -> dict[str, Any]:
    """Extract setup metadata for a skill.
    Parse raw files, paths, or structured text into a predictable shape for downstream
    callers. Centralizing the parsing rules here keeps the route handlers focused on
    request validation and response formatting.

    Args:
        skill_file (Path): Value supplied by the caller.
    Returns:
        dict[str, Any]: Structured mapping assembled from config files, runtime state,
        or parsed content.
    Dependencies:
        Path and shutil.
    Called by:
        `_discover_settings_skills`.
    Side effects:
        None."""
    try:
        text = skill_file.read_text(errors="replace")
    except Exception:
        return {
            "status": "unknown",
            "missingBins": [],
            "installOptions": [],
        }

    frontmatter, _ = _split_skill_frontmatter(text)
    metadata = _parse_skill_frontmatter_metadata(frontmatter)
    openclaw_meta = metadata.get("openclaw") if isinstance(metadata, dict) else {}
    if not isinstance(openclaw_meta, dict):
        openclaw_meta = {}

    requires = openclaw_meta.get("requires")
    if not isinstance(requires, dict):
        requires = {}

    bins = _normalize_skill_string_list(requires.get("bins"))
    any_bins = _normalize_skill_string_list(requires.get("anyBins"))

    if not bins and not any_bins:
        status = "unknown"
        missing_bins = []
    else:
        missing_bins = [bin_name for bin_name in bins if shutil.which(bin_name) is None]
        any_bins_available = any(shutil.which(bin_name) is not None for bin_name in any_bins) if any_bins else True
        if any_bins and not any_bins_available:
            missing_bins.extend([bin_name for bin_name in any_bins if bin_name not in missing_bins])
        status = "ready" if not missing_bins and any_bins_available else "needs_setup"

    install_options = openclaw_meta.get("install")
    if not isinstance(install_options, list):
        install_options = []

    return {
        "status": status,
        "missingBins": missing_bins,
        "installOptions": install_options,
    }


def _extract_skill_description(skill_file: Path) -> str:
    """Extract a skill description.
    Parse raw files, paths, or structured text into a predictable shape for downstream
    callers. Centralizing the parsing rules here keeps the route handlers focused on
    request validation and response formatting.

    Args:
        skill_file (Path): Value supplied by the caller.
    Returns:
        str: Normalized string value prepared for downstream callers.
    Dependencies:
        Path.
    Called by:
        `_discover_settings_skills`.
    Side effects:
        None."""
    try:
        text = skill_file.read_text(errors="replace")
    except Exception:
        return ""

    frontmatter, body = _split_skill_frontmatter(text)

    if frontmatter:
        lines = frontmatter.splitlines()
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped.startswith("description:"):
                continue
            raw_value = stripped.split(":", 1)[1].strip()
            if raw_value and not raw_value.startswith((">", "|")):
                return raw_value.strip("\"' ")

            block = []
            next_idx = idx + 1
            while next_idx < len(lines):
                candidate = lines[next_idx]
                if candidate.startswith((" ", "\t")) or not candidate.strip():
                    block.append(candidate.strip())
                    next_idx += 1
                    continue
                break
            description = " ".join(part for part in block if part).strip()
            if description:
                return description

    paragraphs = []
    current = []
    in_code_block = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if not stripped:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        if stripped.startswith("#"):
            continue
        current.append(stripped)
    if current:
        paragraphs.append(" ".join(current))

    return paragraphs[0].strip() if paragraphs else ""


def _discover_settings_skills() -> list[dict[str, Any]]:
    """Discover settings skills.
    Compute a normalized helper value for the routes in this module. Keeping the shared
    logic here avoids duplicating fallback behavior and data-shape cleanup across
    handlers.

    Returns:
        list[dict[str, Any]]: Ordered collection assembled from the backing dashboard
        data sources.
    Dependencies:
        BUILTIN_SKILLS_DIR and CUSTOM_SKILLS_DIR.
    Called by:
        No in-module callers currently reference this helper.
    Side effects:
        None."""
    skills = []
    index = {}
    for root, skill_type in ((BUILTIN_SKILLS_DIR, "builtin"), (CUSTOM_SKILLS_DIR, "custom")):
        if not root.exists():
            continue
        try:
            entries = sorted(root.iterdir(), key=lambda item: item.name.lower())
        except Exception:
            continue
        for entry in entries:
            if not entry.is_dir():
                continue
            skill_file = entry / "SKILL.md"
            if not skill_file.exists():
                continue
            name = entry.name.strip()
            if not name:
                continue
            record = {
                "name": name,
                "description": _extract_skill_description(skill_file),
                "location": _normalize_skill_location(skill_file),
                "type": skill_type,
            }
            record.update(_extract_skill_setup_metadata(skill_file))
            if name in index:
                if skill_type == "custom":
                    skills[index[name]] = record
                continue
            index[name] = len(skills)
            skills.append(record)
    skills.sort(key=lambda item: item["name"].lower())
    return skills


def _normalize_agent_model(model_value: Any) -> str:
    """Normalize an agent model value.
    Compute a normalized helper value for the routes in this module. Keeping the shared
    logic here avoids duplicating fallback behavior and data-shape cleanup across
    handlers.

    Args:
        model_value (Any): Value supplied by the caller.
    Returns:
        str: Normalized string value prepared for downstream callers.
    Dependencies:
        Module-level constants and standard-library helpers imported by this module.
    Called by:
        `_list_skill_agents`.
    Side effects:
        None."""
    if isinstance(model_value, str):
        return model_value
    if isinstance(model_value, dict):
        primary = model_value.get("primary")
        if primary:
            return str(primary)
        fallbacks = model_value.get("fallbacks")
        if isinstance(fallbacks, list) and fallbacks:
            return str(fallbacks[0])
    return ""


def _list_skill_agents(cfg: dict[str, Any]) -> list[dict[str, str]]:
    """List skill-capable agents.
    Compute a normalized helper value for the routes in this module. Keeping the shared
    logic here avoids duplicating fallback behavior and data-shape cleanup across
    handlers.

    Args:
        cfg (dict[str, Any]): Value supplied by the caller.
    Returns:
        list[dict[str, str]]: Ordered collection assembled from the backing dashboard
        data sources.
    Dependencies:
        Module-level constants and standard-library helpers imported by this module.
    Called by:
        No in-module callers currently reference this helper.
    Side effects:
        None."""
    agents_cfg = cfg.get("agents", {}) if isinstance(cfg, dict) else {}
    default_model = _normalize_agent_model((agents_cfg.get("defaults") or {}).get("model")) or "unknown"
    agents = []
    seen = set()

    if isinstance(agents_cfg.get("list"), list):
        for item in agents_cfg.get("list", []):
            if not isinstance(item, dict):
                continue
            name = str(item.get("id") or item.get("name") or item.get("agentId") or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            agents.append(
                {
                    "name": name,
                    "model": _normalize_agent_model(item.get("model")) or default_model,
                }
            )

    for key, value in agents_cfg.items():
        if key in {"defaults", "list"} or not isinstance(value, dict) or key in seen:
            continue
        seen.add(key)
        agents.append(
            {
                "name": key,
                "model": _normalize_agent_model(value.get("model")) or default_model,
            }
        )

    return agents


def _get_agent_skill_allow(cfg: dict[str, Any], agent_name: str) -> list[str] | None:
    """Get allowed skills for an agent.
    Compute a normalized helper value for the routes in this module. Keeping the shared
    logic here avoids duplicating fallback behavior and data-shape cleanup across
    handlers.

    Args:
        cfg (dict[str, Any]): Value supplied by the caller.
        agent_name (str): Value supplied by the caller.
    Returns:
        list[str] | None: Ordered collection assembled from the backing dashboard data
        sources.
    Dependencies:
        Module-level constants and standard-library helpers imported by this module.
    Called by:
        No in-module callers currently reference this helper.
    Side effects:
        None."""
    agents_cfg = cfg.get("agents", {}) if isinstance(cfg, dict) else {}

    if isinstance(agents_cfg.get("list"), list):
        for item in agents_cfg.get("list", []):
            if not isinstance(item, dict):
                continue
            name = str(item.get("id") or item.get("name") or item.get("agentId") or "").strip()
            if name != agent_name:
                continue
            skills_val = item.get("skills")
            if isinstance(skills_val, list):
                return [str(skill).strip() for skill in skills_val if str(skill).strip()]
            if isinstance(skills_val, dict):
                allow = skills_val.get("allow")
                if isinstance(allow, list):
                    return [str(skill).strip() for skill in allow if str(skill).strip()]
            return None

    legacy_entry = agents_cfg.get(agent_name)
    if isinstance(legacy_entry, dict):
        allow = (legacy_entry.get("skills") or {}).get("allow")
        if isinstance(allow, list):
            return [str(skill).strip() for skill in allow if str(skill).strip()]

    return None


def _set_agent_skill_allow(cfg: dict[str, Any], agent_name: str, allowed_skills: list[str] | None) -> None:
    """Set allowed skills for an agent.
    Compute a normalized helper value for the routes in this module. Keeping the shared
    logic here avoids duplicating fallback behavior and data-shape cleanup across
    handlers.

    Args:
        cfg (dict[str, Any]): Value supplied by the caller.
        agent_name (str): Value supplied by the caller.
        allowed_skills (list[str] | None): Value supplied by the caller.
    Returns:
        None: This helper updates state in place and does not return a value.
    Dependencies:
        Module-level constants and standard-library helpers imported by this module.
    Called by:
        No in-module callers currently reference this helper.
    Side effects:
        None."""
    if "agents" not in cfg or not isinstance(cfg["agents"], dict):
        cfg["agents"] = {}
    agents_cfg = cfg["agents"]

    target_entry = None
    target_style = "list"

    if isinstance(agents_cfg.get("list"), list):
        for item in agents_cfg.get("list", []):
            if not isinstance(item, dict):
                continue
            name = str(item.get("id") or item.get("name") or item.get("agentId") or "").strip()
            if name == agent_name:
                target_entry = item
                break

    if target_entry is None and isinstance(agents_cfg.get(agent_name), dict):
        target_entry = agents_cfg[agent_name]
        target_style = "legacy"

    if target_entry is None:
        if "list" not in agents_cfg or not isinstance(agents_cfg["list"], list):
            agents_cfg["list"] = []
        target_entry = {"id": agent_name}
        agents_cfg["list"].append(target_entry)
        target_style = "list"

    if allowed_skills is None:
        if isinstance(target_entry.get("skills"), dict):
            target_entry["skills"].pop("allow", None)
            if not target_entry["skills"]:
                target_entry.pop("skills", None)
    else:
        if "skills" not in target_entry or not isinstance(target_entry["skills"], dict):
            target_entry["skills"] = {}
        target_entry["skills"]["allow"] = allowed_skills

    if target_style == "legacy":
        agents_cfg[agent_name] = target_entry
