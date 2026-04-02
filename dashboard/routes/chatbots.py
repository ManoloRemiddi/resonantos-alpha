"""Chatbot routes."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, jsonify, request

chatbots_bp = Blueprint("chatbots", __name__)

CHATBOTS_DB: Path = Path(__file__).resolve().parent.parent / "chatbots.db"


def _get_db() -> sqlite3.Connection:
    """Open the chatbot database and ensure the schema exists.

    Create a SQLite connection, configure row access by column name, and initialize required tables and indexes.
    The function centralizes schema setup so each route can rely on the database being ready before queries run.

    Dependencies:
        Uses ``CHATBOTS_DB`` and Python's ``sqlite3`` module.

    Returns:
        sqlite3.Connection: Open database connection with ``sqlite3.Row`` row factory configured.

    Called by:
        Every route in this module that reads or writes chatbot data.

    Side effects:
        Creates the SQLite database file, tables, and indexes if they do not already exist.
    """
    db = sqlite3.connect(str(CHATBOTS_DB))
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS chatbots (
            id TEXT PRIMARY KEY, user_id TEXT DEFAULT 'default', name TEXT NOT NULL,
            system_prompt TEXT, greeting TEXT DEFAULT 'Hi! How can I help you today?',
            suggested_prompts TEXT DEFAULT '[]', position TEXT DEFAULT 'bottom-right',
            theme TEXT DEFAULT 'dark', primary_color TEXT DEFAULT '#4ade80',
            bg_color TEXT DEFAULT '#1a1a1a', text_color TEXT DEFAULT '#e0e0e0',
            allowed_domains TEXT DEFAULT '', rate_per_minute INTEGER DEFAULT 10,
            rate_per_hour INTEGER DEFAULT 100, enable_analytics INTEGER DEFAULT 1,
            show_watermark INTEGER DEFAULT 1, status TEXT DEFAULT 'active',
            created_at INTEGER DEFAULT (strftime('%s', 'now') * 1000),
            updated_at INTEGER DEFAULT (strftime('%s', 'now') * 1000),
            api_type TEXT DEFAULT 'internal', api_key_encrypted TEXT,
            model_id TEXT DEFAULT 'claude-sonnet', last_used_at INTEGER,
            icon_url TEXT DEFAULT '', icon TEXT DEFAULT '💬', icon_type TEXT DEFAULT 'emoji'
        );
        CREATE TABLE IF NOT EXISTS chatbot_conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT, chatbot_id TEXT NOT NULL,
            session_id TEXT NOT NULL, started_at INTEGER DEFAULT (strftime('%s', 'now') * 1000),
            ended_at INTEGER, message_count INTEGER DEFAULT 0, satisfaction_rating INTEGER,
            FOREIGN KEY (chatbot_id) REFERENCES chatbots(id)
        );
        CREATE TABLE IF NOT EXISTS chatbot_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL, content TEXT NOT NULL,
            timestamp INTEGER DEFAULT (strftime('%s', 'now') * 1000),
            FOREIGN KEY (conversation_id) REFERENCES chatbot_conversations(id)
        );
        CREATE TABLE IF NOT EXISTS licenses (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, chatbot_id TEXT,
            tier TEXT DEFAULT 'free', features TEXT DEFAULT '[]',
            stripe_subscription_id TEXT, stripe_customer_id TEXT, expires_at INTEGER,
            created_at INTEGER DEFAULT (strftime('%s', 'now') * 1000),
            updated_at INTEGER DEFAULT (strftime('%s', 'now') * 1000)
        );
        CREATE TABLE IF NOT EXISTS knowledge_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT, chatbot_id TEXT NOT NULL,
            filename TEXT NOT NULL, content TEXT, file_size INTEGER,
            uploaded_at INTEGER DEFAULT (strftime('%s', 'now') * 1000),
            FOREIGN KEY (chatbot_id) REFERENCES chatbots(id)
        );
        CREATE INDEX IF NOT EXISTS idx_conversations_chatbot ON chatbot_conversations(chatbot_id);
        CREATE INDEX IF NOT EXISTS idx_messages_conversation ON chatbot_messages(conversation_id);
        CREATE INDEX IF NOT EXISTS idx_licenses_user ON licenses(user_id);
    """
    )
    return db


@chatbots_bp.route("/api/chatbots")
def api_chatbots() -> Response:
    """Return all chatbots with summary counts.

    Load chatbot records ordered by creation time and attach per-bot conversation counts for the list view.
    The response also includes aggregate totals used by the chatbot dashboard header.

    Dependencies:
        Uses ``CHATBOTS_DB``, ``_get_db``, SQLite queries, and Flask's ``jsonify``.

    Returns:
        Response: JSON response containing chatbot rows and aggregate statistics.
    """
    if not CHATBOTS_DB.exists():
        return jsonify([])
    db = _get_db()
    bots = [dict(r) for r in db.execute("SELECT * FROM chatbots ORDER BY created_at DESC").fetchall()]
    total_convos = 0
    for bot in bots:
        count = db.execute("SELECT COUNT(*) FROM chatbot_conversations WHERE chatbot_id=?", (bot["id"],)).fetchone()[0]
        bot["conversation_count"] = count
        total_convos += count
    db.close()
    active = sum(1 for b in bots if b.get("status") == "active")
    return jsonify(
        {
            "chatbots": bots,
            "total": len(bots),
            "active": active,
            "totalConversations": total_convos,
            "avgSatisfaction": 0,
        }
    )


@chatbots_bp.route("/api/chatbots/<bot_id>")
def api_chatbot_detail(bot_id: str) -> Response:
    """Return one chatbot with usage details.

    Fetch the chatbot row for the requested id and augment it with conversation and message counts.
    Unknown chatbot ids return a 404 payload instead of an empty success response.

    Args:
        bot_id: Identifier of the chatbot to retrieve.

    Dependencies:
        Uses ``_get_db``, SQLite queries, and Flask's ``jsonify``.

    Returns:
        Response: JSON response containing chatbot details or a 404 error body.
    """
    db = _get_db()
    bot = db.execute("SELECT * FROM chatbots WHERE id=?", (bot_id,)).fetchone()
    if not bot:
        db.close()
        return jsonify({"error": "not found"}), 404
    result = dict(bot)
    result["conversation_count"] = db.execute(
        "SELECT COUNT(*) FROM chatbot_conversations WHERE chatbot_id=?", (bot_id,)
    ).fetchone()[0]
    result["message_count"] = db.execute(
        "SELECT COUNT(*) FROM chatbot_messages WHERE conversation_id IN (SELECT id FROM chatbot_conversations WHERE chatbot_id=?)",
        (bot_id,),
    ).fetchone()[0]
    db.close()
    return jsonify(result)


@chatbots_bp.route("/api/chatbots", methods=["POST"])
def api_chatbot_create() -> Response:
    """Create a new chatbot record.

    Read the request payload, assign default values for omitted chatbot settings, and insert the new row into SQLite.
    The endpoint returns the generated chatbot id so the frontend can fetch or edit the new record immediately.

    Dependencies:
        Uses Flask's ``request`` and ``jsonify``, ``_get_db``, ``json.dumps``, and lazy ``time`` and ``uuid`` imports.

    Returns:
        Response: JSON response containing ``ok`` and the created chatbot id.
    """
    import time
    import uuid

    body: dict[str, Any] = request.get_json(force=True)
    bot_id = uuid.uuid4().hex[:8]
    now = int(time.time() * 1000)
    db = _get_db()
    db.execute(
        """INSERT INTO chatbots (id, user_id, name, system_prompt, greeting, suggested_prompts,
        position, theme, primary_color, bg_color, text_color, allowed_domains,
        rate_per_minute, rate_per_hour, enable_analytics, show_watermark, status,
        created_at, updated_at, api_type, model_id, icon, icon_type)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            bot_id,
            "default",
            body.get("name", "New Chatbot"),
            body.get("system_prompt", "You are a helpful assistant."),
            body.get("greeting", "Hi! How can I help you?"),
            json.dumps(body.get("suggested_prompts", [])),
            body.get("position", "bottom-right"),
            body.get("theme", "dark"),
            body.get("primary_color", "#4ade80"),
            body.get("bg_color", "#1a1a1a"),
            body.get("text_color", "#e0e0e0"),
            body.get("allowed_domains", ""),
            body.get("rate_per_minute", 10),
            body.get("rate_per_hour", 100),
            1,
            1,
            "active",
            now,
            now,
            body.get("api_type", "internal"),
            body.get("model_id", "claude-haiku"),
            body.get("icon", "💬"),
            body.get("iconType", "emoji"),
        ),
    )
    db.commit()
    db.close()
    return jsonify({"ok": True, "id": bot_id})


@chatbots_bp.route("/api/chatbots/<bot_id>", methods=["PUT"])
def api_chatbot_update(bot_id: str) -> Response:
    """Update selected fields on a chatbot.

    Validate that the chatbot exists, normalize the incoming icon field name when needed, and update only supplied columns.
    When no supported fields are present, the endpoint leaves the record untouched and still returns success.

    Args:
        bot_id: Identifier of the chatbot to update.

    Dependencies:
        Uses Flask's ``request`` and ``jsonify``, ``_get_db``, and a lazy ``time`` import.

    Returns:
        Response: JSON response containing ``ok`` or a 404 error body.
    """
    import time

    body: dict[str, Any] = request.get_json(force=True)
    db = _get_db()
    bot = db.execute("SELECT id FROM chatbots WHERE id=?", (bot_id,)).fetchone()
    if not bot:
        db.close()
        return jsonify({"error": "not found"}), 404
    fields = [
        "name",
        "system_prompt",
        "greeting",
        "position",
        "theme",
        "primary_color",
        "bg_color",
        "text_color",
        "allowed_domains",
        "rate_per_minute",
        "rate_per_hour",
        "status",
        "model_id",
        "api_type",
        "icon",
        "icon_type",
    ]
    if "iconType" in body:
        body["icon_type"] = body.pop("iconType")
    updates = []
    values = []
    for f in fields:
        if f in body:
            updates.append(f"{f}=?")
            values.append(body[f])
    if updates:
        updates.append("updated_at=?")
        values.append(int(time.time() * 1000))
        values.append(bot_id)
        db.execute(f"UPDATE chatbots SET {','.join(updates)} WHERE id=?", values)
        db.commit()
    db.close()
    return jsonify({"ok": True})


@chatbots_bp.route("/api/chatbots/<bot_id>", methods=["DELETE"])
def api_chatbot_delete(bot_id: str) -> Response:
    """Delete a chatbot and related records.

    Remove the chatbot row along with dependent messages, knowledge files, and conversations stored in SQLite.
    This endpoint performs the cleanup in one request so the frontend does not need separate deletion calls.

    Args:
        bot_id: Identifier of the chatbot to delete.

    Dependencies:
        Uses ``_get_db`` and Flask's ``jsonify``.

    Returns:
        Response: JSON response containing ``ok`` after the delete transaction completes.
    """
    db = _get_db()
    db.execute(
        "DELETE FROM chatbot_messages WHERE conversation_id IN (SELECT id FROM chatbot_conversations WHERE chatbot_id=?)",
        (bot_id,),
    )
    db.execute("DELETE FROM knowledge_files WHERE chatbot_id=?", (bot_id,))
    db.execute("DELETE FROM chatbot_conversations WHERE chatbot_id=?", (bot_id,))
    db.execute("DELETE FROM chatbots WHERE id=?", (bot_id,))
    db.commit()
    db.close()
    return jsonify({"ok": True})


@chatbots_bp.route("/api/chatbots/<bot_id>/conversations")
def api_chatbot_conversations(bot_id: str) -> Response:
    """Return recent conversations for a chatbot.

    Query up to fifty conversations for the requested chatbot ordered by newest start time first.
    The endpoint returns raw conversation rows for the chatbot detail view to render.

    Args:
        bot_id: Identifier of the chatbot whose conversations should be listed.

    Dependencies:
        Uses ``_get_db``, SQLite queries, and Flask's ``jsonify``.

    Returns:
        Response: JSON response containing a list of conversation dictionaries.
    """
    db = _get_db()
    convs = [
        dict(r)
        for r in db.execute(
            "SELECT * FROM chatbot_conversations WHERE chatbot_id=? ORDER BY started_at DESC LIMIT 50", (bot_id,)
        ).fetchall()
    ]
    db.close()
    return jsonify(convs)


@chatbots_bp.route("/api/conversations")
def api_conversations() -> Response:
    """Return conversations across chatbots with filtering and pagination.

    Apply optional chatbot and date filters, fetch the requested page of conversations, and enrich each row with preview metadata.
    The search parameter is accepted by the route interface even though the current query does not apply text filtering.

    Dependencies:
        Uses Flask's ``request`` and ``jsonify``, ``CHATBOTS_DB``, ``_get_db``, and SQLite queries.

    Returns:
        Response: JSON response containing paginated conversations and the total count.
    """
    limit = request.args.get("limit", 20, type=int)
    offset = request.args.get("offset", 0, type=int)
    chatbot_id = request.args.get("chatbot_id", "")
    search = request.args.get("search", "")
    start_date = request.args.get("start_date", type=int)
    end_date = request.args.get("end_date", type=int)

    if not CHATBOTS_DB.exists():
        return jsonify({"conversations": [], "total": 0})

    db = _get_db()
    where = []
    params = []
    if chatbot_id:
        where.append("c.chatbot_id=?")
        params.append(chatbot_id)
    if start_date:
        where.append("c.started_at>=?")
        params.append(start_date)
    if end_date:
        where.append("c.started_at<=?")
        params.append(end_date)

    where_sql = (" AND " + " AND ".join(where)) if where else ""

    total = db.execute(f"SELECT COUNT(*) FROM chatbot_conversations c WHERE 1=1{where_sql}", params).fetchone()[0]

    rows = db.execute(
        f"""SELECT c.*, b.name as chatbot_name
            FROM chatbot_conversations c
            LEFT JOIN chatbots b ON b.id = c.chatbot_id
            WHERE 1=1{where_sql}
            ORDER BY c.started_at DESC LIMIT ? OFFSET ?""",
        params + [limit, offset],
    ).fetchall()

    convs = []
    for r in rows:
        d = dict(r)
        msg = db.execute(
            "SELECT content FROM chatbot_messages WHERE conversation_id=? AND role='user' ORDER BY timestamp ASC LIMIT 1",
            (d["id"],),
        ).fetchone()
        d["first_message"] = msg[0] if msg else None
        d["duration_seconds"] = (
            (d["ended_at"] - d["started_at"]) // 1000 if d.get("ended_at") and d.get("started_at") else None
        )
        convs.append(d)

    db.close()
    return jsonify({"conversations": convs, "total": total})


@chatbots_bp.route("/api/conversations/<int:conv_id>")
def api_conversation_detail(conv_id: int) -> Response:
    """Return one conversation and its messages.

    Load the conversation row joined with chatbot metadata, then attach all messages ordered by timestamp.
    Requests for missing conversations or an absent database return a 404 error payload.

    Args:
        conv_id: Integer primary key of the conversation to retrieve.

    Dependencies:
        Uses ``CHATBOTS_DB``, ``_get_db``, SQLite queries, and Flask's ``jsonify``.

    Returns:
        Response: JSON response containing conversation metadata and its messages, or a 404 error body.
    """
    if not CHATBOTS_DB.exists():
        return jsonify({"error": "not found"}), 404
    db = _get_db()
    conv = db.execute(
        "SELECT c.*, b.name as chatbot_name FROM chatbot_conversations c LEFT JOIN chatbots b ON b.id=c.chatbot_id WHERE c.id=?",
        (conv_id,),
    ).fetchone()
    if not conv:
        db.close()
        return jsonify({"error": "not found"}), 404
    result = dict(conv)
    result["messages"] = [
        dict(m)
        for m in db.execute(
            "SELECT * FROM chatbot_messages WHERE conversation_id=? ORDER BY timestamp ASC", (conv_id,)
        ).fetchall()
    ]
    db.close()
    return jsonify(result)


@chatbots_bp.route("/api/chatbots/<bot_id>/knowledge")
def api_chatbot_knowledge(bot_id: str) -> Response:
    """Return knowledge files for a chatbot.

    Fetch uploaded knowledge records for the requested chatbot ordered by newest upload first.
    When the database file has not been created yet, the endpoint returns an empty file list.

    Args:
        bot_id: Identifier of the chatbot whose knowledge files should be listed.

    Dependencies:
        Uses ``CHATBOTS_DB``, ``_get_db``, SQLite queries, and Flask's ``jsonify``.

    Returns:
        Response: JSON response containing a ``files`` array.
    """
    if not CHATBOTS_DB.exists():
        return jsonify({"files": []})
    db = _get_db()
    files = [
        dict(r)
        for r in db.execute(
            "SELECT * FROM knowledge_files WHERE chatbot_id=? ORDER BY uploaded_at DESC", (bot_id,)
        ).fetchall()
    ]
    db.close()
    return jsonify({"files": files})


@chatbots_bp.route("/api/chatbots/<bot_id>/knowledge", methods=["POST"])
def api_chatbot_knowledge_upload(bot_id: str) -> Response:
    """Upload a knowledge file for a chatbot.

    Read the submitted file from the multipart request, decode its content as UTF-8 with replacement, and store it in SQLite.
    Requests without a file part are rejected with a 400 error payload.

    Args:
        bot_id: Identifier of the chatbot receiving the uploaded file.

    Dependencies:
        Uses Flask's ``request`` and ``jsonify`` plus ``_get_db``.

    Returns:
        Response: JSON response containing ``ok`` or a 400 error body.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    f = request.files["file"]
    content = f.read().decode("utf-8", errors="replace")
    db = _get_db()
    db.execute(
        "INSERT INTO knowledge_files (chatbot_id, filename, content, file_size) VALUES (?,?,?,?)",
        (bot_id, f.filename, content, len(content)),
    )
    db.commit()
    db.close()
    return jsonify({"ok": True})


@chatbots_bp.route("/api/chatbots/<bot_id>/knowledge/<int:file_id>", methods=["DELETE"])
def api_chatbot_knowledge_delete(bot_id: str, file_id: int) -> Response:
    """Delete a chatbot knowledge file.

    Remove the requested knowledge-file row scoped to the given chatbot id.
    The endpoint returns success after issuing the delete statement whether or not a matching row existed.

    Args:
        bot_id: Identifier of the chatbot that owns the knowledge file.
        file_id: Integer primary key of the knowledge file to delete.

    Dependencies:
        Uses ``_get_db`` and Flask's ``jsonify``.

    Returns:
        Response: JSON response containing ``ok``.
    """
    db = _get_db()
    db.execute("DELETE FROM knowledge_files WHERE id=? AND chatbot_id=?", (file_id, bot_id))
    db.commit()
    db.close()
    return jsonify({"ok": True})
