"""Misc dashboard routes."""

from __future__ import annotations

import os
from typing import Any

from flask import Blueprint, Response, jsonify, redirect, request, send_from_directory

from routes.chatbots import _get_db
from routes.shared import _read_gw_token, get_gw_port

misc_bp = Blueprint("misc", __name__)


@misc_bp.route("/chat-redirect")
def chat_redirect() -> Response:
    """Redirect the browser to the local OpenClaw chat UI.

    Read the gateway auth token and inject it into the fragment when one is
    available. Fall back to the plain local chat URL so the route still works
    when token bootstrap is unavailable.

    Dependencies:
        _read_gw_token() and get_gw_port().

    Returns:
        Response: Redirect response targeting the local OpenClaw web chat.
    """
    token = _read_gw_token()
    port = get_gw_port()
    if token:
        return redirect(f"http://localhost:{port}/#token={token}")
    return redirect(f"http://localhost:{port}/")


def _build_coding_agents_payload() -> dict[str, Any]:
    """Build the static coding-agents dashboard payload.

    Assemble the canned task and stats data used by the coding-agents demo
    view. Keep the shape aligned with the front-end expectations without
    reaching into external services at request time.

    Called by:
        api_coding_agents_tasks().
    Side effects:
        None.

    Returns:
        dict[str, Any]: Serialized task and aggregate stats payload.
    """
    return {
        "tasks": [
            {
                "id": "task-001",
                "title": "Implement user authentication middleware",
                "status": "running",
                "model": "Nemotron 120B",
                "model_source": "GX10 Local",
                "elapsed_seconds": 252,
                "tokens_used": 18200,
                "tokens_per_second": 41.5,
                "files_changed": 3,
                "files_modified": 2,
                "files_new": 1,
                "actions_done": 8,
                "actions_total": 12,
                "current_activity": "Running pytest auth/test_middleware.py",
                "health": "clear",
                "health_detail": "0 errors · 0 blocks",
                "steps": ["Read", "Plan", "Code", "Test", "Verify", "Commit"],
                "current_step": 3,
                "details_md": "# Auth Middleware\n## Objective\nImplement JWT-based authentication middleware for FastAPI.\n## Requirements\n- Verify Bearer tokens on all /api/* routes\n- Extract user_id from JWT claims\n- Return 401 on invalid/expired tokens\n## Acceptance\n- All 3 test cases pass\n- No existing tests broken",
                "quality_gates": [
                    {"name": "Shield", "status": "pass", "detail": "All layers passed · No blocks"},
                    {"name": "Logician", "status": "pass", "detail": "3/3 rules verified"},
                ],
                "files": [
                    {"path": "src/middleware/auth.py", "added": 67, "removed": 0},
                    {"path": "src/config/security.py", "added": 12, "removed": 3},
                    {"path": "tests/auth/test_middleware.py", "added": 45, "removed": 0},
                ],
                "log": [
                    {"time": "14:32", "type": "think", "msg": "Analyzing existing auth patterns..."},
                    {"time": "14:33", "type": "action", "msg": "create src/middleware/auth.py (67 lines)"},
                    {"time": "14:35", "type": "action", "msg": "exec: pytest tests/auth/ -v"},
                    {"time": "14:36", "type": "observe", "msg": "3 passed in 0.42s"},
                ],
            },
            {
                "id": "task-002",
                "title": "Add rate limiting to API endpoints",
                "status": "complete",
                "model": "MiniMax M2.7",
                "model_source": "Cloud",
                "elapsed_seconds": 408,
                "tokens_used": 32100,
                "tokens_per_second": 35.8,
                "files_changed": 4,
                "files_modified": 4,
                "files_new": 0,
                "actions_done": 15,
                "actions_total": 15,
                "current_activity": None,
                "health": "recovered",
                "health_detail": "1 Recovered",
                "steps": ["Read", "Plan", "Code", "Test", "Verify", "Commit"],
                "current_step": 5,
                "details_md": "# Rate Limiting\n## Objective\nAdd request throttling to all public API routes.\n## Acceptance\n- Middleware attached at the API boundary\n- Burst traffic returns 429\n- Existing endpoint tests remain green",
                "quality_gates": [
                    {"name": "Shield", "status": "pass", "detail": "All layers passed"},
                    {"name": "Logician", "status": "pass", "detail": "4/4 rules verified"},
                ],
                "files": [
                    {"path": "src/middleware/rate_limit.py", "added": 89, "removed": 4},
                    {"path": "src/main.py", "added": 6, "removed": 1},
                    {"path": "src/config/settings.py", "added": 8, "removed": 0},
                    {"path": "tests/test_rate_limit.py", "added": 52, "removed": 0},
                ],
                "log": [],
            },
            {
                "id": "task-003",
                "title": "Migrate database schema to v3",
                "status": "failed",
                "model": "GPT-5.4",
                "model_source": "OpenAI",
                "elapsed_seconds": 130,
                "tokens_used": 8400,
                "tokens_per_second": 52.1,
                "files_changed": 1,
                "files_modified": 1,
                "files_new": 0,
                "actions_done": 6,
                "actions_total": 6,
                "current_activity": None,
                "health": "blocked",
                "health_detail": "Shield Layer 6",
                "error": 'Shield Layer 6: Blocked destructive operation — cannot DROP TABLE "users_v2" on production database',
                "steps": ["Read", "Plan", "Code", "Test", "Verify", "Commit"],
                "current_step": 3,
                "details_md": "# Schema Migration\n## Objective\nUpgrade the production schema to v3.\n## Risk\nRequires destructive migration steps.\n## Acceptance\n- Migration applies cleanly on staging\n- Production-safe plan approved before execution",
                "quality_gates": [
                    {"name": "Shield", "status": "fail", "detail": "Layer 6 — Destructive operation blocked"},
                    {"name": "Logician", "status": "pass", "detail": "2/2 rules verified (pre-block)"},
                ],
                "files": [
                    {"path": "migrations/versions/003_schema_v3.py", "added": 34, "removed": 0},
                ],
                "log": [
                    {"time": "13:51", "type": "action", "msg": "exec: alembic upgrade head"},
                    {"time": "13:52", "type": "error", "msg": "Shield Layer 6: BLOCKED — destructive op"},
                ],
            },
        ],
        "stats": {
            "active_tasks": 2,
            "completed_today": 7,
            "total_tokens": 156000,
            "avg_throughput": 42.3,
            "peak_throughput": 60.4,
            "agent_slots_used": 2,
            "agent_slots_total": 6,
            "daily_token_budget": 250000,
            "target_tasks_per_day": 10,
            "avg_tokens_per_task": 22300,
        },
    }


@misc_bp.route("/api/coding-agents/tasks")
def api_coding_agents_tasks() -> Response:
    """Return coding-agents task data for the dashboard UI.

    Wrap the static payload builder in a JSON response so the front end can
    render task cards and stats panels. Keep the route thin by delegating the
    payload construction to the local helper.

    Dependencies:
        _build_coding_agents_payload().

    Returns:
        Response: JSON response containing demo coding-agent task data.
    """
    return jsonify(_build_coding_agents_payload())


@misc_bp.route("/api/widget/chat", methods=["POST"])
def api_widget_chat() -> Response:
    """Relay widget chat messages to the configured model provider.

    Validate the incoming widget payload, load the chatbot configuration from
    SQLite, and normalize recent messages into the provider-specific request
    format. Dispatch the request to either OpenAI or Anthropic and return the
    generated reply text to the widget.

    Dependencies:
        request.get_json(), _get_db(), local auth-profiles.json, and urllib.request.

    Returns:
        Response: JSON response containing a model reply or an error payload.
    """
    data: dict[str, Any] = request.get_json() or {}
    bot_id = data.get("botId")
    messages = data.get("messages", [])
    if not bot_id or not messages:
        return jsonify({"error": "botId and messages required"}), 400

    db = _get_db()
    bot = db.execute("SELECT * FROM chatbots WHERE id=?", (bot_id,)).fetchone()
    db.close()
    if not bot:
        return jsonify({"error": "chatbot not found"}), 404

    bot = dict(bot)
    system_prompt = bot.get("system_prompt", "")

    try:
        import json as _json

        auth_path = os.path.expanduser("~/.openclaw/agents/main/agent/auth-profiles.json")
        with open(auth_path) as handle:
            auth = _json.load(handle)
    except Exception as e:
        return jsonify({"error": f"Auth config not found: {e}"}), 500

    api_messages = []
    for message in messages[-20:]:
        role = message.get("role", "user")
        if role in ("user", "assistant"):
            api_messages.append({"role": role, "content": message.get("content", "")})

    model_id = bot.get("model_id", "claude-sonnet")

    try:
        import urllib.request

        if model_id.startswith("gpt"):
            api_key = auth["profiles"]["openai:manual"]["token"]
            oai_model = {"gpt-4o": "gpt-4o", "gpt-4": "gpt-4"}.get(model_id, "gpt-4o")
            oai_messages = [{"role": "system", "content": system_prompt}] + api_messages
            req_body = _json.dumps({"model": oai_model, "max_tokens": 1024, "messages": oai_messages}).encode()
            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=req_body,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = _json.loads(resp.read())
            reply = result["choices"][0]["message"]["content"]
        else:
            api_key = auth["profiles"]["anthropic:manual"]["token"]
            ant_model = {
                "claude-sonnet": "claude-sonnet-4-20250514",
                "claude-opus": "claude-opus-4-20250514",
                "claude-haiku": "claude-haiku-4-20250514",
            }.get(model_id, "claude-sonnet-4-20250514")
            req_body = _json.dumps(
                {
                    "model": ant_model,
                    "max_tokens": 1024,
                    "system": system_prompt,
                    "messages": api_messages,
                }
            ).encode()
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=req_body,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = _json.loads(resp.read())
            reply = result.get("content", [{}])[0].get("text", "Sorry, I couldn't generate a response.")

        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@misc_bp.route("/widget.js")
def widget_js() -> Response:
    """Serve the embeddable widget JavaScript asset.

    Resolve the shared static directory relative to the routes package and send
    the widget bundle with the expected JavaScript MIME type. Keep asset serving
    in-process so embedders can load the script from the dashboard host.

    Dependencies:
        os.path and send_from_directory().

    Returns:
        Response: Static file response for `widget.js`.
    """
    return send_from_directory(
        os.path.join(os.path.dirname(__file__), "..", "static"),
        "widget.js",
        mimetype="application/javascript",
    )
