"""
Projects and Tasks routes.
"""

import json
import time
from pathlib import Path
from flask import jsonify, request

def register_projects_routes(app):
    """Register all projects and tasks routes."""

    def _load_projects():
        from shared import WORKSPACE
        projects_file = WORKSPACE / "projects.json"
        if projects_file.exists():
            try:
                return json.loads(projects_file.read_text())
            except Exception:
                pass
        return {"projects": []}

    def _save_projects(data):
        from shared import WORKSPACE
        projects_file = WORKSPACE / "projects.json"
        projects_file.parent.mkdir(parents=True, exist_ok=True)
        projects_file.write_text(json.dumps(data, indent=2))

    # -------------------------------------------------------------------------
    # Projects API (Monday.com-inspired)
    # -------------------------------------------------------------------------

    @app.route("/api/projects", methods=["GET"])
    def api_projects_list():
        """List all projects."""
        data = _load_projects()
        return jsonify(data.get("projects", []))

    @app.route("/api/projects", methods=["POST"])
    def api_projects_create():
        """Create a new project."""
        data = request.get_json() or {}
        projects_data = _load_projects()
        project = {
            "id": data.get("id", f"proj_{int(time.time())}"),
            "name": data.get("name", "New Project"),
            "description": data.get("description", ""),
            "status": data.get("status", "active"),
            "tasks": [],
            "columns": data.get("columns", [
                {"id": "todo", "name": "To Do", "color": "#e3e3e3"},
                {"id": "in_progress", "name": "In Progress", "color": "#fdbf6f"},
                {"id": "done", "name": "Done", "color": "#90d483"}
            ]),
            "members": data.get("members", []),
            "createdAt": int(time.time() * 1000),
            "updatedAt": int(time.time() * 1000)
        }
        projects_data.setdefault("projects", []).append(project)
        _save_projects(projects_data)
        return jsonify(project), 201

    @app.route("/api/projects/<project_id>", methods=["GET"])
    def api_projects_get(project_id):
        """Get a specific project."""
        projects_data = _load_projects()
        for p in projects_data.get("projects", []):
            if p.get("id") == project_id:
                return jsonify(p)
        return jsonify({"error": "Not found"}), 404

    @app.route("/api/projects/<project_id>", methods=["PUT"])
    def api_projects_update(project_id):
        """Update a project."""
        data = request.get_json() or {}
        projects_data = _load_projects()
        for p in projects_data.get("projects", []):
            if p.get("id") == project_id:
                p.update({k: v for k, v in data.items() if k != "id"})
                p["updatedAt"] = int(time.time() * 1000)
                _save_projects(projects_data)
                return jsonify(p)
        return jsonify({"error": "Not found"}), 404

    @app.route("/api/projects/<project_id>", methods=["DELETE"])
    def api_projects_delete(project_id):
        """Delete a project."""
        projects_data = _load_projects()
        projects_data["projects"] = [p for p in projects_data.get("projects", []) if p.get("id") != project_id]
        _save_projects(projects_data)
        return jsonify({"success": True})

    # -------------------------------------------------------------------------
    # Task Routes
    # -------------------------------------------------------------------------

    @app.route("/api/projects/<project_id>/tasks", methods=["GET"])
    def api_projects_tasks_list(project_id):
        """List all tasks in a project."""
        projects_data = _load_projects()
        for p in projects_data.get("projects", []):
            if p.get("id") == project_id:
                return jsonify(p.get("tasks", []))
        return jsonify([])

    @app.route("/api/projects/<project_id>/tasks", methods=["POST"])
    def api_projects_tasks_create(project_id):
        """Create a task in a project."""
        data = request.get_json() or {}
        projects_data = _load_projects()
        for p in projects_data.get("projects", []):
            if p.get("id") == project_id:
                task = {
                    "id": data.get("id", f"task_{int(time.time())}"),
                    "title": data.get("title", "New Task"),
                    "description": data.get("description", ""),
                    "status": data.get("status", "todo"),
                    "priority": data.get("priority", "medium"),
                    "assignee": data.get("assignee"),
                    "dueDate": data.get("dueDate"),
                    "labels": data.get("labels", []),
                    "comments": [],
                    "createdAt": int(time.time() * 1000),
                    "updatedAt": int(time.time() * 1000)
                }
                p.setdefault("tasks", []).append(task)
                p["updatedAt"] = int(time.time() * 1000)
                _save_projects(projects_data)
                return jsonify(task), 201
        return jsonify({"error": "Project not found"}), 404

    @app.route("/api/projects/<project_id>/tasks/<task_id>", methods=["GET"])
    def api_projects_tasks_get(project_id, task_id):
        """Get a specific task."""
        projects_data = _load_projects()
        for p in projects_data.get("projects", []):
            if p.get("id") == project_id:
                for t in p.get("tasks", []):
                    if t.get("id") == task_id:
                        return jsonify(t)
        return jsonify({"error": "Not found"}), 404

    @app.route("/api/projects/<project_id>/tasks/<task_id>", methods=["PUT"])
    def api_projects_tasks_update(project_id, task_id):
        """Update a task."""
        data = request.get_json() or {}
        projects_data = _load_projects()
        for p in projects_data.get("projects", []):
            if p.get("id") == project_id:
                for t in p.get("tasks", []):
                    if t.get("id") == task_id:
                        t.update({k: v for k, v in data.items() if k not in ("id", "createdAt")})
                        t["updatedAt"] = int(time.time() * 1000)
                        p["updatedAt"] = int(time.time() * 1000)
                        _save_projects(projects_data)
                        return jsonify(t)
        return jsonify({"error": "Not found"}), 404

    @app.route("/api/projects/<project_id>/tasks/<task_id>", methods=["DELETE"])
    def api_projects_tasks_delete(project_id, task_id):
        """Delete a task."""
        projects_data = _load_projects()
        for p in projects_data.get("projects", []):
            if p.get("id") == project_id:
                p["tasks"] = [t for t in p.get("tasks", []) if t.get("id") != task_id]
                p["updatedAt"] = int(time.time() * 1000)
                _save_projects(projects_data)
                return jsonify({"success": True})
        return jsonify({"error": "Not found"}), 404

    # -------------------------------------------------------------------------
    # Standalone TODO API
    # -------------------------------------------------------------------------

    def _load_todos():
        from shared import WORKSPACE
        todos_file = WORKSPACE / "todos.json"
        if todos_file.exists():
            try:
                return json.loads(todos_file.read_text())
            except Exception:
                pass
        return []

    def _save_todos(todos):
        from shared import WORKSPACE
        todos_file = WORKSPACE / "todos.json"
        todos_file.write_text(json.dumps(todos, indent=2))

    @app.route("/api/todos", methods=["GET"])
    def api_todos_list():
        """List all standalone todos."""
        return jsonify(_load_todos())

    @app.route("/api/todos", methods=["POST"])
    def api_todos_create():
        """Create a standalone todo."""
        data = request.get_json() or {}
        todo = {
            "id": data.get("id", f"todo_{int(time.time())}"),
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "status": data.get("status", "pending"),
            "priority": data.get("priority", "medium"),
            "tags": data.get("tags", []),
            "dueDate": data.get("dueDate"),
            "createdAt": int(time.time() * 1000),
            "updatedAt": int(time.time() * 1000)
        }
        todos = _load_todos()
        todos.append(todo)
        _save_todos(todos)
        return jsonify(todo), 201

    @app.route("/api/todos/<todo_id>", methods=["GET"])
    def api_todos_get(todo_id):
        """Get a specific todo."""
        todos = _load_todos()
        for t in todos:
            if t.get("id") == todo_id:
                return jsonify(t)
        return jsonify({"error": "Not found"}), 404

    @app.route("/api/todos/<todo_id>", methods=["PUT"])
    def api_todos_update(todo_id):
        """Update a todo."""
        data = request.get_json() or {}
        todos = _load_todos()
        for i, t in enumerate(todos):
            if t.get("id") == todo_id:
                todos[i].update({k: v for k, v in data.items() if k != "id"})
                todos[i]["updatedAt"] = int(time.time() * 1000)
                _save_todos(todos)
                return jsonify(todos[i])
        return jsonify({"error": "Not found"}), 404

    @app.route("/api/todos/<todo_id>", methods=["DELETE"])
    def api_todos_delete(todo_id):
        """Delete a todo."""
        todos = _load_todos()
        todos = [t for t in todos if t.get("id") != todo_id]
        _save_todos(todos)
        return jsonify({"success": True})

    @app.route("/api/todos/by-status/<status>", methods=["GET"])
    def api_todos_by_status(status):
        """Get todos by status."""
        todos = _load_todos()
        filtered = [t for t in todos if t.get("status") == status]
        return jsonify(filtered)

    return app
