"""Tests for agent tools."""

import json
import os

import pytest

from sentinel.tools import (
    QueryMetrics,
    QueryTraces,
    GetAlerts,
    AnalyzeDrift,
    CorrelateSignals,
    CreateAlert,
    SuggestRemediation,
    SelfIntrospect,
)
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
def phoenix_client():
    return PhoenixMCPClient()


class TestQueryMetrics:
    def test_returns_metrics(self):
        tool = QueryMetrics()
        result = tool.execute(model_id="test-model-v1")
        data = json.loads(result)
        assert "metrics" in data
        assert "model_id" in data

    def test_filters_metrics(self):
        tool = QueryMetrics()
        result = tool.execute(model_id="test-model", metric_names=["accuracy", "error_rate"])
        data = json.loads(result)
        assert set(data["metrics"].keys()) == {"accuracy", "error_rate"}


class TestQueryTraces:
    def test_returns_traces(self):
        tool = QueryTraces()
        result = tool.execute(model_id="test-model", limit=5)
        data = json.loads(result)
        assert isinstance(data, list)
        assert len(data) <= 5

    def test_filters_errors(self):
        tool = QueryTraces()
        result = tool.execute(
            model_id="test-model",
            filter_criteria={"status": "error"},
        )
        data = json.loads(result)
        assert all(t["status"] == "error" for t in data)


class TestGetAlerts:
    def test_returns_alerts(self):
        tool = GetAlerts()
        result = tool.execute()
        data = json.loads(result)
        assert isinstance(data, list)
        assert len(data) > 0

    def test_filters_by_model(self):
        tool = GetAlerts()
        result = tool.execute(model_id="sentiment-classifier-v2")
        data = json.loads(result)
        assert all(a["model_id"] == "sentiment-classifier-v2" for a in data)

    def test_filters_by_severity(self):
        tool = GetAlerts()
        result = tool.execute(severity="critical")
        data = json.loads(result)
        assert all(a["severity"] == "critical" for a in data)


class TestAnalyzeDrift:
    def test_returns_drift_analysis(self):
        tool = AnalyzeDrift()
        result = tool.execute(model_id="test-model")
        data = json.loads(result)
        assert "drift_detected" in data
        assert "drift_score" in data
        assert "affected_features" in data


class TestCorrelateSignals:
    def test_correlates_multiple_signals(self):
        tool = CorrelateSignals()
        result = tool.execute(
            model_id="test-model",
            signal_types=["metrics", "alerts", "drift"],
        )
        data = json.loads(result)
        assert "findings" in data
        assert len(data["findings"]) > 0
        assert "overall_severity" in data


class TestCreateAlert:
    def test_creates_alert(self):
        tool = CreateAlert()
        result = tool.execute(
            model_id="test-model",
            severity="high",
            message="Test alert",
            recommended_action="Investigate",
        )
        data = json.loads(result)
        assert data["model_id"] == "test-model"
        assert data["severity"] == "high"
        assert "alert_id" in data


class TestSuggestRemediation:
    def test_suggests_for_drift(self):
        tool = SuggestRemediation()
        result = tool.execute(issue_type="prediction_drift")
        data = json.loads(result)
        assert len(data["runbook"]) > 0

    def test_suggests_for_latency(self):
        tool = SuggestRemediation()
        result = tool.execute(issue_type="latency_spike")
        data = json.loads(result)
        assert len(data["runbook"]) > 0


class TestSelfIntrospect:
    def test_returns_context(self, phoenix_client):
        tool = SelfIntrospect(phoenix_client)
        result = tool.execute(current_query="Investigate latency spike in model")
        data = json.loads(result)
        assert "self_improvement_context" in data
        assert "similar_past_cases" in data
        assert "recent_sessions" in data
        assert "insights" in data

    def test_finds_similar_cases(self, phoenix_client):
        tool = SelfIntrospect(phoenix_client)
        result = tool.execute(current_query="latency spike model sentiment")
        data = json.loads(result)
        assert len(data["similar_past_cases"]) > 0
