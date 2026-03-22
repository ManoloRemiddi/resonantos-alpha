"""
System routes - Agents, Shield, Logician, System Info.
"""

import json
import os
import platform
import subprocess
import shutil
import time
import uuid
from pathlib import Path
from flask import jsonify, request

def register_system_routes(app):
    """Register all system-related routes."""

    def _extract_text_from_gateway_message(message):
        if isinstance(message, str):
            return message
        if not isinstance(message, dict):
            return ""
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
            return "\n".join([p for p in parts if p])
        if isinstance(message.get("text"), str):
            return message.get("text")
        return ""

    def _get_openclaw_version():
        """Get OpenClaw gateway version via HTTP probe."""
        try:
            import urllib.request
            from shared import OPENCLAW_CONFIG
            cfg_path = OPENCLAW_CONFIG
            gateway_url = "http://127.0.0.1:18789"
            if cfg_path.exists():
                cfg = json.loads(cfg_path.read_text())
                ws_url = cfg.get("gateway", {}).get("wsUrl", "")
                if ws_url:
                    gateway_url = ws_url.replace("ws://", "http://").replace("wss://", "https://")
            req = urllib.request.Request(gateway_url, headers={"User-Agent": "ResonantOS-Dashboard/1.0"}, method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    try:
                        body = json.loads(resp.read().decode())
                        return body.get("version") or body.get("gateway", {}).get("version") or "ok"
                    except Exception:
                        return "ok"
        except Exception:
            pass
        return None

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

    @app.route("/api/system-agents")
    def api_system_agents():
        """Return system agent statuses (heartbeat, orchestrator, etc.)."""
        return jsonify([
            {"id": "heartbeat", "status": "running", "model": "n/a"},
            {"id": "orchestrator", "status": "running", "model": "n/a"},
        ])

    @app.route("/api/agents/<agent_id>/status")
    def api_agents_status(agent_id):
        """Get agent status."""
        from shared import WORKSPACE
        agent_dir = WORKSPACE / "agents" / agent_id
        if not agent_dir.exists():
            return jsonify({"error": "Agent not found"}), 404
        return jsonify({"id": agent_id, "status": "unknown", "running": False})

    # -------------------------------------------------------------------------
    # Gateway Status & Health
    # -------------------------------------------------------------------------

    @app.route("/api/gateway/status")
    def api_gateway_status():
        """Get gateway status."""
        version = _get_openclaw_version()
        return jsonify({
            "connected": version is not None,
            "version": version
        })

    @app.route("/api/gateway/health")
    def api_gateway_health():
        """Get gateway health."""
        version = _get_openclaw_version()
        return jsonify({
            "healthy": version is not None,
            "uptime": 0
        })

    @app.route("/api/gateway/stats")
    def api_gateway_stats():
        """Get gateway stats."""
        return jsonify({"requests": 0, "errors": 0})

    @app.route("/api/gateway/restart", methods=["POST"])
    def api_gateway_restart():
        """Restart gateway."""
        from shared import restart_openclaw_gateway
        try:
            restart_openclaw_gateway()
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

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
        from shared import WORKSPACE
        config_file = WORKSPACE / "shield" / "config.json"
        if config_file.exists():
            try:
                return jsonify(json.loads(config_file.read_text()))
            except Exception:
                pass
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

    @app.route("/api/shield/file-guard/status")
    def api_shield_file_guard_status():
        """Get file guard status."""
        from shared import WORKSPACE
        status_file = WORKSPACE / "shield" / "file_guard_status.json"
        if status_file.exists():
            try:
                return jsonify(json.loads(status_file.read_text()))
            except Exception:
                pass
        return jsonify({"locked": False})

    @app.route("/api/shield/file-guard/lock", methods=["POST"])
    def api_shield_file_guard_lock():
        """Lock files (requires sudo on Unix)."""
        return jsonify({"success": False, "error": "Not implemented"}), 501

    @app.route("/api/shield/file-guard/unlock", methods=["POST"])
    def api_shield_file_guard_unlock():
        """Unlock files."""
        return jsonify({"success": False, "error": "Not implemented"}), 501

    # -------------------------------------------------------------------------
    # Logician Status
    # -------------------------------------------------------------------------

    @app.route("/api/logician/status")
    def api_logician_status():
        """Live-check Logician mangle server."""
        from shared import IS_WINDOWS, IS_MAC, IS_LINUX
        if IS_WINDOWS:
            mangle_sock = os.path.expanduser("~/mangle.sock")
        else:
            mangle_sock = "/tmp/mangle.sock"
        sock_exists = os.path.exists(mangle_sock)
        process_running = False
        try:
            if IS_WINDOWS:
                result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq mangle-server.exe"], capture_output=True, text=True, timeout=5)
                process_running = "mangle-server" in result.stdout
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
        from shared import IS_MAC, IS_LINUX
        try:
            if IS_MAC or IS_LINUX:
                subprocess.Popen(["logician_ctl.sh", "start"], cwd=str(Path.home() / "resonantos-alpha" / "logician" / "scripts"))
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/logician/stop", methods=["POST"])
    def api_logician_stop():
        """Stop Logician."""
        try:
            subprocess.run(["logician_ctl.sh", "stop"], capture_output=True, timeout=5)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/logician/query", methods=["POST"])
    def api_logician_query():
        """Query Logician."""
        return jsonify({"success": False, "error": "Not implemented"}), 501

    @app.route("/api/logician/rules")
    def api_logician_rules():
        """Get Logician rules."""
        from shared import WORKSPACE
        rules_dir = WORKSPACE / "logician" / "rules"
        if not rules_dir.exists():
            return jsonify({"rules": []})
        rules = []
        for f in rules_dir.glob("*.json"):
            try:
                rules.append(json.loads(f.read_text()))
            except Exception:
                pass
        return jsonify({"rules": rules})

    # -------------------------------------------------------------------------
    # System Info
    # -------------------------------------------------------------------------

    @app.route("/api/system/info")
    def api_system_info():
        """Get system info."""
        return jsonify({
            "platform": platform.system(),
            "platform_version": platform.version(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
        })

    @app.route("/api/system/openclaw-status")
    def api_openclaw_status():
        """Get OpenClaw status."""
        version = _get_openclaw_version()
        return jsonify({
            "installed": version is not None,
            "version": version
        })

    @app.route("/api/system/disk-usage")
    def api_disk_usage():
        """Get disk usage."""
        try:
            usage = shutil.disk_usage("/")
            return jsonify({
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/system/uptime")
    def api_system_uptime():
        """Get system uptime."""
        boot_time_file = "/proc/uptime" if os.path.exists("/proc/uptime") else None
        if boot_time_file:
            try:
                with open(boot_time_file) as f:
                    uptime_seconds = float(f.read().split()[0])
                    return jsonify({"uptime": uptime_seconds})
            except Exception:
                pass
        return jsonify({"uptime": time.time() - os.times().elapsed})

    @app.route("/api/system/memory")
    def api_system_memory():
        """Get memory info."""
        try:
            if os.path.exists("/proc/meminfo"):
                with open("/proc/meminfo") as f:
                    lines = f.readlines()
                    mem = {}
                    for line in lines:
                        if ":" in line:
                            k, v = line.split(":", 1)
                            mem[k.strip()] = v.strip()
                    return jsonify({
                        "total": mem.get("MemTotal", "0 kB"),
                        "available": mem.get("MemAvailable", "0 kB"),
                        "used": mem.get("MemFree", "0 kB"),
                    })
        except Exception:
            pass
        return jsonify({"total": 0, "available": 0, "used": 0})

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
        """Set config value."""
        data = request.get_json() or {}
        key = data.get("key")
        value = data.get("value")
        if not key:
            return jsonify({"error": "Missing key"}), 400
        try:
            from shared import Config
            cfg = Config()
            keys = key.split(".")
            obj = cfg._cfg
            for k in keys[:-1]:
                if k not in obj:
                    obj[k] = {}
                obj = obj[k]
            obj[keys[-1]] = value
            dashboard_dir = Path(__file__).resolve().parent
            config_file = dashboard_dir / "config.json"
            config_file.write_text(json.dumps(cfg._cfg, indent=2))
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/config/save", methods=["POST"])
    def api_config_save():
        """Save config to file."""
        return jsonify({"success": False, "error": "Not implemented"}), 501

    # -------------------------------------------------------------------------
    # Models
    # -------------------------------------------------------------------------

    @app.route("/api/models", methods=["GET"])
    def api_models_list():
        """List available models."""
        models = [
            {"id": "anthropic/claude-haiku-4-5", "name": "Claude Haiku"},
            {"id": "anthropic/claude-sonnet-4", "name": "Claude Sonnet"},
            {"id": "openai/gpt-4o-mini", "name": "GPT-4o Mini"},
        ]
        return jsonify(models)

    @app.route("/api/models/default", methods=["GET"])
    def api_models_default():
        """Get default model."""
        from shared import Config
        cfg = Config()
        default_model = cfg.get("agents", "defaults", "model", "primary", default="anthropic/claude-haiku-4-5")
        return jsonify({"model": default_model})

    @app.route("/api/gateway/token")
    def api_gateway_token():
        """Get gateway auth token from openclaw.json."""
        from shared import OPENCLAW_CONFIG
        openclaw_cfg = OPENCLAW_CONFIG
        if openclaw_cfg.exists():
            try:
                cfg = json.loads(openclaw_cfg.read_text())
                token = cfg.get("gateway", {}).get("auth", {}).get("token")
                if token:
                    return jsonify({"token": token})
            except Exception:
                pass
        return jsonify({"token": ""}), 200

    @app.route("/api/setup/chat", methods=["POST"])
    def api_setup_chat():
        data = request.get_json() or {}
        message = (data.get("message") or "").strip()
        session_key = (data.get("sessionKey") or "agent:setup:main").strip()
        if not message:
            return jsonify({"ok": False, "error": "message is required"}), 400

        from shared import OPENCLAW_CONFIG
        gateway_ws_url = "ws://127.0.0.1:18789"
        gateway_token = ""
        try:
            if OPENCLAW_CONFIG.exists():
                cfg = json.loads(OPENCLAW_CONFIG.read_text())
                ws_url = cfg.get("gateway", {}).get("wsUrl") or cfg.get("gateway", {}).get("url")
                if isinstance(ws_url, str) and ws_url:
                    gateway_ws_url = ws_url
        except Exception:
            pass

        try:
            token_result = subprocess.run(
                ["openclaw", "dashboard", "--no-open"],
                capture_output=True, text=True, timeout=10
            )
            for line in token_result.stdout.splitlines():
                m = re.search(r'#token=([a-f0-9]+)', line)
                if m:
                    gateway_token = m.group(1)
                    break
        except Exception:
            pass

        if gateway_ws_url.startswith("http://"):
            gateway_ws_url = "ws://" + gateway_ws_url[len("http://"):]
        if gateway_ws_url.startswith("https://"):
            gateway_ws_url = "wss://" + gateway_ws_url[len("https://"):]

        try:
            from websocket import create_connection
        except Exception as e:
            return jsonify({"ok": False, "error": f"websocket-client unavailable: {e}"}), 500

        ws = None
        try:
            ws = create_connection(gateway_ws_url, timeout=8)

            challenge_deadline = time.time() + 8
            while time.time() < challenge_deadline:
                raw = ws.recv()
                msg = json.loads(raw)
                if msg.get("type") == "event" and msg.get("event") == "connect.challenge":
                    break
            else:
                return jsonify({"ok": False, "error": "gateway challenge timeout"}), 504

            ws.send(json.dumps({
                "type": "req",
                "id": "c0",
                "method": "connect",
                "params": {
                    "auth": {"token": gateway_token},
                    "minProtocol": 3,
                    "maxProtocol": 3,
                    "role": "operator",
                    "scopes": ["operator.read", "operator.write"],
                    "caps": [],
                    "client": {
                        "id": "openclaw-control-ui",
                        "mode": "webchat",
                        "version": "1.0.0",
                        "platform": "web"
                    }
                }
            }))

            connect_deadline = time.time() + 10
            while time.time() < connect_deadline:
                raw = ws.recv()
                msg = json.loads(raw)
                if msg.get("type") == "res" and msg.get("id") == "c0":
                    if not msg.get("ok"):
                        err = (msg.get("error") or {}).get("message") or "gateway connect failed"
                        return jsonify({"ok": False, "error": err}), 502
                    break
            else:
                return jsonify({"ok": False, "error": "gateway connect response timeout"}), 504

            ws.send(json.dumps({
                "type": "req",
                "id": "r1",
                "method": "chat.send",
                "params": {
                    "sessionKey": session_key,
                    "message": message,
                    "deliver": False,
                    "idempotencyKey": str(uuid.uuid4())
                }
            }))

            send_deadline = time.time() + 10
            while time.time() < send_deadline:
                raw = ws.recv()
                msg = json.loads(raw)
                if msg.get("type") == "res" and msg.get("id") == "r1":
                    if not msg.get("ok"):
                        err = (msg.get("error") or {}).get("message") or "chat.send failed"
                        return jsonify({"ok": False, "error": err}), 502
                    break
            else:
                return jsonify({"ok": False, "error": "chat.send response timeout"}), 504

            stream_text = ""
            final_deadline = time.time() + 90
            last_debug = time.time()
            all_messages = []
            while time.time() < final_deadline:
                raw = ws.recv()
                msg = json.loads(raw)
                all_messages.append(msg)
                if time.time() - last_debug > 10 and len(all_messages) > 0:
                    app.logger.warning(f"[setup-chat debug] msgs_received={len(all_messages)} last_type={all_messages[-1].get('type')} last_id={all_messages[-1].get('id')} last_event={all_messages[-1].get('event')}")
                    last_debug = time.time()
                if msg.get("type") == "res" and msg.get("id") == "r1":
                    payload = msg.get("payload", {})
                    text = _extract_text_from_gateway_message(payload)
                    app.logger.warning(f"[setup-chat] res r1 payload keys={list(payload.keys())} text={repr(text[:100])}")
                    return jsonify({"ok": True, "text": text or "(no response received)"})
                if msg.get("type") != "event" or msg.get("event") != "chat":
                    continue
                payload = msg.get("payload") or {}
                if payload.get("sessionKey") != session_key:
                    continue
                state = payload.get("state")
                if state == "delta":
                    delta = payload.get("message")
                    if isinstance(delta, str):
                        stream_text = delta if delta.startswith(stream_text) else (stream_text + delta)
                elif state == "final":
                    final_text = _extract_text_from_gateway_message(payload.get("message")) or stream_text
                    return jsonify({"ok": True, "text": final_text or "(no response received)"})
                elif state == "error":
                    err = payload.get("error") or payload.get("message") or "setup chat failed"
                    return jsonify({"ok": False, "error": str(err)}), 502

            return jsonify({"ok": False, "error": "chat final response timeout"}), 504
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500
        finally:
            try:
                if ws is not None:
                    ws.close()
            except Exception:
                pass

    @app.route("/api/gateway/last-error")
    def api_gateway_last_error():
        """Get last setup-agent related error from gateway logs."""
        try:
            log_dir = Path("/tmp/openclaw")
            if not log_dir.exists():
                return jsonify({"error": ""})
            log_files = sorted(log_dir.glob("openclaw-*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
            if not log_files:
                return jsonify({"error": ""})
            lines = log_files[0].read_text(errors="ignore").splitlines()
            patterns = (
                "lane=session:agent:setup:main",
                "Embedded agent failed before reply",
                "No API key found for provider",
                "Key limit exceeded (monthly limit)",
            )
            for line in reversed(lines[-400:]):
                if any(p in line for p in patterns):
                    return jsonify({"error": line[:1200]})
            return jsonify({"error": ""})
        except Exception as e:
            return jsonify({"error": str(e)})

    @app.route("/api/agents")
    def api_agents():
        """List all agents with agentId and mainModel fields (setup page format)."""
        agents = []
        from shared import OPENCLAW_CONFIG
        openclaw_cfg = OPENCLAW_CONFIG
        if openclaw_cfg.exists():
            try:
                cfg = json.loads(openclaw_cfg.read_text())
                agents_list = cfg.get("agents", {}).get("list", [])
                for entry in agents_list:
                    agents.append({
                        "agentId": entry.get("id", ""),
                        "mainModel": entry.get("model", ""),
                    })
            except Exception:
                pass
        return jsonify(agents)

    @app.route("/api/agents/<agent_id>/model", methods=["GET", "PUT"])
    def api_agent_model(agent_id):
        """Get or set the model for a specific agent."""
        from shared import OPENCLAW_CONFIG
        openclaw_cfg = OPENCLAW_CONFIG
        if not openclaw_cfg.exists():
            return jsonify({"error": "openclaw.json not found"}), 404
        try:
            cfg = json.loads(openclaw_cfg.read_text())
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        if request.method == "GET":
            agents_list = cfg.get("agents", {}).get("list", [])
            for entry in agents_list:
                if entry.get("id") == agent_id:
                    return jsonify({"model": entry.get("model", "")})
            return jsonify({"model": ""})

        data = request.get_json() or {}
        model = data.get("model", "")
        agents_list = cfg.get("agents", {}).get("list", [])
        found = False
        for entry in agents_list:
            if entry.get("id") == agent_id:
                entry["model"] = model
                found = True
                break
        if not found:
            agents_list.append({"id": agent_id, "model": model})
        cfg.setdefault("agents", {})["list"] = agents_list
        try:
            openclaw_cfg.write_text(json.dumps(cfg, indent=2))
            return jsonify({"ok": True, "success": True, "model": model})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.route("/api/settings/update-config", methods=["GET", "PUT"])
    def api_settings_update_config():
        """Read or write the updates section of dashboard config.json."""
        dashboard_dir = Path(__file__).resolve().parent
        config_file = dashboard_dir / "config.json"

        if request.method == "GET":
            if config_file.exists():
                try:
                    cfg = json.loads(config_file.read_text())
                    return jsonify(cfg.get("updates", {}))
                except Exception:
                    pass
            return jsonify({})

        data = request.get_json() or {}
        cfg = {}
        if config_file.exists():
            try:
                cfg = json.loads(config_file.read_text())
            except Exception:
                pass
        cfg.setdefault("updates", {}).update(data)
        try:
            config_file.write_text(json.dumps(cfg, indent=2))
            return jsonify(cfg["updates"])
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/services/status")
    def api_services_status():
        """
        Returns health status for all services the dashboard depends on.
        Extensible: add new services by appending to the services list.
        """
        import urllib.request
        import urllib.error

        from shared import OPENCLAW_CONFIG
        openclaw_cfg_path = OPENCLAW_CONFIG
        gateway_ws_url = "ws://127.0.0.1:18789"
        gateway_http_url = "http://127.0.0.1:18789"

        if openclaw_cfg_path.exists():
            try:
                cfg = json.loads(openclaw_cfg_path.read_text())
                ws_url = cfg.get("gateway", {}).get("wsUrl") or cfg.get("gateway", {}).get("url")
                if ws_url:
                    gateway_ws_url = ws_url
                    gateway_http_url = ws_url.replace("ws://", "http://").replace("wss://", "https://")
            except Exception:
                pass

        services = []

        def probe_gateway():
            reachable = False
            version = None
            error = None
            try:
                req = urllib.request.Request(
                    gateway_http_url,
                    headers={"User-Agent": "ResonantOS-Dashboard/1.0"},
                    method="GET"
                )
                with urllib.request.urlopen(req, timeout=3) as resp:
                    reachable = True
                    if resp.status == 200:
                        try:
                            body = json.loads(resp.read().decode())
                            version = body.get("version") or body.get("gateway", {}).get("version")
                        except Exception:
                            pass
            except urllib.error.URLError as e:
                error = str(e.reason)
            except Exception as e:
                error = str(e)
            return reachable, version, error

        reachable, gw_version, gw_error = probe_gateway()

        services.append({
            "name": "openclaw-gateway",
            "url": gateway_ws_url,
            "reachable": reachable,
            "version": gw_version,
            "error": gw_error,
            "installHint": "npm install -g openclaw",
            "startHint": "openclaw gateway start",
        })

        return jsonify({"services": services})

    return app
