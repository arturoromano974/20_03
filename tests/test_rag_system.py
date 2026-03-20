"""Tests for models/rag_system.py – chunk creation logic."""

import sys
import pytest
from unittest.mock import MagicMock

MOCK_CONFIG = {
    "redis": {"host": "localhost", "port": 6379, "db": 0, "password": None, "ttl": 86400,
              "vectorization": {"enabled": True, "model": "text-embedding-ada-002", "dimension": 1536}},
    "rag": {"enabled": True, "vector_db": "qdrant", "chunk_size": 100, "overlap": 20,
            "top_k": 5, "similarity_threshold": 0.7,
            "index_fields": ["campaign_id", "adset_id", "ad_id"]},
}


@pytest.fixture(autouse=True)
def mock_config(monkeypatch):
    import utils.config_loader as cl
    cl._cached_config = MOCK_CONFIG
    yield
    cl._cached_config = None


@pytest.fixture(autouse=True)
def mock_external_deps(monkeypatch):
    """Mock openai and redis so cache/redis_utils can be imported without real services."""
    # Ensure openai is available as a mock module
    openai_mock = MagicMock()
    monkeypatch.setitem(sys.modules, "openai", openai_mock)

    # Mock redis.Redis to prevent real connections
    import redis as redis_module
    monkeypatch.setattr(redis_module, "Redis", lambda **kwargs: MagicMock())

    # Clear cached imports so the mocks take effect
    for mod_name in list(sys.modules):
        if mod_name.startswith("cache.redis_utils") or mod_name.startswith("models.rag_system"):
            monkeypatch.delitem(sys.modules, mod_name, raising=False)

    yield


def _make_rag():
    from models.rag_system import RAGSystem
    return RAGSystem()


def test_create_chunks_short_text():
    rag = _make_rag()
    chunks = rag._create_chunks("short")
    assert chunks == ["short"]


def test_create_chunks_exact_size():
    rag = _make_rag()
    text = "a" * 100
    chunks = rag._create_chunks(text)
    assert chunks == [text]


def test_create_chunks_overlap():
    rag = _make_rag()
    text = "a" * 250
    chunks = rag._create_chunks(text)
    # chunk_size=100, overlap=20 -> step=80
    assert len(chunks) >= 3
    for c in chunks:
        assert len(c) <= 100


def test_create_chunks_large_overlap_no_infinite_loop():
    """When overlap >= chunk_size the method must still terminate."""
    rag = _make_rag()
    rag.overlap = 200  # > chunk_size of 100
    text = "a" * 500
    chunks = rag._create_chunks(text)  # must not hang
    assert len(chunks) > 0


def test_create_chunks_empty():
    rag = _make_rag()
    assert rag._create_chunks("") == []
