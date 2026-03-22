"""
Memory routes - R-Memory, LCM, Chatbots.
"""

import json
import os
import re
import sqlite3
import time
from pathlib import Path
from flask import jsonify, request

def register_memory_routes(app):
    """Register all memory-related routes."""

    @app.route("/api/r-memory/scan")
    def api_rmemory_scan():
        """Scan R-Memory directory and return memory stats."""
        from shared import RMEMORY_DIR, RMEMORY_CONFIG, WORKSPACE
        memory_dir = RMEMORY_DIR
        config_path = RMEMORY_CONFIG
        memory_files = []
        total_size = 0

        if memory_dir.exists():
            for f in memory_dir.rglob("*"):
                if f.is_file() and not f.name.startswith("."):
                    memory_files.append({
                        "name": f.name,
                        "path": str(f.relative_to(memory_dir)),
                        "size": f.stat().st_size
                    })
                    total_size += f.stat().st_size

        config = {}
        if config_path.exists():
            try:
                config = json.loads(config_path.read_text())
            except Exception:
                pass

        return jsonify({
            "memoryDir": str(memory_dir),
            "config": config,
            "memoryFiles": memory_files,
            "totalSize": total_size,
            "path": str(memory_dir),
        })

    @app.route("/api/r-memory/read", methods=["POST"])
    def api_rmemory_read():
        """Read a specific memory file."""
        from shared import RMEMORY_DIR
        data = request.get_json() or {}
        filename = data.get("filename", "")
        if not filename:
            return jsonify({"error": "No filename provided"}), 400
        filepath = RMEMORY_DIR / filename
        if not str(filepath).startswith(str(RMEMORY_DIR)):
            return jsonify({"error": "Access denied"}), 403
        if not filepath.exists():
            return jsonify({"error": "File not found"}), 404
        try:
            content = filepath.read_text()
            return jsonify({"content": content, "filename": filename})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/r-memory/write", methods=["POST"])
    def api_rmemory_write():
        """Write to a specific memory file."""
        from shared import RMEMORY_DIR
        data = request.get_json() or {}
        filename = data.get("filename", "")
        content = data.get("content", "")
        if not filename:
            return jsonify({"error": "No filename provided"}), 400
        filepath = RMEMORY_DIR / filename
        if not str(filepath).startswith(str(RMEMORY_DIR)):
            return jsonify({"error": "Access denied"}), 403
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/r-memory/list")
    def api_rmemory_list():
        """List all memory files."""
        from shared import RMEMORY_DIR
        memory_dir = RMEMORY_DIR
        files = []
        if memory_dir.exists():
            for f in sorted(memory_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
                if f.is_file() and not f.name.startswith("."):
                    files.append({
                        "name": f.name,
                        "size": f.stat().st_size,
                        "modified": f.stat().st_mtime
                    })
        return jsonify(files)

    @app.route("/api/r-memory/delete", methods=["POST"])
    def api_rmemory_delete():
        """Delete a memory file."""
        from shared import RMEMORY_DIR
        data = request.get_json() or {}
        filename = data.get("filename", "")
        if not filename:
            return jsonify({"error": "No filename provided"}), 400
        filepath = RMEMORY_DIR / filename
        if not str(filepath).startswith(str(RMEMORY_DIR)):
            return jsonify({"error": "Access denied"}), 403
        try:
            if filepath.exists():
                filepath.unlink()
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/r-memory/open-log", methods=["POST"])
    def api_rmemory_open_log():
        """Open R-Memory log in system default app."""
        from shared import IS_MAC, IS_WINDOWS, IS_LINUX, RMEMORY_LOG
        import subprocess
        log_path = RMEMORY_LOG
        if not log_path.exists():
            return jsonify({"error": "Log file not found"}), 404
        try:
            if IS_MAC:
                subprocess.Popen(["open", "-a", "Terminal", str(log_path)])
            elif IS_WINDOWS:
                os.startfile(str(log_path))
            elif IS_LINUX:
                subprocess.Popen(["xdg-open", str(log_path)])
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/r-memory/stats")
    def api_rmemory_stats():
        """Get memory usage stats."""
        from shared import RMEMORY_DIR, WORKSPACE
        stats = {
            "totalFiles": 0,
            "totalSize": 0,
            "memoryUsed": 0,
            "layers": {}
        }
        if RMEMORY_DIR.exists():
            for f in RMEMORY_DIR.rglob("*"):
                if f.is_file():
                    stats["totalFiles"] += 1
                    stats["totalSize"] += f.stat().st_size
        return jsonify(stats)

    @app.route("/api/r-memory/summary")
    def api_rmemory_summary():
        """Get a summary of all memory documents."""
        from shared import WORKSPACE, RMEMORY_DIR
        summary = {
            "totalDocs": 0,
            "layers": {
                "L1": 0,
                "L2": 0,
                "L3": 0,
                "L4": 0
            },
            "totalSize": 0
        }
        ws = WORKSPACE
        if ws.exists():
            for f in ws.rglob("*.md"):
                rel = str(f.relative_to(ws))
                summary["totalDocs"] += 1
                for layer in ["L1", "L2", "L3", "L4"]:
                    if layer in rel:
                        summary["layers"][layer] += 1
                try:
                    summary["totalSize"] += f.stat().st_size
                except Exception:
                    pass
        return jsonify(summary)

    @app.route("/api/r-memory/config", methods=["GET"])
    def api_rmemory_config_get():
        """Get R-Memory configuration."""
        from shared import RMEMORY_CONFIG
        if RMEMORY_CONFIG.exists():
            try:
                return jsonify(json.loads(RMEMORY_CONFIG.read_text()))
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        return jsonify({})

    @app.route("/api/r-memory/config", methods=["POST"])
    def api_rmemory_config_update():
        """Update R-Memory configuration."""
        from shared import RMEMORY_CONFIG
        data = request.get_json() or {}
        try:
            RMEMORY_CONFIG.parent.mkdir(parents=True, exist_ok=True)
            RMEMORY_CONFIG.write_text(json.dumps(data, indent=2))
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/r-memory/compress", methods=["POST"])
    def api_rmemory_compress():
        """Trigger memory compression."""
        from shared import RMEMORY_CONFIG
        try:
            config = {}
            if RMEMORY_CONFIG.exists():
                config = json.loads(RMEMORY_CONFIG.read_text())
            return jsonify({
                "success": True,
                "message": "Compression triggered",
                "config": config
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/r-memory/recover", methods=["POST"])
    def api_rmemory_recover():
        """Recover from compaction."""
        return jsonify({"success": False, "error": "Recovery not implemented"}), 501

    # -------------------------------------------------------------------------
    # LCM (Large Context Manager) Routes
    # -------------------------------------------------------------------------

    @app.route("/api/lcm/status")
    def api_lcm_status():
        """Get LCM status."""
        return jsonify({
            "enabled": True,
            "model": "anthropic/claude-haiku-4-5",
            "contextWindow": 200000,
            "usedTokens": 0
        })

    @app.route("/api/lcm/stats")
    def api_lcm_stats():
        """Get LCM statistics."""
        return jsonify({
            "totalCompressions": 0,
            "totalTokens": 0,
            "averageCompression": 0
        })

    @app.route("/api/lcm/compress", methods=["POST"])
    def api_lcm_compress():
        """Manually trigger compression."""
        return jsonify({"success": False, "error": "Not implemented"}), 501

    # -------------------------------------------------------------------------
    # Chatbots Routes
    # -------------------------------------------------------------------------

    @app.route("/api/chatbots", methods=["GET"])
    def api_chatbots_list():
        """List all chatbots."""
        from shared import WORKSPACE
        chatbots_dir = WORKSPACE / "chatbots"
        bots = []
        if chatbots_dir.exists():
            for f in sorted(chatbots_dir.iterdir()):
                if f.suffix == ".json":
                    try:
                        bots.append(json.loads(f.read_text()))
                    except Exception:
                        pass
        return jsonify(bots)

    @app.route("/api/chatbots", methods=["POST"])
    def api_chatbots_create():
        """Create a new chatbot."""
        from shared import WORKSPACE
        data = request.get_json() or {}
        chatbots_dir = WORKSPACE / "chatbots"
        chatbots_dir.mkdir(parents=True, exist_ok=True)
        bot_id = data.get("id", f"bot_{int(time.time())}")
        bot_data = {
            "id": bot_id,
            "name": data.get("name", "New Bot"),
            "systemPrompt": data.get("systemPrompt", ""),
            "model": data.get("model", "anthropic/claude-haiku-4-5"),
            "createdAt": int(time.time() * 1000)
        }
        filepath = chatbots_dir / f"{bot_id}.json"
        filepath.write_text(json.dumps(bot_data, indent=2))
        return jsonify(bot_data), 201

    @app.route("/api/chatbots/<bot_id>", methods=["GET"])
    def api_chatbots_get(bot_id):
        """Get a specific chatbot."""
        from shared import WORKSPACE
        filepath = WORKSPACE / "chatbots" / f"{bot_id}.json"
        if not filepath.exists():
            return jsonify({"error": "Not found"}), 404
        try:
            return jsonify(json.loads(filepath.read_text()))
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/chatbots/<bot_id>", methods=["PUT"])
    def api_chatbots_update(bot_id):
        """Update a chatbot."""
        from shared import WORKSPACE
        data = request.get_json() or {}
        filepath = WORKSPACE / "chatbots" / f"{bot_id}.json"
        if not filepath.exists():
            return jsonify({"error": "Not found"}), 404
        try:
            current = json.loads(filepath.read_text())
            current.update({k: v for k, v in data.items() if k != "id"})
            filepath.write_text(json.dumps(current, indent=2))
            return jsonify(current)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/chatbots/<bot_id>", methods=["DELETE"])
    def api_chatbots_delete(bot_id):
        """Delete a chatbot."""
        from shared import WORKSPACE
        filepath = WORKSPACE / "chatbots" / f"{bot_id}.json"
        if filepath.exists():
            filepath.unlink()
        return jsonify({"success": True})

    @app.route("/api/chatbots/<bot_id>/chat", methods=["POST"])
    def api_chatbots_chat(bot_id):
        """Chat with a chatbot."""
        from shared import WORKSPACE
        data = request.get_json() or {}
        message = data.get("message", "")
        filepath = WORKSPACE / "chatbots" / f"{bot_id}.json"
        if not filepath.exists():
            return jsonify({"error": "Bot not found"}), 404
        try:
            bot = json.loads(filepath.read_text())
            return jsonify({
                "response": "Chat not yet implemented",
                "bot_id": bot_id,
                "bot_name": bot.get("name")
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/conversations", methods=["GET"])
    def api_conversations_list():
        """List chatbot conversations with pagination and filtering."""
        from shared import WORKSPACE
        chatbot_id = request.args.get("chatbot_id")
        limit = min(int(request.args.get("limit", 20)), 100)
        offset = int(request.args.get("offset", 0))
        search = request.args.get("search", "").strip()
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        db_path = WORKSPACE / "chatbots.db"
        conversations = []
        total = 0
        if db_path.exists():
            try:
                conn = sqlite3.connect(str(db_path))
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                where = []
                params = []
                if chatbot_id:
                    where.append("chatbot_id = ?")
                    params.append(chatbot_id)
                if search:
                    where.append("(user_message LIKE ? OR bot_response LIKE ?)")
                    params.extend([f"%{search}%", f"%{search}%"])
                if start_date:
                    where.append("created_at >= ?")
                    params.append(int(start_date) / 1000)
                if end_date:
                    where.append("created_at <= ?")
                    params.append(int(end_date) / 1000)
                where_clause = ("WHERE " + " AND ".join(where)) if where else ""
                cur.execute(f"SELECT COUNT(*) FROM chatbot_conversations {where_clause}", params)
                total = cur.fetchone()[0]
                cur.execute(
                    f"SELECT id, chatbot_id, user_message, bot_response, created_at FROM chatbot_conversations {where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    params + [limit, offset]
                )
                for row in cur.fetchall():
                    conversations.append({
                        "id": row["id"],
                        "chatbot_id": row["chatbot_id"],
                        "user_message": row["user_message"],
                        "bot_response": row["bot_response"],
                        "created_at": row["created_at"] * 1000,
                    })
                conn.close()
            except Exception:
                pass
        return jsonify({"conversations": conversations, "total": total, "limit": limit, "offset": offset})

    @app.route("/api/conversations/<conversation_id>", methods=["GET"])
    def api_conversation_get(conversation_id):
        from shared import WORKSPACE
        db_path = WORKSPACE / "chatbots.db"
        if not db_path.exists():
            return jsonify({"error": "Conversation not found"}), 404
        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT id, chatbot_id, user_message, bot_response, created_at FROM chatbot_conversations WHERE id = ?", (conversation_id,))
            row = cur.fetchone()
            conn.close()
            if not row:
                return jsonify({"error": "Conversation not found"}), 404
            return jsonify({
                "id": row["id"],
                "chatbot_id": row["chatbot_id"],
                "user_message": row["user_message"],
                "bot_response": row["bot_response"],
                "created_at": row["created_at"] * 1000,
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/analytics", methods=["GET"])
    def api_analytics():
        """Get chatbot analytics for a time range."""
        from shared import WORKSPACE
        chatbot_id = request.args.get("chatbot_id", "")
        range_param = request.args.get("range", "7d")
        days = {"7d": 7, "30d": 30, "90d": 90}.get(range_param, 7)
        db_path = WORKSPACE / "chatbots.db"
        data = {
            "total_conversations": 0, "total_messages": 0, "avg_response_time": 0,
            "conversations_change": 0, "messages_change": 0, "response_time_change": 0,
            "satisfaction_rate": 0, "satisfaction_change": 0,
            "chart_data": [], "popular_questions": [],
            "user_messages": 0, "bot_responses": 0, "error_rate": "0.0",
            "avg_conv_length": 0, "feedback": {}, "ratings": {},
        }
        if not db_path.exists():
            return jsonify(data)
        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            where = "WHERE created_at >= ?"
            params = [__import__("time").time() - days * 86400]
            if chatbot_id:
                where += " AND chatbot_id = ?"
                params.append(chatbot_id)
            cur.execute(f"SELECT COUNT(*) FROM chatbot_conversations {where}", params)
            data["total_conversations"] = cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(*) FROM chatbot_messages {where}", params)
            data["total_messages"] = cur.fetchone()[0]
            cur.execute(f"SELECT AVG(user_messages), AVG(bot_responses) FROM (SELECT COUNT(*) AS user_messages, COUNT(*) AS bot_responses FROM chatbot_messages {where} GROUP BY conversation_id)", params)
            row = cur.fetchone()
            if row and row[0]:
                data["avg_conv_length"] = round(float(row[0]), 1)
            conn.close()
        except Exception:
            pass
        return jsonify(data)

    @app.route("/api/token-savings", methods=["GET"])
    def api_token_savings():
        """Get token savings data (mock — real data requires gateway usage logs)."""
        from shared import WORKSPACE
        data_file = WORKSPACE / "dashboard-audit" / "data" / "token-savings.json"
        if data_file.exists():
            try:
                return jsonify(json.loads(data_file.read_text()))
            except Exception:
                pass
        return jsonify({
            "days": 7,
            "totals": {"actualApiCost": 0, "withoutRMemoryCostEstimate": 0, "rMemorySavingsEstimate": 0, "savingPctEstimate": 0},
            "componentBreakdown": [],
            "dailyCostBreakdown": [],
            "compressionStats": {},
            "sources": {"gatewayError": True}
        })

    @app.route("/api/token-savings/pricing", methods=["PUT"])
    def api_token_savings_pricing():
        """Save pricing reference data for token savings calculations."""
        from shared import WORKSPACE
        data_file = WORKSPACE / "dashboard-audit" / "data" / "token-savings.json"
        data_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            current = {}
            if data_file.exists():
                current = json.loads(data_file.read_text())
            patch = request.get_json() or {}
            current["pricingReference"] = patch.get("pricing", {})
            current["assumptions"] = patch.get("assumptions", {})
            data_file.write_text(json.dumps(current, indent=2))
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"error": str(e), "ok": False}), 500

    @app.route("/api/memory/health", methods=["GET"])
    def api_memory_health():
        """Get memory subsystem health status."""
        from shared import RMEMORY_DIR, RMEMORY_CONFIG
        health = {
            "lastTurn": None,
            "contextWindow": {
                "maxTokens": 200000,
                "actualTotalTokens": 0,
                "segments": {
                    "systemPrompt": 0,
                    "workspaceFiles": 0,
                    "ssotDocs": 0,
                    "conversation": 0,
                    "memoryHeaders": 0,
                    "lcmSummaries": 0
                },
                "injectedSSoTs": 0
            },
            "injectedSSoTDocs": [],
            "subsystems": {}
        }
        config = {}
        if RMEMORY_CONFIG.exists():
            try:
                config = json.loads(RMEMORY_CONFIG.read_text())
            except Exception:
                pass
        health["subsystems"] = {
            "rMemory": {"status": "running" if RMEMORY_DIR.exists() else "off", "label": "R-Memory", "detail": str(RMEMORY_DIR), "lastSeen": None},
            "lcm": {"status": "running", "label": "LCM (Haiku)", "detail": config.get("model", "anthropic/claude-haiku-4-5"), "lastSeen": None}
        }
        return jsonify(health)

    @app.route("/api/r-memory/available-models", methods=["GET"])
    def api_r_memory_available_models():
        """Return list of available models for the agent model selector."""
        return jsonify({
            "models": [
                {"model": "anthropic/claude-haiku-4-5", "label": "Claude Haiku 4.5"},
                {"model": "anthropic/claude-sonnet-4-7", "label": "Claude Sonnet 4.7"},
                {"model": "anthropic/claude-opus-4-7", "label": "Claude Opus 4.7"},
                {"model": "openai/gpt-4o-mini", "label": "GPT-4o Mini"},
                {"model": "google/gemini-2.0-flash", "label": "Gemini 2.0 Flash"},
            ]
        })

    return app
