#!/usr/bin/env python3
"""
sync-ssot-to-dashboard.py — Deterministic SSoT → Dashboard project sync.

Reads L2 SSoT docs, extracts project metadata and task checklists,
generates dashboard-compatible JSON files.

Zero tokens. Fully deterministic. Run via cron or git hook.

Usage:
    python3 tools/sync-ssot-to-dashboard.py [--dry-run]
"""

import json
import os
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SSOT_L2 = REPO_ROOT / "ssot" / "L2"
PROJECTS_DIR = REPO_ROOT / "dashboard" / "data" / "projects"

# ── Project registry: maps SSoT docs → dashboard project IDs ──
# Each entry: ssot_path (relative to L2), project_id, icon, color, priority
PROJECT_MAP = [
    {
        "id": "resonantos",
        "name": "ResonantOS",
        "icon": "🧠",
        "color": "#6C5CE7",
        "priority": "critical",
        "sources": [
            "SSOT-L2-R-MEMORY.md",
            "SSOT-L2-STAGING-ENVIRONMENT.md",
            "SSOT-L2-DOCS-SYNC.md",
            "SSOT-L2-RESONANTOS-WEBSITE.md",
            "resonantos-product/SSOT-L2-RESONANTOS-PRODUCT.md",
        ],
        "tags": ["core", "infrastructure", "memory", "dashboard"],
    },
    {
        "id": "resonant-economy-dao",
        "name": "Resonant Economy & DAO",
        "icon": "🏛️",
        "color": "#00b894",
        "priority": "high",
        "sources": [
            "SSOT-L2-WALLET-DAO.md",
            "token-economy/SSOT-L2-TOKEN-ECONOMY-PHASE1.md",
            "dao/SSOT-L2-DAO-ORCHESTRATION.md",
        ],
        "tags": ["solana", "nft", "dao", "tokens", "wallet"],
    },
    {
        "id": "content-brand",
        "name": "Content & Brand",
        "icon": "🎬",
        "color": "#e17055",
        "priority": "high",
        "sources": [
            "content-strategy/SSOT-L2-CONTENT-STRATEGY.md",
            "brand/SSOT-L2-BRAND-NARRATIVE-GUIDE.md",
            "brand/SSOT-L2-BRAND-REGISTRY.md",
            "brand/SSOT-L2-RESONANT-LEXICON.md",
            "creative-dna/SSOT-L2-CREATIVE-DNA.md",
            "community/SSOT-L2-COMMUNITY.md",
        ],
        "tags": ["youtube", "brand", "content", "community"],
    },
    {
        "id": "agents-ai",
        "name": "Agents & AI Architecture",
        "icon": "🤖",
        "color": "#0984e3",
        "priority": "medium",
        "sources": [
            "agents/SSOT-L2-CAPABILITIES-AUDIT.md",
            "agents/SSOT-L2-AGENT-CONTENT-VOICE.md",
            "agents/SSOT-L2-AGENT-WEBSITE.md",
            "agents/SSOT-L2-AGENT-DAO.md",
            "agents/SSOT-L2-SKILL-CANDIDATES.md",
            "agi-strategy/SSOT-L2-AGI-STRATEGY.md",
        ],
        "tags": ["agents", "orchestration", "codex", "swarm"],
    },
    {
        "id": "staging-env",
        "name": "Staging Environment",
        "icon": "🖥️",
        "color": "#fdcb6e",
        "priority": "high",
        "sources": [
            "SSOT-L2-STAGING-ENVIRONMENT.md",
        ],
        "tags": ["infrastructure", "testing", "linux", "mini-pc"],
    },
]


def extract_metadata(content: str) -> dict:
    """Extract metadata table fields from SSoT doc header."""
    meta = {}
    # Match | Key | Value | patterns
    for m in re.finditer(r"\|\s*\*?\*?(\w[\w\s]*?)\*?\*?\s*\|\s*(.+?)\s*\|", content):
        key = m.group(1).strip().lower()
        val = m.group(2).strip()
        if key in ("status", "id", "created", "updated", "stale after", "level"):
            meta[key] = val
    return meta


def extract_checklist_tasks(content: str, source_file: str) -> list:
    """Extract - [ ] and - [x] items as tasks."""
    tasks = []
    for m in re.finditer(r"^[-*]\s+\[([ xX])\]\s+(.+)$", content, re.MULTILINE):
        checked = m.group(1).lower() == "x"
        title = m.group(2).strip()
        # Detect blocked (strikethrough or explicit "blocked" mention)
        is_blocked = "~~" in title or "(blocked)" in title.lower()
        title = re.sub(r"~~(.+?)~~", r"\1", title)  # remove strikethrough markers
        
        status = "done" if checked else ("blocked" if is_blocked else "todo")
        tasks.append({
            "id": re.sub(r"[^a-z0-9]", "-", title.lower()[:60]).strip("-"),
            "title": title,
            "description": f"Source: {source_file}",
            "status": status,
            "priority": "medium",
            "assignee": None,
            "deadline": None,
            "blockedBy": None,
            "createdAt": None,
            "updatedAt": None,
            "completedAt": None,
        })
    return tasks


def extract_status_table_tasks(content: str, source_file: str) -> list:
    """Extract tasks from status tables like | Component | ✅ Live | ... |"""
    tasks = []
    # Match table rows with status indicators
    for m in re.finditer(
        r"\|\s*(.+?)\s*\|\s*(✅|⚠️|❌|🔧|📋|🚧|⏳|Active|Live|Done|Planned|WIP|In Progress|Not started|Blocked|Complete[d]?)\s*([^|]*)\|",
        content,
    ):
        name = m.group(1).strip()
        status_marker = m.group(2).strip()
        notes = m.group(3).strip().rstrip("|").strip()
        
        # Skip header rows
        if name.startswith("--") or name.lower() in ("component", "item", "feature", "field", "aspect"):
            continue
        
        # Map status
        done_markers = {"✅", "Done", "Live", "Active", "Completed", "Complete"}
        blocked_markers = {"❌", "Blocked"}
        wip_markers = {"🔧", "🚧", "⏳", "WIP", "In Progress"}
        
        if status_marker in done_markers:
            status = "done"
        elif status_marker in blocked_markers:
            status = "blocked"
        elif status_marker in wip_markers:
            status = "in_progress"
        else:
            status = "todo"
        
        title = f"{name}"
        if notes:
            title += f" — {notes[:80]}"
        
        tasks.append({
            "id": re.sub(r"[^a-z0-9]", "-", name.lower()[:60]).strip("-"),
            "title": title,
            "description": f"Source: {source_file}",
            "status": status,
            "priority": "medium",
            "assignee": None,
            "deadline": None,
            "blockedBy": None,
            "createdAt": None,
            "updatedAt": None,
            "completedAt": None,
        })
    return tasks


def extract_section_headers_as_context(content: str) -> list:
    """Extract ## headers for context."""
    return re.findall(r"^##\s+(.+)$", content, re.MULTILINE)


def build_project(project_def: dict) -> dict:
    """Build a complete dashboard project from SSoT sources."""
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    all_tasks = []
    latest_status = "planning"
    description_parts = []
    
    for src in project_def["sources"]:
        src_path = SSOT_L2 / src
        if not src_path.exists():
            continue
        
        content = src_path.read_text()
        meta = extract_metadata(content)
        
        # Extract tasks from both formats
        checklist = extract_checklist_tasks(content, src)
        table_tasks = extract_status_table_tasks(content, src)
        
        # Prefer checklist if available, otherwise use table
        tasks = checklist if checklist else table_tasks
        all_tasks.extend(tasks)
        
        # Determine project status from metadata
        doc_status = meta.get("status", "").lower()
        if doc_status in ("active", "production"):
            latest_status = "active"
        elif doc_status == "planned" and latest_status != "active":
            latest_status = "planning"
        
        # Build description from first meaningful paragraph
        lines = content.split("\n")
        for line in lines:
            if line.strip() and not line.startswith("#") and not line.startswith("|") and not line.startswith("-") and not line.startswith(">") and not line.startswith("```"):
                description_parts.append(line.strip())
                break
    
    # Deduplicate tasks by id
    seen = set()
    unique_tasks = []
    for t in all_tasks:
        if t["id"] not in seen:
            seen.add(t["id"])
            t["createdAt"] = now
            t["updatedAt"] = now
            if t["status"] == "done":
                t["completedAt"] = now
            unique_tasks.append(t)
    
    project = {
        "id": project_def["id"],
        "name": project_def["name"],
        "description": " ".join(description_parts[:3]) if description_parts else "",
        "status": latest_status,
        "priority": project_def["priority"],
        "icon": project_def["icon"],
        "color": project_def["color"],
        "createdAt": now,
        "updatedAt": now,
        "deadline": None,
        "tags": project_def["tags"],
        "tasks": unique_tasks,
        "_generated": True,
        "_generatedAt": now,
        "_sources": project_def["sources"],
    }
    return project


def main():
    dry_run = "--dry-run" in sys.argv
    
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    
    projects = []
    for pdef in PROJECT_MAP:
        project = build_project(pdef)
        projects.append(project)
        
        total = len(project["tasks"])
        done = sum(1 for t in project["tasks"] if t["status"] == "done")
        blocked = sum(1 for t in project["tasks"] if t["status"] == "blocked")
        wip = sum(1 for t in project["tasks"] if t["status"] == "in_progress")
        todo = sum(1 for t in project["tasks"] if t["status"] == "todo")
        pct = round(done / total * 100) if total else 0
        
        print(f"  {project['icon']} {project['name']}: {total} tasks ({done} done, {wip} wip, {blocked} blocked, {todo} todo) [{pct}%]")
        
        if not dry_run:
            out_path = PROJECTS_DIR / f"{project['id']}.json"
            out_path.write_text(json.dumps(project, indent=2))
            print(f"    → wrote {out_path.relative_to(REPO_ROOT)}")
    
    if dry_run:
        print("\n[DRY RUN] No files written.")
    else:
        print(f"\n✅ Synced {len(projects)} projects to {PROJECTS_DIR.relative_to(REPO_ROOT)}/")


if __name__ == "__main__":
    main()
