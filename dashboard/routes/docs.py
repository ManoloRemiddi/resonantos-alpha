"""
Docs routes - browse, read, and search documentation.
"""

import os
from pathlib import Path
from flask import jsonify, request

def register_docs_routes(app):
    """Register all docs routes."""

    def _get_repo_dir():
        return Path.home() / "resonantos-alpha"

    def _get_workspace():
        from shared import WORKSPACE
        return WORKSPACE

    def _build_folder_tree(root, prefix=""):
        """Recursively build a file tree for docs browsing."""
        SKIP = {"node_modules", "target", "dist", "build", "__pycache__", "venv", ".venv", ".git", "media"}
        items = []
        if not root.exists() or not root.is_dir():
            return items
        try:
            for entry in sorted(root.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                if entry.name.startswith(".") or entry.name in SKIP:
                    continue
                rel = f"{prefix}/{entry.name}" if prefix else entry.name
                if entry.is_dir():
                    children = _build_folder_tree(entry, rel)
                    if children:
                        fc = sum(1 for c in children if c["type"] == "file") + sum(c.get("fileCount", 0) for c in children if c["type"] == "folder")
                        items.append({"name": entry.name, "type": "folder", "path": rel, "children": children, "fileCount": fc})
                elif entry.suffix.lower() in (".md", ".txt", ".json", ".py", ".js", ".html", ".css"):
                    try:
                        st = entry.stat()
                        items.append({"name": entry.name, "type": "file", "path": rel, "size": st.st_size, "modified": int(st.st_mtime * 1000)})
                    except Exception:
                        pass
        except PermissionError:
            pass
        return items

    def _build_tree():
        """Build full docs tree from workspace sources."""
        repo_dir = _get_repo_dir()
        workspace = _get_workspace()
        tree = []

        WORKSPACE_SYSTEM_FILES = {
            "AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md", "IDENTITY.md",
            "HEARTBEAT.md", "BOOTSTRAP.md",
        }

        # 1. Repo docs/
        docs_dir = repo_dir / "docs"
        if docs_dir.exists():
            items = _build_folder_tree(docs_dir, "resonantos-alpha/docs")
            if items:
                fc = sum(i.get("fileCount", 0) if i["type"] == "folder" else 1 for i in items)
                tree.append({"name": "docs", "type": "folder", "path": "resonantos-alpha/docs", "icon": "📖", "children": items, "fileCount": fc})

        # 2. SSoT
        ssot_dir = repo_dir / "ssot"
        if ssot_dir.exists():
            items = _build_folder_tree(ssot_dir, "resonantos-alpha/ssot")
            if items:
                fc = sum(i.get("fileCount", 0) if i["type"] == "folder" else 1 for i in items)
                tree.append({"name": "ssot", "type": "folder", "path": "resonantos-alpha/ssot", "icon": "🗂️", "children": items, "fileCount": fc})

        # 3. Dashboard source
        dash_dir = repo_dir / "dashboard"
        if dash_dir.exists():
            items = _build_folder_tree(dash_dir, "resonantos-alpha/dashboard")
            if items:
                fc = sum(i.get("fileCount", 0) if i["type"] == "folder" else 1 for i in items)
                tree.append({"name": "dashboard", "type": "folder", "path": "resonantos-alpha/dashboard", "icon": "🖥️", "children": items, "fileCount": fc})

        # 4. Skills
        skills_dir = repo_dir / "skills"
        if skills_dir.exists():
            items = _build_folder_tree(skills_dir, "resonantos-alpha/skills")
            if items:
                fc = sum(i.get("fileCount", 0) if i["type"] == "folder" else 1 for i in items)
                tree.append({"name": "skills", "type": "folder", "path": "resonantos-alpha/skills", "icon": "🛠️", "children": items, "fileCount": fc})

        # 5. OpenClaw workspace (non-system files)
        if workspace.exists():
            ws_children = []
            for entry in workspace.iterdir():
                if entry.name in WORKSPACE_SYSTEM_FILES or entry.name.startswith("."):
                    continue
                if entry.is_dir():
                    children = _build_folder_tree(entry, f"workspace/{entry.name}")
                    if children:
                        ws_children.append({"name": entry.name, "type": "folder", "path": f"workspace/{entry.name}", "children": children, "fileCount": sum(i.get("fileCount", 0) if i["type"] == "folder" else 1 for i in children)})
                elif entry.suffix.lower() in (".md", ".txt"):
                    ws_children.append({"name": entry.name, "type": "file", "path": f"workspace/{entry.name}"})
            if ws_children:
                tree.append({"name": "workspace", "type": "folder", "path": "workspace", "icon": "📁", "children": ws_children, "fileCount": len(ws_children)})

        return tree

    def _read_file(path_str):
        """Read a doc file by path string."""
        repo_dir = _get_repo_dir()
        workspace = _get_workspace()
        path = Path(path_str)

        if path.is_absolute():
            if not str(path).startswith(str(repo_dir)) and not str(path).startswith(str(workspace)):
                return None, "Access denied"
            if path.exists():
                return path.read_text(), None
            return None, "File not found"

        if path_str.startswith("workspace/"):
            file_path = workspace / path_str[len("workspace/"):]
            if file_path.exists():
                return file_path.read_text(), None

        for prefix in ["", "resonantos-alpha/"]:
            segments = path_str.split("/")
            while segments and segments[0] in ("", "resonantos-alpha"):
                segments.pop(0)
            if segments:
                file_path = repo_dir / "/".join(segments)
                if file_path.exists():
                    return file_path.read_text(), None

        return None, "File not found"

    # -------------------------------------------------------------------------
    # Routes
    # -------------------------------------------------------------------------

    @app.route("/api/ssot/keywords")
    def api_ssot_keywords():
        """Get or update SSoT document keywords mapping (R-Awareness)."""
        import json as _json
        kw_file = _get_workspace() / "r-awareness" / "keywords.json"
        if request.method == "PUT":
            try:
                data = request.get_json() or {}
                kw_file.parent.mkdir(parents=True, exist_ok=True)
                existing = {}
                if kw_file.exists():
                    try:
                        existing = _json.loads(kw_file.read_text())
                    except Exception:
                        pass
                existing.update(data)
                kw_file.write_text(_json.dumps(existing, indent=2))
                return jsonify({"success": True})
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        else:
            if kw_file.exists():
                try:
                    return jsonify(_json.loads(kw_file.read_text()))
                except Exception:
                    pass
            return jsonify({})

    @app.route("/api/docs/tree")
    def api_docs_tree():
        """Get full docs tree."""
        return jsonify(_build_tree())

    @app.route("/api/docs/file", methods=["GET"])
    def api_docs_file():
        """Read a doc file."""
        path = request.args.get("path", "")
        content, err = _read_file(path)
        if err:
            return jsonify({"error": err}), 404
        return jsonify({"content": content, "path": path})

    @app.route("/api/docs/open-in-editor", methods=["POST"])
    def api_docs_open_editor():
        """Open a doc file in the system editor."""
        from shared import open_file_using_system
        data = request.get_json() or {}
        path = data.get("path", "")
        repo_dir = _get_repo_dir()
        workspace = _get_workspace()

        if path.startswith("workspace/"):
            file_path = workspace / path[len("workspace/"):]
        elif path.startswith("resonantos-alpha/"):
            file_path = repo_dir / path[len("resonantos-alpha/"):]
        else:
            return jsonify({"error": "Invalid path"}), 400

        success = open_file_using_system(file_path)
        return jsonify({"success": success})

    @app.route("/api/docs/search", methods=["GET"])
    def api_docs_search():
        """Search docs by content."""
        query = request.args.get("q", "").lower()
        if not query:
            return jsonify([])
        repo_dir = _get_repo_dir()
        results = []
        for root, dirs, files in os.walk(repo_dir):
            dirs[:] = [d for d in dirs if d not in ("node_modules", ".git", "venv", ".venv", "__pycache__")]
            for fn in files:
                if not fn.endswith((".md", ".txt", ".py", ".js")):
                    continue
                fp = Path(root) / fn
                try:
                    text = fp.read_text().lower()
                    if query in text:
                        rel = fp.relative_to(repo_dir)
                        results.append({
                            "name": fn,
                            "path": str(rel),
                            "preview": text[:200].replace("\n", " "),
                        })
                        if len(results) >= 20:
                            break
                except Exception:
                    pass
            if len(results) >= 20:
                break
        return jsonify(results[:20])

    @app.route("/api/docs/search/semantic", methods=["GET"])
    def api_docs_search_semantic():
        """Semantic search (placeholder)."""
        query = request.args.get("q", "")
        if not query:
            return jsonify({"results": []})
        return jsonify({"results": [], "message": "Semantic search not yet implemented"})

    @app.route("/api/docs/resolve/<path:doc_path>", methods=["GET"])
    def api_docs_resolve(doc_path):
        """Resolve a doc path to a file."""
        repo_dir = _get_repo_dir()
        candidates = [
            repo_dir / doc_path,
            repo_dir / "docs" / doc_path,
            repo_dir / "ssot" / doc_path,
        ]
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return jsonify({"path": str(candidate), "exists": True})
        return jsonify({"path": None, "exists": False}), 404

    return app
