"""Unit tests for agents API endpoints."""

import json
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch


@contextmanager
def _patch_agents_env(tmp_path, config_data, gw_health=None):
    """Patch agents route paths into a temporary OpenClaw home."""
    openclaw_home = tmp_path / ".openclaw"
    workspace = openclaw_home / "workspace"
    rmemory_dir = workspace / "r-memory"
    config_path = openclaw_home / "openclaw.json"

    workspace.mkdir(parents=True)
    rmemory_dir.mkdir(parents=True)
    config_path.write_text(json.dumps(config_data))

    with (
        patch("routes.agents.OPENCLAW_HOME", openclaw_home),
        patch("routes.agents.WORKSPACE", workspace),
        patch("routes.agents.RMEMORY_DIR", rmemory_dir),
        patch("routes.agents.OPENCLAW_CONFIG", config_path),
        patch("routes.agents.gw", SimpleNamespace(health=gw_health or {})),
        patch("routes.agents._rmem_config", return_value={"enabled": True}),
        patch(
            "routes.agents._rmem_effective_models",
            return_value={"compression": "gpt-compress", "narrative": "gpt-narrative"},
        ),
    ):
        yield {
            "openclaw_home": openclaw_home,
            "workspace": workspace,
            "rmemory_dir": rmemory_dir,
            "config_path": config_path,
        }


def test_agents_setup_model_writes_override_file(client, tmp_path) -> None:
    """Setup model endpoint should persist the default model override."""
    models_path = tmp_path / ".openclaw" / "agents" / "setup" / "agent"
    models_path.mkdir(parents=True)

    with patch("routes.agents.Path.home", return_value=tmp_path):
        response = client.post("/api/agents/setup/model", json={"model": "gpt-5.4"})

    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "model": "gpt-5.4"}
    assert json.loads((models_path / "models.json").read_text()) == {"default": "gpt-5.4"}


def test_agents_setup_model_rejects_missing_model(client) -> None:
    """Setup model endpoint should reject empty model values."""
    response = client.post("/api/agents/setup/model", json={"model": ""})

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "model required"}


def test_agents_list_returns_virtual_memory_gateway_and_main_agents(client, tmp_path) -> None:
    """Agents endpoint should merge virtual, live, and fallback agents."""
    config = {
        "agents": {
            "list": [{"id": "coder", "model": {"primary": "gpt-coder"}}],
            "defaults": {"model": "gpt-main"},
        }
    }
    gw_health = {"agents": [{"agentId": "coder", "isDefault": False, "heartbeat": {"enabled": True}, "sessions": {}}]}

    with _patch_agents_env(tmp_path, config, gw_health) as env:
        (env["rmemory_dir"] / "r-memory.log").write_text("active\n")
        (env["rmemory_dir"] / "usage-stats.json").write_text(json.dumps({"compression": {"calls": 3}}))
        coder_ws = env["openclaw_home"] / "workspace-coder"
        coder_ws.mkdir()
        (coder_ws / "IDENTITY.md").write_text("**Emoji:** 🛠\n**Name:** Coder Agent\n")

        response = client.get("/api/agents")

    agents = response.get_json()
    by_id = {agent["agentId"]: agent for agent in agents}

    assert response.status_code == 200
    assert [agent["agentId"] for agent in agents] == ["main", "memory", "coder"]
    assert by_id["memory"]["status"] == "active"
    assert by_id["memory"]["subAgents"]["compression"]["calls"] == 3
    assert by_id["coder"]["status"] == "active"
    assert by_id["coder"]["displayName"] == "Coder Agent"
    assert by_id["coder"]["mainModel"] == "gpt-coder"
    assert by_id["main"]["status"] == "configured"
    assert by_id["main"]["mainModel"] == "gpt-main"


def test_agents_list_returns_configured_and_inactive_agents_from_disk(client, tmp_path) -> None:
    """Agents endpoint should surface configured and discovered inactive agents."""
    config = {
        "agents": {
            "list": [{"id": "dao", "default": False, "model": "gpt-dao"}],
            "defaults": {"model": "gpt-main"},
        }
    }

    with _patch_agents_env(tmp_path, config, {"agents": []}) as env:
        researcher_ws = env["openclaw_home"] / "workspace-researcher"
        researcher_ws.mkdir()
        (researcher_ws / "IDENTITY.md").write_text("**Name:** Researcher Agent\n")

        response = client.get("/api/agents")

    agents = {agent["agentId"]: agent for agent in response.get_json()}

    assert response.status_code == 200
    assert agents["memory"]["status"] == "inactive"
    assert agents["dao"]["status"] == "configured"
    assert agents["dao"]["mainModel"] == "gpt-dao"
    assert agents["researcher"]["status"] == "inactive"
    assert agents["researcher"]["displayName"] == "Researcher Agent"
