"""
Projects and Tasks routes.
"""

import json
import time
from pathlib import Path
from flask import jsonify, request

def register_projects_routes(app):
    """Register all projects and tasks routes."""

    # -------------------------------------------------------------------------
    # Projects API (Monday.com-inspired)
    # -------------------------------------------------------------------------

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

    @app.route("/api/projects", methods=["GET"])
    def api_projects_list():
        data = _load_projects()
        return jsonify(data.get("projects", []))

    @app.route("/api/projects", methods=["POST"])
    def api_projects_create():
        data = request.get_json() or {}
        projects_data = _load_projects()
        project = {
            "id": data.get("id", f"proj_{int(time.time())}"),
            "name": data.get("name", "New Project"),
            "description": data.get("description", ""),
            "status": data.get("status", "active"),
            "tasks": [],
            "createdAt": int(time.time() * 1000),
        }
        projects_data.setdefault("projects", []).append(project)
        _save_projects(projects_data)
        return jsonify(project), 201

    @app.route("/api/projects/<project_id>", methods=["GET"])
    def api_projects_get(project_id):
        projects_data = _load_projects()
        for p in projects_data.get("projects", []):
            if p.get("id") == project_id:
                return jsonify(p)
        return jsonify({"error": "Not found"}), 404

    @app.route("/api/projects/<project_id>", methods=["PUT"])
    def api_projects_update(project_id):
        data = request.get_json() or {}
        projects_data = _load_projects()
        for p in projects_data.get("projects", []):
            if p.get("id") == project_id:
                p.update({k: v for k, v in data.items() if k != "id"})
                _save_projects(projects_data)
                return jsonify(p)
        return jsonify({"error": "Not found"}), 404

    @app.route("/api/projects/<project_id>", methods=["DELETE"])
    def api_projects_delete(project_id):
        projects_data = _load_projects()
        projects_data["projects"] = [p for p in projects_data.get("projects", []) if p.get("id") != project_id]
        _save_projects(projects_data)
        return jsonify({"success": True})

    @app.route("/api/projects/<project_id>/tasks", methods=["GET"])
    def api_projects_tasks_list(project_id):
        projects_data = _load_projects()
        for p in projects_data.get("projects", []):
            if p.get("id") == project_id:
                return jsonify(p.get("tasks", []))
        return jsonify([])

    @app.route("/api/projects/<project_id>/tasks", methods=["POST"])
    def api_projects_tasks_create(project_id):
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
                    "createdAt": int(time.time() * 1000),
                }
                p.setdefault("tasks", []).append(task)
                _save_projects(projects_data)
                return jsonify(task), 201
        return jsonify({"error": "Project not found"}), 404

    @app.route("/api/projects/<project_id>/tasks/<task_id>", methods=["PUT"])
    def api_projects_tasks_update(project_id, task_id):
        data = request.get_json() or {}
        projects_data = _load_projects()
        for p in projects_data.get("projects", []):
            if p.get("id") == project_id:
                for t in p.get("tasks", []):
                    if t.get("id") == task_id:
                        t.update({k: v for k, v in data.items() if k not in ("id", "createdAt")})
                        _save_projects(projects_data)
                        return jsonify(t)
        return jsonify({"error": "Not found"}), 404

    @app.route("/api/projects/<project_id>/tasks/<task_id>", methods=["DELETE"])
    def api_projects_tasks_delete(project_id, task_id):
        projects_data = _load_projects()
        for p in projects_data.get("projects", []):
            if p.get("id") == project_id:
                p["tasks"] = [t for t in p.get("tasks", []) if t.get("id") != task_id]
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
        return jsonify(_load_todos())

    @app.route("/api/todos", methods=["POST"])
    def api_todos_create():
        data = request.get_json() or {}
        todo = {
            "id": data.get("id", f"todo_{int(time.time())}"),
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "status": data.get("status", "pending"),
            "priority": data.get("priority", "medium"),
            "createdAt": int(time.time() * 1000),
        }
        todos = _load_todos()
        todos.append(todo)
        _save_todos(todos)
        return jsonify(todo), 201

    @app.route("/api/todos/<todo_id>", methods=["PUT"])
    def api_todos_update(todo_id):
        data = request.get_json() or {}
        todos = _load_todos()
        for t in todos:
            if t.get("id") == todo_id:
                t.update({k: v for k, v in data.items() if k != "id"})
                _save_todos(todos)
                return jsonify(t)
        return jsonify({"error": "Not found"}), 404

    @app.route("/api/todos/<todo_id>", methods=["DELETE"])
    def api_todos_delete(todo_id):
        todos = _load_todos()
        todos = [t for t in todos if t.get("id") != todo_id]
        _save_todos(todos)
        return jsonify({"success": True})

    return app
