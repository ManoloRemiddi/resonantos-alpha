"""Token savings routes."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, Response, jsonify, request

from routes.token_savings_helpers import (
    _ts_int,
    _ts_load_pricing,
    _ts_merge_dict,
    _ts_sanitize_pricing,
    _ts_save_dashboard_config,
    build_token_savings_payload,
)

token_savings_bp = Blueprint("token_savings", __name__)


@token_savings_bp.route("/api/token-savings/pricing", methods=["PUT"])
def api_token_savings_pricing() -> Response:
    """Update the pricing reference used by token-savings views.

    Read the pricing patch from the request body, merge it into the persisted
    pricing configuration, and normalize the result before saving. Return the
    sanitized pricing document so the settings UI can refresh immediately.

    Dependencies:
        request.get_json(), _ts_load_pricing(), _ts_merge_dict(), _ts_sanitize_pricing(), and _ts_save_dashboard_config().

    Returns:
        Response: JSON response containing the saved pricing data or an error payload.
    """
    patch: dict[str, Any] = request.get_json(force=True) or {}
    if not isinstance(patch, dict):
        return jsonify({"ok": False, "error": "invalid payload"}), 400
    pricing, cfg = _ts_load_pricing()
    updated = _ts_sanitize_pricing(_ts_merge_dict(pricing, patch))
    try:
        cfg["pricing"] = updated
        _ts_save_dashboard_config(cfg)
        return jsonify({"ok": True, "pricing": updated})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@token_savings_bp.route("/api/token-savings")
def api_token_savings() -> Response:
    """Return the token-savings operations payload.

    Clamp the requested day window to the supported range and delegate the full
    payload construction to the helper module. Keep the route thin so the data
    assembly logic remains isolated in the token-savings helpers.

    Dependencies:
        request.args, _ts_int(), and build_token_savings_payload().

    Returns:
        Response: JSON response containing token-savings analytics data.
    """
    days = max(1, min(30, _ts_int(request.args.get("days", 7), 7)))
    return jsonify(build_token_savings_payload(days))
