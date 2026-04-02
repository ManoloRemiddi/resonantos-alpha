"""Unit tests for gateway API endpoints."""

from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock, patch


def test_gateway_status_returns_connection_snapshot(client) -> None:
    """Gateway status should expose the expected connection fields."""
    gateway = SimpleNamespace(
        connected=True,
        conn_id="conn-123",
        last_tick=101,
        last_health_ts=202,
        error=None,
    )

    with patch("routes.gateway.gw", gateway):
        response = client.get("/api/gateway/status")

    assert response.status_code == 200
    assert response.get_json() == {
        "connected": True,
        "connId": "conn-123",
        "lastTick": 101,
        "lastHealthTs": 202,
        "error": None,
    }


def test_gateway_health_returns_cached_payload(client) -> None:
    """Health endpoint should return the cached gateway health payload."""
    gateway = SimpleNamespace(_lock=nullcontext(), health={"agents": [{"agentId": "main"}], "ts": 123})

    with patch("routes.gateway.gw", gateway):
        response = client.get("/api/gateway/health")

    assert response.status_code == 200
    assert response.get_json() == {"agents": [{"agentId": "main"}], "ts": 123}


def test_gateway_health_returns_placeholder_when_empty(client) -> None:
    """Health endpoint should fall back when no health data exists yet."""
    gateway = SimpleNamespace(_lock=nullcontext(), health={})

    with patch("routes.gateway.gw", gateway):
        response = client.get("/api/gateway/health")

    assert response.status_code == 200
    assert response.get_json() == {"error": "no health data yet"}


def test_gateway_request_proxies_valid_method(client) -> None:
    """Request endpoint should forward valid gateway calls."""
    request_mock = Mock(return_value={"ok": True, "payload": {"status": "healthy"}})
    gateway = SimpleNamespace(request=request_mock)

    with patch("routes.gateway.gw", gateway):
        response = client.post("/api/gateway/request", json={"method": "health.get", "params": {"full": True}})

    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "payload": {"status": "healthy"}}
    request_mock.assert_called_once_with("health.get", {"full": True})


def test_gateway_request_rejects_missing_method(client) -> None:
    """Request endpoint should reject bodies without a method."""
    gateway = SimpleNamespace(request=Mock())

    with patch("routes.gateway.gw", gateway):
        response = client.post("/api/gateway/request", json={"params": {"full": True}})

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "method required"}
    gateway.request.assert_not_called()
