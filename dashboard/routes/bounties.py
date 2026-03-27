"""Bounty routes."""

from __future__ import annotations

import traceback
from datetime import datetime, timezone
from typing import Any

from flask import Blueprint, Response, jsonify, request

from routes.shared import (
    _enrich_bounty_with_tribe,
    _load_bounties,
    _load_tribes,
    _save_bounties,
    _save_tribes,
    _sync_tribe_bounty_refs,
)
from routes.wallet_helpers import _require_identity_nft

bounties_bp = Blueprint("bounties", __name__)


@bounties_bp.route("/api/bounties", methods=["GET"])
def api_bounties_list() -> Response:
    """List bounties with optional filters and sorting.

    Read the stored bounty and tribe records, apply the requested query-parameter
    filters, and enrich each surviving bounty with tribe metadata for the board UI.
    The final collection is sorted according to the selected strategy before returning.

    Dependencies:
        Uses request query parameters plus shared bounty and tribe loading helpers.

    Returns:
        A JSON response containing the filtered bounty list and item count, or an error response.
    """
    try:
        status = request.args.get("status")
        category = request.args.get("category")
        priority = request.args.get("priority")
        size = request.args.get("size")
        tribe_id = request.args.get("tribeId")
        sort = request.args.get("sort", "priority")

        bounties = _load_bounties()
        tribes = _load_tribes()
        tribe_map = {t.get("id"): t for t in tribes}

        filtered = []
        for bounty in bounties:
            if status and bounty.get("status") != status:
                continue
            if category and bounty.get("category") != category:
                continue
            if priority and bounty.get("priority") != priority:
                continue
            if size and bounty.get("size") != size:
                continue
            if tribe_id and bounty.get("tribeId") != tribe_id:
                continue
            filtered.append(_enrich_bounty_with_tribe(bounty, tribe_map))

        if sort == "reward":
            filtered.sort(key=lambda b: (b.get("rewardRCT", 0), b.get("rewardRES", 0)), reverse=True)
        elif sort == "date":
            filtered.sort(key=lambda b: b.get("createdAt") or "", reverse=True)
        else:
            order = {"P0": 0, "P1": 1, "P2": 2}
            filtered.sort(key=lambda b: (order.get(b.get("priority"), 9), -(b.get("rewardRCT", 0))))

        return jsonify({"bounties": filtered, "count": len(filtered)})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@bounties_bp.route("/api/bounties", methods=["POST"])
def api_bounties_create() -> Response:
    """Create a new bounty record.

    Validate the incoming payload, derive the next sequential bounty ID, and
    populate the default lifecycle fields required by the bounty workflow. The
    new record is persisted immediately and returned to the client.

    Dependencies:
        Uses request JSON plus shared bounty storage helpers and UTC timestamp generation.

    Returns:
        A JSON response with the created bounty and new ID, or a validation error response.
    """
    try:
        data: dict[str, Any] | None = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        title = data.get("title")
        description = data.get("description")
        category = data.get("category", "community")
        priority = data.get("priority", "P2")
        size = data.get("size", "small")
        reward_rct = data.get("rewardRCT", 0)
        reward_res = data.get("rewardRES", 0)

        if not title or not description:
            return jsonify({"error": "title and description required"}), 400

        bounties = _load_bounties()

        max_id = 0
        for b in bounties:
            bid = b.get("id", "")
            if bid.startswith("BOUNTY-"):
                try:
                    max_id = max(max_id, int(bid.split("-")[1]))
                except Exception:
                    pass

        new_id = f"BOUNTY-{max_id + 1:03d}"
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

        new_bounty = {
            "id": new_id,
            "title": title,
            "description": description,
            "category": category,
            "macroGoal": data.get("macroGoal", 1),
            "priority": priority,
            "size": size,
            "status": "open",
            "rewardRCT": reward_rct,
            "rewardRES": reward_res,
            "acceptanceCriteria": data.get("acceptanceCriteria", []),
            "requiredSkills": data.get("requiredSkills", []),
            "teamMinSize": data.get("teamMinSize", 1),
            "teamMaxSize": data.get("teamMaxSize", 6),
            "createdAt": now,
            "deadline": data.get("deadline"),
            "claimedBy": [],
            "reviews": [],
            "qualityGate": {
                "status": "pending",
                "reviewers": [],
                "score": None,
                "verificationMethod": "peer-reviewed",
            },
            "workspaceUrl": data.get("workspaceUrl"),
            "githubBranch": data.get("githubBranch"),
            "tribeId": data.get("tribeId"),
        }

        bounties.append(new_bounty)
        _save_bounties(bounties)

        return jsonify({"bounty": new_bounty, "id": new_id}), 201
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@bounties_bp.route("/api/bounties/<bounty_id>", methods=["GET"])
def api_bounty_detail(bounty_id: str) -> Response:
    """Return the details for one bounty.

    Load the current bounty and tribe data, locate the requested bounty by ID,
    and enrich it with tribe information before responding. Missing bounty IDs
    are reported with a 404 so the client can distinguish not-found cases.

    Args:
        bounty_id: Identifier of the bounty to retrieve.

    Dependencies:
        Uses shared bounty and tribe loading helpers plus _enrich_bounty_with_tribe().

    Returns:
        A JSON response containing the enriched bounty, or an error response if it is missing.
    """
    try:
        bounties = _load_bounties()
        tribes = _load_tribes()
        tribe_map = {t.get("id"): t for t in tribes}
        bounty = next((b for b in bounties if b.get("id") == bounty_id), None)
        if not bounty:
            return jsonify({"error": "Bounty not found"}), 404
        return jsonify(_enrich_bounty_with_tribe(bounty, tribe_map))
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@bounties_bp.route("/api/bounties/<bounty_id>/claim", methods=["POST"])
def api_bounty_claim(bounty_id: str) -> Response:
    """Claim a bounty for a wallet and sync tribe membership.

    Validate the claimant wallet and its identity NFT, then add the wallet to the
    bounty's claimant list while updating the linked tribe membership when needed.
    The route persists both bounty and tribe state after synchronizing references.

    Args:
        bounty_id: Identifier of the bounty being claimed.

    Dependencies:
        Uses request JSON, _require_identity_nft(), and shared bounty/tribe persistence helpers.

    Returns:
        A JSON response with the updated bounty status, or an error response for invalid claims.
    """
    try:
        data: dict[str, Any] = request.get_json(force=True) or {}
        wallet = (data.get("wallet") or "").strip()
        if not wallet:
            return jsonify({"error": "wallet is required"}), 400
        if not _require_identity_nft(wallet):
            return jsonify({"error": "Identity NFT required to claim bounties"}), 403

        bounties = _load_bounties()
        tribes = _load_tribes()
        bounty = next((b for b in bounties if b.get("id") == bounty_id), None)
        if not bounty:
            return jsonify({"error": "Bounty not found"}), 404
        if bounty.get("status") not in {"open", "claimed", "in_progress"}:
            return jsonify({"error": f"Cannot claim bounty with status {bounty.get('status')}"}), 409

        claimed_by = bounty.setdefault("claimedBy", [])
        if wallet not in claimed_by:
            claimed_by.append(wallet)
        if bounty.get("status") == "open":
            bounty["status"] = "claimed"
        bounty["updatedAt"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

        tribe = next((t for t in tribes if t.get("id") == bounty.get("tribeId")), None)
        if tribe:
            members = tribe.setdefault("members", [])
            if not any((m.get("wallet") == wallet) for m in members):
                members.append(
                    {
                        "wallet": wallet,
                        "role": "member",
                        "joinedAt": datetime.now(timezone.utc)
                        .replace(microsecond=0)
                        .isoformat()
                        .replace("+00:00", "Z"),
                    }
                )

        _sync_tribe_bounty_refs(tribes, bounties)
        _save_bounties(bounties)
        _save_tribes(tribes)
        return jsonify({"success": True, "bountyId": bounty_id, "status": bounty.get("status")})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@bounties_bp.route("/api/bounties/<bounty_id>/join", methods=["POST"])
def api_bounty_join(bounty_id: str) -> Response:
    """Join the tribe associated with a bounty.

    Validate the wallet and requested role, confirm the caller has an identity
    NFT, and append the member to the bounty's tribe if they are not already in it.
    The route persists the modified tribe membership list before responding.

    Args:
        bounty_id: Identifier of the bounty whose tribe should be joined.

    Dependencies:
        Uses request JSON, _require_identity_nft(), and shared bounty/tribe loading and saving helpers.

    Returns:
        A JSON response with the tribe ID and member count, or an error response.
    """
    try:
        data: dict[str, Any] = request.get_json(force=True) or {}
        wallet = (data.get("wallet") or "").strip()
        role = (data.get("role") or "member").strip()
        if not wallet:
            return jsonify({"error": "wallet is required"}), 400
        if not _require_identity_nft(wallet):
            return jsonify({"error": "Identity NFT required"}), 403

        bounties = _load_bounties()
        tribes = _load_tribes()
        bounty = next((b for b in bounties if b.get("id") == bounty_id), None)
        if not bounty:
            return jsonify({"error": "Bounty not found"}), 404
        tribe = next((t for t in tribes if t.get("id") == bounty.get("tribeId")), None)
        if not tribe:
            return jsonify({"error": "Associated tribe not found"}), 404

        members = tribe.setdefault("members", [])
        if any((m.get("wallet") == wallet) for m in members):
            return jsonify({"error": "Already a tribe member"}), 409
        members.append(
            {
                "wallet": wallet,
                "role": role if role in {"member", "reviewer"} else "member",
                "joinedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            }
        )
        _save_tribes(tribes)
        return jsonify({"success": True, "tribeId": tribe.get("id"), "memberCount": len(tribe.get("members", []))})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@bounties_bp.route("/api/bounties/<bounty_id>/leave", methods=["POST"])
def api_bounty_leave(bounty_id: str) -> Response:
    """Leave the tribe associated with a bounty.

    Remove the provided wallet from both the tribe membership list and the bounty's
    claimant list, then reopen the bounty if no claimants remain in a claimed state.
    The route saves the updated tribe and bounty collections before returning.

    Args:
        bounty_id: Identifier of the bounty whose tribe membership should be left.

    Dependencies:
        Uses request JSON plus shared bounty and tribe loading and saving helpers.

    Returns:
        A JSON response confirming the leave action, or an error response if records are missing.
    """
    try:
        data: dict[str, Any] = request.get_json(force=True) or {}
        wallet = (data.get("wallet") or "").strip()
        if not wallet:
            return jsonify({"error": "wallet is required"}), 400

        bounties = _load_bounties()
        tribes = _load_tribes()
        bounty = next((b for b in bounties if b.get("id") == bounty_id), None)
        if not bounty:
            return jsonify({"error": "Bounty not found"}), 404
        tribe = next((t for t in tribes if t.get("id") == bounty.get("tribeId")), None)
        if not tribe:
            return jsonify({"error": "Associated tribe not found"}), 404

        members = tribe.get("members", [])
        tribe["members"] = [m for m in members if m.get("wallet") != wallet]
        claimed_by = bounty.get("claimedBy", [])
        bounty["claimedBy"] = [w for w in claimed_by if w != wallet]
        if not bounty["claimedBy"] and bounty.get("status") in {"claimed", "in_progress"}:
            bounty["status"] = "open"
        _save_tribes(tribes)
        _save_bounties(bounties)
        return jsonify({"success": True, "bountyId": bounty_id})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@bounties_bp.route("/api/bounties/<bounty_id>/submit", methods=["POST"])
def api_bounty_submit(bounty_id: str) -> Response:
    """Submit a claimed bounty for review.

    Confirm that the provided wallet belongs to an existing claimant, then move
    the bounty into the review state and stamp its update time. The route persists
    the modified bounty collection immediately after the transition.

    Args:
        bounty_id: Identifier of the bounty being submitted for review.

    Dependencies:
        Uses request JSON and shared bounty loading and saving helpers.

    Returns:
        A JSON response with the new review status, or an error response if submission is invalid.
    """
    try:
        data: dict[str, Any] = request.get_json(force=True) or {}
        wallet = (data.get("wallet") or "").strip()
        if not wallet:
            return jsonify({"error": "wallet is required"}), 400

        bounties = _load_bounties()
        bounty = next((b for b in bounties if b.get("id") == bounty_id), None)
        if not bounty:
            return jsonify({"error": "Bounty not found"}), 404
        if wallet not in bounty.get("claimedBy", []):
            return jsonify({"error": "Only claimants can submit for review"}), 403

        bounty["status"] = "review"
        bounty["updatedAt"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        _save_bounties(bounties)
        return jsonify({"success": True, "status": "review"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@bounties_bp.route("/api/bounties/<bounty_id>/review", methods=["POST"])
def api_bounty_review(bounty_id: str) -> Response:
    """Record a review for a submitted bounty.

    Validate the reviewer, score, and bounty state, then append a new review and
    recompute the bounty's quality gate and lifecycle status based on approvals.
    Reviewers who belong to the associated tribe are rejected to preserve separation.

    Args:
        bounty_id: Identifier of the bounty being reviewed.

    Dependencies:
        Uses request JSON plus shared bounty/tribe loading and bounty persistence helpers.

    Returns:
        A JSON response with the updated bounty status and review count, or an error response.
    """
    try:
        data: dict[str, Any] = request.get_json(force=True) or {}
        reviewer_wallet = (data.get("wallet") or "").strip()
        approved = bool(data.get("approve"))
        score = int(data.get("score") or 0)
        comments = (data.get("comments") or "").strip()
        verification_method = (data.get("verificationMethod") or "peer-reviewed").strip()
        if not reviewer_wallet:
            return jsonify({"error": "wallet is required"}), 400
        if score < 1 or score > 5:
            return jsonify({"error": "score must be between 1 and 5"}), 400

        bounties = _load_bounties()
        tribes = _load_tribes()
        bounty = next((b for b in bounties if b.get("id") == bounty_id), None)
        if not bounty:
            return jsonify({"error": "Bounty not found"}), 404
        if bounty.get("status") not in {"review", "verified"}:
            return jsonify({"error": f"Bounty status must be review/verified, got {bounty.get('status')}"}), 409

        tribe = next((t for t in tribes if t.get("id") == bounty.get("tribeId")), None)
        member_wallets = {m.get("wallet") for m in (tribe or {}).get("members", [])}
        if reviewer_wallet in member_wallets:
            return jsonify({"error": "Reviewer cannot be a tribe member"}), 409

        reviews = bounty.setdefault("reviews", [])
        if any(r.get("reviewerWallet") == reviewer_wallet for r in reviews):
            return jsonify({"error": "Reviewer already reviewed this bounty"}), 409

        review_entry = {
            "reviewerWallet": reviewer_wallet,
            "approved": approved,
            "score": score,
            "comments": comments,
            "verificationMethod": verification_method,
            "createdAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        }
        reviews.append(review_entry)

        approvals = [r for r in reviews if r.get("approved")]
        required_reviews = 1 if bounty.get("size") == "small" else 2 if bounty.get("size") == "medium" else 3
        if len(approvals) >= required_reviews:
            bounty["status"] = "verified"
            bounty["qualityGate"] = {
                "status": "passed",
                "reviewers": [r.get("reviewerWallet") for r in approvals],
                "score": round(sum(r.get("score", 0) for r in approvals) / len(approvals), 2),
                "verificationMethod": verification_method,
            }
        else:
            bounty["status"] = "review"

        bounty["updatedAt"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        _save_bounties(bounties)
        return jsonify({"success": True, "status": bounty.get("status"), "reviews": len(reviews)})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@bounties_bp.route("/api/bounties/<bounty_id>/reward", methods=["POST"])
def api_bounty_reward(bounty_id: str) -> Response:
    """Calculate and record bounty reward distribution.

    Ensure the bounty has reached the verified state, split the configured token
    rewards evenly across unique claimants, and store the payout snapshot on the
    bounty record. Tribe-to-bounty references are synchronized before the updated data is saved.

    Args:
        bounty_id: Identifier of the bounty being rewarded.

    Dependencies:
        Uses shared bounty/tribe loading, reference sync, and persistence helpers.

    Returns:
        A JSON response containing the recorded recipients and rewarded status, or an error response.
    """
    try:
        bounties = _load_bounties()
        tribes = _load_tribes()
        bounty = next((b for b in bounties if b.get("id") == bounty_id), None)
        if not bounty:
            return jsonify({"error": "Bounty not found"}), 404
        if bounty.get("status") != "verified":
            return jsonify({"error": "Bounty must be verified before reward"}), 409

        claimants = bounty.get("claimedBy", [])
        if not claimants:
            return jsonify({"error": "No claimants to reward"}), 409
        split = len(claimants)
        payout = []
        rct_each = round(float(bounty.get("rewardRCT", 0)) / split, 4)
        res_each = round(float(bounty.get("rewardRES", 0)) / split, 4)
        for wallet in sorted(set(claimants)):
            payout.append({"wallet": wallet, "rct": rct_each, "res": res_each})

        bounty["status"] = "rewarded"
        now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        bounty["updatedAt"] = now_iso
        bounty["reward"] = {
            "triggeredAt": now_iso,
            "recipients": payout,
            "totalRCT": float(bounty.get("rewardRCT", 0)),
            "totalRES": float(bounty.get("rewardRES", 0)),
            "onChain": False,
            "transactions": None,
        }

        _sync_tribe_bounty_refs(tribes, bounties)
        _save_bounties(bounties)
        _save_tribes(tribes)
        return jsonify({"success": True, "status": "rewarded", "recipients": payout})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
