"""Todo routes."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, jsonify, request

from routes.projects import _load_projects

todo_bp = Blueprint("todo", __name__)

TODOS_FILE: Path = Path(__file__).parent.parent / "data" / "todos.json"


def _load_standalone_todos() -> list[dict[str, Any]]:
    """Load standalone todo records from disk.

    Read the JSON file that stores todos which are not attached to any project
    board and return its decoded contents. Missing storage is treated as an
    empty list so the todo API can operate without prior initialization.

    Called by:
        All standalone todo routes and `api_todo_list()`.

    Side effects:
        Reads `TODOS_FILE` from disk.

    Returns:
        list[dict[str, Any]]: Stored standalone todo objects.
    """
    if TODOS_FILE.exists():
        return json.loads(TODOS_FILE.read_text())
    return []


def _save_standalone_todos(todos: list[dict[str, Any]]) -> None:
    """Persist standalone todo records to disk.

    Ensure the data directory exists and overwrite the standalone todo JSON
    file with the latest list. The helper keeps standalone todo state outside
    the project JSON files.

    Called by:
        Standalone create, update, and delete routes in this module.

    Side effects:
        Creates the parent directory if needed and writes `TODOS_FILE`.

    Returns:
        None: This helper only performs file-system persistence.
    """
    TODOS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TODOS_FILE.write_text(json.dumps(todos, indent=2))


@todo_bp.route("/api/todo")
def api_todo_list() -> Response:
    """Merge project tasks and standalone todos into one list.

    Read every project task plus the standalone todo file, normalize their
    shared fields, and sort the combined collection for the dashboard view.
    Incomplete items are surfaced first, then ordered by priority and deadline.

    Dependencies:
        `_load_projects()`, `_load_standalone_todos()`, and local sort logic.

    Returns:
        Response: JSON object containing merged todo items and their count.
    """
    items: list[dict[str, Any]] = []
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    # Pull tasks from all projects
    projects = _load_projects()
    for p in projects:
        color = p.get("color", "#ffffff")
        pname = p.get("name", "")
        pid = p.get("id", "")
        icon = p.get("icon", "")
        for t in p.get("tasks", []):
            items.append(
                {
                    **t,
                    "projectId": pid,
                    "projectName": pname,
                    "projectIcon": icon,
                    "projectColor": color,
                    "source": "project",
                }
            )

    # Standalone todos
    for t in _load_standalone_todos():
        items.append(
            {
                **t,
                "projectId": None,
                "projectName": None,
                "projectIcon": None,
                "projectColor": "#ffffff",
                "source": "standalone",
            }
        )

    # Sort: incomplete first, then by priority, then by deadline
    def sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
        """Build the sort key used by the combined todo list.

        Rank unfinished items ahead of completed ones, then apply the shared
        priority ordering and deadline fallback used by the todo page. The key
        shape matches the multi-field ordering required by `list.sort()`.

        Called by:
            `api_todo_list()` while sorting merged project and standalone items.

        Side effects:
            None.

        Returns:
            tuple[int, int, str]: Sort tuple of completion state, priority, and
            deadline string.
        """
        done = 1 if item.get("status") == "done" else 0
        prio = priority_order.get(item.get("priority", "medium"), 2)
        dl = item.get("deadline") or "9999-12-31"
        return (done, prio, dl)

    items.sort(key=sort_key)
    return jsonify({"items": items, "count": len(items)})


@todo_bp.route("/api/todo/standalone", methods=["POST"])
def api_todo_create_standalone() -> Response:
    """Create a new standalone todo item.

    Validate the incoming title, generate a short id, stamp creation metadata,
    and append the new item to the standalone todo store. This route manages
    todos that live outside any project board.

    Dependencies:
        request JSON payload, `_load_standalone_todos()`,
        `_save_standalone_todos()`, `uuid`, and `datetime.now()`.

    Returns:
        Response: JSON representation of the created todo or a 400 error when
        the title is missing.
    """
    data: dict[str, Any] = request.json or {}
    if not data.get("title"):
        return jsonify({"error": "Title required"}), 400
    todos = _load_standalone_todos()
    import uuid

    todo = {
        "id": str(uuid.uuid4())[:8],
        "title": data["title"],
        "description": data.get("description", ""),
        "status": data.get("status", "todo"),
        "priority": data.get("priority", "medium"),
        "deadline": data.get("deadline"),
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    todos.append(todo)
    _save_standalone_todos(todos)
    return jsonify(todo), 201


@todo_bp.route("/api/todo/standalone/<todo_id>", methods=["PUT"])
def api_todo_update_standalone(todo_id: str) -> Response:
    """Update fields on an existing standalone todo.

    Find the stored todo by id, apply any provided mutable fields, and refresh
    the update timestamp before saving the list back to disk. When the status
    first changes to `done`, the route also stamps `completedAt`.

    Dependencies:
        `todo_id`, request JSON payload, `_load_standalone_todos()`,
        `_save_standalone_todos()`, and `datetime.now()`.

    Returns:
        Response: JSON representation of the updated todo or a 404 error when
        the id is unknown.
    """
    todos = _load_standalone_todos()
    for t in todos:
        if t["id"] == todo_id:
            data: dict[str, Any] = request.json or {}
            for k in ("title", "description", "status", "priority", "deadline"):
                if k in data:
                    t[k] = data[k]
            t["updatedAt"] = datetime.now(timezone.utc).isoformat()
            if data.get("status") == "done" and not t.get("completedAt"):
                t["completedAt"] = datetime.now(timezone.utc).isoformat()
            _save_standalone_todos(todos)
            return jsonify(t)
    return jsonify({"error": "Not found"}), 404


@todo_bp.route("/api/todo/standalone/<todo_id>", methods=["DELETE"])
def api_todo_delete_standalone(todo_id: str) -> Response:
    """Delete a standalone todo by id.

    Filter the stored standalone todo list to remove the matching item and
    persist the remaining records. The route is idempotent in practice because
    deleting a missing id still writes the filtered list and returns success.

    Dependencies:
        `todo_id`, `_load_standalone_todos()`, and `_save_standalone_todos()`.

    Returns:
        Response: JSON confirmation payload indicating the delete operation ran.
    """
    todos = _load_standalone_todos()
    todos = [t for t in todos if t["id"] != todo_id]
    _save_standalone_todos(todos)
    return jsonify({"ok": True})
