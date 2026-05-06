"""Tests for Phoenix MCP client."""

import os

import pytest

from sentinel.mcp import PhoenixMCPClient


@pytest.fixture(autouse=True)
def demo_mode():
    """Force demo mode for all tests."""
    original = os.environ.get("SENTINEL_DEMO_MODE")
    os.environ["SENTINEL_DEMO_MODE"] = "true"
    yield
    if original is not None:
        os.environ["SENTINEL_DEMO_MODE"] = original
    else:
        os.environ.pop("SENTINEL_DEMO_MODE", None)


@pytest.fixture
def client():
    return PhoenixMCPClient()


class TestPhoenixMCPClient:
    def test_query_recent_traces(self, client):
        traces = client.query_recent_traces()
        assert isinstance(traces, list)
        assert len(traces) > 0
        assert all("trace_id" in t for t in traces)

    def test_query_sessions(self, client):
        sessions = client.query_sessions()
        assert isinstance(sessions, list)
        assert len(sessions) > 0

    def test_query_evaluations(self, client):
        evals = client.query_evaluations()
        assert isinstance(evals, list)
        assert len(evals) > 0
        assert all("score" in e for e in evals)

    def test_find_similar_incidents(self, client):
        similar = client.find_similar_incidents("latency spike model")
        assert isinstance(similar, list)

    def test_get_self_improvement_context(self, client):
        context = client.get_self_improvement_context("latency spike in sentiment model")
        assert isinstance(context, str)
        assert len(context) > 0
        assert "Phoenix" in context
