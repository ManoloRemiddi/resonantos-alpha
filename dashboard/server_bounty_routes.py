"""
DAO Bounty Board — Routes Module
Import and call register_bounty_routes(app, ctx) from server_v2.py

ctx dict should provide:
  - require_identity_nft(wallet) -> bool
  - check_rct_cap(recipient, amount) -> (bool, reason)
  - record_rct_mint(recipient, amount)
  - derive_symbiotic_pda(wallet) -> str
  - get_fee_payer(network, wallet) -> (path, label)
  - TokenManager class
  - SolanaWallet class
  - RCT_MINT: str
  - RES_MINT: str
  - RCT_DECIMALS: int
"""
import json
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import jsonify, render_template, request

ROOT_DIR = Path(__file__).parent
BOUNTIES_FILE = (ROOT_DIR / "data" / "bounties.json") if (ROOT_DIR / "data" / "bounties.json").exists() else (ROOT_DIR / "bounties.json")
TRIBES_FILE = (ROOT_DIR / "data" / "tribes.json") if (ROOT_DIR / "data" / "tribes.json").exists() else (ROOT_DIR / "tribes.json")
ACTIVE_BOUNTY_STATUSES = {"claimed", "in_progress", "review"}
STATUS_ORDER = {
    "draft": 0, "open": 1, "claimed": 2, "in_progress": 3,
    "review": 4, "verified": 5, "rewarded": 6,
}
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}
DEFAULT_TRIBE_MAX_SIZE = 12


def _now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_bounties():
    if not BOUNTIES_FILE.exists():
        return []
    try:
        data = json.loads(BOUNTIES_FILE.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_bounties(bounties):
    BOUNTIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    BOUNTIES_FILE.write_text(json.dumps(bounties, indent=2))


def _load_tribes():
    if not TRIBES_FILE.exists():
        return []
    try:
        data = json.loads(TRIBES_FILE.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_tribes(tribes):
    TRIBES_FILE.parent.mkdir(parents=True, exist_ok=True)
    TRIBES_FILE.write_text(json.dumps(tribes, indent=2))


def _find_bounty(bounty_id, bounties=None):
    bounties = bounties if bounties is not None else _load_bounties()
    for idx, bounty in enumerate(bounties):
        if bounty.get("id") == bounty_id:
            return idx, bounty
    return None, None


def _find_tribe(tribe_id, tribes=None):
    tribes = tribes if tribes is not None else _load_tribes()
    for idx, tribe in enumerate(tribes):
        if tribe.get("id") == tribe_id:
            return idx, tribe
    return None, None


def _required_reviewers(size):
    return {"small": 1, "medium": 2, "large": 3}.get(size, 1)


def _normalize_wallet(payload):
    if not isinstance(payload, dict):
        return None
    wallet = payload.get("wallet") or payload.get("walletAddress") or payload.get("address")
    return wallet.strip() if isinstance(wallet, str) and wallet.strip() else None


def _tribe_members(tribe):
    members = tribe.setdefault("members", [])
    normalized = []
    for m in members:
        if isinstance(m, str):
            normalized.append({"wallet": m, "role": "member", "joinedAt": _now_iso()})
        elif isinstance(m, dict) and m.get("wallet"):
            normalized.append({
                "wallet": m["wallet"],
                "role": m.get("role", "member"),
                "joinedAt": m.get("joinedAt", _now_iso()),
            })
    tribe["members"] = normalized
    return normalized


def _tribe_wallets(tribe):
    members = _tribe_members(tribe)
    wallets = {m["wallet"] for m in members}
    return wallets


def _tribe_counts_for_bounties(bounties):
    counts = {}
    for b in bounties:
        tribe_id = b.get("tribeId")
        if not tribe_id:
            continue
        item = counts.setdefault(tribe_id, {"active": 0, "total": 0})
        item["total"] += 1
        if b.get("status") != "rewarded":
            item["active"] += 1
    return counts


def _resolve_tribe(bounty, tribes_lookup):
    tribe_id = bounty.get("tribeId")
    if tribe_id and tribe_id in tribes_lookup:
        return tribes_lookup[tribe_id]
    return None


def _resolve_bounty_tribe_data(bounty, tribes_lookup):
    tribe = _resolve_tribe(bounty, tribes_lookup)
    if not tribe:
        return {"id": None, "name": "Unassigned", "members": [], "coordinator": None}
    data = dict(tribe)
    data["members"] = _tribe_members(data)
    return data


def _hydrate_bounty(bounty, tribes_lookup):
    hydrated = dict(bounty)
    hydrated["tribe"] = _resolve_bounty_tribe_data(bounty, tribes_lookup)
    return hydrated


def _active_bounty_count_for_wallet(wallet, bounties, tribes_lookup, exclude_id=None):
    count = 0
    for b in bounties:
        if b.get("id") == exclude_id:
            continue
        tribe = _resolve_tribe(b, tribes_lookup)
        wallets = _tribe_wallets(tribe) if tribe else set()
        wallets.update({w for w in b.get("claimedBy", []) if isinstance(w, str) and w})
        if b.get("status") in ACTIVE_BOUNTY_STATUSES and wallet in wallets:
            count += 1
    return count


def _set_status_from_team_size(bounty, tribe):
    size = bounty.get("size", "small")
    member_wallets = set(_tribe_wallets(tribe)) if tribe else set()
    member_wallets.update({w for w in bounty.get("claimedBy", []) if isinstance(w, str) and w})
    members = len(member_wallets)
    min_required = 1 if size == "small" else 3
    if members <= 0:
        bounty["status"] = "open"
        return
    if members < min_required:
        bounty["status"] = "claimed"
        return
    if bounty.get("status") in {"open", "claimed", "in_progress"}:
        bounty["status"] = "in_progress"


def _is_tribe_member(bounty, wallet, tribes_lookup):
    tribe = _resolve_tribe(bounty, tribes_lookup)
    if not tribe:
        return False
    return wallet in _tribe_wallets(tribe)


def _add_member(bounty, tribe, wallet, role="member"):
    if tribe is None:
        return False, "Tribe not found for this bounty"
    if wallet in _tribe_wallets(tribe):
        return False, "Wallet is already in this tribe"
    members = _tribe_members(tribe)
    if len(members) >= DEFAULT_TRIBE_MAX_SIZE:
        return False, "Max tribe size reached (12 entities)"
    members.append({"wallet": wallet, "role": role, "joinedAt": _now_iso()})
    claimed = bounty.setdefault("claimedBy", [])
    if wallet not in claimed:
        claimed.append(wallet)
    if not tribe.get("coordinator"):
        tribe["coordinator"] = wallet
    _set_status_from_team_size(bounty, tribe)
    bounty["updatedAt"] = _now_iso()
    return True, None


def _ensure_tribe_for_bounty(bounty, tribes):
    tribe_id = bounty.get("tribeId")
    if tribe_id:
        idx, tribe = _find_tribe(tribe_id, tribes)
        if tribe is not None:
            return idx, tribe

    next_num = 1
    existing = {t.get("id") for t in tribes}
    while f"TRIBE-{next_num:03d}" in existing:
        next_num += 1
    new_id = f"TRIBE-{next_num:03d}"
    created_at = bounty.get("createdAt") or _now_iso()
    tribe = {
        "id": new_id,
        "name": f"{bounty.get('category', 'core').title()} Collective",
        "description": f"Default tribe for {bounty.get('category', 'core')} bounties.",
        "category": bounty.get("category", "core"),
        "members": [],
        "coordinator": None,
        "activeBounties": [],
        "completedBounties": [],
        "createdAt": created_at,
        "avatar": None,
        "tags": list(dict.fromkeys(bounty.get("requiredSkills", [])))[:6],
    }
    tribes.append(tribe)
    bounty["tribeId"] = new_id
    return len(tribes) - 1, tribe


def register_bounty_routes(app, ctx=None):
    """Register all bounty-related routes on the Flask app.
    
    Args:
        app: Flask app instance.
        ctx: Dict of server helpers for on-chain integration. If None, on-chain
             features are disabled (JSON-only mode).
    """
    ctx = ctx or {}

    @app.route("/bounties")
    def bounties_page():
        return render_template("bounties.html", active_page="bounties")

    @app.route("/tribes")
    def tribes_page():
        return render_template("tribes.html", active_page="tribes")

    @app.route("/api/tribes")
    def api_tribes_list():
        tribes = _load_tribes()
        bounties = _load_bounties()
        counts = _tribe_counts_for_bounties(bounties)

        payload = []
        for tribe in tribes:
            t = dict(tribe)
            members = _tribe_members(t)
            c = counts.get(t.get("id"), {"active": 0, "total": 0})
            t["memberCount"] = len(members)
            t["activeBountyCount"] = c["active"]
            t["bountyCount"] = c["total"]
            payload.append(t)
        return jsonify({"tribes": payload, "count": len(payload)})

    @app.route("/api/tribes/<tribe_id>")
    def api_tribe_get(tribe_id):
        tribes = _load_tribes()
        idx, tribe = _find_tribe(tribe_id, tribes)
        if tribe is None:
            return jsonify({"error": "Tribe not found"}), 404

        bounties = _load_bounties()
        tribe_bounties = [b for b in bounties if b.get("tribeId") == tribe_id]
        lookup = {t.get("id"): t for t in tribes if t.get("id")}

        detail = dict(tribe)
        detail["members"] = _tribe_members(detail)
        detail["bounties"] = [_hydrate_bounty(b, lookup) for b in tribe_bounties]
        detail["activeBountyCount"] = len([b for b in tribe_bounties if b.get("status") != "rewarded"])
        detail["bountyCount"] = len(tribe_bounties)
        return jsonify(detail)

    @app.route("/api/tribes/<tribe_id>/join", methods=["POST"])
    def api_tribe_join(tribe_id):
        tribes = _load_tribes()
        idx, tribe = _find_tribe(tribe_id, tribes)
        if tribe is None:
            return jsonify({"error": "Tribe not found"}), 404

        payload = request.json or {}
        wallet = _normalize_wallet(payload)
        if not wallet:
            return jsonify({"error": "Wallet address is required"}), 400

        require_nft = ctx.get("require_identity_nft")
        if require_nft and not require_nft(wallet):
            return jsonify({"error": "Identity NFT required. Complete onboarding first."}), 403

        members = _tribe_members(tribe)
        if any(m.get("wallet") == wallet for m in members):
            return jsonify({"error": "Wallet is already in this tribe"}), 409
        if len(members) >= DEFAULT_TRIBE_MAX_SIZE:
            return jsonify({"error": "Max tribe size reached (12 entities)"}), 409

        members.append({"wallet": wallet, "role": "member", "joinedAt": _now_iso()})
        if not tribe.get("coordinator"):
            tribe["coordinator"] = wallet

        tribes[idx] = tribe
        _save_tribes(tribes)
        return jsonify(tribe)

    @app.route("/api/tribes/<tribe_id>/leave", methods=["POST"])
    def api_tribe_leave(tribe_id):
        tribes = _load_tribes()
        idx, tribe = _find_tribe(tribe_id, tribes)
        if tribe is None:
            return jsonify({"error": "Tribe not found"}), 404

        payload = request.json or {}
        wallet = _normalize_wallet(payload)
        if not wallet:
            return jsonify({"error": "Wallet address is required"}), 400

        members = [m for m in _tribe_members(tribe) if m.get("wallet") != wallet]
        if len(members) == len(_tribe_members(tribe)):
            return jsonify({"error": "Wallet is not in this tribe"}), 404
        tribe["members"] = members
        if tribe.get("coordinator") == wallet:
            tribe["coordinator"] = members[0]["wallet"] if members else None

        tribes[idx] = tribe
        _save_tribes(tribes)
        return jsonify(tribe)

    @app.route("/api/bounties")
    def api_bounties_list():
        bounties = _load_bounties()
        tribes = _load_tribes()
        tribes_lookup = {t.get("id"): t for t in tribes if t.get("id")}
        status = request.args.get("status")
        category = request.args.get("category")
        priority = request.args.get("priority")
        size = request.args.get("size")
        tribe_id = request.args.get("tribeId")
        sort = request.args.get("sort", "priority")

        if status:
            bounties = [b for b in bounties if b.get("status") == status]
        if category:
            bounties = [b for b in bounties if b.get("category") == category]
        if priority:
            bounties = [b for b in bounties if b.get("priority") == priority]
        if size:
            bounties = [b for b in bounties if b.get("size") == size]
        if tribe_id:
            bounties = [b for b in bounties if b.get("tribeId") == tribe_id]

        if sort == "reward":
            bounties.sort(key=lambda b: (b.get("rewardRCT", 0), b.get("rewardRES", 0)), reverse=True)
        elif sort == "date":
            bounties.sort(key=lambda b: b.get("createdAt", ""), reverse=True)
        else:
            bounties.sort(key=lambda b: (PRIORITY_ORDER.get(b.get("priority"), 99), -STATUS_ORDER.get(b.get("status"), 0)))

        return jsonify({"bounties": [_hydrate_bounty(b, tribes_lookup) for b in bounties], "count": len(bounties)})

    @app.route("/api/bounties/<bounty_id>")
    def api_bounty_get(bounty_id):
        _, bounty = _find_bounty(bounty_id)
        if not bounty:
            return jsonify({"error": "Bounty not found"}), 404
        tribes_lookup = {t.get("id"): t for t in _load_tribes() if t.get("id")}
        return jsonify(_hydrate_bounty(bounty, tribes_lookup))

    @app.route("/api/bounties", methods=["POST"])
    def api_bounty_create():
        data = request.json or {}
        if not data.get("title"):
            return jsonify({"error": "title is required"}), 400

        bounties = _load_bounties()
        tribes = _load_tribes()
        next_num = 1
        existing = [b.get("id", "") for b in bounties]
        while f"BOUNTY-{next_num:03d}" in existing:
            next_num += 1
        bid = data.get("id") or f"BOUNTY-{next_num:03d}"
        now = _now_iso()

        bounty = {
            "id": bid,
            "title": data.get("title"),
            "description": data.get("description", ""),
            "category": data.get("category", "core"),
            "macroGoal": data.get("macroGoal", 1),
            "priority": data.get("priority", "P2"),
            "size": data.get("size", "small"),
            "status": data.get("status", "draft"),
            "rewardRCT": int(data.get("rewardRCT", 0)),
            "rewardRES": int(data.get("rewardRES", 0)),
            "acceptanceCriteria": data.get("acceptanceCriteria", []),
            "requiredSkills": data.get("requiredSkills", []),
            "teamMinSize": int(data.get("teamMinSize", 1)),
            "teamMaxSize": int(data.get("teamMaxSize", 6)),
            "createdAt": data.get("createdAt", now),
            "updatedAt": now,
            "deadline": data.get("deadline"),
            "claimedBy": data.get("claimedBy", []),
            "tribeId": data.get("tribeId"),
            "reviews": data.get("reviews", []),
            "qualityGate": data.get("qualityGate", {
                "status": "pending", "reviewers": [], "score": None,
                "verificationMethod": "peer-reviewed"
            }),
            "workspaceUrl": data.get("workspaceUrl"),
            "githubBranch": data.get("githubBranch"),
        }

        _ensure_tribe_for_bounty(bounty, tribes)
        bounties.append(bounty)
        _save_bounties(bounties)
        _save_tribes(tribes)

        tribes_lookup = {t.get("id"): t for t in tribes if t.get("id")}
        return jsonify(_hydrate_bounty(bounty, tribes_lookup)), 201

    @app.route("/api/bounties/<bounty_id>", methods=["PUT"])
    def api_bounty_update(bounty_id):
        bounties = _load_bounties()
        idx, bounty = _find_bounty(bounty_id, bounties)
        if bounty is None:
            return jsonify({"error": "Bounty not found"}), 404

        data = request.json or {}
        allowed = {
            "title", "description", "category", "macroGoal", "priority", "size", "status",
            "rewardRCT", "rewardRES", "acceptanceCriteria", "requiredSkills", "teamMinSize",
            "teamMaxSize", "deadline", "workspaceUrl", "githubBranch", "tribeId"
        }
        for k in allowed:
            if k in data:
                bounty[k] = data[k]
        bounty["updatedAt"] = _now_iso()

        bounties[idx] = bounty
        _save_bounties(bounties)
        tribes_lookup = {t.get("id"): t for t in _load_tribes() if t.get("id")}
        return jsonify(_hydrate_bounty(bounty, tribes_lookup))

    @app.route("/api/bounties/<bounty_id>", methods=["DELETE"])
    def api_bounty_delete(bounty_id):
        bounties = _load_bounties()
        idx, bounty = _find_bounty(bounty_id, bounties)
        if bounty is None:
            return jsonify({"error": "Bounty not found"}), 404
        del bounties[idx]
        _save_bounties(bounties)
        return jsonify({"deleted": bounty_id})

    @app.route("/api/bounties/<bounty_id>/claim", methods=["POST"])
    def api_bounty_claim(bounty_id):
        bounties = _load_bounties()
        tribes = _load_tribes()
        tribes_lookup = {t.get("id"): t for t in tribes if t.get("id")}
        idx, bounty = _find_bounty(bounty_id, bounties)
        if bounty is None:
            return jsonify({"error": "Bounty not found"}), 404

        payload = request.json or {}
        wallet = _normalize_wallet(payload)
        if not wallet:
            return jsonify({"error": "Wallet address is required"}), 400

        require_nft = ctx.get("require_identity_nft")
        if require_nft and not require_nft(wallet):
            return jsonify({"error": "Identity NFT required. Complete onboarding first."}), 403
        if bounty.get("status") not in {"open", "claimed", "in_progress"}:
            return jsonify({"error": f"Cannot claim in status {bounty.get('status')}"}), 409
        if _active_bounty_count_for_wallet(wallet, bounties, tribes_lookup, exclude_id=bounty_id) >= 3:
            return jsonify({"error": "Active bounty limit reached (3)"}), 409

        tribe_idx, tribe = _ensure_tribe_for_bounty(bounty, tribes)
        ok, err = _add_member(bounty, tribe, wallet, "coordinator")
        if not ok:
            return jsonify({"error": err}), 409

        tribes[tribe_idx] = tribe
        bounties[idx] = bounty
        _save_bounties(bounties)
        _save_tribes(tribes)
        tribes_lookup = {t.get("id"): t for t in tribes if t.get("id")}
        return jsonify(_hydrate_bounty(bounty, tribes_lookup))

    @app.route("/api/bounties/<bounty_id>/join", methods=["POST"])
    def api_bounty_join(bounty_id):
        bounties = _load_bounties()
        tribes = _load_tribes()
        tribes_lookup = {t.get("id"): t for t in tribes if t.get("id")}
        idx, bounty = _find_bounty(bounty_id, bounties)
        if bounty is None:
            return jsonify({"error": "Bounty not found"}), 404

        payload = request.json or {}
        wallet = _normalize_wallet(payload)
        if not wallet:
            return jsonify({"error": "Wallet address is required"}), 400

        require_nft = ctx.get("require_identity_nft")
        if require_nft and not require_nft(wallet):
            return jsonify({"error": "Identity NFT required. Complete onboarding first."}), 403
        if bounty.get("status") in {"draft", "review", "verified", "rewarded"}:
            return jsonify({"error": f"Cannot join in status {bounty.get('status')}"}), 409
        if _active_bounty_count_for_wallet(wallet, bounties, tribes_lookup, exclude_id=bounty_id) >= 3:
            return jsonify({"error": "Active bounty limit reached (3)"}), 409

        tribe_idx, tribe = _ensure_tribe_for_bounty(bounty, tribes)
        ok, err = _add_member(bounty, tribe, wallet, "member")
        if not ok:
            return jsonify({"error": err}), 409

        tribes[tribe_idx] = tribe
        bounties[idx] = bounty
        _save_bounties(bounties)
        _save_tribes(tribes)
        tribes_lookup = {t.get("id"): t for t in tribes if t.get("id")}
        return jsonify(_hydrate_bounty(bounty, tribes_lookup))

    @app.route("/api/bounties/<bounty_id>/leave", methods=["POST"])
    def api_bounty_leave(bounty_id):
        bounties = _load_bounties()
        tribes = _load_tribes()
        idx, bounty = _find_bounty(bounty_id, bounties)
        if bounty is None:
            return jsonify({"error": "Bounty not found"}), 404

        payload = request.json or {}
        wallet = _normalize_wallet(payload)
        if not wallet:
            return jsonify({"error": "Wallet address is required"}), 400
        if bounty.get("status") in {"review", "verified", "rewarded"}:
            return jsonify({"error": "Cannot leave once review has started"}), 409

        tribe_idx, tribe = _find_tribe(bounty.get("tribeId"), tribes)
        if tribe is None:
            return jsonify({"error": "Tribe not found for this bounty"}), 404
        if wallet not in _tribe_wallets(tribe):
            return jsonify({"error": "Wallet is not in this tribe"}), 404

        bounty["claimedBy"] = [w for w in bounty.get("claimedBy", []) if w != wallet]
        members = [m for m in _tribe_members(tribe) if m.get("wallet") != wallet]
        tribe["members"] = members
        if tribe.get("coordinator") == wallet:
            tribe["coordinator"] = members[0]["wallet"] if members else None

        _set_status_from_team_size(bounty, tribe)
        bounty["updatedAt"] = _now_iso()

        tribes[tribe_idx] = tribe
        bounties[idx] = bounty
        _save_bounties(bounties)
        _save_tribes(tribes)
        tribes_lookup = {t.get("id"): t for t in tribes if t.get("id")}
        return jsonify(_hydrate_bounty(bounty, tribes_lookup))

    @app.route("/api/bounties/<bounty_id>/submit", methods=["POST"])
    def api_bounty_submit(bounty_id):
        bounties = _load_bounties()
        tribes = _load_tribes()
        idx, bounty = _find_bounty(bounty_id, bounties)
        if bounty is None:
            return jsonify({"error": "Bounty not found"}), 404

        payload = request.json or {}
        wallet = _normalize_wallet(payload)
        if not wallet:
            return jsonify({"error": "Wallet address is required"}), 400
        tribes_lookup = {t.get("id"): t for t in tribes if t.get("id")}
        if not _is_tribe_member(bounty, wallet, tribes_lookup):
            return jsonify({"error": "Only tribe members can submit"}), 403
        if bounty.get("status") != "in_progress":
            return jsonify({"error": f"Bounty must be in_progress to submit (current: {bounty.get('status')})"}), 409

        tribe = _resolve_tribe(bounty, tribes_lookup)
        member_count = len(_tribe_wallets(tribe)) if tribe else 0
        min_size = 1 if bounty.get("size") == "small" else 3
        if member_count < min_size:
            return jsonify({"error": f"Minimum tribe size not met ({member_count}/{min_size})"}), 409

        bounty["status"] = "review"
        bounty["qualityGate"] = {
            "status": "pending", "reviewers": [], "score": None,
            "verificationMethod": "peer-reviewed",
        }
        bounty["updatedAt"] = _now_iso()

        bounties[idx] = bounty
        _save_bounties(bounties)
        return jsonify(_hydrate_bounty(bounty, tribes_lookup))

    @app.route("/api/bounties/<bounty_id>/review", methods=["POST"])
    def api_bounty_review(bounty_id):
        bounties = _load_bounties()
        tribes = _load_tribes()
        tribes_lookup = {t.get("id"): t for t in tribes if t.get("id")}
        idx, bounty = _find_bounty(bounty_id, bounties)
        if bounty is None:
            return jsonify({"error": "Bounty not found"}), 404
        if bounty.get("status") != "review":
            return jsonify({"error": "Bounty is not in review"}), 409

        payload = request.json or {}
        wallet = _normalize_wallet(payload)
        approve = payload.get("approve")
        score = payload.get("score")
        comments = payload.get("comments", "")
        verification_method = payload.get("verificationMethod", "peer-reviewed")

        if not wallet:
            return jsonify({"error": "Wallet address is required"}), 400
        if _is_tribe_member(bounty, wallet, tribes_lookup):
            return jsonify({"error": "Reviewers cannot be tribe members"}), 403
        if approve is None:
            return jsonify({"error": "approve (true/false) is required"}), 400
        try:
            score = int(score)
        except Exception:
            return jsonify({"error": "score must be an integer 1-5"}), 400
        if score < 1 or score > 5:
            return jsonify({"error": "score must be between 1 and 5"}), 400

        reviews = bounty.setdefault("reviews", [])
        if any(r.get("reviewerWallet") == wallet for r in reviews):
            return jsonify({"error": "Reviewer already submitted review"}), 409

        review = {
            "reviewerWallet": wallet,
            "approved": bool(approve),
            "score": score,
            "comments": comments,
            "verificationMethod": verification_method,
            "createdAt": _now_iso(),
        }
        reviews.append(review)

        needed = _required_reviewers(bounty.get("size"))
        approvals = [r for r in reviews if r.get("approved")]
        rejected = [r for r in reviews if not r.get("approved")]

        quality = bounty.setdefault("qualityGate", {})
        quality["reviewers"] = sorted({r.get("reviewerWallet") for r in reviews if r.get("reviewerWallet")})
        quality["score"] = round(sum(r.get("score", 0) for r in reviews) / len(reviews), 2)

        if len(reviews) >= needed:
            if not rejected and len(approvals) >= needed:
                quality["status"] = "passed"
                quality["verificationMethod"] = verification_method
                bounty["status"] = "verified"
            elif rejected:
                quality["status"] = "failed"
                bounty["status"] = "in_progress"
        else:
            quality["status"] = "pending"
            quality["verificationMethod"] = verification_method

        bounty["updatedAt"] = _now_iso()
        bounties[idx] = bounty
        _save_bounties(bounties)
        return jsonify({"bounty": _hydrate_bounty(bounty, tribes_lookup), "review": review, "requiredReviews": needed})

    @app.route("/api/bounties/<bounty_id>/reward", methods=["POST"])
    def api_bounty_reward(bounty_id):
        bounties = _load_bounties()
        tribes = _load_tribes()
        tribes_lookup = {t.get("id"): t for t in tribes if t.get("id")}
        idx, bounty = _find_bounty(bounty_id, bounties)
        if bounty is None:
            return jsonify({"error": "Bounty not found"}), 404

        quality = bounty.get("qualityGate", {})
        if bounty.get("status") != "verified" or quality.get("status") != "passed":
            return jsonify({"error": "Bounty must be verified and quality gate passed"}), 409

        tribe = _resolve_tribe(bounty, tribes_lookup)
        wallets = sorted(_tribe_wallets(tribe)) if tribe else []
        if not wallets:
            return jsonify({"error": "No tribe members to reward"}), 409

        total_rct = float(bounty.get("rewardRCT", 0))
        total_res = float(bounty.get("rewardRES", 0))
        split_count = len(wallets)

        per_rct = round(total_rct / split_count, 4)
        per_res = round(total_res / split_count, 4)

        TokenManager = ctx.get("TokenManager")
        SolanaWallet = ctx.get("SolanaWallet")
        derive_pda = ctx.get("derive_symbiotic_pda")
        check_cap = ctx.get("check_rct_cap")
        record_mint = ctx.get("record_rct_mint")
        rct_mint = ctx.get("RCT_MINT")
        res_mint = ctx.get("RES_MINT")
        rct_decimals = ctx.get("RCT_DECIMALS", 9)

        on_chain = bool(TokenManager and SolanaWallet and rct_mint and res_mint)
        tx_log = []
        mint_errors = []

        if on_chain:
            try:
                network = (request.json or {}).get("network", "devnet")
                token_manager = TokenManager(SolanaWallet(network=network))

                for w in wallets:
                    if check_cap:
                        can_mint, reason = check_cap(w, per_rct)
                        if not can_mint:
                            mint_errors.append({"wallet": w, "error": f"RCT cap: {reason}"})
                            continue

                    pda = derive_pda(w) if derive_pda else w

                    try:
                        rct_sig = token_manager.mint_tokens(
                            mint=rct_mint,
                            destination_owner=pda,
                            amount=int(per_rct * (10 ** rct_decimals)),
                            token_program="token2022"
                        )
                        res_sig = token_manager.mint_tokens(
                            mint=res_mint,
                            destination_owner=pda,
                            amount=int(per_res * (10 ** 6)),
                            token_program="spl"
                        )
                        tx_log.append({"wallet": w, "rctTx": str(rct_sig), "resTx": str(res_sig)})

                        if record_mint:
                            record_mint(w, per_rct)
                    except Exception as e:
                        mint_errors.append({"wallet": w, "error": str(e)})
            except Exception as e:
                traceback.print_exc()
                mint_errors.append({"global": str(e)})

        payout = {
            "triggeredAt": _now_iso(),
            "recipients": [{"wallet": w, "rct": per_rct, "res": per_res} for w in wallets],
            "totalRCT": total_rct,
            "totalRES": total_res,
            "onChain": on_chain,
            "transactions": tx_log if tx_log else None,
            "mintErrors": mint_errors if mint_errors else None,
        }

        bounty["reward"] = payout
        bounty["status"] = "rewarded"
        bounty["updatedAt"] = _now_iso()

        bounties[idx] = bounty
        _save_bounties(bounties)
        return jsonify({"ok": True, "bounty": _hydrate_bounty(bounty, tribes_lookup), "reward": payout})

    @app.route("/api/bounties/discover")
    def api_bounty_discover():
        wallet = request.args.get("wallet")
        skills = [s.strip() for s in request.args.get("skills", "").split(",") if s.strip()]

        bounties = _load_bounties()
        tribes_lookup = {t.get("id"): t for t in _load_tribes() if t.get("id")}
        open_bounties = [b for b in bounties if b.get("status") in {"open", "claimed"}]

        results = []
        for b in open_bounties:
            if wallet and _is_tribe_member(b, wallet, tribes_lookup):
                continue
            if wallet and _active_bounty_count_for_wallet(wallet, bounties, tribes_lookup) >= 3:
                break

            required = set(b.get("requiredSkills", []))
            user_skills = set(skills)
            match_count = len(required & user_skills) if user_skills else 0
            match_pct = round((match_count / len(required) * 100), 2) if required else 100

            tribe = _resolve_tribe(b, tribes_lookup)
            team_current = len(_tribe_wallets(tribe)) if tribe else 0
            team_needed = (1 if b.get("size") == "small" else 3) - team_current
            team_needed = max(0, team_needed)

            results.append({
                "id": b["id"],
                "title": b["title"],
                "category": b.get("category"),
                "priority": b.get("priority"),
                "size": b.get("size"),
                "rewardRCT": b.get("rewardRCT", 0),
                "rewardRES": b.get("rewardRES", 0),
                "requiredSkills": list(required),
                "skillMatch": match_pct,
                "teamCurrent": team_current,
                "teamNeeded": team_needed,
                "status": b.get("status"),
                "tribe": _resolve_bounty_tribe_data(b, tribes_lookup),
            })

        results.sort(key=lambda r: (-r["skillMatch"], PRIORITY_ORDER.get(r["priority"], 99)))
        return jsonify({"matches": results, "count": len(results)})

    @app.route("/api/bounties/stats")
    def api_bounty_stats():
        bounties = _load_bounties()
        tribes_lookup = {t.get("id"): t for t in _load_tribes() if t.get("id")}
        by_status = {}
        by_category = {}
        total_rct = 0
        total_res = 0
        total_rewarded_rct = 0
        total_rewarded_res = 0

        for b in bounties:
            s = b.get("status", "unknown")
            c = b.get("category", "unknown")
            by_status[s] = by_status.get(s, 0) + 1
            by_category[c] = by_category.get(c, 0) + 1
            total_rct += b.get("rewardRCT", 0)
            total_res += b.get("rewardRES", 0)
            if s == "rewarded":
                total_rewarded_rct += b.get("rewardRCT", 0)
                total_rewarded_res += b.get("rewardRES", 0)

        unique_contributors = set()
        for b in bounties:
            tribe = _resolve_tribe(b, tribes_lookup)
            if tribe:
                unique_contributors.update(_tribe_wallets(tribe))

        return jsonify({
            "totalBounties": len(bounties),
            "byStatus": by_status,
            "byCategory": by_category,
            "totalRewardPool": {"rct": total_rct, "res": total_res},
            "totalRewarded": {"rct": total_rewarded_rct, "res": total_rewarded_res},
            "uniqueContributors": len(unique_contributors),
        })
