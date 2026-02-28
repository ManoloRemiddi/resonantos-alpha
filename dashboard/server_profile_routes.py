"""
DAO Contributor Profiles — Routes Module
Import and call register_profile_routes(app) from server_v2.py
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from flask import jsonify, render_template, request

PROFILES_FILE = Path(__file__).parent / "data" / "profiles.json"


def _now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_profiles():
    if not PROFILES_FILE.exists():
        return {}
    try:
        data = json.loads(PROFILES_FILE.read_text())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_profiles(profiles):
    PROFILES_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROFILES_FILE.write_text(json.dumps(profiles, indent=2))


def register_profile_routes(app):
    """Register contributor profile routes."""

    @app.route("/tribes")
    def tribes_page():
        return render_template("tribes.html", active_page="tribes")

    @app.route("/api/profiles/<wallet>")
    def api_profile_get(wallet):
        profiles = _load_profiles()
        profile = profiles.get(wallet)
        if not profile:
            return jsonify({"error": "Profile not found"}), 404
        return jsonify(profile)

    @app.route("/api/profiles/<wallet>", methods=["PUT"])
    def api_profile_update(wallet):
        profiles = _load_profiles()
        data = request.json or {}

        existing = profiles.get(wallet, {
            "wallet": wallet,
            "createdAt": _now_iso(),
            "skills": [],
            "bio": "",
            "displayName": "",
            "bountyHistory": [],
        })

        # Update allowed fields
        if "skills" in data:
            skills = data["skills"]
            if isinstance(skills, list):
                existing["skills"] = [s.strip().lower() for s in skills if isinstance(s, str) and s.strip()][:20]
        if "bio" in data:
            existing["bio"] = str(data["bio"])[:500]
        if "displayName" in data:
            existing["displayName"] = str(data["displayName"])[:50]

        existing["updatedAt"] = _now_iso()
        existing["wallet"] = wallet
        profiles[wallet] = existing
        _save_profiles(profiles)
        return jsonify(existing)

    @app.route("/api/profiles")
    def api_profiles_list():
        profiles = _load_profiles()
        skill_filter = request.args.get("skill")
        results = list(profiles.values())

        if skill_filter:
            skill_filter = skill_filter.strip().lower()
            results = [p for p in results if skill_filter in p.get("skills", [])]

        results.sort(key=lambda p: len(p.get("skills", [])), reverse=True)
        return jsonify({"profiles": results, "count": len(results)})

    @app.route("/api/profiles/<wallet>/skills", methods=["POST"])
    def api_profile_add_skill(wallet):
        profiles = _load_profiles()
        existing = profiles.get(wallet, {
            "wallet": wallet,
            "createdAt": _now_iso(),
            "skills": [],
            "bio": "",
            "displayName": "",
        })

        data = request.json or {}
        skill = data.get("skill", "").strip().lower()
        if not skill:
            return jsonify({"error": "skill is required"}), 400

        skills = existing.get("skills", [])
        if skill in skills:
            return jsonify({"error": "Skill already added"}), 409
        if len(skills) >= 20:
            return jsonify({"error": "Max 20 skills"}), 409

        skills.append(skill)
        existing["skills"] = skills
        existing["updatedAt"] = _now_iso()
        existing["wallet"] = wallet
        profiles[wallet] = existing
        _save_profiles(profiles)
        return jsonify(existing)

    @app.route("/api/profiles/<wallet>/skills/<skill>", methods=["DELETE"])
    def api_profile_remove_skill(wallet, skill):
        profiles = _load_profiles()
        existing = profiles.get(wallet)
        if not existing:
            return jsonify({"error": "Profile not found"}), 404

        skill = skill.strip().lower()
        skills = existing.get("skills", [])
        if skill not in skills:
            return jsonify({"error": "Skill not found"}), 404

        skills.remove(skill)
        existing["skills"] = skills
        existing["updatedAt"] = _now_iso()
        profiles[wallet] = existing
        _save_profiles(profiles)
        return jsonify(existing)

    @app.route("/api/profiles/skills/popular")
    def api_profile_popular_skills():
        """Get most popular skills across all profiles."""
        profiles = _load_profiles()
        skill_counts = {}
        for p in profiles.values():
            for s in p.get("skills", []):
                skill_counts[s] = skill_counts.get(s, 0) + 1
        sorted_skills = sorted(skill_counts.items(), key=lambda x: -x[1])[:30]
        return jsonify({"skills": [{"skill": s, "count": c} for s, c in sorted_skills]})
