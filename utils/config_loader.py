"""
Centralized Configuration Loader

Provides a single source of truth for loading config and resolving project paths,
replacing hardcoded paths throughout the codebase.
"""

import os
import json

_cached_config = None


def get_project_root() -> str:
    """Return the project root directory dynamically."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_config() -> dict:
    """Load and cache the project configuration.

    Resolution order:
    1. CONFIG_PATH environment variable
    2. <project_root>/config/config.json
    """
    global _cached_config
    if _cached_config is not None:
        return _cached_config

    config_path = os.environ.get("CONFIG_PATH")
    if not config_path:
        config_path = os.path.join(get_project_root(), "config", "config.json")

    with open(config_path, "r") as f:
        _cached_config = json.load(f)

    return _cached_config
