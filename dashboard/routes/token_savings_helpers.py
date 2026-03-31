"""Token savings helpers."""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

from routes.config import _CFG, _CONFIG_FILE, OPENCLAW_CONFIG, OPENCLAW_HOME, RMEMORY_DIR, WORKSPACE
from routes.logging_config import get_logger
from routes.rmemory import _rmem_current_session_id, _rmem_effective_models, _rmem_history_blocks

logger = get_logger(__name__)

_KNOWN_MODEL_PRICING: dict[str, dict[str, float | str]] = {
    "anthropic/claude-opus-4-6": {
        "label": "Claude Opus 4.6",
        "inputPer1M": 5.0,
        "outputPer1M": 25.0,
        "cacheReadPer1M": 0.5,
        "cacheWritePer1M": 6.25,
    },
    "minimax/MiniMax-M2.5": {
        "label": "MiniMax M2.5",
        "inputPer1M": 0.3,
        "outputPer1M": 1.2,
        "cacheReadPer1M": 0.03,
        "cacheWritePer1M": 0.12,
    },
    "minimax/MiniMax-M2.5-Lightning": {
        "label": "MiniMax M2.5 Lightning",
        "inputPer1M": 0.3,
        "outputPer1M": 1.2,
        "cacheReadPer1M": 0.03,
        "cacheWritePer1M": 0.12,
    },
    "anthropic/claude-sonnet-4-6": {
        "label": "Claude Sonnet 4.6",
        "inputPer1M": 3.0,
        "outputPer1M": 15.0,
        "cacheReadPer1M": 0.3,
        "cacheWritePer1M": 3.75,
    },
    "anthropic/claude-haiku-4-5": {
        "label": "Claude Haiku 4.5",
        "inputPer1M": 1.0,
        "outputPer1M": 5.0,
        "cacheReadPer1M": 0.1,
        "cacheWritePer1M": 1.25,
    },
    "openai-codex/gpt-4o-mini": {
        "label": "GPT-4o mini",
        "inputPer1M": 0.15,
        "outputPer1M": 0.6,
        "cacheReadPer1M": 0.075,
        "cacheWritePer1M": 0.15,
    },
    "openai-codex/gpt-5.3-codex": {
        "label": "GPT-5.3 Codex",
        "inputPer1M": 2.0,
        "outputPer1M": 8.0,
        "cacheReadPer1M": 0.5,
        "cacheWritePer1M": 2.0,
    },
    "openai/gpt-4o-mini": {
        "label": "GPT-4o mini (direct)",
        "inputPer1M": 0.15,
        "outputPer1M": 0.6,
        "cacheReadPer1M": 0.075,
        "cacheWritePer1M": 0.15,
    },
    "openai/gpt-4o": {
        "label": "GPT-4o",
        "inputPer1M": 2.5,
        "outputPer1M": 10.0,
        "cacheReadPer1M": 1.25,
        "cacheWritePer1M": 2.5,
    },
    "google/gemini-2.0-flash": {
        "label": "Gemini 2.0 Flash",
        "inputPer1M": 0.1,
        "outputPer1M": 0.4,
        "cacheReadPer1M": 0.025,
        "cacheWritePer1M": 0.1,
    },
}

_TOKEN_SAVINGS_DEFAULT_PRICING: dict[str, Any] = {
    "currency": "USD",
    "defaultModel": "gateway/blended",
    "models": {
        "gateway/blended": {
            "label": "Gateway Blended (from usage-cost)",
            "inputPer1M": 5.0,
            "outputPer1M": 25.0,
            "cacheReadPer1M": 0.5,
            "cacheWritePer1M": 6.25,
        },
    },
    "assumptions": {
        "avgOutputTokensPerCall": 800,
        "heartbeatInputTokensPerCall": 700,
        "heartbeatOutputTokensPerCall": 140,
        "cronInputTokensPerCall": 900,
        "cronOutputTokensPerCall": 180,
        "subagentShare": 0.18,
    },
}


def _ts_discover_system_models() -> list[str]:
    """Discover model identifiers referenced across local configs.

    Inspect the OpenClaw agent config, cron jobs, and R-Memory camouflage file
    to build a unique set of model identifiers. Swallow read failures so token
    savings can still render when one optional source is unavailable.

    Called by:
        _ts_load_pricing().
    Side effects:
        Reads local configuration files when they exist.

    Returns:
        list[str]: Sorted list of discovered model identifiers.
    """
    models = set()
    try:
        cfg = json.loads(OPENCLAW_CONFIG.read_text()) if OPENCLAW_CONFIG.exists() else {}
        dp = cfg.get("agents", {}).get("defaults", {}).get("model", {}).get("primary", "")
        if dp:
            models.add(dp)
        hb = cfg.get("agents", {}).get("defaults", {}).get("heartbeat", {}).get("model", "")
        if hb:
            models.add(hb)
        for agent in cfg.get("agents", {}).get("list", []):
            model = agent.get("model", "")
            if model:
                models.add(model)
    except Exception:
        logger.debug("Failed to discover default agent models from %s", OPENCLAW_CONFIG, exc_info=True)
    try:
        cron_path = OPENCLAW_HOME / "cron" / "jobs.json"
        if cron_path.exists():
            data = json.loads(cron_path.read_text())
            jobs = data if isinstance(data, list) else data.get("jobs", [])
            for job in jobs:
                model = job.get("payload", {}).get("model", "")
                if model:
                    models.add(model)
    except Exception:
        logger.debug("Failed to discover cron job models", exc_info=True)
    try:
        cam_path = RMEMORY_DIR / "camouflage.json"
        if cam_path.exists():
            cam = json.loads(cam_path.read_text())
            for _provider, model_str in cam.get("backgroundModels", {}).items():
                if model_str:
                    models.add(model_str)
    except Exception:
        logger.debug("Failed to discover R-Memory camouflage models", exc_info=True)
    return sorted(models)


def _ts_merge_dict(base: Any, override: Any) -> dict[str, Any]:
    """Merge nested dictionaries recursively.

    Preserve existing nested mappings from the base structure while applying
    override values from the patch structure. Replace non-dict values directly
    so callers can update individual leaves without rebuilding the whole tree.

    Called by:
        _ts_sanitize_pricing() and recursive calls to _ts_merge_dict().
    Side effects:
        None.

    Returns:
        dict[str, Any]: Merged dictionary result.
    """
    out = dict(base) if isinstance(base, dict) else {}
    if not isinstance(override, dict):
        return out
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _ts_merge_dict(out[key], value)
        else:
            out[key] = value
    return out


def _ts_load_dashboard_config() -> dict[str, Any]:
    """Load the dashboard configuration JSON from disk.

    Read the current config file when possible and fall back to the in-memory
    module cache when the file cannot be parsed. Keep the helper tolerant so
    read failures do not break token-savings routes.

    Called by:
        _ts_load_pricing().
    Side effects:
        Reads `config.json` from disk.

    Returns:
        dict[str, Any]: Parsed dashboard configuration dictionary.
    """
    try:
        return json.loads(_CONFIG_FILE.read_text())
    except Exception:
        return _CFG if isinstance(_CFG, dict) else {}


def _ts_save_dashboard_config(cfg: dict[str, Any]) -> None:
    """Persist the dashboard configuration and refresh the module cache.

    Serialize the supplied configuration with stable indentation and write it
    back to the shared dashboard config file. Update the module-level cache so
    later helper calls observe the new values immediately.

    Called by:
        api_token_savings_pricing().
    Side effects:
        Writes `config.json` and mutates the module-level `_CFG` cache.

    Returns:
        None: This helper updates persisted and in-memory config state.
    """
    global _CFG
    _CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
    _CFG = cfg


def _ts_float(value: Any, default: float = 0.0) -> float:
    """Convert a value to `float` with a fallback default.

    Attempt a direct numeric conversion and fall back to the supplied default
    when parsing fails. Keep callers concise by centralizing permissive numeric
    coercion in one helper.

    Called by:
        Multiple token-savings helpers that normalize numeric config and usage values.
    Side effects:
        None.

    Returns:
        float: Parsed float value or the default converted to float.
    """
    try:
        return float(value)
    except Exception:
        return float(default)


def _ts_int(value: Any, default: int = 0) -> int:
    """Convert a value to `int` with a fallback default.

    Attempt a direct integer conversion and fall back to the supplied default
    when parsing fails. Keep integer coercion behavior consistent across token
    savings routes and helper calculations.

    Called by:
        Multiple token-savings helpers that normalize counts, tokens, and day windows.
    Side effects:
        None.

    Returns:
        int: Parsed integer value or the default converted to int.
    """
    try:
        return int(value)
    except Exception:
        return int(default)


def _ts_parse_every_minutes(every: Any) -> float | None:
    """Parse a compact interval string into minutes.

    Accept numeric values directly and parse suffixed strings such as `30m` or
    `2h` into minute counts. Return `None` for invalid or non-positive inputs so
    callers can detect disabled or malformed schedules.

    Called by:
        build_token_savings_payload().
    Side effects:
        None.

    Returns:
        float | None: Interval length in minutes, or `None` when parsing fails.
    """
    if every is None:
        return None
    if isinstance(every, (int, float)):
        return float(every) if every > 0 else None
    raw = str(every).strip().lower()
    match = re.match(r"^(\d+(?:\.\d+)?)\s*([smhd])$", raw)
    if not match:
        return None
    num = _ts_float(match.group(1), 0)
    unit = match.group(2)
    if num <= 0:
        return None
    return num * {"s": 1 / 60, "m": 1, "h": 60, "d": 1440}[unit]


def _ts_minutes_between(start: Any, end: Any) -> int:
    """Compute the wrapped minute span between two clock times.

    Parse `HH:MM`-style values, normalize them onto a single day, and allow the
    range to wrap across midnight. Fall back to a full day when either value
    cannot be parsed.

    Called by:
        build_token_savings_payload().
    Side effects:
        None.

    Returns:
        int: Number of minutes between the two times, modulo one day.
    """
    try:
        s_h, s_m = [int(x) for x in str(start).split(":")[:2]]
        e_h, e_m = [int(x) for x in str(end).split(":")[:2]]
        s_val = (s_h * 60 + s_m) % 1440
        e_val = (e_h * 60 + e_m) % 1440
        return (e_val - s_val) % 1440
    except Exception:
        return 24 * 60


def _ts_estimate_calls_from_cron(expr: Any, days: int) -> int:
    """Estimate how many times a cron schedule runs over a window.

    Parse the main cron fields and approximate the number of matching minutes
    and hours per day. Scale that estimate across the requested day window and
    apply simple day-of-month or day-of-week factors.

    Called by:
        build_token_savings_payload().
    Side effects:
        None.

    Returns:
        int: Estimated number of invocations for the supplied period.
    """
    if not expr or not isinstance(expr, str):
        return 0
    parts = expr.split()
    if len(parts) < 5:
        return 0
    minute, hour, dom, _month, dow = parts[:5]

    def _count_field(field, low, high):
        """Estimate how many values a cron field matches.

        Interpret wildcards, step expressions, comma-separated values, and
        simple numeric literals for one cron field. Keep the estimate coarse but
        stable because the outer helper only needs an approximate call count.

        Called by:
            _ts_estimate_calls_from_cron().
        Side effects:
            None.

        Returns:
            int: Approximate number of matching values in the field span.
        """
        span = high - low + 1
        if field == "*":
            return span
        if field.startswith("*/"):
            step = max(_ts_int(field[2:], 1), 1)
            return max(1, (span + step - 1) // step)
        if "," in field:
            items = [part for part in field.split(",") if part]
            return max(1, len(items))
        if field.isdigit():
            return 1
        return 1

    calls_per_day = _count_field(minute, 0, 59) * _count_field(hour, 0, 23)
    day_factor = 1.0
    if dom != "*" and dow == "*":
        day_factor = min(1.0, _count_field(dom, 1, 31) / 30.0)
    elif (dow != "*" and dom == "*") or (dom != "*" and dow != "*"):
        day_factor = min(1.0, _count_field(dow, 0, 6) / 7.0)
    return max(0, int(round(calls_per_day * day_factor * max(days, 1))))


def _ts_lookup_rates(pricing: dict[str, Any], model_name: str) -> tuple[str, dict[str, Any]]:
    """Look up pricing rates for a model identifier.

    Check for an exact model match first, then fall back to a suffix match so
    short model names can reuse fully qualified pricing entries. Return the
    configured default model when no specific entry is available.

    Called by:
        build_token_savings_payload().
    Side effects:
        None.

    Returns:
        tuple[str, dict[str, Any]]: Matched pricing key and its rate dictionary.
    """
    models = pricing.get("models", {})
    default_key = pricing.get("defaultModel", "gateway/blended")
    if model_name in models:
        return model_name, models[model_name]
    if isinstance(model_name, str):
        needle = model_name.split("/")[-1]
        for key, rates in models.items():
            if key.endswith(needle):
                return key, rates
    return default_key, models.get(default_key, {})


def _ts_component_cost(
    rates: dict[str, Any],
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    """Calculate total cost for a token usage component.

    Convert the configured per-million rates into per-request costs across
    input, output, cache-read, and cache-write token buckets. Keep the pricing
    math centralized so each component uses the same cost formula.

    Called by:
        build_token_savings_payload().
    Side effects:
        None.

    Returns:
        float: Total estimated dollar cost for the supplied token counts.
    """
    ip = _ts_float(rates.get("inputPer1M"), 0)
    op = _ts_float(rates.get("outputPer1M"), 0)
    cr = _ts_float(rates.get("cacheReadPer1M"), 0)
    cw = _ts_float(rates.get("cacheWritePer1M"), 0)
    return (
        _ts_float(input_tokens) * ip / 1_000_000
        + _ts_float(output_tokens) * op / 1_000_000
        + _ts_float(cache_read_tokens) * cr / 1_000_000
        + _ts_float(cache_write_tokens) * cw / 1_000_000
    )


def _ts_sanitize_pricing(pricing: Any) -> dict[str, Any]:
    """Sanitize token-savings pricing configuration data.

    Merge the incoming pricing structure with defaults, normalize model rate
    fields to non-negative floats, and clamp assumption values into safe ranges.
    Ensure the route layer always works with a complete pricing document.

    Called by:
        _ts_load_pricing() and api_token_savings_pricing().
    Side effects:
        None.

    Returns:
        dict[str, Any]: Normalized pricing configuration dictionary.
    """
    merged = _ts_merge_dict(_TOKEN_SAVINGS_DEFAULT_PRICING, pricing if isinstance(pricing, dict) else {})
    models = merged.get("models", {})
    for model_name, rates in list(models.items()):
        if not isinstance(rates, dict):
            models[model_name] = {}
            rates = models[model_name]
        for key in ("inputPer1M", "outputPer1M", "cacheReadPer1M", "cacheWritePer1M"):
            rates[key] = max(0.0, _ts_float(rates.get(key), 0.0))
        if "label" in rates and not isinstance(rates.get("label"), str):
            rates["label"] = str(rates["label"])
    assumptions = merged.get("assumptions", {})
    assumptions["avgOutputTokensPerCall"] = max(1, _ts_int(assumptions.get("avgOutputTokensPerCall"), 800))
    assumptions["heartbeatInputTokensPerCall"] = max(0, _ts_int(assumptions.get("heartbeatInputTokensPerCall"), 700))
    assumptions["heartbeatOutputTokensPerCall"] = max(0, _ts_int(assumptions.get("heartbeatOutputTokensPerCall"), 140))
    assumptions["cronInputTokensPerCall"] = max(0, _ts_int(assumptions.get("cronInputTokensPerCall"), 900))
    assumptions["cronOutputTokensPerCall"] = max(0, _ts_int(assumptions.get("cronOutputTokensPerCall"), 180))
    assumptions["subagentShare"] = min(0.95, max(0.0, _ts_float(assumptions.get("subagentShare"), 0.18)))
    merged["assumptions"] = assumptions
    return merged


def _ts_load_pricing() -> tuple[dict[str, Any], dict[str, Any]]:
    """Load and enrich the token-savings pricing configuration.

    Read the dashboard config, sanitize its pricing section, and augment the
    model list with any auto-discovered system models. Add zero-priced placeholder
    entries when a discovered model has no known pricing reference.

    Called by:
        api_token_savings_pricing(), _ts_load_tracker_usage(), and build_token_savings_payload().
    Side effects:
        Reads dashboard and local OpenClaw configuration files.

    Returns:
        tuple[dict[str, Any], dict[str, Any]]: Pricing payload and raw dashboard config.
    """
    cfg = _ts_load_dashboard_config()
    pricing = _ts_sanitize_pricing(cfg.get("pricing", {}))
    discovered = _ts_discover_system_models()
    models = pricing.get("models", {})
    for model_id in discovered:
        if model_id not in models:
            known = _KNOWN_MODEL_PRICING.get(model_id)
            if known:
                models[model_id] = dict(known)
            else:
                short_name = model_id.split("/")[-1] if "/" in model_id else model_id
                models[model_id] = {
                    "label": f"{short_name} (auto-discovered, set pricing)",
                    "inputPer1M": 0.0,
                    "outputPer1M": 0.0,
                    "cacheReadPer1M": 0.0,
                    "cacheWritePer1M": 0.0,
                }
    pricing["models"] = models
    pricing["_discoveredModels"] = discovered
    return pricing, cfg


def _ts_collect_cron_jobs(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Collect cron job definitions from known config locations.

    Check the legacy and newer config shapes that can contain job lists and
    flatten any valid dictionaries into one sequence. Keep the extraction logic
    here so payload generation does not need to know the config variants.

    Called by:
        build_token_savings_payload().
    Side effects:
        None.

    Returns:
        list[dict[str, Any]]: Cron job dictionaries found in the config.
    """
    candidates = [
        cfg.get("cron", {}).get("jobs"),
        cfg.get("jobs"),
        cfg.get("commands", {}).get("cron", {}).get("jobs"),
        cfg.get("commands", {}).get("jobs"),
    ]
    jobs = []
    for candidate in candidates:
        if isinstance(candidate, list):
            jobs.extend([job for job in candidate if isinstance(job, dict)])
    return jobs


def _ts_run_gateway_usage_cost(days: int) -> tuple[dict[str, Any] | None, str | None, dict[str, Any]]:
    """Run the gateway usage-cost command and parse its JSON output.

    Execute the local `openclaw gateway usage-cost` command for the requested
    day window and normalize failure details into a structured tuple. Recover
    from wrapped stdout noise by extracting the outer JSON object when needed.

    Called by:
        build_token_savings_payload().
    Side effects:
        Spawns the `openclaw` subprocess and reads its stdout and stderr.

    Returns:
        tuple[dict[str, Any] | None, str | None, dict[str, Any]]: Parsed data, error string, and command metadata.
    """
    cmd = ["openclaw", "gateway", "usage-cost", "--days", str(days), "--json"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except Exception as e:
        return None, f"gateway usage-cost command failed: {e}", {"cmd": cmd}
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        return None, err or f"command exited {result.returncode}", {"cmd": cmd}

    raw = (result.stdout or "").strip()
    if not raw:
        return None, "gateway usage-cost returned empty output", {"cmd": cmd}
    try:
        return json.loads(raw), None, {"cmd": cmd}
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start : end + 1]), None, {"cmd": cmd}
            except Exception as e:
                return None, f"invalid JSON from gateway usage-cost: {e}", {"cmd": cmd}
        return None, "invalid JSON from gateway usage-cost", {"cmd": cmd}


def _ts_parse_tracker_timestamp(value: Any) -> datetime | None:
    """Parse a usage-tracker timestamp into UTC.

    Accept `datetime` objects, Unix timestamps in seconds or milliseconds, and
    ISO-8601 strings, then normalize the result to UTC. Return `None` when the
    value is empty or cannot be interpreted as a timestamp.

    Called by:
        _ts_load_tracker_usage().
    Side effects:
        None.

    Returns:
        datetime | None: Parsed UTC timestamp or `None` when parsing fails.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        num = float(value)
        seconds = num / 1000.0 if num > 10_000_000_000 else num
        try:
            dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
        except Exception:
            return None
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if re.match(r"^-?\d+(?:\.\d+)?$", raw):
            try:
                num = float(raw)
                seconds = num / 1000.0 if num > 10_000_000_000 else num
                dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
            except Exception:
                return None
        else:
            try:
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except Exception:
                return None
    else:
        return None

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(UTC)


def _ts_load_tracker_usage(days: int) -> tuple[dict[str, Any] | None, str | None, dict[str, Any]]:
    """Load recent usage data from the usage-tracker log.

    Read the JSONL tracker file, filter entries to the requested date window,
    and aggregate per-day and total token and cost statistics. Fall back to an
    empty structure when the tracker file is missing.

    Called by:
        build_token_savings_payload().
    Side effects:
        Reads the usage-tracker JSONL file and pricing configuration from disk.

    Returns:
        tuple[dict[str, Any] | None, str | None, dict[str, Any]]: Aggregated data, error string, and file metadata.
    """
    tracker_file = WORKSPACE / "usage-tracker" / "usage.jsonl"
    meta = {
        "path": str(tracker_file),
        "days": int(days),
        "exists": tracker_file.exists(),
        "entries": 0,
        "keptEntries": 0,
        "invalidLines": 0,
    }
    empty_totals = {
        "input": 0,
        "output": 0,
        "cacheRead": 0,
        "cacheWrite": 0,
        "totalTokens": 0,
        "inputCost": 0.0,
        "outputCost": 0.0,
        "cacheReadCost": 0.0,
        "cacheWriteCost": 0.0,
        "totalCost": 0.0,
    }
    empty_data = {"daily": [], "totals": dict(empty_totals)}

    if not tracker_file.exists():
        return empty_data, None, meta

    try:
        pricing, _cfg = _ts_load_pricing()
    except Exception:
        pricing = _TOKEN_SAVINGS_DEFAULT_PRICING

    models = pricing.get("models", {}) if isinstance(pricing, dict) else {}
    default_model = pricing.get("defaultModel", "gateway/blended") if isinstance(pricing, dict) else "gateway/blended"
    fallback_rates = models.get(default_model) if isinstance(models, dict) else None
    if not isinstance(fallback_rates, dict):
        fallback_rates = _TOKEN_SAVINGS_DEFAULT_PRICING["models"]["gateway/blended"]

    def _new_day_bucket(date_key):
        """Create an empty aggregation bucket for one calendar day.

        Initialize the token and cost fields used while accumulating tracker
        entries for a single date. Keep the bucket shape centralized so daily
        and total rollups stay structurally consistent.

        Called by:
            _ts_load_tracker_usage().
        Side effects:
            None.

        Returns:
            dict[str, Any]: Empty per-day usage bucket.
        """
        return {
            "date": date_key,
            "input": 0,
            "output": 0,
            "cacheRead": 0,
            "cacheWrite": 0,
            "totalTokens": 0,
            "inputCost": 0.0,
            "outputCost": 0.0,
            "cacheReadCost": 0.0,
            "cacheWriteCost": 0.0,
            "totalCost": 0.0,
        }

    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, _ts_int(days, 7)))
    daily = {}
    totals = dict(empty_totals)

    try:
        with tracker_file.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                row = line.strip()
                if not row:
                    continue
                meta["entries"] += 1
                try:
                    payload = json.loads(row)
                except Exception:
                    meta["invalidLines"] += 1
                    continue

                ts = _ts_parse_tracker_timestamp(payload.get("ts"))
                if ts is None or ts < cutoff:
                    continue

                input_tokens = max(0, _ts_int(payload.get("input"), 0))
                output_tokens = max(0, _ts_int(payload.get("output"), 0))
                cache_read_tokens = max(0, _ts_int(payload.get("cacheRead"), 0))
                cache_write_tokens = max(0, _ts_int(payload.get("cacheWrite"), 0))
                if (input_tokens + output_tokens + cache_read_tokens + cache_write_tokens) <= 0:
                    continue

                provider = str(payload.get("provider") or "").strip()
                model = str(payload.get("model") or "").strip()
                model_key = f"{provider}/{model}" if (provider and model) else None
                rates = _KNOWN_MODEL_PRICING.get(model_key) if model_key else None
                if not isinstance(rates, dict):
                    rates = fallback_rates

                ip = _ts_float(rates.get("inputPer1M"), 0.0)
                op = _ts_float(rates.get("outputPer1M"), 0.0)
                cr = _ts_float(rates.get("cacheReadPer1M"), 0.0)
                cw = _ts_float(rates.get("cacheWritePer1M"), 0.0)

                input_cost = input_tokens * ip / 1_000_000
                output_cost = output_tokens * op / 1_000_000
                cache_read_cost = cache_read_tokens * cr / 1_000_000
                cache_write_cost = cache_write_tokens * cw / 1_000_000
                total_tokens = input_tokens + output_tokens + cache_read_tokens + cache_write_tokens
                total_cost = input_cost + output_cost + cache_read_cost + cache_write_cost

                date_key = ts.date().isoformat()
                bucket = daily.setdefault(date_key, _new_day_bucket(date_key))
                bucket["input"] += input_tokens
                bucket["output"] += output_tokens
                bucket["cacheRead"] += cache_read_tokens
                bucket["cacheWrite"] += cache_write_tokens
                bucket["totalTokens"] += total_tokens
                bucket["inputCost"] += input_cost
                bucket["outputCost"] += output_cost
                bucket["cacheReadCost"] += cache_read_cost
                bucket["cacheWriteCost"] += cache_write_cost
                bucket["totalCost"] += total_cost

                totals["input"] += input_tokens
                totals["output"] += output_tokens
                totals["cacheRead"] += cache_read_tokens
                totals["cacheWrite"] += cache_write_tokens
                totals["totalTokens"] += total_tokens
                totals["inputCost"] += input_cost
                totals["outputCost"] += output_cost
                totals["cacheReadCost"] += cache_read_cost
                totals["cacheWriteCost"] += cache_write_cost
                totals["totalCost"] += total_cost
                meta["keptEntries"] += 1
    except Exception as e:
        return None, f"failed to read tracker usage file: {e}", meta

    return {"daily": [daily[day] for day in sorted(daily.keys())], "totals": totals}, None, meta


def build_token_savings_payload(days: int) -> dict[str, Any]:
    """Build the full token-savings analytics payload.

    Combine gateway or usage-tracker cost data with R-Memory compression stats,
    pricing metadata, and estimated system component costs. Produce the single
    response document consumed by the token-savings dashboard view.

    Called by:
        api_token_savings().
    Side effects:
        Reads multiple local config and stats files and may invoke the gateway usage-cost command.

    Returns:
        dict[str, Any]: Aggregated token-savings payload for the requested day window.
    """
    pricing, _cfg = _ts_load_pricing()
    assumptions = pricing.get("assumptions", {})

    usage_stats = {}
    usage_stats_path = RMEMORY_DIR / "usage-stats.json"
    if usage_stats_path.exists():
        try:
            usage_stats = json.loads(usage_stats_path.read_text())
        except Exception:
            usage_stats = {}

    all_blocks = _rmem_history_blocks()
    cur_sid = _rmem_current_session_id()
    cur_blocks = [block for block in all_blocks if cur_sid and cur_sid in block.get("_file", "")]

    all_raw = sum(_ts_int(block.get("tokensRaw"), 0) for block in all_blocks)
    all_comp = sum(_ts_int(block.get("tokensCompressed"), 0) for block in all_blocks)

    meaningful_blocks = [
        block
        for block in all_blocks
        if _ts_int(block.get("tokensRaw"), 0) > 50
        and _ts_int(block.get("tokensRaw"), 0) > _ts_int(block.get("tokensCompressed"), 0)
    ]
    meaningful_raw = sum(_ts_int(block.get("tokensRaw"), 0) for block in meaningful_blocks)
    meaningful_comp = sum(_ts_int(block.get("tokensCompressed"), 0) for block in meaningful_blocks)

    context_raw = sum(_ts_int(block.get("tokensRaw"), 0) for block in cur_blocks)
    context_comp = sum(_ts_int(block.get("tokensCompressed"), 0) for block in cur_blocks)
    cur_saved = sum(
        max(0, _ts_int(block.get("tokensRaw"), 0) - _ts_int(block.get("tokensCompressed"), 0)) for block in cur_blocks
    )
    if cur_saved > 1000:
        context_saved_per_call = cur_saved
    elif meaningful_blocks:
        avg_saving_per_block = (meaningful_raw - meaningful_comp) / len(meaningful_blocks)
        avg_context_blocks = max(len(cur_blocks), 25)
        context_saved_per_call = int(avg_saving_per_block * avg_context_blocks)
    else:
        context_saved_per_call = 0
    archived_blocks = max(0, len(all_blocks) - len(cur_blocks))
    archived_raw = max(0, all_raw - context_raw)
    archived_comp = max(0, all_comp - context_comp)

    tracker_data, tracker_error, tracker_meta = _ts_load_tracker_usage(days)
    tracker_meta = tracker_meta if isinstance(tracker_meta, dict) else {}
    tracker_daily = tracker_data.get("daily", []) if isinstance(tracker_data, dict) else []
    tracker_totals = tracker_data.get("totals", {}) if isinstance(tracker_data, dict) else {}
    tracker_has_entries = (
        _ts_int(tracker_meta.get("keptEntries"), 0) > 0
        or len(tracker_daily) > 0
        or _ts_int(tracker_totals.get("totalTokens"), 0) > 0
    )

    source = "usage-tracker" if tracker_has_entries else "gateway"
    if tracker_has_entries:
        gateway_data, gateway_error, gateway_meta = tracker_data, tracker_error, tracker_meta
    else:
        gateway_data, gateway_error, gateway_meta = _ts_run_gateway_usage_cost(days)

    daily = gateway_data.get("daily", []) if isinstance(gateway_data, dict) else []
    totals = gateway_data.get("totals", {}) if isinstance(gateway_data, dict) else {}

    total_cost = _ts_float(totals.get("totalCost"), 0)
    total_input = _ts_int(totals.get("input"), 0)
    total_output = _ts_int(totals.get("output"), 0)
    total_cache_read = _ts_int(totals.get("cacheRead"), 0)
    total_cache_write = _ts_int(totals.get("cacheWrite"), 0)
    total_tokens = _ts_int(totals.get("totalTokens"), 0)

    input_cost = _ts_float(totals.get("inputCost"), sum(_ts_float(day.get("inputCost"), 0) for day in daily))
    output_cost = _ts_float(totals.get("outputCost"), sum(_ts_float(day.get("outputCost"), 0) for day in daily))
    cache_read_cost = _ts_float(
        totals.get("cacheReadCost"), sum(_ts_float(day.get("cacheReadCost"), 0) for day in daily)
    )
    cache_write_cost = _ts_float(
        totals.get("cacheWriteCost"), sum(_ts_float(day.get("cacheWriteCost"), 0) for day in daily)
    )

    def _safe_rate(cost, tokens):
        """Return a per-token rate while guarding against division by zero.

        Divide the supplied cost by the token count when tokens are present and
        otherwise return zero. Keep the derived-rate calculation readable inside
        the larger payload assembly routine.

        Called by:
            build_token_savings_payload().
        Side effects:
            None.

        Returns:
            float: Per-token rate for the supplied cost bucket.
        """
        return (cost / tokens) if tokens > 0 else 0.0

    rates = {
        "input": _safe_rate(input_cost, total_input),
        "output": _safe_rate(output_cost, total_output),
        "cacheRead": _safe_rate(cache_read_cost, total_cache_read),
        "cacheWrite": _safe_rate(cache_write_cost, total_cache_write),
    }
    fractions = {
        "input": (input_cost / total_cost) if total_cost > 0 else 0.0,
        "output": (output_cost / total_cost) if total_cost > 0 else 0.0,
        "cacheRead": (cache_read_cost / total_cost) if total_cost > 0 else 0.0,
        "cacheWrite": (cache_write_cost / total_cost) if total_cost > 0 else 0.0,
    }
    weighted_cost_per_token = (
        fractions["input"] * rates["input"]
        + fractions["output"] * rates["output"]
        + fractions["cacheRead"] * rates["cacheRead"]
        + fractions["cacheWrite"] * rates["cacheWrite"]
    )
    if weighted_cost_per_token <= 0 and total_cost > 0 and total_tokens > 0:
        weighted_cost_per_token = total_cost / total_tokens

    explicit_calls = None
    for key in ("apiCalls", "requestCount", "totalTurns", "turns"):
        value = totals.get(key)
        if isinstance(value, (int, float)) and value > 0:
            explicit_calls = int(value)
            break
    if explicit_calls is None:
        for key in ("apiCalls", "requestCount", "totalTurns", "turns"):
            summed = sum(_ts_int(day.get(key), 0) for day in daily)
            if summed > 0:
                explicit_calls = summed
                break
    if explicit_calls is None:
        avg_output_per_call = max(1, _ts_int(assumptions.get("avgOutputTokensPerCall"), 800))
        explicit_calls = max(1, int(round(total_output / avg_output_per_call))) if total_output > 0 else 0

    compound_saved_tokens = context_saved_per_call * explicit_calls

    input_side_cost = input_cost + cache_read_cost + cache_write_cost
    meaningful_efficiency = (meaningful_raw - meaningful_comp) / meaningful_raw if meaningful_raw > 0 else 0.0
    if meaningful_efficiency > 0 and input_side_cost > 0:
        without_rmemory_input = input_side_cost / (1.0 - meaningful_efficiency)
        compound_saved_cost = without_rmemory_input - input_side_cost
        without_rmemory_cost = output_cost + without_rmemory_input
    else:
        compound_saved_cost = (
            compound_saved_tokens * weighted_cost_per_token
            if (compound_saved_tokens > 0 and weighted_cost_per_token > 0)
            else 0.0
        )
        without_rmemory_cost = (total_cost + compound_saved_cost) if total_cost > 0 else None
    saving_pct = (
        ((compound_saved_cost / without_rmemory_cost) * 100.0)
        if without_rmemory_cost and without_rmemory_cost > 0
        else None
    )

    try:
        ocfg = json.loads(OPENCLAW_CONFIG.read_text())
    except Exception:
        ocfg = {}
    defaults = ocfg.get("agents", {}).get("defaults", {})
    main_model = defaults.get("model")
    if isinstance(main_model, dict):
        main_model = main_model.get("primary") or str(main_model)
    if not main_model:
        main_model = pricing.get("defaultModel", "gateway/blended")

    hb_cfg = defaults.get("heartbeat", {}) if isinstance(defaults.get("heartbeat", {}), dict) else {}
    hb_every = hb_cfg.get("every", "30m")
    hb_model = hb_cfg.get("model", pricing.get("defaultModel", "gateway/blended"))
    hb_enabled = hb_cfg.get("enabled", True)
    hb_minutes = _ts_parse_every_minutes(hb_every)
    active_hours = hb_cfg.get("activeHours", {})
    active_minutes = (
        _ts_minutes_between(active_hours.get("start", "00:00"), active_hours.get("end", "00:00"))
        if active_hours
        else 24 * 60
    )
    hb_calls_per_day = int(round(active_minutes / hb_minutes)) if (hb_enabled and hb_minutes and hb_minutes > 0) else 0
    hb_calls = max(0, hb_calls_per_day * days)

    cron_jobs = _ts_collect_cron_jobs(ocfg)
    components = []

    def _add_component(component_id, name, model, input_tokens, output_tokens, cost, source_text, estimated):
        """Append one normalized component entry to the payload list.

        Convert the supplied raw values into the rounded component shape exposed
        by the API response. Centralize that formatting so each component row is
        serialized consistently before the final payload is returned.

        Called by:
            build_token_savings_payload().
        Side effects:
            Mutates the enclosing `components` list.

        Returns:
            None: The helper appends a serialized component entry in place.
        """
        components.append(
            {
                "id": component_id,
                "component": name,
                "model": model,
                "inputTokens": int(max(0, round(_ts_float(input_tokens, 0)))),
                "outputTokens": int(max(0, round(_ts_float(output_tokens, 0)))),
                "cost": round(max(0.0, _ts_float(cost, 0.0)), 4),
                "source": source_text,
                "estimated": bool(estimated),
            }
        )

    rmem_effective = _rmem_effective_models()
    comp_stats = usage_stats.get("compression", {}) if isinstance(usage_stats.get("compression"), dict) else {}
    nar_stats = usage_stats.get("narrative", {}) if isinstance(usage_stats.get("narrative"), dict) else {}

    comp_model = rmem_effective.get("compression", "anthropic/claude-haiku-4-5")
    nar_model = rmem_effective.get("narrative", comp_model)
    _, comp_rates = _ts_lookup_rates(pricing, comp_model)
    _, nar_rates = _ts_lookup_rates(pricing, nar_model)

    comp_input = _ts_int(comp_stats.get("inputTokens"), 0)
    comp_output = _ts_int(comp_stats.get("outputTokens"), 0)
    nar_input = _ts_int(nar_stats.get("inputTokens"), 0)
    nar_output = _ts_int(nar_stats.get("outputTokens"), 0)

    comp_cost = _ts_component_cost(comp_rates, comp_input, comp_output)
    nar_cost = _ts_component_cost(nar_rates, nar_input, nar_output)

    hb_input = hb_calls * _ts_int(assumptions.get("heartbeatInputTokensPerCall"), 700)
    hb_output = hb_calls * _ts_int(assumptions.get("heartbeatOutputTokensPerCall"), 140)
    _, hb_rates = _ts_lookup_rates(pricing, hb_model)
    hb_cost = _ts_component_cost(hb_rates, hb_input, hb_output)
    _add_component(
        "heartbeat",
        "Heartbeat",
        hb_model,
        hb_input,
        hb_output,
        hb_cost,
        f"openclaw.json heartbeat.every={hb_every} (est.)",
        True,
    )

    cron_total_input = 0
    cron_total_output = 0
    cron_total_cost = 0.0
    for index, job in enumerate(cron_jobs):
        if job.get("enabled") is False:
            continue
        job_name = job.get("name") or job.get("id") or f"Job {index + 1}"
        job_model = job.get("model") or main_model
        calls = 0
        if job.get("every"):
            minutes = _ts_parse_every_minutes(job.get("every"))
            calls = int(round((days * 24 * 60) / minutes)) if minutes and minutes > 0 else 0
        elif job.get("schedule"):
            calls = _ts_estimate_calls_from_cron(str(job.get("schedule")), days)
        if calls <= 0:
            calls = days
        input_per_call = _ts_int(job.get("avgInputTokens"), _ts_int(assumptions.get("cronInputTokensPerCall"), 900))
        output_per_call = _ts_int(job.get("avgOutputTokens"), _ts_int(assumptions.get("cronOutputTokensPerCall"), 180))
        inp = max(0, calls * input_per_call)
        out = max(0, calls * output_per_call)
        _, job_rates = _ts_lookup_rates(pricing, job_model)
        cost = _ts_component_cost(job_rates, inp, out)
        cron_total_input += inp
        cron_total_output += out
        cron_total_cost += cost
        _add_component(
            f"cron-{index + 1}",
            f"Cron: {job_name}",
            job_model,
            inp,
            out,
            cost,
            f"openclaw cron schedule ({job.get('every') or job.get('schedule') or 'default'}) (est.)",
            True,
        )

    known_cost = comp_cost + nar_cost + hb_cost + cron_total_cost
    known_input = comp_input + nar_input + hb_input + cron_total_input
    known_output = comp_output + nar_output + hb_output + cron_total_output

    remaining_cost = max(0.0, total_cost - known_cost)
    subagent_share = _ts_float(assumptions.get("subagentShare"), 0.18)
    subagent_share = min(0.95, max(0.0, subagent_share))
    subagent_cost = remaining_cost * subagent_share
    main_cost = max(0.0, remaining_cost - subagent_cost)

    remaining_input = max(0, total_input - known_input)
    remaining_output = max(0, total_output - known_output)
    subagent_input = int(round(remaining_input * subagent_share))
    subagent_output = int(round(remaining_output * subagent_share))
    main_input = max(0, remaining_input - subagent_input)
    main_output = max(0, remaining_output - subagent_output)

    _add_component(
        "subagents",
        "Sub-Agents Runtime",
        "subagents/default",
        subagent_input,
        subagent_output,
        subagent_cost,
        "Residual share after known components (est.)",
        True,
    )
    _add_component(
        "main-session",
        "Main Session",
        main_model,
        main_input,
        main_output,
        main_cost,
        "Gateway total minus system components",
        True,
    )

    components.sort(key=lambda component: component.get("cost", 0), reverse=True)

    component_cost_lookup = {component["id"]: component["cost"] for component in components}
    daily_breakdown = []
    for entry in daily:
        day_cost = _ts_float(entry.get("totalCost"), 0.0)
        ratio = (day_cost / total_cost) if total_cost > 0 else 0.0
        component_costs = {
            component_id: round(value * ratio, 4) for component_id, value in component_cost_lookup.items()
        }
        drift = day_cost - sum(component_costs.values())
        if "main-session" in component_costs:
            component_costs["main-session"] = round(component_costs["main-session"] + drift, 4)
        daily_breakdown.append(
            {
                "date": entry.get("date"),
                "totalCost": round(day_cost, 4),
                "components": component_costs,
            }
        )

    context_efficiency = ((context_raw - context_comp) / context_raw) if context_raw > 0 else None
    archived_efficiency = ((archived_raw - archived_comp) / archived_raw) if archived_raw > 0 else None
    lifetime_raw = meaningful_raw if meaningful_raw > 0 else all_raw
    lifetime_comp = meaningful_comp if meaningful_raw > 0 else all_comp
    lifetime_efficiency = ((lifetime_raw - lifetime_comp) / lifetime_raw) if lifetime_raw > 0 else None
    return {
        "ok": gateway_error is None and total_cost > 0,
        "source": source,
        "days": days,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "trackingStartDate": "2026-02-25",
        "sources": {
            "usageTracker": tracker_meta.get("path"),
            "trackerError": tracker_error,
            "trackerEntries": _ts_int(tracker_meta.get("keptEntries"), 0),
            "gatewayUsageCost": "openclaw gateway usage-cost --days N --json",
            "rMemoryUsageStats": "~/.openclaw/workspace/r-memory/usage-stats.json",
            "rMemoryHistory": "~/.openclaw/workspace/r-memory/history-*.json",
            "pricing": "dashboard/config.json:pricing",
            "gatewayError": gateway_error if source == "gateway" else None,
            "gatewayCmd": gateway_meta.get("cmd") if isinstance(gateway_meta, dict) else None,
        },
        "totals": {
            "actualApiCost": round(total_cost, 4) if total_cost > 0 else None,
            "withoutRMemoryCostEstimate": round(without_rmemory_cost, 4) if without_rmemory_cost is not None else None,
            "rMemorySavingsEstimate": round(compound_saved_cost, 4) if compound_saved_cost > 0 else None,
            "savingPctEstimate": round(saving_pct, 2) if saving_pct is not None else None,
        },
        "gatewayTotals": {
            "inputTokens": total_input,
            "outputTokens": total_output,
            "cacheReadTokens": total_cache_read,
            "cacheWriteTokens": total_cache_write,
            "totalTokens": total_tokens,
            "inputCost": round(input_cost, 4),
            "outputCost": round(output_cost, 4),
            "cacheReadCost": round(cache_read_cost, 4),
            "cacheWriteCost": round(cache_write_cost, 4),
            "fractions": fractions,
            "ratesPerToken": rates,
            "weightedCostPerToken": weighted_cost_per_token,
        },
        "compoundSavings": {
            "estimated": True,
            "method": "sum(tokensRaw - tokensCompressed in current context blocks) × estimated API calls",
            "contextBlocks": len(cur_blocks),
            "tokensSavedPerCall": context_saved_per_call,
            "estimatedApiCalls": explicit_calls,
            "compoundSavedTokens": compound_saved_tokens,
            "weightedCostPerToken": weighted_cost_per_token,
            "costSavedEstimate": round(compound_saved_cost, 4),
        },
        "compressionStats": {
            "blocksInContext": len(cur_blocks),
            "blocksCompressed": len(all_blocks),
            "blocksArchived": archived_blocks,
            "contextRawTokens": context_raw,
            "contextCompressedTokens": context_comp,
            "archivedRawTokens": archived_raw,
            "archivedCompressedTokens": archived_comp,
            "contextEfficiency": round(context_efficiency * 100, 2) if context_efficiency is not None else None,
            "archivedEfficiency": round(archived_efficiency * 100, 2) if archived_efficiency is not None else None,
            "lifetimeRawTokens": lifetime_raw,
            "lifetimeCompressedTokens": lifetime_comp,
            "lifetimeEfficiency": round(lifetime_efficiency * 100, 2) if lifetime_efficiency is not None else None,
            "compressionCalls": _ts_int(comp_stats.get("calls"), 0),
            "narrativeCalls": _ts_int(nar_stats.get("calls"), 0),
            "compressionInputTokens": comp_input,
            "compressionOutputTokens": comp_output,
            "narrativeInputTokens": nar_input,
            "narrativeOutputTokens": nar_output,
        },
        "componentBreakdown": components,
        "dailyCostBreakdown": daily_breakdown,
        "pricingReference": pricing,
    }
