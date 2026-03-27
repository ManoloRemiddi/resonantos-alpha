#!/usr/bin/env python3
"""
ResonantOS Dashboard v2 - Clean OpenClaw-native server.
Connects to OpenClaw gateway via WebSocket for real-time data.
No legacy Clawdbot/Watchtower dependencies.
"""

import ast
import importlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
import hashlib
import traceback
import urllib.request
import urllib.error
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from flask import Flask, jsonify, redirect, request, send_from_directory
from flask_cors import CORS
from waitress import serve
from routes.config import REPO_DIR, SSOT_ACCESS_FILE, SSOT_ROOT, _SYMBIOTIC_PROGRAM_ID
from routes.logging_config import get_logger
from routes.shared import (
    GW_HOST,
    GW_PORT,
    GW_TOKEN,
    GW_WS_URL,
    GatewayClient,
    _enrich_bounty_with_tribe,
    _load_bounties,
    _load_ssot_access_store,
    _load_profiles,
    _load_tribes,
    _read_gw_token,
    _save_bounties,
    _save_profiles,
    _save_tribes,
    _sync_tribe_bounty_refs,
    gw,
)
from routes.wallet_helpers import (
    _check_rct_cap,
    _derive_symbiotic_pda,
    _get_fee_payer,
    _get_wallet_pubkey,
    _record_rct_mint,
    _require_identity_nft,
    _solana_rpc,
)

logger = get_logger(__name__)

# Solana wallet integration imports — resolve toolkit path dynamically
_toolkit_candidates = [
    REPO_DIR / "solana-toolkit",
]
for _toolkit_path in _toolkit_candidates:
    if _toolkit_path.exists():
        sys.path.insert(0, str(_toolkit_path))
        break
try:
    from nft_minter import NFTMinter
    from token_manager import TokenManager
    from wallet import SolanaWallet
except ImportError:
    # Graceful fallback if solana-toolkit not available
    logger.warning("Solana toolkit imports unavailable; wallet features disabled", exc_info=True)
    NFTMinter = None
    TokenManager = None
    SolanaWallet = None

try:
    from protocol_nft_minter import ProtocolNFTMinter, PROTOCOL_NFTS
except ImportError:
    logger.warning("Protocol NFT minter import unavailable", exc_info=True)
    ProtocolNFTMinter = None
    PROTOCOL_NFTS = {}

# ---------------------------------------------------------------------------
# Paths & Config
# ---------------------------------------------------------------------------

OPENCLAW_HOME = Path.home() / ".openclaw"
OPENCLAW_CONFIG = OPENCLAW_HOME / "openclaw.json"
BUILTIN_SKILLS_DIR = Path("/opt/homebrew/lib/node_modules/openclaw/skills")
CUSTOM_SKILLS_DIR = OPENCLAW_HOME / "workspace" / "skills"
WORKSPACE = OPENCLAW_HOME / "workspace"
AGENTS_DIR = OPENCLAW_HOME / "agents"
EXTENSIONS_DIR = OPENCLAW_HOME / "extensions"
R_AWARENESS_LOG = WORKSPACE / "r-awareness" / "r-awareness.log"

# --- Load config.json (with hardcoded fallbacks for backward compatibility) ---
_DASHBOARD_DIR = Path(__file__).resolve().parent
_CONFIG_FILE = _DASHBOARD_DIR / "config.json"
_CFG = {}
if _CONFIG_FILE.exists():
    try:
        _CFG = json.loads(_CONFIG_FILE.read_text())
    except Exception:
        logger.warning("Failed to parse dashboard config at %s", _CONFIG_FILE, exc_info=True)

_REGISTRATION_BASKET_KEYPAIR = Path(
    _CFG.get("solana", {}).get("daoRegistrationBasketKeypairPath", "~/.config/solana/dao-registration-basket.json")
).expanduser()

_RCT_MINT = _CFG.get("tokens", {}).get("RCT_MINT", "2z2GEVqhTVUc6Pb3pzmVTTyBh2BeMHqSw1Xrej8KVUKG")
_RES_MINT = _CFG.get("tokens", {}).get("RES_MINT", "DiZuWvmQ6DEwsfz7jyFqXCsMfnJiMVahCj3J5MxkdV5N")

_SOLANA_RPCS = _CFG.get("solana", {}).get("rpcs") or {
    "devnet": "https://api.devnet.solana.com",
    "testnet": "https://api.testnet.solana.com",
    "mainnet-beta": "https://api.mainnet-beta.solana.com",
}

_rct_caps_cfg = _CFG.get("rctCaps", {})
_RCT_DECIMALS = _rct_caps_cfg.get("decimals", 9)


def _read_ssot_access(agent_id, levels=("L0", "L1", "L2")):
    """Read normalized SSoT access flags for an agent.

    Build a default-false mapping for the requested levels, then overlay any
    persisted values found for `agent_id`. Coerce stored values to booleans and
    keep the normalized shape even when the agent record is absent or invalid.

    Dependencies:
        Uses `_load_ssot_access_store()` and the requested `levels` iterable.

    Returns:
        dict: Boolean access flags keyed by SSoT level.

    Called by:
        Internal dashboard code that needs per-agent SSoT access state.

    Side effects:
        Reads the persisted SSoT access store through `_load_ssot_access_store()`.
    """
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


def _write_ssot_access(agent_id, access, levels=("L0", "L1", "L2")):
    """Write normalized SSoT access flags for an agent.

    Validate that an agent identifier was provided, then coerce the requested
    access payload into a boolean mapping for the tracked levels. Merge that
    mapping into the persisted store and rewrite the JSON file atomically from
    this process's perspective.

    Dependencies:
        Uses `_load_ssot_access_store()`, `SSOT_ACCESS_FILE`, and `json.dumps()`.

    Returns:
        None: This helper persists state in place and does not return a value.

    Called by:
        Internal dashboard code that updates per-agent SSoT access state.

    Side effects:
        Creates the parent directory for `SSOT_ACCESS_FILE` and overwrites the
        access JSON file on disk.
    """
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


# ---------------------------------------------------------------------------
# Flask App
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True
CORS(app)


def _get_version():
    """Read the dashboard version string from the repository root.

    Resolve the sibling `VERSION` file relative to this module and prefix the
    trimmed contents with `v` when the file exists. Fall back to `v0.0.0` if
    the file is missing or any filesystem error occurs.

    Dependencies:
        Uses `Path`, `os.path.dirname(__file__)`, and the repository `VERSION`
        file.

    Returns:
        str: User-facing semantic version string for template rendering.

    Called by:
        `inject_version()`.

    Side effects:
        Reads the `VERSION` file from disk when available.
    """
    try:
        version_file = Path(os.path.dirname(__file__)).parent / "VERSION"
        if version_file.exists():
            return "v" + version_file.read_text().strip()
        return "v0.0.0"
    except Exception:
        return "v0.0.0"


@app.context_processor
def inject_version():
    """Inject the dashboard version into every template context.

    Ask `_get_version()` for the current version string and wrap it in the key
    expected by the Jinja templates. Keep the processor small so template
    rendering always has a stable fallback version value.

    Dependencies:
        Uses Flask's `app.context_processor` hook and `_get_version()`.

    Returns:
        dict: Template context containing `resonantos_version`.
    """
    return {"resonantos_version": _get_version()}


def _load_modules_registry() -> dict[str, object]:
    """Load the full dashboard module registry from ``modules.json``.

    Read the local module manifest from the dashboard directory and return the
    parsed registry when it is present and valid. Fall back to an empty-shaped
    registry so startup can continue in fail-safe mode.

    Returns:
        dict[str, object]: Registry containing ``modules``, ``groups``, and
        ``icon_svgs`` keys.
    """
    modules_file = Path(__file__).resolve().parent / "modules.json"
    try:
        data = json.loads(modules_file.read_text())
        if isinstance(data, dict):
            return data
    except Exception:
        logger.warning("Failed to load dashboard modules from %s", modules_file, exc_info=True)
    return {"modules": [], "groups": {}, "icon_svgs": {}}


@app.context_processor
def inject_modules():
    """Inject registry-backed module data into templates."""
    registry = app.config.get("MODULE_REGISTRY", {})
    modules = registry.get("modules", [])
    groups_meta = registry.get("groups", {})
    icon_svgs = registry.get("icon_svgs", {})
    enabled = sorted(
        [module for module in modules if module.get("enabled", False)],
        key=lambda module: module.get("sidebar_position", 999),
    )
    grouped = {}
    for module in enabled:
        group_name = module.get("group", "core")
        grouped.setdefault(group_name, []).append(module)
    group_order = sorted(groups_meta.items(), key=lambda item: item[1].get("position", 99))
    return {
        "modules": enabled,
        "all_modules": modules,
        "module_groups": grouped,
        "module_group_order": group_order,
        "module_icon_svgs": icon_svgs,
    }


# ---------------------------------------------------------------------------
# API: Dashboard Self-Update (git-based)
# ---------------------------------------------------------------------------

# For self-update, operate on the repository that contains this dashboard checkout.
DASHBOARD_REPO_DIR = str(REPO_DIR)
_UPDATE_CONFIG_LOCK = threading.Lock()
_UPDATE_CHECKER_STARTED = False
_UPDATE_DEFAULTS = {
    "autoCheck": True,
    "autoCheckIntervalHours": 6,
    "autoApply": False,
    "notifyOnUpdate": True,
    "lastCheck": None,
    "lastCheckResult": None,
}
_UPDATE_INTERVAL_OPTIONS = {1, 2, 4, 6, 12, 24}


def _utc_now_iso():
    """Format the current UTC time as a compact ISO 8601 string.

    Read the current timezone-aware UTC timestamp, drop microseconds, and
    rewrite the UTC offset to a trailing `Z`. Keep the format stable so update
    metadata can be stored and compared without extra normalization.

    Dependencies:
        Uses `datetime.now()` and `timezone.utc`.

    Returns:
        str: ISO 8601 UTC timestamp with second precision.

    Called by:
        `_run_background_update_check()`.

    Side effects:
        Reads the current system clock.
    """
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso_utc(ts):
    """Parse an ISO timestamp into a UTC datetime.

    Accept only string inputs, convert a trailing `Z` into an explicit UTC
    offset, and then normalize the parsed value back to UTC. Return `None`
    instead of raising when the input is empty or cannot be parsed.

    Dependencies:
        Uses `datetime.fromisoformat()` and `timezone.utc`.

    Returns:
        datetime | None: Parsed UTC timestamp, or `None` on invalid input.

    Called by:
        `_auto_update_checker_loop()`.

    Side effects:
        None.
    """
    if not ts or not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _normalize_updates_config(raw):
    """Normalize the persisted updates configuration payload.

    Start from `_UPDATE_DEFAULTS` and selectively copy only supported values
    from `raw`, coercing the interval through the allowed option set. Preserve
    unknown or malformed input by ignoring it so downstream code always reads a
    complete, validated structure.

    Dependencies:
        Uses `_UPDATE_DEFAULTS` and `_UPDATE_INTERVAL_OPTIONS`.

    Returns:
        dict: Sanitized updates configuration with all expected keys present.

    Called by:
        `_read_updates_config()` and `_write_updates_config()`.

    Side effects:
        None.
    """
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


def _load_dashboard_config_for_updates():
    """Load the dashboard configuration source for update settings.

    Read `config.json` directly when possible so update operations see the
    latest on-disk values rather than a stale module-level cache. Fall back to
    the already-loaded `_CFG` mapping when the file is missing or unreadable.

    Dependencies:
        Uses `_CONFIG_FILE`, `_CFG`, and `json.loads()`.

    Returns:
        dict: Dashboard configuration mapping suitable for update reads.

    Called by:
        `_read_updates_config()` and `_write_updates_config()`.

    Side effects:
        Reads `config.json` from disk when available.
    """
    try:
        cfg = json.loads(_CONFIG_FILE.read_text())
        if isinstance(cfg, dict):
            return cfg
    except Exception:
        pass
    return _CFG if isinstance(_CFG, dict) else {}


def _read_updates_config():
    """Read the normalized dashboard auto-update settings.

    Acquire `_UPDATE_CONFIG_LOCK`, load the current dashboard config, and
    sanitize the nested `updates` section before returning it. Keep the lock
    around the read path so concurrent writers cannot interleave partial state.

    Dependencies:
        Uses `_UPDATE_CONFIG_LOCK`, `_load_dashboard_config_for_updates()`, and
        `_normalize_updates_config()`.

    Returns:
        dict: Validated auto-update settings with defaults applied.

    Called by:
        `_run_background_update_check()` and `_auto_update_checker_loop()`.

    Side effects:
        Reads `config.json` while holding `_UPDATE_CONFIG_LOCK`.
    """
    with _UPDATE_CONFIG_LOCK:
        cfg = _load_dashboard_config_for_updates()
        return _normalize_updates_config(cfg.get("updates"))


def _write_updates_config(updates):
    """Persist normalized dashboard auto-update settings.

    Sanitize the incoming payload before taking `_UPDATE_CONFIG_LOCK`, then
    merge the normalized section back into the full dashboard config. Rewrite
    `config.json` and refresh `_CFG` so later reads in this process observe the
    same values that were written to disk.

    Dependencies:
        Uses `_UPDATE_CONFIG_LOCK`, `_CONFIG_FILE`, `_CFG`, and
        `_normalize_updates_config()`.

    Returns:
        dict: Normalized updates payload that was persisted.

    Called by:
        `_run_background_update_check()` and update-settings API handlers.

    Side effects:
        Overwrites `config.json` on disk and updates the module-level `_CFG`
        cache.
    """
    global _CFG
    normalized = _normalize_updates_config(updates)
    with _UPDATE_CONFIG_LOCK:
        cfg = _load_dashboard_config_for_updates()
        cfg["updates"] = normalized
        _CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
        _CFG = cfg
    return normalized


def _perform_update_check_logic():
    """Check whether the dashboard repository is behind `origin/main`.

    Run the same `git fetch`, `rev-parse`, and `rev-list` sequence used by the
    manual update endpoint, then condense the results into a small status
    payload. Convert subprocess failures and timeouts into string errors so the
    caller can store the outcome without raising.

    Dependencies:
        Uses `subprocess.run()` and `DASHBOARD_REPO_DIR`.

    Returns:
        tuple[dict | None, str | None]: Update status payload and error string.

    Called by:
        `_run_background_update_check()` and manual update-check handlers.

    Side effects:
        Executes `git` commands against the dashboard repository.
    """
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


def _perform_auto_apply_logic():
    """Apply the latest fast-forward update from `origin/main`.

    Run a `git pull --ff-only` in the dashboard repository and translate the
    subprocess result into a success flag plus a small response payload. Return
    structured error details instead of raising so background update checks can
    record the failure.

    Dependencies:
        Uses `subprocess.run()` and `DASHBOARD_REPO_DIR`.

    Returns:
        tuple[bool, dict]: Success flag and command output or error details.

    Called by:
        `_run_background_update_check()`.

    Side effects:
        Executes `git pull` and may modify the working tree if the fast-forward
        succeeds.
    """
    try:
        pull_result = subprocess.run(
            ["git", "pull", "--ff-only", "origin", "main"],
            cwd=DASHBOARD_REPO_DIR,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if pull_result.returncode == 0:
            return True, {"output": pull_result.stdout.strip()}
        return False, {"error": pull_result.stderr.strip() or "git pull failed", "output": pull_result.stdout.strip()}
    except subprocess.TimeoutExpired:
        return False, {"error": "git pull timed out"}
    except Exception as e:
        return False, {"error": str(e)}


def _run_background_update_check():
    """Run one automatic update-check cycle and persist the outcome.

    Load the current update settings, execute the repository check, and convert
    failures into a stable result payload with availability defaults. Attempt an
    auto-apply when enabled and refresh the stored result after a successful
    pull so the persisted status reflects post-apply state.

    Dependencies:
        Uses `_read_updates_config()`, `_perform_update_check_logic()`,
        `_perform_auto_apply_logic()`, `_utc_now_iso()`, and
        `_write_updates_config()`.

    Returns:
        None: This helper records status to config storage and does not return.

    Called by:
        `_auto_update_checker_loop()`.

    Side effects:
        May execute `git` commands and overwrites the `updates` section in
        `config.json`.
    """
    updates = _read_updates_config()
    check_result, check_error = _perform_update_check_logic()

    if check_result is None:
        check_result = {"available": False, "behind": 0, "error": check_error}
    else:
        if updates.get("autoApply") and check_result.get("available"):
            applied, apply_result = _perform_auto_apply_logic()
            check_result["autoApplyAttempted"] = True
            check_result["autoApplySuccess"] = applied
            if not applied:
                check_result["autoApplyError"] = apply_result.get("error")
            else:
                post_check, post_error = _perform_update_check_logic()
                if post_check is not None:
                    post_check["autoApplyAttempted"] = True
                    post_check["autoApplySuccess"] = True
                    check_result = post_check
                elif post_error:
                    check_result["postApplyCheckError"] = post_error

    updates["lastCheck"] = _utc_now_iso()
    updates["lastCheckResult"] = check_result
    _write_updates_config(updates)


def _auto_update_checker_loop():
    """Run the background scheduler for automatic update checks.

    Poll the normalized update settings in an infinite loop, compute whether a
    check is due based on the stored timestamp and configured interval, and run
    the background check when needed. Sleep between iterations and print stack
    traces on unexpected failures so the daemon keeps running.

    Dependencies:
        Uses `_read_updates_config()`, `_parse_iso_utc()`,
        `_run_background_update_check()`, `datetime.now()`, and `time.sleep()`.

    Returns:
        None: This worker loop runs until the process exits.

    Called by:
        `start_auto_update_checker()` through a background thread target.

    Side effects:
        Sleeps, executes update checks, and writes tracebacks to stderr on
        unhandled exceptions.
    """
    while True:
        try:
            updates = _read_updates_config()
            if not updates.get("autoCheck"):
                time.sleep(60)
                continue

            interval_seconds = max(1, int(updates.get("autoCheckIntervalHours", 6))) * 3600
            last_check_dt = _parse_iso_utc(updates.get("lastCheck"))
            due = last_check_dt is None
            if not due:
                elapsed = (datetime.now(timezone.utc) - last_check_dt).total_seconds()
                due = elapsed >= interval_seconds

            if due:
                _run_background_update_check()
                time.sleep(5)
                continue

            wait_seconds = min(60, max(1, int(interval_seconds - elapsed)))
            time.sleep(wait_seconds)
        except Exception:
            traceback.print_exc()
            time.sleep(60)


def start_auto_update_checker():
    """Start the auto-update checker thread once per process.

    Guard startup with `_UPDATE_CHECKER_STARTED`, then create a daemon thread
    that runs `_auto_update_checker_loop()` in the background. Mark the module
    flag after the thread starts so repeated calls become no-ops.

    Dependencies:
        Uses `_UPDATE_CHECKER_STARTED`, `threading.Thread`, and
        `_auto_update_checker_loop()`.

    Returns:
        None: The function starts background work and exits immediately.
    """
    global _UPDATE_CHECKER_STARTED
    if _UPDATE_CHECKER_STARTED:
        return
    thread = threading.Thread(target=_auto_update_checker_loop, daemon=True, name="auto-update-checker")
    thread.start()
    _UPDATE_CHECKER_STARTED = True


# ---------------------------------------------------------------------------
# Memory Logs settings
# ---------------------------------------------------------------------------
_MEMORY_CRON_IDS = {
    "daily": "cc9b58f8-9039-4f68-95ca-25148bd34be5",
    "intraday": "3c4fc129-c78d-476f-a45b-e04ee07ebe73",
}


def _parse_cron_json():
    """Parse the OpenClaw cron job listing into an ID-indexed mapping.

    Execute `openclaw cron list --all --json`, strip any leading log noise
    before the JSON object, and then index the returned jobs by their `id`.
    Return an empty mapping when the command fails or does not emit valid JSON.

    Dependencies:
        Uses `subprocess.run()` and `json.loads()`.

    Returns:
        dict: Cron job payloads keyed by job identifier.

    Called by:
        `_memory_log_state()`.

    Side effects:
        Executes the `openclaw` CLI.
    """
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


def _get_orchestrator_model():
    """Read the default OpenClaw orchestrator model from config.

    Load `OPENCLAW_CONFIG` as JSON and return `defaultModel` when it is
    available. Fall back to the hardcoded Claude model string when the config
    file is missing or cannot be parsed.

    Dependencies:
        Uses `OPENCLAW_CONFIG` and `json.loads()`.

    Returns:
        str: Default orchestrator model identifier.

    Called by:
        `_memory_log_state()`.

    Side effects:
        Reads `OPENCLAW_CONFIG` from disk when it exists.
    """
    try:
        cfg = json.loads(OPENCLAW_CONFIG.read_text())
        return cfg.get("defaultModel", "anthropic/claude-opus-4-6")
    except Exception:
        return "anthropic/claude-opus-4-6"


def _memory_log_state():
    """Assemble the dashboard view of memory-log cron job state.

    Read the current cron job listing and the orchestrator default model, then
    project the tracked cron IDs into a compact status payload for the UI.
    Synthesize disabled placeholder entries when a tracked job is absent so the
    frontend always receives the same keys.

    Dependencies:
        Uses `_parse_cron_json()`, `_get_orchestrator_model()`,
        `_MEMORY_CRON_IDS`, and `datetime.fromtimestamp()`.

    Returns:
        dict: Memory-log status keyed by schedule bucket plus orchestrator data.

    Called by:
        Memory-log API handlers in the dashboard.

    Side effects:
        Reads cron state indirectly through `_parse_cron_json()`.
    """
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


def _read_openclaw_config():
    """Read the OpenClaw configuration file into a mapping.

    Return an empty mapping immediately when `OPENCLAW_CONFIG` does not exist.
    Otherwise load and decode the file as JSON so callers can inspect or update
    persisted OpenClaw settings.

    Dependencies:
        Uses `OPENCLAW_CONFIG` and `json.loads()`.

    Returns:
        dict: Parsed OpenClaw configuration payload.

    Called by:
        Dashboard settings handlers that inspect OpenClaw configuration.

    Side effects:
        Reads `OPENCLAW_CONFIG` from disk.
    """
    if not OPENCLAW_CONFIG.exists():
        return {}
    return json.loads(OPENCLAW_CONFIG.read_text())


def _write_openclaw_config(cfg):
    """Write the OpenClaw configuration mapping to disk.

    Ensure the parent directory exists before serializing the provided mapping
    with indentation for readability. Keep the helper narrow so config writers
    share one filesystem path and JSON encoding strategy.

    Dependencies:
        Uses `OPENCLAW_CONFIG` and `json.dumps()`.

    Returns:
        None: This helper persists configuration and does not return a value.

    Called by:
        Dashboard settings handlers that update OpenClaw configuration.

    Side effects:
        Creates the config directory when needed and overwrites the JSON file.
    """
    OPENCLAW_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    OPENCLAW_CONFIG.write_text(json.dumps(cfg, indent=2))


def _normalize_skill_location(path_obj):
    """Normalize a skill path for display in the settings UI.

    Convert the provided path object to a string and rewrite the home directory
    prefix to `~` when the path lives under the current user's home. Leave all
    other paths unchanged so absolute locations remain explicit.

    Dependencies:
        Uses `Path.home()`.

    Returns:
        str: Display-friendly skill file path.

    Called by:
        `_discover_settings_skills()`.

    Side effects:
        None.
    """
    path_str = str(path_obj)
    home_prefix = str(Path.home())
    if path_str.startswith(home_prefix):
        return "~" + path_str[len(home_prefix) :]
    return path_str


def _split_skill_frontmatter(text):
    """Split a skill document into frontmatter and body segments.

    Detect the leading `---` fence used by skill metadata and scan for the
    matching closing fence before returning the separated sections. Return an
    empty frontmatter string and the original text when the document does not
    contain a complete leading frontmatter block.

    Dependencies:
        Uses `str.startswith()` and `str.splitlines()`.

    Returns:
        tuple[str, str]: Frontmatter text and remaining body content.

    Called by:
        `_extract_skill_setup_metadata()` and `_extract_skill_description()`.

    Side effects:
        None.
    """
    if not text.startswith("---"):
        return "", text

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text

    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            return "\n".join(lines[1:idx]), "\n".join(lines[idx + 1 :])

    return "", text


def _extract_frontmatter_value(frontmatter, key):
    """Extract a scalar or indented block value from skill frontmatter.

    Scan the frontmatter line by line for an unindented `key:` entry, then
    return either the inline value or the following indented block. Stop at the
    next top-level key so multi-line metadata values are preserved without
    needing a full YAML parser.

    Dependencies:
        Uses basic string parsing over the provided `frontmatter` text.

    Returns:
        str: Extracted value for `key`, or an empty string when not found.

    Called by:
        `_parse_skill_frontmatter_metadata()`.

    Side effects:
        None.
    """
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


def _parse_skill_frontmatter_metadata(frontmatter):
    """Parse the `metadata` block from skill frontmatter.

    Pull the raw `metadata` field out of the frontmatter text and evaluate it
    with `ast.literal_eval()` only when a value is present. Return an empty
    mapping when parsing fails or the decoded object is not a dictionary.

    Dependencies:
        Uses `_extract_frontmatter_value()` and `ast.literal_eval()`.

    Returns:
        dict: Parsed metadata mapping, or an empty dict on failure.

    Called by:
        `_extract_skill_setup_metadata()`.

    Side effects:
        None.
    """
    metadata_raw = _extract_frontmatter_value(frontmatter, "metadata")
    if not metadata_raw:
        return {}

    try:
        parsed = ast.literal_eval(metadata_raw)
    except (SyntaxError, ValueError):
        return {}

    return parsed if isinstance(parsed, dict) else {}


def _normalize_skill_string_list(value):
    """Normalize skill metadata values into a clean string list.

    Promote single strings into a one-item list, reject non-sequence values,
    and trim whitespace from every item before returning it. Drop empty entries
    so downstream setup checks can rely on a compact list of command names.

    Dependencies:
        Uses basic type checks and string coercion.

    Returns:
        list[str]: Non-empty normalized string items.

    Called by:
        `_extract_skill_setup_metadata()`.

    Side effects:
        None.
    """
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


def _extract_skill_setup_metadata(skill_file):
    """Extract setup readiness metadata for a skill file.

    Read the skill document, parse its frontmatter metadata, and inspect any
    declared binary requirements with `shutil.which()`. Convert those checks
    into a compact readiness payload that includes missing commands and install
    options for the settings page.

    Dependencies:
        Uses `skill_file.read_text()`, `_split_skill_frontmatter()`,
        `_parse_skill_frontmatter_metadata()`, `_normalize_skill_string_list()`,
        and `shutil.which()`.

    Returns:
        dict: Setup metadata with readiness status, missing binaries, and
        install options.

    Called by:
        `_discover_settings_skills()`.

    Side effects:
        Reads the skill file from disk and probes executables on `PATH`.
    """
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


def _extract_skill_description(skill_file):
    """Extract the human-readable description for a skill.

    Prefer the frontmatter `description` value when it is present, including
    indented block forms, and otherwise fall back to the first prose paragraph
    in the Markdown body. Skip headings and fenced code blocks so the returned
    text reflects user-facing documentation rather than markup structure.

    Dependencies:
        Uses `skill_file.read_text()` and `_split_skill_frontmatter()`.

    Returns:
        str: Best-effort skill description for the settings UI.

    Called by:
        `_discover_settings_skills()`.

    Side effects:
        Reads the skill file from disk.
    """
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


def _discover_settings_skills():
    """Discover built-in and custom skills for the settings page.

    Walk the configured skill roots, skip non-skill entries, and build one
    record per skill with description, location, type, and setup metadata.
    Prefer a custom skill over a built-in one when both share the same name so
    the UI reflects local overrides.

    Dependencies:
        Uses `BUILTIN_SKILLS_DIR`, `CUSTOM_SKILLS_DIR`,
        `_extract_skill_description()`, `_normalize_skill_location()`, and
        `_extract_skill_setup_metadata()`.

    Returns:
        list[dict]: Sorted skill records ready for API serialization.

    Called by:
        Settings API handlers that serve the skills inventory.

    Side effects:
        Reads skill directories and skill files from disk.
    """
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


def _normalize_agent_model(model_value):
    """Normalize an agent model config value into a single string.

    Return string values as-is, or extract the primary model and then the first
    fallback model from dictionary payloads used by agent config. Produce an
    empty string when the value cannot be resolved to a meaningful model name.

    Dependencies:
        Uses basic type checks over agent config payloads.

    Returns:
        str: Canonical model identifier or an empty string.

    Called by:
        `_list_skill_agents()`.

    Side effects:
        None.
    """
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


def _list_skill_agents(cfg):
    """List agents that can receive skill assignments.

    Read the `agents` config block, collect unique agent identifiers from both
    the list-style and legacy mapping-style config shapes, and attach the best
    available model for each entry. Preserve declaration order while skipping
    duplicates so the settings UI can render a stable agent matrix.

    Dependencies:
        Uses `_normalize_agent_model()` and the `agents` section of `cfg`.

    Returns:
        list[dict]: Agent records containing `name` and resolved `model`.

    Called by:
        Settings API handlers that build the skill assignment payload.

    Side effects:
        None.
    """
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


def _get_agent_skill_allow(cfg, agent_name):
    """Read the allowed skill list for one agent configuration entry.

    Search the modern `agents.list` structure first, then fall back to the
    legacy per-agent mapping shape when needed. Normalize any returned skill
    names by trimming whitespace and return `None` when no allow-list is
    configured for the agent.

    Dependencies:
        Uses the `agents` section of `cfg`.

    Returns:
        list[str] | None: Allowed skill names, or `None` when unset.

    Called by:
        Settings API handlers that serialize skill assignments.

    Side effects:
        None.
    """
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


def _set_agent_skill_allow(cfg, agent_name, allowed_skills):
    """Set or clear the allowed skill list for an agent.

    Resolve the target agent entry across the current list-style and legacy
    config shapes, creating a list entry when the agent does not yet exist.
    Write the `skills.allow` list when provided, or remove it cleanly when the
    caller passes `None`.

    Dependencies:
        Uses the mutable `cfg` mapping and the expected `agents` config shapes.

    Returns:
        None: This helper mutates `cfg` in place and does not return a value.

    Called by:
        Settings API handlers that update skill assignments.

    Side effects:
        Mutates the provided `cfg` dictionary in place.
    """
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


# ---------------------------------------------------------------------------
# API: Memory Bridge
# ---------------------------------------------------------------------------


SSOT_KEYWORDS_FILE = SSOT_ROOT / ".ssot-keywords.json"
R_AWARENESS_KEYWORDS_FILE = WORKSPACE / "r-awareness" / "keywords.json"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

app.config["WALLET_SHARED"] = {
    "load_bounties": _load_bounties,
    "load_tribes": _load_tribes,
    "enrich_bounty_with_tribe": _enrich_bounty_with_tribe,
}

from routes.projects import _load_projects  # noqa: F401
from routes.pages import pages_bp
from routes.gateway import gateway_bp
from routes.knowledge import knowledge_bp
from routes.memory_bridge import memory_bridge_bp
from routes.misc import misc_bp
from routes.system import system_bp
from routes.token_savings import token_savings_bp


BLUEPRINT_MAP = {
    "shield_bp": ("routes.shield", "shield_bp"),
    "logician_bp": ("routes.logician", "logician_bp"),
    "agents_bp": ("routes.agents", "agents_bp"),
    "wallet_bp": ("routes.wallet", "wallet_bp"),
    "docs_bp": ("routes.docs", "docs_bp"),
    "settings_bp": ("routes.settings", "settings_bp"),
    "symbiotic_bp": ("routes.symbiotic", "symbiotic_bp"),
    "chatbots_bp": ("routes.chatbots", "chatbots_bp"),
    "todo_bp": ("routes.todo", "todo_bp"),
    "projects_bp": ("routes.projects", "projects_bp"),
    "tribes_bp": ("routes.tribes", "tribes_bp"),
    "bounties_bp": ("routes.bounties", "bounties_bp"),
    "protocols_bp": ("routes.protocols", "protocols_bp"),
}

registry = _load_modules_registry()
app.config["MODULE_REGISTRY"] = registry
app.config["MODULES"] = registry.get("modules", [])

for blueprint in [
    pages_bp,
    gateway_bp,
    system_bp,
    misc_bp,
    knowledge_bp,
    memory_bridge_bp,
    token_savings_bp,
]:
    app.register_blueprint(blueprint)

modules = registry.get("modules", [])
if not modules:
    for module_path, attr in BLUEPRINT_MAP.values():
        imported = importlib.import_module(module_path)
        app.register_blueprint(getattr(imported, attr))
else:
    for module in modules:
        blueprint_name = module.get("blueprint")
        if not blueprint_name or not module.get("enabled", False):
            continue
        if blueprint_name in BLUEPRINT_MAP:
            module_path, attr = BLUEPRINT_MAP[blueprint_name]
            imported = importlib.import_module(module_path)
            app.register_blueprint(getattr(imported, attr))

# ── DAO Bounty Board routes (registered late so all helpers are defined) ──
try:
    from server_bounty_routes import register_bounty_routes

    _bounty_ctx = {
        "require_identity_nft": _require_identity_nft,
        "check_rct_cap": _check_rct_cap,
        "record_rct_mint": _record_rct_mint,
        "derive_symbiotic_pda": _derive_symbiotic_pda,
        "get_fee_payer": _get_fee_payer,
        "TokenManager": TokenManager,
        "SolanaWallet": SolanaWallet,
        "RCT_MINT": _RCT_MINT,
        "RES_MINT": _RES_MINT,
        "RCT_DECIMALS": _RCT_DECIMALS,
    }
    register_bounty_routes(app, _bounty_ctx)
    print("[OK] Bounty board routes loaded")
except Exception as _bounty_err:
    print(f"[WARN] Bounty routes not loaded: {_bounty_err}")

# ── Contributor Profile routes ──
try:
    from server_profile_routes import register_profile_routes

    register_profile_routes(app)
    print("[OK] Profile routes loaded")
except Exception as _profile_err:
    print(f"[WARN] Profile routes not loaded: {_profile_err}")


def main():
    """Start the dashboard web server and background services.

    Print startup diagnostics for the gateway connection and repository paths,
    then start the gateway client and auto-update checker before serving the
    dashboard via Waitress.
    Pause briefly to report the current gateway connection status before binding
    the app to port `19100`.

    Dependencies:
        Uses `gw.start()`, `start_auto_update_checker()`, `time.sleep()`, and
        `waitress.serve()`.

    Returns:
        None: This function blocks in the Waitress production server.
    """
    print(f"\n⚡ ResonantOS Dashboard v2")
    print(f"   Gateway: {GW_WS_URL}")
    print(f"   SSoT root: {SSOT_ROOT}")
    print(f"   Auth token: ***{GW_TOKEN[-6:]}" if GW_TOKEN else "   Auth token: (none)")

    gw.start()
    start_auto_update_checker()

    # Wait briefly for connection
    time.sleep(1)
    if gw.connected:
        print(f"   ✓ Gateway connected (connId: {gw.conn_id})")
    else:
        print(f"   ✗ Gateway not connected yet ({gw.error or 'connecting...'})")

    print(f"\n   Dashboard: http://localhost:19100\n")
    try:
        serve(app, host="127.0.0.1", port=19100, threads=4)
    except Exception as e:
        logger.exception("Dashboard failed to start; rolling back to origin/main")
        print(f"\n[FATAL] Dashboard failed to start: {e}")
        print("Rolling back to origin/main...")
        subprocess.run(["git", "reset", "--hard", "origin/main"], cwd=str(Path(__file__).parent))
        print("Run 'openclaw service restart dashboard' after fixing the issue.")
        sys.exit(1)


if __name__ == "__main__":
    main()
