"""Unit tests for shield API endpoints."""

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch


@contextmanager
def _patch_file_guard(status):
    """Patch the dynamic file_guard loader used by shield routes."""
    module = SimpleNamespace(get_status=lambda: status)
    spec = SimpleNamespace(loader=SimpleNamespace(exec_module=lambda _module: None))
    with (
        patch("importlib.util.spec_from_file_location", return_value=spec),
        patch("importlib.util.module_from_spec", return_value=module),
    ):
        yield


def test_shield_status_returns_healthy_state_with_file_guard_summary(client) -> None:
    """Shield status should merge daemon health and file guard counts."""
    guard_status = {
        "core": {"total": 5, "locked_count": 3},
        "docs": {"total": 2, "locked_count": 1},
    }

    with (
        patch("routes.shield._shield_daemon_health", return_value=(True, {"uptime_seconds": 88}, None)),
        _patch_file_guard(guard_status),
    ):
        response = client.get("/api/shield/status")

    assert response.status_code == 200
    assert response.get_json() == {
        "active": True,
        "available": True,
        "mode": "daemon",
        "uptime_seconds": 88,
        "file_guard": {
            "total_files": 7,
            "locked_files": 4,
            "groups": guard_status,
        },
    }


def test_shield_status_returns_unhealthy_state_when_daemon_fails(client) -> None:
    """Shield status should report daemon errors when unhealthy."""
    guard_status = {"core": {"total": 2, "locked_count": 0}}

    with (
        patch("routes.shield._shield_daemon_health", return_value=(False, None, "connection refused")),
        _patch_file_guard(guard_status),
    ):
        response = client.get("/api/shield/status")

    assert response.status_code == 200
    assert response.get_json()["active"] is False
    assert response.get_json()["available"] is False
    assert response.get_json()["mode"] == "off"
    assert response.get_json()["error"] == "connection refused"
    assert response.get_json()["file_guard"]["locked_files"] == 0


def test_shield_guard_status_returns_loaded_file_guard_payload(client) -> None:
    """Guard status endpoint should return file_guard.get_status()."""
    guard_status = {"core": {"total": 4, "locked_count": 2}}

    with _patch_file_guard(guard_status):
        response = client.get("/api/shield/guard/status")

    assert response.status_code == 200
    assert response.get_json() == guard_status


def test_shield_guard_status_returns_500_when_file_guard_load_fails(client) -> None:
    """Guard status endpoint should surface loader failures."""
    with patch("importlib.util.spec_from_file_location", side_effect=RuntimeError("file guard missing")):
        response = client.get("/api/shield/guard/status")

    assert response.status_code == 500
    assert response.get_json() == {"error": "file guard missing"}


def test_shield_doorman_status_reports_running_process(client) -> None:
    """Doorman status should detect a running launchctl entry."""
    launchctl = SimpleNamespace(returncode=0, stdout="321\t0\tcom.resonantos.workspace-sanitizer\n", stderr="")

    with (
        patch("routes.shield.subprocess.run", return_value=launchctl),
        patch("routes.shield.os.path.exists", return_value=False),
    ):
        response = client.get("/api/shield/doorman/status")

    assert response.status_code == 200
    assert response.get_json()["running"] is True
    assert response.get_json()["pid"] == 321


def test_shield_doorman_status_reports_not_running_when_missing(client) -> None:
    """Doorman status should stay false when no process entry matches."""
    launchctl = SimpleNamespace(returncode=0, stdout="123\t0\tcom.other.service\n", stderr="")

    with (
        patch("routes.shield.subprocess.run", return_value=launchctl),
        patch("routes.shield.os.path.exists", return_value=False),
    ):
        response = client.get("/api/shield/doorman/status")

    assert response.status_code == 200
    assert response.get_json()["running"] is False
    assert response.get_json()["pid"] is None
