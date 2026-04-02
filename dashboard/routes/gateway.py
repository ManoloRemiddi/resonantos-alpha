"""Gateway routes."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, Response, jsonify, request

from routes.shared import _read_gw_token, get_gw_ws_url, gw

gateway_bp = Blueprint("gateway", __name__)


@gateway_bp.route("/api/gateway/status")
def api_gateway_status() -> Response:
    """Return the current cached gateway connection status.

    Expose the latest connection identifiers, tick timestamps, and error state
    tracked by the shared gateway client. Keep the response lightweight so the
    dashboard can poll connectivity without triggering new gateway traffic.

    Dependencies:
        gw: Shared `GatewayClient` instance holding cached connection state.

    Returns:
        Response: JSON payload describing the current gateway connection state.
    """
    return jsonify(
        {
            "connected": gw.connected,
            "connId": gw.conn_id,
            "lastTick": gw.last_tick,
            "lastHealthTs": gw.last_health_ts,
            "error": gw.error,
        }
    )


@gateway_bp.route("/api/gateway/health")
def api_gateway_health() -> Response:
    """Return the latest cached gateway health payload.

    Read the shared health snapshot under the gateway client lock so callers
    see a consistent view of the cached state. Fall back to a placeholder error
    payload when the gateway has not yet published any health data.

    Dependencies:
        gw._lock: Synchronizes access to the cached health payload.

    Returns:
        Response: JSON gateway health data, or a placeholder error payload.
    """
    with gw._lock:
        return jsonify(gw.health or {"error": "no health data yet"})


@gateway_bp.route("/api/gateway/request", methods=["POST"])
def api_gateway_request() -> Response:
    """Proxy an arbitrary method call to the shared gateway client.

    Read the incoming JSON body, validate that a method name was provided, and
    forward the request to the live websocket client with optional parameters.
    Preserve the gateway client's response payload so frontend callers receive
    the same success and error structure produced by the backend proxy.

    Dependencies:
        request.get_json: Reads the incoming API payload.
        gw.request: Sends the proxied request to the gateway connection.

    Returns:
        Response: JSON payload containing the proxied gateway response.
    """
    body: dict[str, Any] = request.get_json(force=True)
    method = body.get("method")
    params = body.get("params")
    if not method:
        return jsonify({"ok": False, "error": "method required"}), 400
    result = gw.request(method, params)
    return jsonify(result)


@gateway_bp.route("/api/gateway/restart", methods=["POST"])
def api_gateway_restart() -> Response:
    """Restart the local OpenClaw gateway process.

    Invoke the `openclaw gateway restart` command and report either the command
    output or a structured error payload to the caller. Convert subprocess
    exceptions into the same JSON error format used by the rest of the API.

    Dependencies:
        subprocess.run: Executes the local gateway restart command.

    Returns:
        Response: JSON payload describing restart success or failure.
    """
    try:
        import subprocess

        result = subprocess.run(["openclaw", "gateway", "restart"], capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            return jsonify({"ok": True, "output": result.stdout.strip()})
        return jsonify({"ok": False, "error": result.stderr.strip() or "restart failed"}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@gateway_bp.route("/api/gateway/token")
def api_gateway_token() -> Response:
    """Return browser-facing gateway connection credentials.

    Expose the configured websocket URL and authentication token used by the
    dashboard so browser clients can establish their own gateway sessions. Keep
    the payload minimal and limited to the connection details the UI needs.

    Dependencies:
        get_gw_ws_url(): Resolves the local websocket URL for the gateway.
        _read_gw_token(): Reads the current gateway authentication token.

    Returns:
        Response: JSON payload containing gateway connection credentials.
    """
    return jsonify(
        {
            "url": get_gw_ws_url(),
            "token": _read_gw_token(),
        }
    )
