"""Unit tests for settings API endpoints."""

import json
from pathlib import Path
from unittest.mock import Mock, patch


def test_settings_update_config_get_returns_updates_payload(client) -> None:
    """Update-config GET should return the stored updates settings."""
    updates = {"autoCheck": True, "autoApply": False, "autoCheckIntervalHours": 6}

    with patch("routes.settings._read_updates_config", return_value=updates):
        response = client.get("/api/settings/update-config")

    assert response.status_code == 200
    assert response.get_json() == updates


def test_settings_update_config_put_saves_valid_updates(client) -> None:
    """Update-config PUT should merge and persist valid fields."""
    write_mock = Mock(return_value={"autoCheck": False, "autoApply": True, "autoCheckIntervalHours": 12})

    with (
        patch(
            "routes.settings._read_updates_config",
            return_value={"autoCheck": True, "autoApply": False, "notifyOnUpdate": True, "autoCheckIntervalHours": 6},
        ),
        patch("routes.settings._write_updates_config", write_mock),
    ):
        response = client.put(
            "/api/settings/update-config",
            json={"autoCheck": False, "autoApply": True, "autoCheckIntervalHours": 12},
        )

    assert response.status_code == 200
    assert response.get_json() == {"autoCheck": False, "autoApply": True, "autoCheckIntervalHours": 12}
    write_mock.assert_called_once_with(
        {"autoCheck": False, "autoApply": True, "notifyOnUpdate": True, "autoCheckIntervalHours": 12}
    )


def test_settings_update_config_put_rejects_invalid_interval(client) -> None:
    """Update-config PUT should reject unsupported check intervals."""
    with patch("routes.settings._read_updates_config", return_value={"autoCheckIntervalHours": 6}):
        response = client.put("/api/settings/update-config", json={"autoCheckIntervalHours": 3})

    assert response.status_code == 400
    assert response.get_json() == {"error": "autoCheckIntervalHours must be one of: 1, 2, 4, 6, 12, 24"}


def test_settings_skills_get_returns_skills_agents_and_assignments(client) -> None:
    """Skills GET should return discovered skills and per-agent assignments."""
    skills = [{"name": "alpha"}, {"name": "beta"}]
    agents = [{"name": "main"}, {"name": "coder"}]

    with (
        patch("routes.settings._read_openclaw_config", return_value={"agents": {}}),
        patch("routes.settings._discover_settings_skills", return_value=skills),
        patch("routes.settings._list_skill_agents", return_value=agents),
        patch("routes.settings._get_agent_skill_allow", side_effect=[None, ["beta", "beta", "missing"]]),
    ):
        response = client.get("/api/settings/skills")

    assert response.status_code == 200
    assert response.get_json() == {
        "skills": skills,
        "agents": agents,
        "assignments": {
            "main": ["alpha", "beta"],
            "coder": ["beta"],
        },
    }


def test_settings_plugins_discovers_plugins_from_custom_extensions_dir(client, tmp_path) -> None:
    """Plugins GET should scan the configured custom extensions directory."""
    custom_dir = tmp_path / "custom-extensions"
    stock_dir = tmp_path / "stock-extensions"
    plugin_dir = custom_dir / "custom-plugin"
    plugin_dir.mkdir(parents=True)
    stock_dir.mkdir()

    (plugin_dir / "openclaw.plugin.json").write_text(
        json.dumps({"name": "Custom Plugin", "description": "Testing plugin", "version": "1.2.3"})
    )

    config_path = tmp_path / "openclaw.json"
    config_path.write_text(
        json.dumps(
            {
                "plugins": {
                    "entries": {"custom-plugin": {"enabled": True}},
                    "allow": ["custom-plugin"],
                    "slots": {"contextEngine": "context-slot"},
                }
            }
        )
    )

    def _path_factory(value: str) -> Path:
        if value == "/opt/homebrew/lib/node_modules/openclaw/extensions":
            return stock_dir
        return Path(value)

    with (
        patch("routes.settings.OPENCLAW_CONFIG", config_path),
        patch("routes.settings.EXTENSIONS_DIR", custom_dir),
        patch("routes.settings.Path", side_effect=_path_factory),
    ):
        response = client.get("/api/settings/plugins")

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["allow"] == ["custom-plugin"]
    assert payload["contextEngineSlot"] == "context-slot"
    assert payload["totalCustom"] == 1
    assert payload["totalStock"] == 0
    assert payload["plugins"] == [
        {
            "configuredInEntries": True,
            "description": "Testing plugin",
            "enabled": True,
            "id": "custom-plugin",
            "inAllowList": True,
            "name": "Custom Plugin",
            "path": str(plugin_dir),
            "source": "custom",
            "version": "1.2.3",
        }
    ]
