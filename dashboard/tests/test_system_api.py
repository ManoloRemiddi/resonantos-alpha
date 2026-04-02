"""Unit tests for system API endpoints."""

import json
from types import SimpleNamespace
from unittest.mock import Mock, patch


class MissingPath:
    """Path-like object that reports no files."""

    def __truediv__(self, _other):
        return self

    def exists(self):
        return False

    def read_text(self, errors=None):
        raise FileNotFoundError("missing")


def test_system_status_returns_json_payload(client) -> None:
    """Successful JSON status should be returned as-is."""
    with patch(
        "routes.system.subprocess.run",
        return_value=SimpleNamespace(returncode=0, stdout='{"status":"ok","uptime":42}', stderr=""),
    ) as run_mock:
        response = client.get("/api/system/status")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "uptime": 42}
    run_mock.assert_called_once_with(["openclaw", "status", "--json"], capture_output=True, text=True, timeout=15)


def test_system_status_falls_back_to_raw_output_on_json_failure(client) -> None:
    """Non-zero JSON command should fall back to plain status output."""
    with patch(
        "routes.system.subprocess.run",
        side_effect=[
            SimpleNamespace(returncode=1, stdout="", stderr="json failed"),
            SimpleNamespace(returncode=0, stdout="gateway running", stderr="warning"),
        ],
    ) as run_mock:
        response = client.get("/api/system/status")

    assert response.status_code == 200
    assert response.get_json() == {"raw": "gateway running", "error": "warning"}
    assert run_mock.call_count == 2


def test_config_redacts_gateway_token(client) -> None:
    """Config endpoint should redact the gateway auth token."""
    config_payload = {
        "gateway": {"auth": {"token": "secret-token", "user": "operator"}},
        "model": "gpt-test",
    }

    with patch("routes.system.OPENCLAW_CONFIG", Mock(read_text=Mock(return_value=json.dumps(config_payload)))):
        response = client.get("/api/config")

    assert response.status_code == 200
    assert response.get_json() == {
        "gateway": {"auth": {"token": "***", "user": "operator"}},
        "model": "gpt-test",
    }


def test_models_returns_gateway_model_list(client) -> None:
    """Models endpoint should proxy the gateway request."""
    request_mock = Mock(return_value={"ok": True, "payload": {"models": [{"id": "gpt-5"}]}})

    with patch("routes.system.gw.request", request_mock):
        response = client.get("/api/models")

    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "payload": {"models": [{"id": "gpt-5"}]}}
    request_mock.assert_called_once_with("models.list")


def test_memory_health_returns_mocked_summary(client) -> None:
    """Memory health should use mocked R-Memory and filesystem data."""
    log_events = [
        {"event": "init", "cachedBlocks": 2, "ts": "2026-03-25T10:00:00Z"},
        {
            "event": "compaction_done",
            "ts": "2026-03-25T10:05:00Z",
            "saving": "50%",
            "compressed": 120,
            "raw": 240,
            "cacheHits": 3,
            "cacheMisses": 1,
        },
    ]

    with (
        patch("routes.system._rmem_config", return_value={"compressTrigger": 36000, "evictTrigger": 80000}),
        patch("routes.system._rmem_current_session_id", return_value="abc123"),
        patch("routes.system._rmem_history_blocks", return_value=[]),
        patch("routes.system._rmem_parse_log", return_value=log_events),
        patch(
            "routes.system._rmem_gateway_session",
            return_value={
                "totalTokens": 20000,
                "contextTokens": 40000,
                "model": "gpt-test",
                "inputTokens": 900,
                "outputTokens": 150,
            },
        ),
        patch("routes.system._scan_ssot_layer", return_value=[{"tokens": 10, "id": "doc"}]),
        patch("routes.system.WORKSPACE", MissingPath()),
        patch("routes.system.R_AWARENESS_LOG", Mock(exists=Mock(return_value=False))),
        patch("routes.system.LCM_DB", Mock(exists=Mock(return_value=False))),
        patch("glob.glob", return_value=[]),
    ):
        response = client.get("/api/memory/health")

    data = response.get_json()
    assert response.status_code == 200
    assert data["contextWindow"]["model"] == "gpt-test"
    assert data["contextWindow"]["status"] == "warning"
    assert data["contextWindow"]["injectedSSoTs"] == 5
    assert data["subsystems"]["plugin"]["status"] == "ok"
    assert data["subsystems"]["compression"]["status"] == "ok"
