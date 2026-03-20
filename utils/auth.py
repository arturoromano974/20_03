"""
Authentication utilities for agent endpoints.
"""

import os
import logging
from functools import wraps
from flask import request, jsonify

logger = logging.getLogger(__name__)

AGENT_API_KEY = os.environ.get("AGENT_API_KEY")


def require_auth(f):
    """Decorator that enforces API key authentication on Flask routes.

    The client must send the key in the ``X-API-Key`` header.
    If ``AGENT_API_KEY`` is not configured, all requests are allowed
    so that development / testing is not blocked.
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        if not AGENT_API_KEY:
            # Auth not configured – allow all requests
            return f(*args, **kwargs)

        token = request.headers.get("X-API-Key")
        if token != AGENT_API_KEY:
            logger.warning("Unauthorized request from %s", request.remote_addr)
            return jsonify({"status": "error", "error": "Unauthorized"}), 401

        return f(*args, **kwargs)

    return decorated
