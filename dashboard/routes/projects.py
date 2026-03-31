"""Project routes."""

from __future__ import annotations

import json
import time
import uuid as _uuid
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, jsonify, request

projects_bp = Blueprint("projects", __name__)

PROJECTS_DIR: Path = Path(__file__).resolve().parent.parent / "data" / "projects"
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)


def _load_projects() -> list[dict[str, Any]]:
    """Load project records from disk.

    Read every non-private JSON file in the projects data directory and deserialize it into memory.
    Files that cannot be parsed are skipped so the list route can continue serving the remaining projects.

    Dependencies:
        Uses ``PROJECTS_DIR``, ``Path.glob``, and ``json.loads``.

    Returns:
        list[dict[str, Any]]: Parsed project dictionaries discovered on disk.

    Called by:
        ``api_projects_list`` and ``api_projects_graph``.

    Side effects:
        Reads project JSON files from ``data/projects``.
    """
    projects = []
    for f in sorted(PROJECTS_DIR.glob("*.json")):
        if f.name.startswith("_"):
            continue
        try:
            projects.append(json.loads(f.read_text()))
        except Exception:
            pass
    return projects


def _save_project(project: dict[str, Any]) -> dict[str, Any]:
    """Persist a project record to disk.

    Serialize the provided project dictionary and write it to the file named after the project id.
    The returned object is the same mapping so callers can continue working with the in-memory project state.

    Args:
        project: Project payload containing an ``id`` key and serializable values.

    Dependencies:
        Uses ``PROJECTS_DIR`` and ``json.dumps``.

    Returns:
        dict[str, Any]: The same project dictionary after it has been written.

    Called by:
        ``api_project_create``, ``api_project_update``, ``api_task_create``, ``api_task_update``,
        ``api_task_delete``, and ``api_tasks_reorder``.

    Side effects:
        Writes a project JSON file under ``data/projects``.
    """
    pid = project["id"]
    path = PROJECTS_DIR / f"{pid}.json"
    path.write_text(json.dumps(project, indent=2))
    return project


def _compute_metrics(project: dict[str, Any]) -> dict[str, Any]:
    """Compute task summary metrics for a project.

    Count tasks by status and attach a ``metrics`` block that the UI and graph endpoints can reuse.
    The function mutates the supplied project mapping in place before returning it for convenience.

    Args:
        project: Project payload whose ``tasks`` collection should be summarized.

    Dependencies:
        Uses the task status conventions stored in each project dictionary.

    Returns:
        dict[str, Any]: The same project dictionary with an added ``metrics`` field.

    Called by:
        ``api_projects_list``, ``api_projects_graph``, ``api_project_get``, ``api_project_create``,
        and ``api_project_update``.

    Side effects:
        Mutates the input project dictionary by adding or replacing ``project["metrics"]``.
    """
    tasks = project.get("tasks", [])
    total = len(tasks)
    done = sum(1 for t in tasks if t.get("status") == "done")
    blocked = sum(1 for t in tasks if t.get("status") == "blocked")
    in_progress = sum(1 for t in tasks if t.get("status") == "in_progress")
    todo = sum(1 for t in tasks if t.get("status") == "todo")
    project["metrics"] = {
        "totalTasks": total,
        "completedTasks": done,
        "blockedTasks": blocked,
        "inProgressTasks": in_progress,
        "todoTasks": todo,
        "completionPercent": round(done / total * 100) if total else 0,
    }
    return project


@projects_bp.route("/api/projects")
def api_projects_list() -> Response:
    """Return all projects with computed metrics.

    Load every stored project, derive task summary metrics for each one, and package the list for the frontend.
    This endpoint is the main collection read for the projects dashboard.

    Dependencies:
        Uses ``_load_projects``, ``_compute_metrics``, and Flask's ``jsonify``.

    Returns:
        Response: JSON response containing a ``projects`` array.
    """
    projects = _load_projects()
    for p in projects:
        _compute_metrics(p)
    return jsonify({"projects": projects})


@projects_bp.route("/api/projects/graph")
def api_projects_graph() -> Response:
    """Return project data formatted for the graph view.

    Transform projects, tasks, and tags into Cytoscape-compatible node and edge dictionaries.
    This endpoint derives display metadata from stored project fields without modifying persisted data.

    Dependencies:
        Uses ``_load_projects``, ``_compute_metrics``, and Flask's ``jsonify``.

    Returns:
        Response: JSON response containing ``nodes`` and ``edges`` collections.
    """
    projects = _load_projects()
    nodes = []
    edges = []
    tag_set = {}

    for p in projects:
        _compute_metrics(p)
        m = p.get("metrics", {})
        nodes.append(
            {
                "data": {
                    "id": p["id"],
                    "label": p["name"],
                    "type": "project",
                    "status": p.get("status", "planning"),
                    "priority": p.get("priority", "medium"),
                    "icon": p.get("icon", ""),
                    "color": p.get("color", "#6C5CE7"),
                    "progress": m.get("completionPercent", 0),
                    "totalTasks": m.get("totalTasks", 0),
                    "doneTasks": m.get("completedTasks", 0),
                    "description": (p.get("description") or "")[:120],
                }
            }
        )
        for t in p.get("tasks", []):
            tid = f"{p['id']}:{t['id']}"
            nodes.append(
                {
                    "data": {
                        "id": tid,
                        "label": t["title"],
                        "type": "task",
                        "status": t.get("status", "todo"),
                        "priority": t.get("priority", "medium"),
                        "parent_project": p["id"],
                        "deadline": t.get("deadline"),
                        "assignee": t.get("assignee"),
                        "blockedBy": t.get("blockedBy"),
                        "createdAt": t.get("createdAt"),
                    }
                }
            )
            edges.append(
                {
                    "data": {
                        "id": f"e-{p['id']}-{t['id']}",
                        "source": p["id"],
                        "target": tid,
                        "type": "has_task",
                    }
                }
            )
        for tag in p.get("tags", []):
            tag_set.setdefault(tag, []).append(p["id"])

    for tag, pids in tag_set.items():
        tag_id = f"tag:{tag}"
        nodes.append(
            {
                "data": {
                    "id": tag_id,
                    "label": tag,
                    "type": "tag",
                    "count": len(pids),
                }
            }
        )
        for pid in pids:
            edges.append(
                {
                    "data": {
                        "id": f"e-tag-{tag}-{pid}",
                        "source": pid,
                        "target": tag_id,
                        "type": "tagged",
                    }
                }
            )

    return jsonify({"nodes": nodes, "edges": edges})


@projects_bp.route("/api/projects/<project_id>")
def api_project_get(project_id: str) -> Response:
    """Return a single project by id.

    Load the matching project JSON file, compute its current task metrics, and return the full payload.
    Missing project ids produce a 404 response instead of an empty object.

    Args:
        project_id: Identifier of the project file to load.

    Dependencies:
        Uses ``PROJECTS_DIR``, ``json.loads``, ``_compute_metrics``, and Flask's ``jsonify``.

    Returns:
        Response: JSON response with the project payload or a 404 error body.
    """
    path = PROJECTS_DIR / f"{project_id}.json"
    if not path.exists():
        return jsonify({"error": "Project not found"}), 404
    project = json.loads(path.read_text())
    _compute_metrics(project)
    return jsonify(project)


@projects_bp.route("/api/projects", methods=["POST"])
def api_project_create() -> Response:
    """Create and persist a new project.

    Build a project record from the request body, fill in default values, and assign timestamps before saving.
    The response returns the created project with freshly computed task metrics.

    Dependencies:
        Uses Flask's ``request`` and ``jsonify``, plus ``_save_project`` and ``_compute_metrics``.

    Returns:
        Response: JSON response containing the created project and HTTP 201.
    """
    data: dict[str, Any] = request.json or {}
    pid = data.get("id") or str(_uuid.uuid4())[:8]
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    project = {
        "id": pid,
        "name": data.get("name", "Untitled Project"),
        "description": data.get("description", ""),
        "status": data.get("status", "planning"),
        "priority": data.get("priority", "medium"),
        "icon": data.get("icon", "🚀"),
        "color": data.get("color", "#6C5CE7"),
        "createdAt": now,
        "updatedAt": now,
        "deadline": data.get("deadline"),
        "tags": data.get("tags", []),
        "tasks": data.get("tasks", []),
    }
    _save_project(project)
    _compute_metrics(project)
    return jsonify(project), 201


@projects_bp.route("/api/projects/<project_id>", methods=["PUT"])
def api_project_update(project_id: str) -> Response:
    """Update mutable fields on an existing project.

    Read the stored project, merge any supported fields from the request body, and refresh the update timestamp.
    The endpoint preserves unspecified fields and returns the updated project state with recomputed metrics.

    Args:
        project_id: Identifier of the project to update.

    Dependencies:
        Uses ``PROJECTS_DIR``, Flask's ``request`` and ``jsonify``, plus ``_save_project`` and ``_compute_metrics``.

    Returns:
        Response: JSON response with the updated project payload or a 404 error body.
    """
    path = PROJECTS_DIR / f"{project_id}.json"
    if not path.exists():
        return jsonify({"error": "Project not found"}), 404
    project = json.loads(path.read_text())
    data: dict[str, Any] = request.json or {}
    for key in ("name", "description", "status", "priority", "icon", "color", "deadline", "tags"):
        if key in data:
            project[key] = data[key]
    project["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _save_project(project)
    _compute_metrics(project)
    return jsonify(project)


@projects_bp.route("/api/projects/<project_id>", methods=["DELETE"])
def api_project_delete(project_id: str) -> Response:
    """Delete an existing project file.

    Remove the JSON file associated with the given project id when it exists on disk.
    Requests for unknown project ids return a 404 error payload instead of silently succeeding.

    Args:
        project_id: Identifier of the project to remove.

    Dependencies:
        Uses ``PROJECTS_DIR``, ``Path.unlink``, and Flask's ``jsonify``.

    Returns:
        Response: JSON response confirming the deleted project id or a 404 error body.
    """
    path = PROJECTS_DIR / f"{project_id}.json"
    if not path.exists():
        return jsonify({"error": "Project not found"}), 404
    path.unlink()
    return jsonify({"deleted": project_id})


@projects_bp.route("/api/projects/<project_id>/tasks", methods=["POST"])
def api_task_create(project_id: str) -> Response:
    """Create a task within an existing project.

    Load the target project, assemble a task record from the request body, and append it to the project's task list.
    The endpoint updates the project's timestamp and persists the revised project file before returning the new task.

    Args:
        project_id: Identifier of the project that will receive the new task.

    Dependencies:
        Uses ``PROJECTS_DIR``, Flask's ``request`` and ``jsonify``, plus ``_save_project``.

    Returns:
        Response: JSON response containing the created task and HTTP 201, or a 404 error body.
    """
    path = PROJECTS_DIR / f"{project_id}.json"
    if not path.exists():
        return jsonify({"error": "Project not found"}), 404
    project = json.loads(path.read_text())
    data: dict[str, Any] = request.json or {}
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    task = {
        "id": data.get("id") or str(_uuid.uuid4())[:8],
        "title": data.get("title", "Untitled Task"),
        "description": data.get("description", ""),
        "status": data.get("status", "todo"),
        "priority": data.get("priority", "medium"),
        "assignee": data.get("assignee"),
        "deadline": data.get("deadline"),
        "blockedBy": data.get("blockedBy"),
        "createdAt": now,
        "updatedAt": now,
        "completedAt": None,
    }
    project.setdefault("tasks", []).append(task)
    project["updatedAt"] = now
    _save_project(project)
    return jsonify(task), 201


@projects_bp.route("/api/projects/<project_id>/tasks/<task_id>", methods=["PUT"])
def api_task_update(project_id: str, task_id: str) -> Response:
    """Update an existing task within a project.

    Find the referenced task inside the stored project payload and merge supported request fields into it.
    Completion timestamps are maintained from the submitted status so the task lifecycle stays consistent.

    Args:
        project_id: Identifier of the project containing the task.
        task_id: Identifier of the task to update.

    Dependencies:
        Uses ``PROJECTS_DIR``, Flask's ``request`` and ``jsonify``, plus ``_save_project``.

    Returns:
        Response: JSON response with the updated task, or a 404 error body for missing project or task ids.
    """
    path = PROJECTS_DIR / f"{project_id}.json"
    if not path.exists():
        return jsonify({"error": "Project not found"}), 404
    project = json.loads(path.read_text())
    data: dict[str, Any] = request.json or {}
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for task in project.get("tasks", []):
        if task["id"] == task_id:
            for key in ("title", "description", "status", "priority", "assignee", "deadline", "blockedBy"):
                if key in data:
                    task[key] = data[key]
            task["updatedAt"] = now
            if data.get("status") == "done" and not task.get("completedAt"):
                task["completedAt"] = now
            elif data.get("status") != "done":
                task["completedAt"] = None
            project["updatedAt"] = now
            _save_project(project)
            return jsonify(task)
    return jsonify({"error": "Task not found"}), 404


@projects_bp.route("/api/projects/<project_id>/tasks/<task_id>", methods=["DELETE"])
def api_task_delete(project_id: str, task_id: str) -> Response:
    """Delete a task from a project.

    Remove the task with the requested id from the stored project payload and rewrite the project file.
    The endpoint reports missing projects and missing tasks separately using 404 responses.

    Args:
        project_id: Identifier of the project containing the task.
        task_id: Identifier of the task to remove.

    Dependencies:
        Uses ``PROJECTS_DIR``, Flask's ``jsonify``, and ``_save_project``.

    Returns:
        Response: JSON response confirming the deleted task id or a 404 error body.
    """
    path = PROJECTS_DIR / f"{project_id}.json"
    if not path.exists():
        return jsonify({"error": "Project not found"}), 404
    project = json.loads(path.read_text())
    before = len(project.get("tasks", []))
    project["tasks"] = [t for t in project.get("tasks", []) if t["id"] != task_id]
    if len(project["tasks"]) == before:
        return jsonify({"error": "Task not found"}), 404
    project["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _save_project(project)
    return jsonify({"deleted": task_id})


@projects_bp.route("/api/projects/<project_id>/tasks/reorder", methods=["POST"])
def api_tasks_reorder(project_id: str) -> Response:
    """Reorder tasks within a project.

    Apply the submitted task id order to the project's current task list while preserving tasks omitted from the request.
    When the request does not include task ids, the endpoint leaves the stored project unchanged and still returns success.

    Args:
        project_id: Identifier of the project whose tasks should be reordered.

    Dependencies:
        Uses ``PROJECTS_DIR``, Flask's ``request`` and ``jsonify``, plus ``_save_project``.

    Returns:
        Response: JSON response containing ``{"ok": True}`` or a 404 error body.
    """
    path = PROJECTS_DIR / f"{project_id}.json"
    if not path.exists():
        return jsonify({"error": "Project not found"}), 404
    project = json.loads(path.read_text())
    data: dict[str, Any] = request.json or {}
    task_ids = data.get("taskIds", [])
    if task_ids:
        task_map = {t["id"]: t for t in project.get("tasks", [])}
        reordered = [task_map[tid] for tid in task_ids if tid in task_map]
        remaining = [t for t in project.get("tasks", []) if t["id"] not in task_ids]
        project["tasks"] = reordered + remaining
        _save_project(project)
    return jsonify({"ok": True})
