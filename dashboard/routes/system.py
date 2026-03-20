"""
System routes - Agents, Shield, Logician, System Info.
"""

import json
import os
import subprocess
import time
from pathlib import Path
from flask import jsonify, request

def register_system_routes(app):
    """Register all system-related routes."""

    # -------------------------------------------------------------------------
    # Agents API
    # -------------------------------------------------------------------------

    @app.route("/api/agents/list")
    def api_agents_list():
        """List available agents."""
        from shared import WORKSPACE
        agents_dir = WORKSPACE / "agents"
        agents = []
        if agents_dir.exists():
            for entry in agents_dir.iterdir():
                if entry.is_dir():
                    agents.append({"id": entry.name, "path": str(entry)})
        return jsonify(agents)

    @app.route("/api/agents/<agent_id>/status")
    def api_agents_status(agent_id):
        """Get agent status."""
        return jsonify({"id": agent_id, "status": "unknown", "running": False})

    # -------------------------------------------------------------------------
    # Gateway Status & Health
    # -------------------------------------------------------------------------

    @app.route("/api/gateway/status")
    def api_gateway_status():
        """Get gateway status."""
        return jsonify({"connected": False, "version": "unknown"})

    @app.route("/api/gateway/health")
    def api_gateway_health():
        """Get gateway health."""
        return jsonify({"healthy": False, "uptime": 0})

    @app.route("/api/gateway/stats")
    def api_gateway_stats():
        """Get gateway stats."""
        return jsonify({"requests": 0, "errors": 0})

    @app.route("/api/gateway/restart", methods=["POST"])
    def api_gateway_restart():
        """Restart gateway."""
        from shared import restart_openclaw_gateway
        restart_openclaw_gateway()
        return jsonify({"success": True})

    # -------------------------------------------------------------------------
    # Shield Status
    # -------------------------------------------------------------------------

    @app.route("/api/shield/status")
    def api_shield_status():
        """Get shield status."""
        from shared import WORKSPACE
        shield_dir = WORKSPACE / "shield"
        status = {
            "enabled": shield_dir.exists(),
            "file_guard": False,
            "coherence_gate": False,
        }
        if shield_dir.exists():
            for f in shield_dir.iterdir():
                if f.suffix in (".py", ".js"):
                    status["enabled"] = True
        return jsonify(status)

    @app.route("/api/shield/config")
    def api_shield_config():
        """Get shield config."""
        return jsonify({"enabled": False})

    @app.route("/api/shield/logs")
    def api_shield_logs():
        """Get shield logs."""
        from shared import WORKSPACE
        log_file = WORKSPACE / "shield" / "logs" / "shield.log"
        if log_file.exists():
            try:
                content = log_file.read_text()
                return jsonify({"logs": content[-5000:]})
            except Exception:
                pass
        return jsonify({"logs": ""})

    # -------------------------------------------------------------------------
    # Logician Status
    # -------------------------------------------------------------------------

    @app.route("/api/logician/status")
    def api_logician_status():
        """Live-check Logician mangle server."""
        from shared import IS_WINDOWS, IS_MAC, IS_LINUX
        import subprocess
        if IS_WINDOWS:
            mangle_sock = os.path.expanduser("~/mangle.sock")
        else:
            mangle_sock = "/tmp/mangle.sock"
        sock_exists = os.path.exists(mangle_sock)
        process_running = False
        try:
            if IS_WINDOWS:
                result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq mangle-server.exe"], capture_output=True, text=True, timeout=5)
                process_running = result.returncode == 0
            else:
                result = subprocess.run(["pgrep", "-f", "mangle-server"], capture_output=True, text=True, timeout=5)
                process_running = result.returncode == 0
        except Exception:
            pass
        return jsonify({
            "running": sock_exists or process_running,
            "socket": mangle_sock,
            "process_running": process_running,
        })

    @app.route("/api/logician/start", methods=["POST"])
    def api_logician_start():
        """Start Logician."""
        return jsonify({"success": False, "error": "Not implemented"}), 501

    @app.route("/api/logician/stop", methods=["POST"])
    def api_logician_stop():
        """Stop Logician."""
        return jsonify({"success": False, "error": "Not implemented"}), 501

    @app.route("/api/logician/query", methods=["POST"])
    def api_logician_query():
        """Query Logician."""
        return jsonify({"success": False, "error": "Not implemented"}), 501

    # -------------------------------------------------------------------------
    # System Info
    # -------------------------------------------------------------------------

    @app.route("/api/system/info")
    def api_system_info():
        """Get system info."""
        import platform
        return jsonify({
            "platform": platform.system(),
            "platform_version": platform.version(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
        })

    @app.route("/api/system/openclaw-status")
    def api_openclaw_status():
        """Get OpenClaw status."""
        return jsonify({"installed": False, "version": None})

    @app.route("/api/system/disk-usage")
    def api_disk_usage():
        """Get disk usage."""
        import shutil
        usage = shutil.disk_usage("/")
        return jsonify({
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
        })

    @app.route("/api/system/uptime")
    def api_system_uptime():
        """Get system uptime."""
        return jsonify({"uptime": time.time() - __import__("os").getpid()})

    # -------------------------------------------------------------------------
    # Config
    # -------------------------------------------------------------------------

    @app.route("/api/config", methods=["GET"])
    def api_config_get():
        """Get config."""
        from shared import Config
        cfg = Config()
        return jsonify(cfg._cfg)

    @app.route("/api/config", methods=["POST"])
    def api_config_set():
        """Set config."""
        return jsonify({"success": False, "error": "Not implemented"}), 501

    @app.route("/api/config/save", methods=["POST"])
    def api_config_save():
        """Save config."""
        return jsonify({"success": False, "error": "Not implemented"}), 501

    # -------------------------------------------------------------------------
    # Models
    # -------------------------------------------------------------------------

    @app.route("/api/models", methods=["GET"])
    def api_models_list():
        """List available models."""
        return jsonify([])

    @app.route("/api/models/default", methods=["GET"])
    def api_models_default():
        """Get default model."""
        return jsonify({"model": "anthropic/claude-haiku-4-5"})

    return app
