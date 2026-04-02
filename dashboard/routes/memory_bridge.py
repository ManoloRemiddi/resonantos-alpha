"""Memory bridge routes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, jsonify, request

memory_bridge_bp = Blueprint("memory_bridge", __name__)

_MCP_CONFIG: Path = Path(__file__).resolve().parents[2] / "mcp-server" / "mcp-config.json"


@memory_bridge_bp.route("/api/memory-bridge/config", methods=["GET"])
def memory_bridge_config_get() -> Response:
    """Return the persisted memory-bridge configuration.

    Read the MCP config JSON from disk and serialize it directly to the client.
    Keep the route minimal so the settings UI can fetch the current bridge
    configuration without additional transformation.

    Dependencies:
        _MCP_CONFIG.read_text() and json.loads().

    Returns:
        Response: JSON response containing the current memory-bridge config.
    """
    try:
        return jsonify(json.loads(_MCP_CONFIG.read_text()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@memory_bridge_bp.route("/api/memory-bridge/config", methods=["POST"])
def memory_bridge_config_post() -> Response:
    """Persist a new memory-bridge configuration document.

    Read the posted JSON body and write it back to the MCP config file with
    stable indentation. Return a compact success payload so the settings UI can
    confirm that the new configuration reached disk.

    Dependencies:
        request.get_json(), _MCP_CONFIG.write_text(), and json.dumps().

    Returns:
        Response: JSON response confirming the save operation or reporting an error.
    """
    try:
        data: dict[str, Any] = request.get_json()
        _MCP_CONFIG.write_text(json.dumps(data, indent=2))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
