"""Query tools for fetching SRE data."""

from __future__ import annotations

import json
import random
import time
from typing import Any

from .base import BaseTool


class QueryMetrics(BaseTool):
    """Query model performance metrics."""

    name = "query_metrics"
    description = "Query real-time model performance metrics including accuracy, latency, throughput, and error rates. Use this to check current model health."

    def to_gemini_tool(self) -> dict[str, Any]:
        return {
            "function_declarations": [{
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "model_id": {
                            "type": "STRING",
                            "description": "The model identifier to query metrics for",
                        },
                        "metric_names": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"},
                            "description": "Specific metrics: accuracy, latency_p50, latency_p99, throughput, error_rate",
                        },
                        "time_range_hours": {
                            "type": "INTEGER",
                            "description": "Time range for metrics in hours (default: 24)",
                        },
                    },
                    "required": ["model_id"],
                },
            }]
        }

    def execute(
        self,
        model_id: str,
        metric_names: list[str] | None = None,
        time_range_hours: int = 24,
    ) -> str:
        metrics = self._get_metrics(model_id)

        if metric_names:
            metrics = {k: v for k, v in metrics.items() if k in metric_names}

        result = {
            "model_id": model_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "time_range_hours": time_range_hours,
            "metrics": metrics,
        }
        return json.dumps(result, indent=2)

    def _get_metrics(self, model_id: str) -> dict:
        """Generate realistic metrics based on model patterns."""
        seed = hash(model_id) % 1000
        random.seed(seed)

        base_latency = random.randint(25, 50)
        current_latency_p99 = base_latency * random.uniform(1.5, 3.0)
        baseline_latency_p99 = base_latency * 1.3

        base_error = random.uniform(0.01, 0.03)
        current_error = base_error * random.uniform(2.0, 5.0)

        return {
            "accuracy": {
                "current": round(random.uniform(0.82, 0.95), 3),
                "baseline": round(random.uniform(0.93, 0.97), 3),
                "trend": "declining" if random.random() > 0.5 else "stable",
            },
            "latency_p50": {
                "current": round(base_latency * random.uniform(1.0, 1.5), 1),
                "baseline": base_latency,
                "unit": "ms",
            },
            "latency_p99": {
                "current": round(current_latency_p99, 1),
                "baseline": round(baseline_latency_p99, 1),
                "unit": "ms",
                "change_pct": round((current_latency_p99 - baseline_latency_p99) / baseline_latency_p99 * 100, 1),
            },
            "throughput": {
                "current": random.randint(800, 1400),
                "baseline": random.randint(1200, 1800),
                "unit": "req/min",
            },
            "error_rate": {
                "current": round(current_error, 4),
                "baseline": round(base_error, 4),
                "trend": "increasing",
            },
        }


class QueryTraces(BaseTool):
    """Query individual request traces."""

    name = "query_traces"
    description = "Query individual request traces from a model to analyze specific requests, errors, latency outliers, or patterns."

    def to_gemini_tool(self) -> dict[str, Any]:
        return {
            "function_declarations": [{
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "model_id": {
                            "type": "STRING",
                            "description": "The model identifier to query traces for",
                        },
                        "filter_criteria": {
                            "type": "OBJECT",
                            "properties": {
                                "status": {"type": "STRING", "description": "Filter: 'error' or 'success'"},
                                "min_latency_ms": {"type": "NUMBER", "description": "Minimum latency filter"},
                            },
                            "description": "Optional filters for trace selection",
                        },
                        "limit": {
                            "type": "INTEGER",
                            "description": "Maximum traces to return (default: 50)",
                        },
                    },
                    "required": ["model_id"],
                },
            }]
        }

    def execute(
        self,
        model_id: str,
        filter_criteria: dict[str, str] | None = None,
        limit: int = 50,
    ) -> str:
        seed = hash(model_id) % 1000
        random.seed(seed)

        traces = []
        for i in range(min(limit, 20)):
            is_error = random.random() < 0.15
            latency = random.gauss(45, 30)
            if is_error:
                latency = random.gauss(180, 60)

            trace = {
                "trace_id": f"trace-{model_id}-{i:04d}",
                "timestamp": f"2026-05-06T{10 + i // 60:02d}:{i % 60:02d}:00Z",
                "latency_ms": round(max(latency, 10), 1),
                "status": "error" if is_error else "success",
                "model_version": "v2.3.1",
                "input_size": random.randint(100, 2000),
                "output_size": random.randint(50, 500),
            }

            if filter_criteria:
                if filter_criteria.get("status") and trace["status"] != filter_criteria["status"]:
                    continue
                if filter_criteria.get("min_latency_ms"):
                    if trace["latency_ms"] < float(filter_criteria["min_latency_ms"]):
                        continue

            traces.append(trace)

        return json.dumps(traces, indent=2)


class GetAlerts(BaseTool):
    """Get active alerts."""

    name = "get_alerts"
    description = "Get active alerts for models. Use this to see what issues are currently being flagged by the monitoring system."

    def to_gemini_tool(self) -> dict[str, Any]:
        return {
            "function_declarations": [{
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "model_id": {
                            "type": "STRING",
                            "description": "Filter alerts by model ID (optional)",
                        },
                        "severity": {
                            "type": "STRING",
                            "enum": ["critical", "high", "medium", "low"],
                            "description": "Filter by severity level",
                        },
                    },
                },
            }]
        }

    def execute(
        self,
        model_id: str | None = None,
        severity: str | None = None,
    ) -> str:
        alerts = [
            {
                "alert_id": "ALT-001",
                "model_id": "sentiment-classifier-v2",
                "type": "latency_spike",
                "severity": "critical",
                "message": "P99 latency increased 147% above baseline (210ms vs 85ms)",
                "triggered_at": "2026-05-06T10:20:00Z",
                "status": "active",
            },
            {
                "alert_id": "ALT-002",
                "model_id": "sentiment-classifier-v2",
                "type": "error_rate_increase",
                "severity": "high",
                "message": "Error rate increased 4x from baseline (8% vs 2%)",
                "triggered_at": "2026-05-06T10:15:00Z",
                "status": "active",
            },
            {
                "alert_id": "ALT-003",
                "model_id": "sentiment-classifier-v2",
                "type": "prediction_drift",
                "severity": "high",
                "message": "Prediction drift score 0.34 exceeds threshold 0.20",
                "triggered_at": "2026-05-06T10:23:00Z",
                "status": "active",
            },
            {
                "alert_id": "ALT-004",
                "model_id": "recommendation-engine-v3",
                "type": "throughput_degradation",
                "severity": "medium",
                "message": "Throughput dropped 25% below baseline (900 vs 1200 req/min)",
                "triggered_at": "2026-05-06T09:45:00Z",
                "status": "active",
            },
            {
                "alert_id": "ALT-005",
                "model_id": "fraud-detection-v1",
                "type": "accuracy_degradation",
                "severity": "medium",
                "message": "Accuracy dropped from 96.2% to 89.1%",
                "triggered_at": "2026-05-06T08:30:00Z",
                "status": "active",
            },
        ]

        if model_id:
            alerts = [a for a in alerts if a["model_id"] == model_id]
        if severity:
            alerts = [a for a in alerts if a["severity"] == severity]

        return json.dumps(alerts, indent=2)
