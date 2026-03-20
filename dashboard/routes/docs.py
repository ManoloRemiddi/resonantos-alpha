"""
Docs API routes - browse, read, and search documentation.
"""

import re
from pathlib import Path
from flask import jsonify, request, send_from_directory

def docs_build_folder_tree(root, prefix=""):
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
                children = docs_build_folder_tree(entry, rel)
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


def docs_build_tree():
    """Build full docs tree from workspace sources."""
    from shared import WORKSPACE
    tree = []
    REPO_DIR = Path.home() / "resonantos-augmentor"

    WORKSPACE_SYSTEM_FILES = {
        "AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md", "IDENTITY.md",
        "HEARTBEAT.md", "BOOTSTRAP.md",
    }

    # 1. Repo docs/
    docs_dir = REPO_DIR / "docs"
    if docs_dir.exists():
        items = docs_build_folder_tree(docs_dir, "resonantos-augmentor/docs")
        if items:
            tree.append({"name": "docs", "type": "folder", "path": "resonantos-augmentor/docs", "icon": "📖", "children": items, "fileCount": sum(i.get("fileCount", 0) if i["type"] == "folder" else 1 for i in items)})

    # 2. SSoT
    ssot_dir = REPO_DIR / "ssot"
    if ssot_dir.exists():
        items = docs_build_folder_tree(ssot_dir, "resonantos-augmentor/ssot")
        if items:
            tree.append({"name": "ssot", "type": "folder", "path": "resonantos-augmentor/ssot", "icon": "🗂️", "children": items, "fileCount": sum(i.get("fileCount", 0) if i["type"] == "folder" else 1 for i in items)})

    # 3. Dashboard source
    dash_dir = REPO_DIR / "dashboard"
    if dash_dir.exists():
        items = docs_build_folder_tree(dash_dir, "resonantos-augmentor/dashboard")
        if items:
            tree.append({"name": "dashboard", "type": "folder", "path": "resonantos-augmentor/dashboard", "icon": "🖥️", "children": items, "fileCount": sum(i.get("fileCount", 0) if i["type"] == "folder" else 1 for i in items)})

    # 4. Skills
    skills_dir = REPO_DIR / "skills"
    if skills_dir.exists():
        items = docs_build_folder_tree(skills_dir, "resonantos-augmentor/skills")
        if items:
            tree.append({"name": "skills", "type": "folder", "path": "resonantos-augmentor/skills", "icon": "🛠️", "children": items, "fileCount": sum(i.get("fileCount", 0) if i["type"] == "folder" else 1 for i in items)})

    # 5. OpenClaw workspace (non-system files)
    for ws_root in [WORKSPACE]:
        if not ws_root.exists():
            continue
        ws_children = []
        for entry in ws_root.iterdir():
            if entry.name in WORKSPACE_SYSTEM_FILES or entry.name.startswith("."):
                continue
            if entry.is_dir():
                children = docs_build_folder_tree(entry, f"workspace/{entry.name}")
                if children:
                    ws_children.append({"name": entry.name, "type": "folder", "path": f"workspace/{entry.name}", "children": children, "fileCount": sum(i.get("fileCount", 0) if i["type"] == "folder" else 1 for i in children)})
            elif entry.suffix.lower() in (".md", ".txt"):
                ws_children.append({"name": entry.name, "type": "file", "path": f"workspace/{entry.name}"})
        if ws_children:
            tree.append({"name": "workspace", "type": "folder", "path": "workspace", "icon": "📁", "children": ws_children, "fileCount": len(ws_children)})

    return tree


def docs_read_file(path_str):
    """Read a doc file by path string."""
    REPO_DIR = Path.home() / "resonantos-augmentor"
    DOCS_WORKSPACE = WORKSPACE

    path = Path(path_str)
    if path.is_absolute():
        if not str(path).startswith(str(REPO_DIR)) and not str(path).startswith(str(DOCS_WORKSPACE)):
            return None, "Access denied"
        return path.read_text(), None

    # Remove workspace/ prefix if present
    if path_str.startswith("workspace/"):
        file_path = DOCS_WORKSPACE / path_str[len("workspace/"):]
        if file_path.exists():
            return file_path.read_text(), None

    # Try repo-relative paths
    for prefix in ["", "resonantos-augmentor/"]:
        segments = path_str.split("/")
        search_root = REPO_DIR
        while segments and segments[0] in ("", "resonantos-augmentor"):
            segments.pop(0)
        if segments:
            file_path = search_root / "/".join(segments)
            if file_path.exists():
                return file_path.read_text(), None

    return None, "File not found"


def register_docs_routes(app):
    """Register all docs routes with the Flask app."""

    @app.route("/api/docs/tree")
    def api_docs_tree():
        return jsonify(docs_build_tree())

    @app.route("/api/docs/file", methods=["GET"])
    def api_docs_file():
        path = request.args.get("path", "")
        content, err = docs_read_file(path)
        if err:
            return jsonify({"error": err}), 404
        return jsonify({"content": content, "path": path})

    @app.route("/api/docs/open-in-editor", methods=["POST"])
    def api_docs_open_editor():
        from shared import open_file_using_system
        data = request.get_json() or {}
        path = data.get("path", "")
        REPO_DIR = Path.home() / "resonantos-augmentor"
        DOCS_WORKSPACE = WORKSPACE
        if path.startswith("workspace/"):
            file_path = DOCS_WORKSPACE / path[len("workspace/"):]
        elif path.startswith("resonantos-augmentor/"):
            file_path = REPO_DIR / path[len("resonantos-augmentor/"):]
        else:
            return jsonify({"error": "Invalid path"}), 400
        success = open_file_using_system(file_path)
        return jsonify({"success": success})

    @app.route("/api/docs/search", methods=["GET"])
    def api_docs_search():
        query = request.args.get("q", "").lower()
        if not query:
            return jsonify([])
        import glob as _glob
        REPO_DIR = Path.home() / "resonantos-augmentor"
        DOCS_WORKSPACE = WORKSPACE
        results = []
        for root, dirs, files in os.walk(REPO_DIR):
            dirs[:] = [d for d in dirs if d not in ("node_modules", ".git", "venv", ".venv", "__pycache__")]
            for fn in files:
                if not fn.endswith((".md", ".txt", ".py", ".js")):
                    continue
                fp = Path(root) / fn
                try:
                    text = fp.read_text().lower()
                    if query in text:
                        rel = fp.relative_to(REPO_DIR)
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
        query = request.args.get("q", "")
        if not query:
            return jsonify({"results": []})
        return jsonify({"results": [], "message": "Semantic search not yet implemented"})

    return app
