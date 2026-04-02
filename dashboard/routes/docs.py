"""Docs routes."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, jsonify, request

from routes.config import REPO_DIR, WORKSPACE

docs_bp = Blueprint("docs", __name__)

DOCS_WORKSPACE: Path = WORKSPACE  # ~/.openclaw/workspace
REPO_PATH_PREFIX = "repo"
_LEGACY_REPO_PREFIXES = ("repo/", "resonantos-alpha/")

WORKSPACE_SYSTEM_FILES: set[str] = {
    "AGENTS.md",
    "SOUL.md",
    "USER.md",
    "TOOLS.md",
    "IDENTITY.md",
    "HEARTBEAT.md",
    "BOOTSTRAP.md",
}


def _repo_tree_path(*parts: str) -> str:
    """Build a stable repo-scoped docs path label."""
    return "/".join((REPO_PATH_PREFIX, *parts))


def _resolve_repo_docs_path(path: str) -> Path | None:
    """Resolve a repo-scoped docs request path to the current checkout."""
    for prefix in _LEGACY_REPO_PREFIXES:
        if path.startswith(prefix):
            return REPO_DIR / path[len(prefix) :]
    return None


def _docs_build_folder_tree(root: Path, prefix: str = "") -> list[dict[str, Any]]:
    """Build a browsable subtree for the docs explorer.

    Walk the provided directory and collect folders plus supported document and
    source files into the structure expected by the docs UI. Hidden paths and
    generated directories are skipped so the browser only exposes relevant content.

    Args:
        root: Directory to scan for child folders and files.
        prefix: Relative path prefix to attach to emitted tree entries.

    Called by:
        _docs_build_tree() when assembling each top-level docs source.

    Side effects:
        Reads directory metadata from disk.

    Returns:
        A list of folder and file metadata dictionaries for the explorer tree.
    """
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
                children = _docs_build_folder_tree(entry, rel)
                if children:
                    fc = sum(1 for c in children if c["type"] == "file") + sum(
                        c.get("fileCount", 0) for c in children if c["type"] == "folder"
                    )
                    items.append(
                        {"name": entry.name, "type": "folder", "path": rel, "children": children, "fileCount": fc}
                    )
            elif entry.suffix.lower() in (".md", ".txt", ".json", ".py", ".js", ".html", ".css"):
                try:
                    st = entry.stat()
                    items.append(
                        {
                            "name": entry.name,
                            "type": "file",
                            "path": rel,
                            "size": st.st_size,
                            "modified": int(st.st_mtime * 1000),
                        }
                    )
                except Exception:
                    pass
    except PermissionError:
        pass
    return items


def _docs_build_tree() -> list[dict[str, Any]]:
    """Assemble the full documentation tree for the dashboard.

    Gather browsable content from the repo, workspace, and memory directories
    so the docs page can present a single merged hierarchy. Each top-level
    section is labeled with metadata the frontend uses for display and counts.

    Called by:
        api_docs_tree() before returning the docs browser payload.

    Side effects:
        Reads filesystem state from the repository and workspace directories.

    Returns:
        A list of top-level tree nodes describing all available docs sources.
    """
    tree = []

    # 1. Repo docs/
    docs_dir = REPO_DIR / "docs"
    if docs_dir.exists():
        items = _docs_build_folder_tree(docs_dir, _repo_tree_path("docs"))
        if items:
            tree.append(
                {
                    "name": "docs",
                    "type": "folder",
                    "path": _repo_tree_path("docs"),
                    "icon": "📖",
                    "children": items,
                    "fileCount": sum(i.get("fileCount", 0) if i["type"] == "folder" else 1 for i in items),
                }
            )

    # 2. SSoT
    ssot_dir = REPO_DIR / "ssot"
    if ssot_dir.exists():
        items = _docs_build_folder_tree(ssot_dir, _repo_tree_path("ssot"))
        if items:
            tree.append(
                {
                    "name": "ssot",
                    "type": "folder",
                    "path": _repo_tree_path("ssot"),
                    "icon": "🗂️",
                    "children": items,
                    "fileCount": sum(i.get("fileCount", 0) if i["type"] == "folder" else 1 for i in items),
                }
            )

    # 3. Dashboard source
    dash_dir = REPO_DIR / "dashboard"
    if dash_dir.exists():
        items = _docs_build_folder_tree(dash_dir, _repo_tree_path("dashboard"))
        if items:
            tree.append(
                {
                    "name": "dashboard",
                    "type": "folder",
                    "path": _repo_tree_path("dashboard"),
                    "icon": "📊",
                    "children": items,
                    "fileCount": sum(i.get("fileCount", 0) if i["type"] == "folder" else 1 for i in items),
                }
            )

    # 4. Reference
    ref_dir = REPO_DIR / "reference"
    if ref_dir.exists():
        items = _docs_build_folder_tree(ref_dir, _repo_tree_path("reference"))
        if items:
            tree.append(
                {
                    "name": "reference",
                    "type": "folder",
                    "path": _repo_tree_path("reference"),
                    "icon": "📚",
                    "children": items,
                    "fileCount": sum(i.get("fileCount", 0) if i["type"] == "folder" else 1 for i in items),
                }
            )

    # 5. Workspace root .md files (excluding system files)
    root_docs = []
    for f in sorted(DOCS_WORKSPACE.glob("*.md")):
        if f.name not in WORKSPACE_SYSTEM_FILES:
            try:
                st = f.stat()
                root_docs.append(
                    {
                        "name": f.name,
                        "type": "file",
                        "path": f.name,
                        "size": st.st_size,
                        "modified": int(st.st_mtime * 1000),
                    }
                )
            except Exception:
                pass
    if root_docs:
        tree.append(
            {
                "name": "workspace",
                "type": "folder",
                "path": "",
                "icon": "📄",
                "children": root_docs,
                "fileCount": len(root_docs),
            }
        )

    # 6. Memory folder
    mem_dir = DOCS_WORKSPACE / "memory"
    if mem_dir.exists():
        items = _docs_build_folder_tree(mem_dir, "memory")
        if items:
            tree.append(
                {
                    "name": "memory",
                    "type": "folder",
                    "path": "memory",
                    "icon": "🧠",
                    "children": items,
                    "fileCount": sum(i.get("fileCount", 0) if i["type"] == "folder" else 1 for i in items),
                }
            )

    return tree


@docs_bp.route("/api/docs/tree")
def api_docs_tree() -> Response:
    """Return the merged docs tree payload.

    Build the current documentation hierarchy from all configured sources and
    compute the aggregate file count for the browser view. The response gives
    the frontend both the tree data and the resolved workspace root.

    Dependencies:
        Uses _docs_build_tree() and the DOCS_WORKSPACE path constant.

    Returns:
        A JSON response containing the docs tree, root path, and total file count.
    """
    tree = _docs_build_tree()
    total = sum(i.get("fileCount", 0) for i in tree)
    return jsonify({"tree": tree, "root": str(DOCS_WORKSPACE), "totalFiles": total})


@docs_bp.route("/api/docs/file")
def api_docs_file() -> Response:
    """Return the contents and metadata for a docs file.

    Resolve the requested path against the workspace or repository roots, then
    validate that the target stays inside an allowed directory before reading it.
    The response includes rendered metadata the docs viewer uses for titles and stats.

    Dependencies:
        Uses request arguments plus DOCS_WORKSPACE and REPO_DIR for path validation.

    Returns:
        A JSON response with file content and metadata, or an error response for invalid paths.
    """
    path = request.args.get("path", "")
    repo_filepath = _resolve_repo_docs_path(path)
    if path.startswith("/"):
        filepath = Path(path)
    elif repo_filepath is not None:
        filepath = repo_filepath
    else:
        filepath = DOCS_WORKSPACE / path
    try:
        resolved = filepath.resolve()
        allowed = resolved.is_relative_to(DOCS_WORKSPACE.resolve()) or resolved.is_relative_to(REPO_DIR.resolve())
        if not allowed:
            return jsonify({"error": "Access denied"}), 403
    except Exception:
        return jsonify({"error": "Invalid path"}), 403
    if not filepath.exists():
        return jsonify({"error": "File not found"}), 404
    if not filepath.is_file():
        return jsonify({"error": "Not a file"}), 400
    try:
        content = filepath.read_text(errors="replace")
        stat = filepath.stat()
        title = filepath.stem
        for line in content.split("\n")[:10]:
            if line.startswith("# "):
                title = line[2:].strip()
                break
        return jsonify(
            {
                "path": path,
                "name": filepath.name,
                "title": title,
                "content": content,
                "size": stat.st_size,
                "modified": int(stat.st_mtime * 1000),
                "wordCount": len(content.split()),
                "lineCount": content.count("\n") + 1,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@docs_bp.route("/api/docs/open-in-editor", methods=["POST"])
def api_docs_open_editor() -> Response:
    """Open a docs file in the local editor.

    Resolve the requested docs path and enforce the same workspace and repository
    boundaries used by the file viewer before launching an editor process. The
    route prefers VS Code and falls back to the system open handler when needed.

    Dependencies:
        Uses request JSON, subprocess launching, and DOCS_WORKSPACE/REPO_DIR path checks.

    Returns:
        A JSON response describing the editor used, or an error response if the file is invalid.
    """
    data: dict[str, Any] = request.get_json() or {}
    path = data.get("path", "")
    if not path:
        return jsonify({"error": "No path"}), 400
    repo_filepath = _resolve_repo_docs_path(path)
    if path.startswith("/"):
        filepath = Path(path)
    elif repo_filepath is not None:
        filepath = repo_filepath
    else:
        filepath = DOCS_WORKSPACE / path
    try:
        resolved = filepath.resolve()
        if not (resolved.is_relative_to(DOCS_WORKSPACE.resolve()) or resolved.is_relative_to(REPO_DIR.resolve())):
            return jsonify({"error": "Access denied"}), 403
    except Exception:
        return jsonify({"error": "Invalid path"}), 403
    if not filepath.exists():
        return jsonify({"error": "Not found"}), 404
    try:
        import shutil

        if shutil.which("code"):
            subprocess.Popen(["code", str(filepath)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return jsonify({"success": True, "editor": "VS Code"})
        else:
            subprocess.Popen(["open", str(filepath)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return jsonify({"success": True, "editor": "system"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@docs_bp.route("/api/docs/search")
def api_docs_search() -> Response:
    """Search docs content with simple substring matching.

    Scan the browsable markdown sources for the requested query and collect a
    small set of line-level matches per file for the docs search UI. Results are
    ranked by match count so files with denser hits appear first.

    Dependencies:
        Uses request query parameters, repository/workspace search roots, and file reads from disk.

    Returns:
        A JSON response containing matched files, snippets, the query, and result count.
    """
    q = request.args.get("q", "")
    if len(q) < 2:
        return jsonify({"results": [], "query": q, "count": 0})
    results = []
    search_term = q.lower()

    def _search_file(fp: Path, rel_path: str) -> None:
        """Collect substring matches from one candidate file.

        Read the file, locate up to five matching lines, and append a summarized
        result entry when the query appears. The helper also infers a title from
        the first markdown heading so the UI can label the hit cleanly.

        Args:
            fp: Absolute path to the file being scanned.
            rel_path: Path label returned to the frontend for the result entry.

        Called by:
            api_docs_search() while iterating over each searchable root.

        Side effects:
            Reads file contents from disk and mutates the enclosing results list.

        Returns:
            None.
        """
        try:
            content = fp.read_text(errors="replace")
            lines = content.split("\n")
            matches = []
            for i, line in enumerate(lines):
                if search_term in line.lower():
                    start, end = max(0, i - 1), min(len(lines), i + 2)
                    matches.append(
                        {"line": i + 1, "text": line.strip()[:200], "snippet": "\n".join(lines[start:end])[:300]}
                    )
                    if len(matches) >= 5:
                        break
            if matches:
                title = fp.stem
                for line in content.split("\n")[:10]:
                    if line.startswith("# "):
                        title = line[2:].strip()
                        break
                results.append(
                    {"path": rel_path, "name": fp.name, "title": title, "matches": matches, "matchCount": len(matches)}
                )
        except Exception:
            pass

    # Search all browsable sources from the current checkout plus workspace content.
    search_roots = [
        (REPO_DIR / "docs", _repo_tree_path("docs")),
        (REPO_DIR / "ssot", _repo_tree_path("ssot")),
        (REPO_DIR / "reference", _repo_tree_path("reference")),
        (DOCS_WORKSPACE / "memory", "memory"),
    ]
    for root, prefix in search_roots:
        if root.exists():
            for fp in root.rglob("*.md"):
                if len(results) >= 30:
                    break
                _search_file(fp, f"{prefix}/{fp.relative_to(root)}")

    # Root workspace docs
    for fp in DOCS_WORKSPACE.glob("*.md"):
        if len(results) >= 30:
            break
        if fp.name not in WORKSPACE_SYSTEM_FILES:
            _search_file(fp, fp.name)

    results.sort(key=lambda x: x["matchCount"], reverse=True)
    return jsonify({"results": results, "query": q, "count": len(results)})


@docs_bp.route("/api/docs/search/semantic")
def api_docs_search_semantic() -> Response:
    """Run the heuristic semantic docs search.

    Score markdown files by exact query hits, word overlap, nearby context, and
    fuzzy token similarity to produce broader search results than substring
    matching alone. The route returns the highest scoring documents with a best snippet.

    Dependencies:
        Uses request query parameters, local regex and difflib helpers, and filesystem reads.

    Returns:
        A JSON response containing scored semantic search results and query metadata.
    """
    import re
    from difflib import SequenceMatcher

    q = request.args.get("q", "")
    if len(q) < 2:
        return jsonify({"results": [], "query": q, "count": 0})
    results = []
    query_words = q.lower().split()

    def _relevance(content: str, fpath: str) -> float:
        """Score how relevant a document is to the query.

        Combine exact phrase matches, token overlap, path matches, nearby-word
        boosts, and fuzzy word similarity into a single heuristic score. The
        result is used to filter out weak hits before ranking the final response.

        Args:
            content: Full text content of the candidate file.
            fpath: Relative path label associated with the file.

        Called by:
            api_docs_search_semantic() for each markdown file under the search roots.

        Side effects:
            None.

        Returns:
            A floating-point relevance score for the candidate document.
        """
        cl = content.lower()
        fl = fpath.lower()
        score = 0.0
        if q.lower() in cl:
            score += 50.0
        wf = sum(1 for w in query_words if w in cl)
        score += (wf / len(query_words)) * 30.0
        score += sum(1 for w in query_words if w in fl) * 10.0
        for word in query_words:
            if word in cl:
                for m in re.finditer(re.escape(word), cl):
                    nearby = cl[max(0, m.start() - 100) : m.start() + 100]
                    score += sum(1 for w in query_words if w in nearby) * 2.0
        for word in query_words:
            for cw in set(re.findall(r"\b\w+\b", cl)):
                if len(cw) > 3:
                    r = SequenceMatcher(None, word, cw).ratio()
                    if 0.8 < r < 1.0:
                        score += r * 5.0
        return score

    def _snippet(content: str) -> tuple[str, int]:
        """Extract the strongest snippet for a semantic hit.

        Inspect each line for query-word density and choose the highest scoring
        location as the anchor for the returned preview. The helper includes a
        small amount of surrounding context so the result is readable in the UI.

        Args:
            content: Full text content of the candidate file.

        Called by:
            api_docs_search_semantic() after a document passes the relevance threshold.

        Side effects:
            None.

        Returns:
            A tuple of snippet text and the 1-based line number it came from.
        """
        lines = content.split("\n")
        best_i, best_s = 0, 0
        for i, line in enumerate(lines):
            ll = line.lower()
            s = sum(1 for w in query_words if w in ll)
            if q.lower() in ll:
                s += 5
            if s > best_s:
                best_s = s
                best_i = i
        start, end = max(0, best_i - 1), min(len(lines), best_i + 3)
        snip = "\n".join(lines[start:end])[:300]
        return snip, best_i + 1

    search_roots = [
        (_repo_tree_path("docs"), REPO_DIR / "docs"),
        (_repo_tree_path("ssot"), REPO_DIR / "ssot"),
        (_repo_tree_path("reference"), REPO_DIR / "reference"),
        ("memory", DOCS_WORKSPACE / "memory"),
    ]
    for prefix, root in search_roots:
        if not root.exists():
            continue
        for fp in root.rglob("*.md"):
            try:
                content = fp.read_text(errors="replace")
                rel = f"{prefix}/{fp.relative_to(root)}"
                score = _relevance(content, rel)
                if score < 5.0:
                    continue
                snip, ln = _snippet(content)
                title = fp.stem
                for line in content.split("\n")[:5]:
                    if line.startswith("# "):
                        title = line[2:].strip()
                        break
                results.append(
                    {
                        "path": rel,
                        "name": fp.name,
                        "title": title,
                        "matches": [{"line": ln, "text": snip[:200], "snippet": snip}],
                        "matchCount": 1,
                        "score": round(score, 2),
                    }
                )
            except Exception:
                continue
    results.sort(key=lambda x: x["score"], reverse=True)
    return jsonify({"query": q, "mode": "semantic", "results": results[:20], "count": len(results)})
