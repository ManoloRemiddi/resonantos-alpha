"""Logician routes."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, jsonify, request

logician_bp = Blueprint("logician", __name__)


@logician_bp.route("/api/logician/status")
def api_logician_status() -> Response:
    """Report live status for the Logician mangle server.

    Check both the expected Unix socket path and the presence of the
    `mangle-server` process to determine current service health. Return a live
    status payload with a UTC timestamp and a concise failure reason when down.

    Dependencies:
        os.path.exists: Verifies socket presence.
        subprocess.run: Checks whether the server process is running.

    Returns:
        Response: JSON status data describing the current Logician state.
    """
    import datetime
    import subprocess

    mangle_sock = "/tmp/mangle.sock"
    sock_exists = os.path.exists(mangle_sock)
    try:
        result = subprocess.run(["pgrep", "-f", "mangle-server"], capture_output=True, text=True, timeout=5)
        process_running = result.returncode == 0
    except Exception:
        process_running = False
    now = datetime.datetime.utcnow().isoformat() + "Z"
    if sock_exists and process_running:
        return jsonify({"status": "healthy", "lastCheck": now, "ok": True, "source": "live-check"})
    else:
        reasons = []
        if not sock_exists:
            reasons.append("mangle socket not found")
        if not process_running:
            reasons.append("mangle-server process not running")
        return jsonify(
            {"status": "down", "ok": False, "error": "; ".join(reasons), "lastCheck": now, "source": "live-check"}
        )


@logician_bp.route("/api/logician/rules")
def api_logician_rules() -> Response:
    """List Logician rules grouped into dashboard categories.

    Read the active `production_rules.mg` file and derive section-level fact
    and rule counts from the source currently loaded by `mangle-server`.
    Aggregate those counts into dashboard-facing categories so the settings UI
    can display rule inventory without relying on stale split files.

    Dependencies:
        os.path: Resolves the production rules file path.
        jsonify: Serializes category totals for the dashboard API response.

    Returns:
        Response: JSON payload containing categorized rule and fact totals.
    """
    rules_file = os.path.join(os.path.dirname(__file__), "..", "..", "logician", "poc", "production_rules.mg")

    # Section-name -> dashboard category mapping
    SECTION_CATEGORY = {
        "AGENT REGISTRY": ("🤖 Agent Behavior", "How agents spawn, communicate, and operate within the system"),
        "SPAWN RULES": ("🤖 Agent Behavior", "How agents spawn, communicate, and operate within the system"),
        "TOOL PERMISSIONS": (
            "🤖 Agent Behavior",
            "How agents spawn, communicate, and operate within the system",
        ),
        "DELEGATION RULES": ("📐 Protocols", "Delegation, preparation, and research workflow enforcement"),
        "COST POLICY": ("📐 Protocols", "Delegation, preparation, and research workflow enforcement"),
        "GATEWAY LIFECYCLE RULES": (
            "📐 Protocols",
            "Delegation, preparation, and research workflow enforcement",
        ),
        "SENSITIVE DATA & FORBIDDEN OUTPUT": (
            "🔒 Security",
            "Data protection, access control, and threat prevention",
        ),
        "INJECTION DETECTION": ("🔒 Security", "Data protection, access control, and threat prevention"),
        "DESTRUCTIVE PATTERNS": ("🔒 Security", "Data protection, access control, and threat prevention"),
        "FILE PROTECTION (SHIELD)": ("🔒 Security", "Data protection, access control, and threat prevention"),
        "BLOCKCHAIN SAFETY RULES": (
            "🪙 Crypto & Wallet",
            "Transaction safety, wallet protection, and blockchain operations",
        ),
    }
    KEYWORD_OVERRIDES = {
        "VERIFICATION": (
            "✅ Verification & Integrity",
            "State claim verification, atomic operations, and verification gates",
        ),
        "COHERENCE": ("💻 Code Quality", "Testing requirements, coding standards, and coherence gates"),
    }

    LOCKED_CATEGORIES = {"🔒 Security"}

    try:
        with open(rules_file) as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        return jsonify(
            {
                "categories": [],
                "totals": {"rules": 0, "facts": 0, "sections": 0, "categories": 0},
                "error": "production_rules.mg not found",
            }
        )

    sections = []
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if s.startswith("# ===") and s.endswith("===") and len(s) > 10:
            inner = s.strip("# =").strip()
            if inner and not inner.startswith("Resonant"):
                sections.append((i, inner))
                i += 1
                continue
        if (
            i + 2 < len(lines)
            and lines[i].strip().startswith("# ===")
            and lines[i + 2].strip().startswith("# ===")
            and lines[i + 1].strip().startswith("# ")
        ):
            name = lines[i + 1].strip()[2:].strip()
            sections.append((i + 1, name))
            i += 3
            continue
        i += 1

    section_stats = {}
    for idx, (line_no, name) in enumerate(sections):
        start = line_no + 1
        end = sections[idx + 1][0] - 1 if idx + 1 < len(sections) else len(lines)
        facts = rules = 0
        for raw in lines[start:end]:
            s = raw.strip()
            if not s or s.startswith("#") or s.startswith("%"):
                continue
            if ":-" in s:
                rules += 1
            elif s.endswith(".") and len(s) > 1:
                facts += 1
        section_stats[name] = {"facts": facts, "rules": rules}

    cat_data = {}
    for sec_name, stats in section_stats.items():
        mapped = None
        for kw, (cat_name, cat_desc) in KEYWORD_OVERRIDES.items():
            if kw in sec_name.upper():
                mapped = (cat_name, cat_desc)
                break
        if not mapped:
            mapped = SECTION_CATEGORY.get(sec_name)
        if not mapped:
            mapped = ("📦 Other", "Uncategorized rules")

        cat_name, cat_desc = mapped
        if cat_name not in cat_data:
            cat_data[cat_name] = {
                "description": cat_desc,
                "facts": 0,
                "rules": 0,
                "sections": 0,
                "locked": cat_name in LOCKED_CATEGORIES,
            }
        cat_data[cat_name]["facts"] += stats["facts"]
        cat_data[cat_name]["rules"] += stats["rules"]
        cat_data[cat_name]["sections"] += 1

    CATEGORY_ORDER = [
        "🤖 Agent Behavior",
        "🔒 Security",
        "📐 Protocols",
        "💻 Code Quality",
        "✅ Verification & Integrity",
        "🪙 Crypto & Wallet",
        "📦 Other",
    ]
    categories = []
    seen = set()
    for cat_name in CATEGORY_ORDER:
        if cat_name in cat_data:
            d = cat_data[cat_name]
            categories.append(
                {
                    "name": cat_name,
                    "description": d["description"],
                    "icon": cat_name.split(" ")[0],
                    "ruleCount": d["rules"],
                    "factCount": d["facts"],
                    "fileCount": d["sections"],
                    "locked": d["locked"],
                }
            )
            seen.add(cat_name)
    for cat_name, d in cat_data.items():
        if cat_name not in seen:
            categories.append(
                {
                    "name": cat_name,
                    "description": d["description"],
                    "icon": cat_name.split(" ")[0],
                    "ruleCount": d["rules"],
                    "factCount": d["facts"],
                    "fileCount": d["sections"],
                    "locked": d["locked"],
                }
            )

    total_rules = sum(d["rules"] for d in cat_data.values())
    total_facts = sum(d["facts"] for d in cat_data.values())

    return jsonify(
        {
            "categories": categories,
            "totals": {
                "rules": total_rules,
                "facts": total_facts,
                "sections": len(sections),
                "categories": len(categories),
            },
            "source": "production_rules.mg",
        }
    )


@logician_bp.route("/api/logician/rules/<section_slug>")
def api_logician_rule_section(section_slug: str) -> Response:
    """Return one named section from the active Logician rules file.

    Validate the supplied slug, scan `production_rules.mg`, and extract the
    matching section content using the same heading conventions the dashboard
    recognizes elsewhere. Count facts and rules within the extracted section so
    callers receive both the raw text and lightweight summary metadata.

    Dependencies:
        re.sub: Normalizes section headings into dashboard slugs.
        jsonify: Serializes section content and summary counts.

    Returns:
        Response: JSON payload for the requested rules section or an error.
    """
    if "/" in section_slug or "\\" in section_slug or ".." in section_slug:
        return jsonify({"error": "Invalid section slug"}), 400

    rules_file = os.path.join(os.path.dirname(__file__), "..", "..", "logician", "poc", "production_rules.mg")

    try:
        with open(rules_file) as f:
            lines = f.readlines()
    except FileNotFoundError:
        return jsonify({"error": "production_rules.mg not found"}), 404

    sections = {}
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if line.startswith("# ===") and line.endswith("===") and i + 2 < len(lines):
            name_line = lines[i + 1].rstrip()
            next_line = lines[i + 2].rstrip()
            if name_line.startswith("# ") and next_line.startswith("# ===") and next_line.endswith("==="):
                name = name_line[2:].strip()
                slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
                i += 3
                content_lines = []
                while i < len(lines):
                    cl = lines[i].rstrip()
                    if (
                        cl.startswith("# ===")
                        and cl.endswith("===")
                        and i + 1 < len(lines)
                        and lines[i + 1].rstrip().startswith("# ")
                    ):
                        break
                    content_lines.append(lines[i])
                    i += 1
                sections[slug] = {"name": name, "content": "".join(content_lines).strip()}
                continue
        if line.startswith("# === ") and line.endswith(" ==="):
            nxt = lines[min(i + 1, len(lines) - 1)].rstrip() if i + 1 < len(lines) else ""
            if not nxt.startswith("# ==="):
                name = line[6:-4].strip()
                slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
                i += 1
                content_lines = []
                while i < len(lines):
                    cl = lines[i].rstrip()
                    if cl.startswith("# ===") and cl.endswith("==="):
                        break
                    content_lines.append(lines[i])
                    i += 1
                sections[slug] = {"name": name, "content": "".join(content_lines).strip()}
                continue
        i += 1

    if section_slug not in sections:
        available = sorted(sections.keys())
        return jsonify({"error": f"Section not found: {section_slug}", "available": available}), 404

    sec = sections[section_slug]
    facts = rules_count = 0
    for cl in sec["content"].splitlines():
        stripped = cl.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("//"):
            if ":-" in stripped:
                rules_count += 1
            elif stripped.endswith("."):
                facts += 1

    return jsonify(
        {
            "slug": section_slug,
            "name": sec["name"],
            "content": sec["content"],
            "facts": facts,
            "rules": rules_count,
            "source": "production_rules.mg",
        }
    )


@logician_bp.route("/api/logician/query", methods=["POST"])
def api_logician_query() -> Response:
    """Proxy a dashboard query to the Logician service.

    Forward the incoming JSON request body to the local Logician HTTP endpoint
    and relay the service response unchanged when the call succeeds. Convert
    transport or parsing failures into the dashboard's standard JSON error
    response format.

    Dependencies:
        requests: Sends the outbound HTTP request to the Logician service.
        request.get_json: Reads the incoming dashboard request payload.

    Returns:
        Response: JSON payload returned by Logician, or an error response.
    """
    import requests as http_req

    try:
        data: dict[str, Any] | None = request.get_json()
        resp = http_req.post("http://127.0.0.1:8081/query", json=data, timeout=5)
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@logician_bp.route("/api/protocols")
def api_protocols() -> Response:
    """Return protocol data from the dashboard data store.

    Load the JSON protocol catalog from disk and expose it directly through the
    API so the frontend can render protocol metadata. Convert file or parsing
    errors into the route's standard JSON error payload.

    Dependencies:
        Path.read_text: Reads the protocols JSON file from disk.
        json.loads: Deserializes the stored protocol data.

    Returns:
        Response: JSON protocol data, or an error response on failure.
    """
    protocols_path = Path(__file__).parent.parent / "data" / "protocols.json"
    try:
        return jsonify(json.loads(protocols_path.read_text()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@logician_bp.route("/api/rules")
def api_rules() -> Response:
    """Return static rules data from the dashboard data store.

    Load the legacy `rules.json` payload from disk and return it directly for
    consumers that still use the older API shape. Fall back to an empty list
    when the file is missing instead of treating absence as a server error.

    Dependencies:
        os.path: Resolves the rules data file path.
        json.load: Deserializes the stored rules payload.

    Returns:
        Response: JSON rules data, or an empty list when the file is absent.
    """
    rules_path = os.path.join(os.path.dirname(__file__), "..", "data", "rules.json")
    try:
        with open(rules_path) as f:
            return jsonify(json.load(f))
    except FileNotFoundError:
        return jsonify([])
