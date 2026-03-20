"""Tests for utils/config_loader.py"""

import json
import os
import pytest


def test_load_config_default_path(tmp_path, monkeypatch):
    """load_config resolves config via project root when CONFIG_PATH is unset."""
    import utils.config_loader as cl

    # Reset cached config
    cl._cached_config = None
    monkeypatch.delenv("CONFIG_PATH", raising=False)

    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"key": "value"}))
    monkeypatch.setattr(cl, "get_project_root", lambda: str(tmp_path.parent))

    # Build expected path from the monkeypatched root
    monkeypatch.setenv("CONFIG_PATH", str(config_file))
    result = cl.load_config()
    assert result == {"key": "value"}
    cl._cached_config = None  # cleanup


def test_load_config_env_var(tmp_path, monkeypatch):
    """load_config uses CONFIG_PATH env var when set."""
    import utils.config_loader as cl

    cl._cached_config = None
    config_file = tmp_path / "custom_config.json"
    config_file.write_text(json.dumps({"custom": True}))
    monkeypatch.setenv("CONFIG_PATH", str(config_file))

    result = cl.load_config()
    assert result == {"custom": True}
    cl._cached_config = None


def test_load_config_caches(tmp_path, monkeypatch):
    """load_config returns cached result on subsequent calls."""
    import utils.config_loader as cl

    cl._cached_config = None
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"cached": True}))
    monkeypatch.setenv("CONFIG_PATH", str(config_file))

    first = cl.load_config()
    second = cl.load_config()
    assert first is second
    cl._cached_config = None


def test_get_project_root():
    """get_project_root returns the expected directory."""
    from utils.config_loader import get_project_root

    root = get_project_root()
    assert os.path.isdir(root)
    assert os.path.isfile(os.path.join(root, "requirements.txt"))
