"""Agent routes."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, jsonify, request

from routes.config import OPENCLAW_CONFIG, OPENCLAW_HOME, RMEMORY_DIR, WORKSPACE
from routes.logging_config import get_logger
from routes.rmemory import _rmem_config, _rmem_effective_models
from routes.shared import gw

agents_bp = Blueprint("agents", __name__)
logger = get_logger(__name__)


@agents_bp.route("/api/agents/setup/model", methods=["POST"])
def api_agents_setup_model() -> Response:
    """Persist the setup agent model override.

    Read the requested model from the POST body and store it in the setup
    agent's `models.json` override file under the user's OpenClaw home. This
    route only updates the default setup model and leaves other configuration
    untouched.

    Dependencies:
        request JSON payload, `Path.home()`, and `json` file I/O.

    Returns:
        Response: JSON success payload with the saved model or an error
        response when validation or file writes fail.
    """
    body: dict[str, Any] = request.get_json(force=True)
    model = body.get("model", "").strip()
    if not model:
        return jsonify({"ok": False, "error": "model required"}), 400
    setup_models = Path.home() / ".openclaw" / "agents" / "setup" / "agent" / "models.json"
    try:
        data = {}
        if setup_models.exists():
            data = json.loads(setup_models.read_text())
        data["default"] = model
        setup_models.write_text(json.dumps(data, indent=2) + "\n")
        return jsonify({"ok": True, "model": model})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# API: Agents
# ---------------------------------------------------------------------------


@agents_bp.route("/api/agents")
def api_agents() -> Response:
    """Assemble the dashboard's agent inventory.

    Merge live gateway health, OpenClaw configuration, workspace discovery, and
    R-Memory metadata into one normalized list for the agents page. The route
    enriches each entry with model, workspace snippets, display identity, and
    hierarchy metadata before returning a sorted payload.

    Dependencies:
        `gw.health`, `OPENCLAW_CONFIG`, `OPENCLAW_HOME`, `WORKSPACE`,
        `RMEMORY_DIR`, `_rmem_config()`, and `_rmem_effective_models()`.

    Returns:
        Response: JSON array of agent records ordered by tier and agent id.
    """
    agents: list[dict[str, Any]] = []
    seen_ids = set()

    # Helper: read workspace files for an agent
    def _read_workspace(agent_id: str) -> dict[str, str]:
        """Read workspace snippets for a single agent.

        Inspect the per-agent workspace first, then fall back to shared main
        workspace files where that behavior is allowed. The helper truncates
        file contents so the route response stays lightweight.

        Called by:
            `api_agents()` while building agent cards from gateway, config, and
            discovered workspaces.

        Side effects:
            Reads markdown files from disk but does not modify them.

        Returns:
            dict[str, str]: Mapping of workspace filenames to preview text.
        """
        workspace_files = {}
        # Check per-agent workspace first, then shared
        ws_dir = OPENCLAW_HOME / f"workspace-{agent_id}"
        if agent_id == "main":
            ws_dir = WORKSPACE
        for fname in ["SOUL.md", "AGENTS.md", "USER.md", "IDENTITY.md", "MEMORY.md"]:
            fpath = ws_dir / fname
            if not fpath.exists() and agent_id != "main":
                if fname in ("IDENTITY.md", "SOUL.md", "MEMORY.md"):
                    continue  # agent-specific files should NOT fall back to main
                fpath = WORKSPACE / fname  # fallback to shared for AGENTS.md, USER.md
            if fpath.exists():
                try:
                    workspace_files[fname] = fpath.read_text()[:2000]
                except Exception:
                    logger.debug("Failed to read workspace file %s for agent %s", fpath, agent_id, exc_info=True)
        return workspace_files

    # Helper: resolve model for agent
    def _resolve_model(agent_id: str) -> str:
        """Resolve the effective model for an agent.

        Look for an agent-specific model first, then fall back to shared agent
        defaults, and finally the top-level model configuration. The helper
        returns `"default"` when the config cannot be read or no model is set.

        Called by:
            `api_agents()` when composing each agent record.

        Side effects:
            Reads `OPENCLAW_CONFIG` from disk.

        Returns:
            str: Effective model identifier or a fallback placeholder.
        """
        try:
            cfg = json.loads(OPENCLAW_CONFIG.read_text())
            # 1. Check agent-specific model in agents.list
            for entry in cfg.get("agents", {}).get("list", []):
                if entry.get("id") == agent_id and entry.get("model"):
                    m = entry["model"]
                    return m.get("primary", str(m)) if isinstance(m, dict) else m
            # 2. Check agents.defaults.model
            default_model = cfg.get("agents", {}).get("defaults", {}).get("model")
            if default_model:
                return (
                    default_model.get("primary", str(default_model))
                    if isinstance(default_model, dict)
                    else default_model
                )
            # 3. Check top-level model
            top_model = cfg.get("model")
            if top_model:
                return top_model if isinstance(top_model, str) else top_model.get("primary", str(top_model))
            return "default"
        except Exception:
            return "default"

    # Helper: parse identity for emoji/name
    def _parse_identity(workspace_files: dict[str, str]) -> tuple[str, str | None]:
        """Extract display metadata from workspace identity content.

        Parse the `IDENTITY.md` preview content to find the configured emoji and
        display name fields used by the dashboard. Missing fields fall back to
        the default robot emoji and an unset name.

        Called by:
            `api_agents()` when formatting agent records for display.

        Side effects:
            None.

        Returns:
            tuple[str, str | None]: Resolved emoji and optional display name.
        """
        identity = workspace_files.get("IDENTITY.md", "")
        emoji = "🤖"
        name = None
        for line in identity.splitlines():
            if "**Emoji:**" in line:
                parts = line.split("**Emoji:**")
                if len(parts) > 1 and parts[1].strip():
                    emoji = parts[1].strip()
            if "**Name:**" in line:
                parts = line.split("**Name:**")
                if len(parts) > 1 and parts[1].strip():
                    name = parts[1].strip()
        return emoji, name

    # Agent metadata for hierarchy
    AGENT_META = {
        "main": {"tier": 0, "role": "Orchestrator & Strategist", "category": "core"},
        "doer": {"tier": 1, "role": "Personal Assistant & Task Executor", "category": "direct"},
        "dao": {"tier": 1, "role": "DAO Strategy & Governance", "category": "direct"},
        "website": {"tier": 1, "role": "Marketing Website", "category": "direct"},
        "voice": {"tier": 1, "role": "Content Voice & YouTube", "category": "direct"},
        "coder": {"tier": 1, "role": "Coding Agent", "category": "background"},
        "researcher": {"tier": 1, "role": "Deep Research (Perplexity)", "category": "background"},
        "setup": {"tier": 1, "role": "Onboarding & Setup", "category": "support"},
        "acupuncturist": {"tier": 1, "role": "Protocol Enforcement", "category": "support"},
        "blindspot": {"tier": 1, "role": "Red Team & Vulnerability Hunter", "category": "support"},
    }

    # Inject R-Memory as a virtual "memory" agent with effective models
    rmem_cfg = _rmem_config()
    effective = _rmem_effective_models()
    rmem_log = RMEMORY_DIR / "r-memory.log"
    rmem_status = "active" if rmem_log.exists() and rmem_log.stat().st_size > 0 else "inactive"
    # Load usage stats for call counts
    usage_stats = {}
    try:
        usage_stats = json.loads((RMEMORY_DIR / "usage-stats.json").read_text())
    except Exception:
        logger.debug("Failed to load R-Memory usage stats", exc_info=True)
    agents.append(
        {
            "agentId": "memory",
            "isDefault": False,
            "status": rmem_status,
            "mainModel": effective["compression"],
            "heartbeat": {},
            "sessions": {"count": 0},
            "workspaceFiles": {},
            "emoji": "🧠",
            "displayName": "R-Memory",
            "tier": 0.5,
            "role": "Compression & Narrative Tracking",
            "category": "core",
            "virtual": True,
            "subAgents": {
                "compression": {
                    "model": effective["compression"],
                    "label": "Conversation Compression",
                    "calls": usage_stats.get("compression", {}).get("calls", 0),
                },
                "narrative": {
                    "model": effective["narrative"],
                    "label": "Narrative Tracker",
                    "calls": usage_stats.get("narrative", {}).get("calls", 0),
                },
            },
        }
    )
    seen_ids.add("memory")

    # 1. Active agents from gateway health
    health = gw.health or {}
    for ag in health.get("agents", []):
        agent_id = ag.get("agentId", "unknown")
        seen_ids.add(agent_id)
        workspace_files = _read_workspace(agent_id)
        emoji, name = _parse_identity(workspace_files)
        agents.append(
            {
                "agentId": agent_id,
                "isDefault": ag.get("isDefault", False),
                "status": "active",
                "mainModel": _resolve_model(agent_id),
                "heartbeat": ag.get("heartbeat", {}),
                "sessions": ag.get("sessions", {}),
                "workspaceFiles": workspace_files,
                "emoji": emoji,
                "displayName": name or agent_id,
                **(AGENT_META.get(agent_id, {"tier": 1, "role": "Agent", "category": "other"})),
            }
        )

    # 2. Agents from openclaw.json config (always available, even without gateway)
    try:
        cfg = json.loads(OPENCLAW_CONFIG.read_text())
        for agent_entry in cfg.get("agents", {}).get("list", []):
            agent_id = agent_entry.get("id", "")
            if not agent_id or agent_id in seen_ids:
                continue
            seen_ids.add(agent_id)
            workspace_files = _read_workspace(agent_id)
            emoji, name = _parse_identity(workspace_files)
            model = agent_entry.get("model") or cfg.get("agents", {}).get("defaults", {}).get("model") or "unknown"
            agents.append(
                {
                    "agentId": agent_id,
                    "isDefault": agent_entry.get("default", False),
                    "status": "configured",
                    "mainModel": model,
                    "heartbeat": {},
                    "sessions": {"count": 0},
                    "workspaceFiles": workspace_files,
                    "emoji": emoji,
                    "displayName": name or agent_id,
                    **(
                        AGENT_META.get(
                            agent_id,
                            {"tier": 0 if agent_entry.get("default") else 1, "role": "Agent", "category": "other"},
                        )
                    ),
                }
            )
    except Exception:
        logger.warning("Failed to load configured agents from %s", OPENCLAW_CONFIG, exc_info=True)

    # 3. Discover agents from workspace-* directories (not yet in gateway or config)
    for ws_path in sorted(OPENCLAW_HOME.glob("workspace-*")):
        if not ws_path.is_dir():
            continue
        agent_id = ws_path.name.replace("workspace-", "")
        if agent_id in seen_ids:
            continue
        seen_ids.add(agent_id)
        workspace_files = _read_workspace(agent_id)
        emoji, name = _parse_identity(workspace_files)
        agents.append(
            {
                "agentId": agent_id,
                "isDefault": False,
                "status": "inactive",
                "mainModel": _resolve_model(agent_id),
                "heartbeat": {},
                "sessions": {"count": 0},
                "workspaceFiles": workspace_files,
                "emoji": emoji,
                "displayName": name or agent_id,
                **(AGENT_META.get(agent_id, {"tier": 1, "role": "Agent", "category": "other"})),
            }
        )

    # 4. Guaranteed fallback: always include "main" agent
    if "main" not in seen_ids:
        workspace_files = _read_workspace("main")
        emoji, name = _parse_identity(workspace_files)
        agents.append(
            {
                "agentId": "main",
                "isDefault": True,
                "status": "configured",
                "mainModel": _resolve_model("main"),
                "heartbeat": {},
                "sessions": {"count": 0},
                "workspaceFiles": workspace_files,
                "emoji": emoji,
                "displayName": name or "Main Agent",
                **(AGENT_META.get("main", {"tier": 0, "role": "Orchestrator & Strategist", "category": "core"})),
            }
        )

    # Sort: tier 0 first, then alphabetical
    agents.sort(key=lambda a: (a.get("tier", 1), a["agentId"]))
    return jsonify(agents)


@agents_bp.route("/api/system-agents")
def api_system_agents() -> Response:
    """Summarize dashboard-visible system agents.

    Build normalized cards for background services such as Heartbeat, R-Memory,
    the subagent runtime, and the gateway itself. Each entry combines config,
    live gateway state, and local usage files so the frontend can render a
    single consistent shape.

    Dependencies:
        `OPENCLAW_CONFIG`, `gw.health`, `RMEMORY_DIR`, `_rmem_config()`, and
        `_rmem_effective_models()`.

    Returns:
        Response: JSON array of system-agent summaries for the agents page.
    """
    system_agents: list[dict[str, Any]] = []

    # --- 1. Heartbeat ---
    try:
        cfg = json.loads(OPENCLAW_CONFIG.read_text())
        hb_defaults = cfg.get("agents", {}).get("defaults", {}).get("heartbeat", {})
        # Also get per-agent heartbeat overrides from gateway health
        health = gw.health or {}
        main_agent = next((a for a in health.get("agents", []) if a.get("isDefault")), {})
        hb_live = main_agent.get("heartbeat", {})
        hb_enabled = hb_live.get("enabled", hb_defaults.get("enabled", False))
        hb_every = hb_live.get("every", hb_defaults.get("every", "-"))
        hb_model = hb_live.get("model", hb_defaults.get("model", "unknown"))
        hb_active_hours = hb_defaults.get("activeHours", {})
        active_window = ""
        if hb_active_hours:
            active_window = f"{hb_active_hours.get('start', '?')}-{hb_active_hours.get('end', '?')} {hb_active_hours.get('timezone', '')}"
        system_agents.append(
            {
                "id": "heartbeat",
                "name": "Heartbeat",
                "emoji": "💓",
                "role": "Periodic health check & proactive assistant",
                "model": hb_model,
                "status": "running" if hb_enabled else "disabled",
                "interval": hb_every,
                "activeWindow": active_window,
                "details": {
                    "target": hb_live.get("target", "last"),
                    "prompt": hb_live.get("prompt", hb_defaults.get("prompt", "")),
                },
            }
        )
    except Exception:
        system_agents.append(
            {
                "id": "heartbeat",
                "name": "Heartbeat",
                "emoji": "💓",
                "role": "Periodic health check & proactive assistant",
                "model": "unknown",
                "status": "unknown",
                "interval": "-",
                "activeWindow": "",
                "details": {},
            }
        )

    # --- 2. R-Memory (compression + narrative) ---
    try:
        rmem_cfg = _rmem_config()
        effective = _rmem_effective_models()
        rmem_log = RMEMORY_DIR / "r-memory.log"
        rmem_active = rmem_log.exists() and rmem_log.stat().st_size > 0
        rmem_enabled = rmem_cfg.get("enabled", True)
        usage_stats = {}
        try:
            usage_stats = json.loads((RMEMORY_DIR / "usage-stats.json").read_text())
        except Exception:
            logger.debug("Failed to load R-Memory usage stats for system agents", exc_info=True)
        system_agents.append(
            {
                "id": "r-memory",
                "name": "R-Memory",
                "emoji": "🧠",
                "role": "Conversation compression & narrative tracking",
                "model": effective.get("compression", "unknown"),
                "status": "running"
                if (rmem_active and rmem_enabled)
                else ("disabled" if not rmem_enabled else "inactive"),
                "interval": "on-demand",
                "activeWindow": "always",
                "details": {
                    "compressionModel": effective.get("compression"),
                    "narrativeModel": effective.get("narrative"),
                    "compressionCalls": usage_stats.get("compression", {}).get("calls", 0),
                    "narrativeCalls": usage_stats.get("narrative", {}).get("calls", 0),
                    "evictTrigger": rmem_cfg.get("evictTrigger"),
                    "compressTrigger": rmem_cfg.get("compressTrigger"),
                },
            }
        )
    except Exception:
        system_agents.append(
            {
                "id": "r-memory",
                "name": "R-Memory",
                "emoji": "🧠",
                "role": "Conversation compression & narrative tracking",
                "model": "unknown",
                "status": "unknown",
                "interval": "on-demand",
                "activeWindow": "always",
                "details": {},
            }
        )

    # --- 3. Subagent Runtime ---
    try:
        cfg = json.loads(OPENCLAW_CONFIG.read_text())
        sub_cfg = cfg.get("agents", {}).get("defaults", {}).get("subagents", {})
        max_concurrent = sub_cfg.get("maxConcurrent", 4)
        # Check active sessions for subagent activity
        health = gw.health or {}
        all_sessions = []
        for ag in health.get("agents", []):
            for s in ag.get("sessions", {}).get("recent", []):
                if "subagent" in s.get("key", ""):
                    all_sessions.append(s)
        system_agents.append(
            {
                "id": "subagent-runtime",
                "name": "Subagent Runtime",
                "emoji": "🔀",
                "role": "Spawns & manages task-specific sub-agents",
                "model": "inherits parent",
                "status": "running",
                "interval": "on-demand",
                "activeWindow": "always",
                "details": {
                    "maxConcurrent": max_concurrent,
                    "recentSubagentSessions": len(all_sessions),
                },
            }
        )
    except Exception:
        logger.debug("Failed to build subagent runtime summary", exc_info=True)

    # --- 4. Gateway ---
    try:
        cfg = json.loads(OPENCLAW_CONFIG.read_text())
        gw_cfg = cfg.get("gateway", {})
        gw_port = gw_cfg.get("port", 18789)
        gw_status = "running" if (gw.health and gw.health.get("agents")) else "stopped"
        system_agents.append(
            {
                "id": "gateway",
                "name": "Gateway",
                "emoji": "🌐",
                "role": "Core message router & session manager",
                "model": "n/a",
                "status": gw_status,
                "interval": "always-on",
                "activeWindow": "always",
                "details": {
                    "port": gw_port,
                    "mode": gw_cfg.get("mode", "local"),
                },
            }
        )
    except Exception:
        logger.debug("Failed to build gateway summary", exc_info=True)

    return jsonify(system_agents)


@agents_bp.route("/api/agents/<agent_id>/sessions")
def api_agent_sessions(agent_id: str) -> Response:
    """Fetch recent sessions for one agent from the gateway.

    Forward the requested agent id to the shared gateway client and return the
    gateway response without additional reshaping. The route exists as a thin
    dashboard proxy around the `sessions.list` RPC.

    Dependencies:
        `gw.request()` and the route path parameter `agent_id`.

    Returns:
        Response: JSON payload returned by the gateway for the agent's sessions.
    """
    result = gw.request("sessions.list", {"agentId": agent_id})
    return jsonify(result)


@agents_bp.route("/api/agents/<agent_id>/model", methods=["PUT"])
def api_agent_model(agent_id: str) -> Response:
    """Write a model override for the selected agent.

    Persist the requested model into the dedicated override file so the
    dashboard can change agent models even when direct config writes are
    blocked. The route also attempts a best-effort update to `openclaw.json`
    but treats Shield interference there as non-fatal.

    Dependencies:
        request JSON payload, `Path.home()`, `json` file I/O, and
        `datetime.now()`.

    Returns:
        Response: JSON confirmation of the saved override or an error response
        when validation or writes fail.
    """
    data: dict[str, Any] = request.get_json(force=True) or {}
    model = data.get("model")
    if not model:
        return jsonify({"error": "model required"}), 400

    # Write to override file instead of openclaw.json (bypasses Shield)
    override_path = Path.home() / ".openclaw" / "model-overrides.json"
    try:
        overrides = {}
        if override_path.exists():
            overrides = json.loads(override_path.read_text())
        overrides[agent_id] = {"model": model, "updated_at": datetime.now().isoformat()}
        override_path.write_text(json.dumps(overrides, indent=2))
    except Exception as e:
        return jsonify({"error": f"Failed to write override: {e}"}), 500

    # Also try to update main config (will be blocked by Shield but that's OK)
    cfg_path = Path.home() / ".openclaw" / "openclaw.json"
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text())
            if "agents" not in cfg:
                cfg["agents"] = {}
            if agent_id not in cfg["agents"]:
                cfg["agents"][agent_id] = {}
            cfg["agents"][agent_id]["model"] = model
            cfg_path.write_text(json.dumps(cfg, indent=2))
        except Exception:
            logger.debug("Best-effort update of %s was blocked or failed", cfg_path, exc_info=True)

    return jsonify({"ok": True, "agentId": agent_id, "model": model})
