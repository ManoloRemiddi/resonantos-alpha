#!/usr/bin/env python3
"""
Route tests for ResonantOS Dashboard — runs via Flask test client.
No server needed; all requests are in-process.

Usage:
    pip install pytest flask
    pytest dashboard/tests/test_routes.py -v
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def pytest_configure(config):
    os.environ.setdefault("SKIP_VALIDATION", "1")

import pytest
from server_v2 import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c

# ── Page routes ───────────────────────────────────────────────────────────────

PAGES = [
    "/",
    "/agents",
    "/r-memory",
    "/projects",
    "/chatbots",
    "/bounties",
    "/wallet",
    "/tribes",
    "/docs",
    "/setup",
    "/license",
    "/shield",
    "/ssot",
    "/todo",
]
# /settings excluded: partials/settings/header.html has pre-existing Jinja2 syntax error (issue #78)

@pytest.mark.parametrize("path", PAGES)
def test_page_returns_200(client, path):
    """Every page route should return 200."""
    rv = client.get(path)
    assert rv.status_code == 200, f"{path} returned {rv.status_code}"

# ── API routes (JSON) ──────────────────────────────────────────────────────────

API_GET = [
    ("/api/gateway/status",      "connected"),
    ("/api/gateway/health",      "healthy"),
    ("/api/shield/status",       any),
    ("/api/system-agents",       list),     # returns list of agent objects
    ("/api/agents",              list),     # returns list of agent objects
    ("/api/r-memory/available-models", "models"),
    ("/api/memory/health",       "contextWindow"),
    ("/api/token-savings",       "days"),
    ("/api/conversations",       "conversations"),
    ("/api/analytics",           "total_conversations"),
    ("/api/settings/update-config", None),   # returns {} when no config file
    ("/api/memory-logs/settings", "enabled"),
    ("/api/docs/tree",           any),
]

def _assert_json_key(client, path, key):
    rv = client.get(path)
    assert rv.status_code == 200, f"{path} → {rv.status_code}"
    if key is None:
        return  # only care about status
    data = rv.get_json()
    assert data is not None, f"{path} returned non-JSON: {rv.data[:100]}"
    if key is any:
        assert isinstance(data, (list, dict)), f"{path} expected dict/list, got {type(data).__name__}"
    elif key is list:
        assert isinstance(data, list), f"{path} expected list, got {type(data).__name__}"
    elif isinstance(key, list):
        for k in key:
            assert k in data, f"{path} missing key '{k}' in {list(data.keys())}"
    else:
        assert key in data, f"{path} missing key '{key}' in {list(data.keys())}"

@pytest.mark.parametrize("path,key", API_GET)
def test_api_get_returns_json(client, path, key):
    """API GET endpoints should return 200 with expected JSON key."""
    _assert_json_key(client, path, key)

# ── API error cases ────────────────────────────────────────────────────────────

def test_api_agents_nonexistent_returns_404(client):
    rv = client.get("/api/agents/nonexistent-agent/status")
    assert rv.status_code == 404

def test_api_conversations_pagination(client):
    rv = client.get("/api/conversations?limit=5&offset=0")
    assert rv.status_code == 200
    data = rv.get_json()
    assert "conversations" in data
    assert "total" in data
    assert isinstance(data["conversations"], list)

def test_api_analytics_range_params(client):
    for rng in ["7d", "30d", "90d"]:
        rv = client.get(f"/api/analytics?range={rng}")
        assert rv.status_code == 200, f"range={rng} failed with {rv.status_code}"
        data = rv.get_json()
        assert "total_conversations" in data

# ── Static / favicon ──────────────────────────────────────────────────────────

def test_favicon_returns_not_404(client):
    rv = client.get("/favicon.ico")
    assert rv.status_code != 404, "favicon.ico should not 404"

# ── 404 for unknown routes ───────────────────────────────────────────────────

def test_unknown_route_returns_404(client):
    rv = client.get("/api/does-not-exist")
    assert rv.status_code == 404

# ── Smoke: app imports without error ──────────────────────────────────────────

def test_app_imports():
    import server_v2
    assert hasattr(server_v2, "app")
