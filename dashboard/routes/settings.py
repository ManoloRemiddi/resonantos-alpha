"""
Settings routes - dashboard settings, skills, plugins, cron, knowledge, and updates.
"""

import json
import subprocess
from pathlib import Path

from flask import jsonify, request

from shared import BUILTIN_SKILLS_DIR, CUSTOM_SKILLS_DIR, DASHBOARD_DIR, OPENCLAW_CONFIG, OPENCLAW_HOME, WORKSPACE


def register_settings_routes(app):
    """Register settings-related routes used by the dashboard settings page."""

    settings_state = {
        "theme": "dark",
        "autoRefresh": True,
        "refreshInterval": 30,
        "notifications": True,
        "permissions": {
            "browserAccess": True,
            "shellCommands": True,
            "fileWrite": True,
            "externalMessaging": False,
            "toolInstallation": False,
        },
    }

    memory_logs_state = {
        "daily": {"enabled": True, "model": "", "lastStatus": "idle"},
        "intraday": {"enabled": False, "lastStatus": "idle"},
    }

    def _load_openclaw_config():
        if not OPENCLAW_CONFIG.exists():
            return {}
        try:
            return json.loads(OPENCLAW_CONFIG.read_text())
        except Exception:
            return {}

    def _save_openclaw_config(config):
        OPENCLAW_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        OPENCLAW_CONFIG.write_text(json.dumps(config, indent=2))

    def _list_plugin_rows():
        config = _load_openclaw_config()
        entries = (((config.get("plugins") or {}).get("entries")) or {})
        allow = (((config.get("plugins") or {}).get("allow")) or [])
        plugins = []
        for plugin_id, plugin_cfg in sorted(entries.items()):
            plugin_cfg = plugin_cfg or {}
            plugins.append({
                "id": plugin_id,
                "name": plugin_id,
                "source": "custom",
                "enabled": plugin_cfg.get("enabled"),
                "retired": False,
                "version": plugin_cfg.get("version", ""),
                "description": plugin_cfg.get("description", ""),
                "configuredInEntries": True,
                "inAllowList": plugin_id in allow,
            })
        return {
            "plugins": plugins,
            "allow": allow,
            "totalCustom": len([p for p in plugins if p["source"] == "custom"]),
            "totalStock": len([p for p in plugins if p["source"] == "stock"]),
            "contextEngineSlot": (((config.get("plugins") or {}).get("contextEngine")) or {}).get("id"),
        }

    def _read_cron_jobs():
        jobs_file = OPENCLAW_HOME / "cron" / "jobs.json"
        if jobs_file.exists():
            try:
                payload = json.loads(jobs_file.read_text())
                if isinstance(payload, dict) and isinstance(payload.get("jobs"), list):
                    return payload["jobs"]
            except Exception:
                pass
        try:
            result = subprocess.run(
                ["openclaw", "cron", "list", "--all", "--json"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                payload = json.loads(result.stdout)
                if isinstance(payload, dict) and isinstance(payload.get("jobs"), list):
                    return payload["jobs"]
                if isinstance(payload, list):
                    return payload
        except Exception:
            pass
        return []

    def _knowledge_root():
        candidates = [
            OPENCLAW_HOME / "knowledge",
            WORKSPACE / "knowledge",
            WORKSPACE / "rag",
            WORKSPACE / "workspace-knowledge",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]

    def _list_knowledge_folders():
        root = _knowledge_root()
        folders = {}
        if not root.exists():
            return {"root": str(root), "folders": folders}
        for folder in sorted(root.iterdir()):
            if not folder.is_dir() or folder.name.startswith("."):
                continue
            files = []
            for file_path in sorted(folder.rglob("*")):
                if file_path.is_file() and not file_path.name.startswith("."):
                    files.append({
                        "name": file_path.name,
                        "path": str(file_path.relative_to(root)),
                        "size": file_path.stat().st_size,
                    })
            folders[folder.name] = {
                "totalFiles": len(files),
                "files": files,
            }
        return {"root": str(root), "folders": folders}

    def _discover_skills():
        entries = {}
        search_roots = []
        if CUSTOM_SKILLS_DIR:
            search_roots.append(("custom", CUSTOM_SKILLS_DIR))
        if BUILTIN_SKILLS_DIR:
            search_roots.append(("builtin", BUILTIN_SKILLS_DIR))

        for source, root in search_roots:
            try:
                if not root or not root.exists():
                    continue
                for skill_file in root.glob("*/SKILL.md"):
                    skill_name = skill_file.parent.name
                    if skill_name in entries:
                        continue
                    description = ""
                    try:
                        content = skill_file.read_text(encoding="utf-8", errors="ignore")
                        for line in content.splitlines():
                            stripped = line.strip()
                            if stripped and not stripped.startswith("---") and not stripped.startswith("#") and not stripped.startswith("name:") and not stripped.startswith("description:"):
                                description = stripped
                                break
                    except Exception:
                        pass
                    entries[skill_name] = {
                        "name": skill_name,
                        "description": description or "No description available",
                        "source": source,
                        "status": "ready",
                        "category": "Other",
                        "missingBins": [],
                        "installOptions": [],
                    }
            except Exception:
                continue
        return [entries[name] for name in sorted(entries)]

    def _agents_for_skills():
        config = _load_openclaw_config()
        agent_entries = ((config.get("agents") or {}).get("list")) or []
        agents = []
        for entry in agent_entries:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name") or entry.get("id") or "").strip()
            if name:
                agents.append({"name": name})
        if not agents:
            agents.append({"name": "main"})
        return agents

    def _get_agent_skill_allow(config, agent_name):
        agents_cfg = config.get("agents") or {}
        entries = agents_cfg.get("list") or []
        for item in entries:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("id") or "").strip()
            if name != agent_name:
                continue
            skills_value = item.get("skills")
            if isinstance(skills_value, list):
                return [str(skill).strip() for skill in skills_value if str(skill).strip()]
            if isinstance(skills_value, dict):
                allow = skills_value.get("allow")
                if isinstance(allow, list):
                    return [str(skill).strip() for skill in allow if str(skill).strip()]
            return None

        legacy_entry = agents_cfg.get(agent_name)
        if isinstance(legacy_entry, dict):
            allow = ((legacy_entry.get("skills") or {}).get("allow"))
            if isinstance(allow, list):
                return [str(skill).strip() for skill in allow if str(skill).strip()]
        return None

    def _set_agent_skill_allow(config, agent_name, allowed_skills):
        config.setdefault("agents", {})
        agents_cfg = config["agents"]
        target_entry = None
        target_style = "list"

        if isinstance(agents_cfg.get("list"), list):
            for item in agents_cfg["list"]:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or item.get("id") or "").strip()
                if name == agent_name:
                    target_entry = item
                    break

        if target_entry is None and isinstance(agents_cfg.get(agent_name), dict):
            target_entry = agents_cfg[agent_name]
            target_style = "legacy"

        if target_entry is None:
            agents_cfg.setdefault("list", [])
            target_entry = {"id": agent_name}
            agents_cfg["list"].append(target_entry)

        if allowed_skills is None:
            if isinstance(target_entry.get("skills"), dict):
                target_entry["skills"].pop("allow", None)
                if not target_entry["skills"]:
                    target_entry.pop("skills", None)
        else:
            target_entry.setdefault("skills", {})
            if isinstance(target_entry["skills"], list):
                target_entry["skills"] = {"allow": allowed_skills}
            else:
                target_entry["skills"]["allow"] = allowed_skills

        if target_style == "legacy":
            agents_cfg[agent_name] = target_entry

    @app.route("/api/settings", methods=["GET", "POST"])
    def api_settings():
        """Get or update lightweight dashboard settings used by the settings page."""
        nonlocal settings_state
        if request.method == "GET":
            return jsonify(settings_state)

        data = request.get_json(silent=True) or {}
        settings_state = {
            "theme": data.get("theme", settings_state["theme"]),
            "autoRefresh": bool(data.get("autoRefresh", settings_state["autoRefresh"])),
            "refreshInterval": int(data.get("refreshInterval", settings_state["refreshInterval"])),
            "notifications": bool(data.get("notifications", settings_state["notifications"])),
            "permissions": {
                "browserAccess": bool((data.get("permissions") or {}).get("browserAccess", settings_state["permissions"]["browserAccess"])),
                "shellCommands": bool((data.get("permissions") or {}).get("shellCommands", settings_state["permissions"]["shellCommands"])),
                "fileWrite": bool((data.get("permissions") or {}).get("fileWrite", settings_state["permissions"]["fileWrite"])),
                "externalMessaging": bool((data.get("permissions") or {}).get("externalMessaging", settings_state["permissions"]["externalMessaging"])),
                "toolInstallation": bool((data.get("permissions") or {}).get("toolInstallation", settings_state["permissions"]["toolInstallation"])),
            },
        }
        return jsonify({"success": True, **settings_state})

    @app.route("/api/settings/plugins")
    def api_settings_plugins():
        """Expose plugin configuration from openclaw.json with safe defaults."""
        return jsonify(_list_plugin_rows())

    @app.route("/api/settings/skills", methods=["GET", "PUT"])
    def api_settings_skills():
        """Expose skill inventory and per-agent assignments."""
        if request.method == "GET":
            config = _load_openclaw_config()
            skills = _discover_skills()
            skill_names = [skill["name"] for skill in skills]
            skill_name_set = set(skill_names)
            assignments = {}

            for agent in _agents_for_skills():
                agent_name = agent["name"]
                allow = _get_agent_skill_allow(config, agent_name)
                if allow is None:
                    assignments[agent_name] = list(skill_names)
                else:
                    seen = set()
                    assignments[agent_name] = [
                        skill_name for skill_name in allow
                        if skill_name in skill_name_set and skill_name not in seen and not seen.add(skill_name)
                    ]
            return jsonify({
                "agents": _agents_for_skills(),
                "skills": skills,
                "assignments": assignments,
            })

        data = request.get_json(silent=True) or {}
        agent_name = str(data.get("agent") or "").strip()
        skill_list = data.get("skills")
        if not agent_name:
            return jsonify({"error": "Missing agent"}), 400
        if not isinstance(skill_list, list):
            return jsonify({"error": "Skills must be a list"}), 400

        available_skills = _discover_skills()
        available_names = [skill["name"] for skill in available_skills]
        available_name_set = set(available_names)
        requested = []
        seen = set()
        for skill_name in skill_list:
            normalized = str(skill_name).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            requested.append(normalized)

        unknown = [skill_name for skill_name in requested if skill_name not in available_name_set]
        if unknown:
            return jsonify({"error": "Unknown skills: " + ", ".join(unknown)}), 400

        config = _load_openclaw_config()
        allowed_skills = [name for name in available_names if name in seen]
        if len(allowed_skills) == len(available_names):
            allowed_skills = None

        try:
            _set_agent_skill_allow(config, agent_name, allowed_skills)
            _save_openclaw_config(config)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

        return jsonify({
            "success": True,
            "agent": agent_name,
            "skills": available_names if allowed_skills is None else allowed_skills,
        })

    @app.route("/api/skills/setup-request", methods=["POST"])
    def api_skill_setup_request():
        """Accept skill setup requests with a friendly non-blocking response."""
        data = request.get_json(silent=True) or {}
        skill_name = str(data.get("skill") or "").strip()
        if not skill_name:
            return jsonify({"error": "Missing skill"}), 400
        return jsonify({
            "success": True,
            "message": f"Setup request noted for {skill_name}. Install support is not automated in this dashboard yet."
        })

    @app.route("/api/settings/memory-logs", methods=["GET", "PUT"])
    def api_settings_memory_logs():
        """Expose memory-log settings with graceful fallback when cron data is unavailable."""
        nonlocal memory_logs_state
        if request.method == "GET":
            return jsonify(memory_logs_state)

        data = request.get_json(silent=True) or {}
        daily = data.get("daily") or {}
        intraday = data.get("intraday") or {}
        model = data.get("model")

        memory_logs_state["daily"]["enabled"] = bool(daily.get("enabled", memory_logs_state["daily"]["enabled"]))
        memory_logs_state["intraday"]["enabled"] = bool(intraday.get("enabled", memory_logs_state["intraday"]["enabled"]))
        if model is not None:
            memory_logs_state["daily"]["model"] = model

        return jsonify(memory_logs_state)

    @app.route("/api/cron/jobs")
    def api_cron_jobs():
        """Return cron jobs if available, otherwise an empty schedule."""
        return jsonify({"jobs": _read_cron_jobs()})

    @app.route("/api/knowledge/base")
    def api_knowledge_base():
        """List local knowledge folders and files, if configured."""
        return jsonify(_list_knowledge_folders())

    @app.route("/api/knowledge/file")
    def api_knowledge_file():
        """Read a single file from the local knowledge root."""
        rel_path = request.args.get("path", "").strip()
        if not rel_path:
            return jsonify({"error": "Missing path"}), 400

        root = _knowledge_root().resolve()
        file_path = (root / rel_path).resolve()
        if root not in file_path.parents and file_path != root:
            return jsonify({"error": "Access denied"}), 403
        if not file_path.exists() or not file_path.is_file():
            return jsonify({"error": "File not found"}), 404
        try:
            return jsonify({"path": rel_path, "content": file_path.read_text(encoding="utf-8", errors="ignore")})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.route("/api/logician/rules")
    def api_logician_rules():
        """Get rules in the category/totals shape expected by the settings page."""
        data_file = DASHBOARD_DIR / "data" / "rules.json"
        categories = {}
        totals = {"rules": 0, "facts": 0, "categories": 0, "sections": 0}

        if data_file.exists():
            try:
                payload = json.loads(data_file.read_text())
                if isinstance(payload, list):
                    totals["rules"] = len(payload)
                    for item in payload:
                        if not isinstance(item, dict):
                            continue
                        category_key = str(item.get("category") or "general").strip() or "general"
                        bucket = categories.setdefault(category_key, {
                            "name": category_key.title(),
                            "icon": "•",
                            "description": "",
                            "ruleCount": 0,
                            "factCount": 0,
                            "sectionCount": 0,
                            "locked": False,
                        })
                        bucket["ruleCount"] += 1
                        bucket["factCount"] += len(item.get("steps") or [])
                        bucket["sectionCount"] += 1
                        if not bucket["description"]:
                            bucket["description"] = item.get("description") or "Rule category"
                    totals["categories"] = len(categories)
                    totals["facts"] = sum(category["factCount"] for category in categories.values())
                    totals["sections"] = sum(category["sectionCount"] for category in categories.values())
            except Exception:
                pass

        return jsonify({
            "categories": list(categories.values()),
            "totals": totals,
        })

    return app
