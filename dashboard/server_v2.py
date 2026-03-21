#!/usr/bin/env python3
"""
ResonantOS Dashboard v2 — Thin Router

This file imports and registers all route modules.
Route implementations are in dashboard/routes/

To add a new route module:
1. Create dashboard/routes/<module>.py with a register_<module>_routes(app) function
2. Import and call it in this file
"""

import sys
from pathlib import Path

# Add parent to path for shared imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

from flask import Flask, jsonify, redirect, render_template, request, send_from_directory
from flask_cors import CORS

# Import shared utilities
from shared import (
    IS_WINDOWS, IS_MAC, IS_LINUX,
    is_windows, is_mac, is_linux,
    open_file_using_system,
    restart_openclaw_gateway,
    Config,
    WORKSPACE, OPENCLAW_HOME, OPENCLAW_CONFIG,
    RMEMORY_DIR, RMEMORY_CONFIG,
)

# Import route modules
from routes import (
    register_docs_routes,
    register_memory_routes,
    register_projects_routes,
    register_wallet_routes,
    register_system_routes,
    register_bounty_routes,
    register_profile_routes,
)

# ============================================================================
# Flask App Setup
# ============================================================================

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["JSON_SORT_KEYS"] = False
CORS(app)

# ============================================================================
# Page Routes
# ============================================================================

@app.route("/")
def page_home():
    return render_template("pages/index.html")

@app.route("/chat-redirect")
def chat_redirect():
    return redirect("/")

@app.route("/agents")
def page_agents():
    return render_template("pages/agents.html")

@app.route("/r-memory")
def page_r_memory():
    return render_template("pages/r-memory.html")

@app.route("/projects")
def page_projects():
    return render_template("pages/projects.html")

@app.route("/setup")
def page_setup():
    return render_template("pages/setup.html")

@app.route("/chatbots")
def page_chatbots():
    return render_template("pages/chatbots.html")

@app.route("/wallet")
def page_wallet():
    return render_template("pages/wallet.html")

@app.route("/tribes")
def page_tribes():
    return render_template("pages/tribes.html")

@app.route("/bounties")
def page_bounties():
    return render_template("pages/bounties.html")

@app.route("/protocol-store")
def page_protocol_store():
    return render_template("pages/protocol-store.html")

@app.route("/docs")
def page_docs():
    return render_template("pages/docs.html")

@app.route("/license")
def page_license():
    return render_template("pages/license.html")

@app.route("/<path:filename>")
def serve_static(filename):
    return send_from_directory("static", filename)

# ============================================================================
# Register All Route Modules
# ============================================================================

register_docs_routes(app)
register_memory_routes(app)
register_projects_routes(app)
register_wallet_routes(app)
register_system_routes(app)

# Register full implementations if available
if register_bounty_routes:
    register_bounty_routes(app)

if register_profile_routes:
    register_profile_routes(app)

# ============================================================================
# Additional Routes (TODO - extract to modules)
# ============================================================================

@app.route("/api/dashboard/update", methods=["POST"])
def api_dashboard_update():
    """Dashboard self-update via git pull."""
    return jsonify({"success": False, "error": "Not implemented"}), 501

@app.route("/api/dashboard/restart", methods=["POST"])
def api_dashboard_restart():
    """Restart dashboard."""
    return jsonify({"success": True})

# ============================================================================
# Memory Logs Settings
# ============================================================================

@app.route("/api/memory-logs/settings")
def api_memory_logs_settings():
    """Get memory logs settings."""
    return jsonify({
        "enabled": True,
        "path": str(RMEMORY_DIR / "r-memory.log"),
    })

@app.route("/api/memory-logs/settings", methods=["POST"])
def api_memory_logs_settings_update():
    """Update memory logs settings."""
    return jsonify({"success": False, "error": "Not implemented"}), 501

# ============================================================================
# Startup
# ============================================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ResonantOS Dashboard")
    parser.add_argument("--port", type=int, default=19100, help="Port to run on")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    print(f"Starting ResonantOS Dashboard on port {args.port}")
    app.run(host="0.0.0.0", port=args.port, debug=args.debug)
