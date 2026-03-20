"""Tests for utils/auth.py"""

import os
import pytest
from flask import Flask


@pytest.fixture
def app():
    """Create a test Flask app."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    return app


def test_auth_bypassed_when_key_not_set(app, monkeypatch):
    """When AGENT_API_KEY is not set, requests pass through."""
    monkeypatch.delenv("AGENT_API_KEY", raising=False)

    # Reload module to pick up env change
    import utils.auth
    monkeypatch.setattr(utils.auth, "AGENT_API_KEY", None)

    from utils.auth import require_auth

    @app.route("/test", methods=["POST"])
    @require_auth
    def test_route():
        return "ok"

    with app.test_client() as client:
        resp = client.post("/test")
        assert resp.status_code == 200


def test_auth_rejects_missing_key(app, monkeypatch):
    """When AGENT_API_KEY is set, requests without key are rejected."""
    import utils.auth
    monkeypatch.setattr(utils.auth, "AGENT_API_KEY", "secret123")

    from utils.auth import require_auth

    @app.route("/test2", methods=["POST"])
    @require_auth
    def test_route2():
        return "ok"

    with app.test_client() as client:
        resp = client.post("/test2")
        assert resp.status_code == 401


def test_auth_accepts_correct_key(app, monkeypatch):
    """When correct key is provided, request passes through."""
    import utils.auth
    monkeypatch.setattr(utils.auth, "AGENT_API_KEY", "secret123")

    from utils.auth import require_auth

    @app.route("/test3", methods=["POST"])
    @require_auth
    def test_route3():
        return "ok"

    with app.test_client() as client:
        resp = client.post("/test3", headers={"X-API-Key": "secret123"})
        assert resp.status_code == 200


def test_auth_rejects_wrong_key(app, monkeypatch):
    """When wrong key is provided, request is rejected."""
    import utils.auth
    monkeypatch.setattr(utils.auth, "AGENT_API_KEY", "secret123")

    from utils.auth import require_auth

    @app.route("/test4", methods=["POST"])
    @require_auth
    def test_route4():
        return "ok"

    with app.test_client() as client:
        resp = client.post("/test4", headers={"X-API-Key": "wrong"})
        assert resp.status_code == 401
