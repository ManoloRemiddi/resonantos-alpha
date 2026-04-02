"""Shared test fixtures for ResonantOS dashboard tests."""

from pathlib import Path

import pytest


@pytest.fixture
def app():
    """Create a test Flask application."""
    # Import here to avoid circular imports during collection
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from server_v2 import app as flask_app

    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()
