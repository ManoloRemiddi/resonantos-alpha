"""Smoke tests: verify all page routes return 200."""

import pytest

PAGE_ROUTES = [
    "/",
    "/agents",
    "/coding-agents",
    "/r-memory",
    "/projects",
    "/chatbots",
    "/wallet",
    "/tribes",
    "/bounties",
    "/protocol-store",
    "/docs",
    "/license",
    "/setup",
    "/todo",
    "/intelligence",
    "/memory-bridge",
    "/settings",
    "/ssot",
    "/shield",
    "/policy-graph",
]


@pytest.mark.parametrize("route", PAGE_ROUTES)
def test_page_returns_200(client, route: str) -> None:
    """Each page route should return HTTP 200."""
    response = client.get(route)
    assert response.status_code == 200, f"{route} returned {response.status_code}"
