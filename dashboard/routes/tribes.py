"""Tribe routes."""

from __future__ import annotations

import traceback
from datetime import datetime, timezone
from typing import Any

from flask import Blueprint, Response, jsonify, request

from routes.shared import _load_bounties, _load_tribes, _save_tribes, _sync_tribe_bounty_refs
from routes.wallet_helpers import _require_identity_nft

tribes_bp = Blueprint("tribes", __name__)


@tribes_bp.route("/api/tribes", methods=["GET"])
def api_tribes_list() -> Response:
    """Return tribes with derived membership and bounty counts.

    Load the persisted tribe and bounty datasets, then synchronize stored
    bounty references before building the response payload. Add summary
    counters so the client can render overview cards without extra queries.

    Dependencies:
        _load_tribes(), _load_bounties(), _sync_tribe_bounty_refs(), and _save_tribes().

    Returns:
        Response: JSON response containing serialized tribes and the total count.
    """
    try:
        tribes = _load_tribes()
        bounties = _load_bounties()
        _sync_tribe_bounty_refs(tribes, bounties)
        _save_tribes(tribes)

        payload = []
        for tribe in tribes:
            payload.append(
                {
                    **tribe,
                    "memberCount": len(tribe.get("members", [])),
                    "activeBountyCount": len(tribe.get("activeBounties", [])),
                    "completedBountyCount": len(tribe.get("completedBounties", [])),
                }
            )
        return jsonify({"tribes": payload, "count": len(payload)})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@tribes_bp.route("/api/tribes/<tribe_id>", methods=["GET"])
def api_tribe_detail(tribe_id: str) -> Response:
    """Return the detail payload for one tribe.

    Look up the requested tribe and attach its related bounty records to the
    response. Compute member and bounty counts inline so the client receives a
    fully expanded detail document in one request.

    Args:
        tribe_id: Identifier of the tribe to load.

    Dependencies:
        _load_tribes() and _load_bounties().

    Returns:
        Response: JSON response containing the tribe detail document or an error.
    """
    try:
        tribes = _load_tribes()
        bounties = _load_bounties()
        tribe = next((t for t in tribes if t.get("id") == tribe_id), None)
        if not tribe:
            return jsonify({"error": "Tribe not found"}), 404

        tribe_bounties = [b for b in bounties if b.get("tribeId") == tribe_id]
        detail = dict(tribe)
        detail["bounties"] = tribe_bounties
        detail["memberCount"] = len(tribe.get("members", []))
        detail["activeBountyCount"] = len([b for b in tribe_bounties if b.get("status") != "rewarded"])
        detail["completedBountyCount"] = len([b for b in tribe_bounties if b.get("status") == "rewarded"])
        return jsonify(detail)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@tribes_bp.route("/api/tribes", methods=["POST"])
def api_tribe_create() -> Response:
    """Create a new tribe record from request data.

    Validate the wallet and name fields, enforce the identity NFT gate, and
    derive the next sequential tribe identifier. Persist the new tribe with an
    initial coordinator member entry before returning the created payload.

    Dependencies:
        request.get_json(), _require_identity_nft(), _load_tribes(), and _save_tribes().

    Returns:
        Response: JSON response containing the created tribe or an error payload.
    """
    try:
        data: dict[str, Any] = request.get_json(force=True) or {}
        wallet = (data.get("wallet") or "").strip()
        name = (data.get("name") or "").strip()
        description = (data.get("description") or "").strip()
        category = (data.get("category") or "core").strip()
        tags = data.get("tags") if isinstance(data.get("tags"), list) else []

        if not wallet or not name:
            return jsonify({"error": "wallet and name are required"}), 400
        if not _require_identity_nft(wallet):
            return jsonify({"error": "Identity NFT required to create a tribe"}), 403

        tribes = _load_tribes()
        max_id = 0
        for t in tribes:
            try:
                max_id = max(max_id, int(str(t.get("id", "")).split("-")[-1]))
            except Exception:
                continue
        tribe_id = f"TRIBE-{max_id + 1:03d}"
        now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        tribe = {
            "id": tribe_id,
            "name": name,
            "description": description or f"Working group for {name}.",
            "category": category,
            "members": [{"wallet": wallet, "role": "coordinator", "joinedAt": now_iso}],
            "coordinator": wallet,
            "activeBounties": [],
            "completedBounties": [],
            "createdAt": now_iso,
            "avatar": None,
            "tags": [str(t).strip() for t in tags if str(t).strip()],
        }
        tribes.append(tribe)
        _save_tribes(tribes)
        return jsonify(tribe), 201
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@tribes_bp.route("/api/tribes/<tribe_id>/join", methods=["POST"])
def api_tribe_join(tribe_id: str) -> Response:
    """Add a wallet to an existing tribe.

    Validate the posted wallet, confirm the identity NFT requirement, and
    reject duplicate memberships before appending the new member record.
    Persist the updated tribe list and return the new membership count.

    Args:
        tribe_id: Identifier of the tribe to join.

    Dependencies:
        request.get_json(), _require_identity_nft(), _load_tribes(), and _save_tribes().

    Returns:
        Response: JSON response describing the join result or an error payload.
    """
    try:
        data: dict[str, Any] = request.get_json(force=True) or {}
        wallet = (data.get("wallet") or "").strip()
        role = (data.get("role") or "member").strip()
        if not wallet:
            return jsonify({"error": "wallet is required"}), 400
        if not _require_identity_nft(wallet):
            return jsonify({"error": "Identity NFT required"}), 403

        tribes = _load_tribes()
        tribe = next((t for t in tribes if t.get("id") == tribe_id), None)
        if not tribe:
            return jsonify({"error": "Tribe not found"}), 404
        members = tribe.setdefault("members", [])
        if any((m.get("wallet") == wallet) for m in members):
            return jsonify({"error": "Already a tribe member"}), 409
        members.append(
            {
                "wallet": wallet,
                "role": role if role in {"member", "coordinator", "reviewer"} else "member",
                "joinedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            }
        )
        _save_tribes(tribes)
        return jsonify({"success": True, "tribeId": tribe_id, "memberCount": len(members)})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@tribes_bp.route("/api/tribes/<tribe_id>/leave", methods=["POST"])
def api_tribe_leave(tribe_id: str) -> Response:
    """Remove a wallet from an existing tribe.

    Validate the posted wallet, filter the membership list, and reassign the
    coordinator role when the current coordinator leaves. Persist the updated
    tribe list and return the resulting membership count.

    Args:
        tribe_id: Identifier of the tribe to leave.

    Dependencies:
        request.get_json(), _load_tribes(), and _save_tribes().

    Returns:
        Response: JSON response describing the leave result or an error payload.
    """
    try:
        data: dict[str, Any] = request.get_json(force=True) or {}
        wallet = (data.get("wallet") or "").strip()
        if not wallet:
            return jsonify({"error": "wallet is required"}), 400

        tribes = _load_tribes()
        tribe = next((t for t in tribes if t.get("id") == tribe_id), None)
        if not tribe:
            return jsonify({"error": "Tribe not found"}), 404
        members = tribe.get("members", [])
        updated = [m for m in members if m.get("wallet") != wallet]
        if len(updated) == len(members):
            return jsonify({"error": "Wallet is not a tribe member"}), 404
        tribe["members"] = updated
        if tribe.get("coordinator") == wallet:
            tribe["coordinator"] = updated[0]["wallet"] if updated else None
            if updated:
                updated[0]["role"] = "coordinator"
        _save_tribes(tribes)
        return jsonify({"success": True, "tribeId": tribe_id, "memberCount": len(updated)})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
