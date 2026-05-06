"""Analysis tools for drift detection and signal correlation."""

from __future__ import annotations

import json
import random
import time
from typing import Any

from .base import BaseTool


class AnalyzeDrift(BaseTool):
    """Analyze prediction drift for a model."""

    name = "analyze_drift"
    description = "Analyze prediction drift to detect if the model's input distribution or output behavior has changed significantly from baseline. Returns drift score, affected features, and severity."

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
                            "description": "The model identifier to analyze drift for",
                        },
                        "reference_window_hours": {
                            "type": "INTEGER",
                            "description": "Reference/baseline window in hours (default: 168 = 1 week)",
                        },
                        "current_window_hours": {
                            "type": "INTEGER",
                            "description": "Current evaluation window in hours (default: 24)",
                        },
                    },
                    "required": ["model_id"],
                },
            }]
        }

    def execute(
        self,
        model_id: str,
        reference_window_hours: int = 168,
        current_window_hours: int = 24,
    ) -> str:
        seed = hash(model_id) % 1000
        random.seed(seed + 42)

        drift_score = round(random.uniform(0.15, 0.45), 3)
        threshold = 0.20

        features = [
            {"feature": "user_session_length", "drift_score": round(random.uniform(0.30, 0.60), 3)},
            {"feature": "request_payload_size", "drift_score": round(random.uniform(0.15, 0.35), 3)},
            {"feature": "geographic_region", "drift_score": round(random.uniform(0.05, 0.20), 3)},
            {"feature": "device_type", "drift_score": round(random.uniform(0.10, 0.25), 3)},
            {"feature": "time_of_day", "drift_score": round(random.uniform(0.02, 0.12), 3)},
        ]

        for f in features:
            f["severity"] = "high" if f["drift_score"] > 0.4 else ("medium" if f["drift_score"] > 0.2 else "low")

        affected = [f for f in features if f["drift_score"] > threshold]

        result = {
            "model_id": model_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "drift_detected": drift_score > threshold,
            "drift_score": drift_score,
            "drift_threshold": threshold,
            "affected_features": affected,
            "all_features": features,
            "reference_window_hours": reference_window_hours,
            "current_window_hours": current_window_hours,
            "recommendation": (
                "Immediate action recommended: significant drift detected. "
                "Consider model retraining or fallback to previous version."
                if drift_score > threshold
                else "Drift within acceptable range. Continue monitoring."
            ),
        }
        return json.dumps(result, indent=2)


class CorrelateSignals(BaseTool):
    """Correlate multiple observability signals to identify patterns."""

    name = "correlate_signals"
    description = "Correlate metrics, traces, alerts, and drift data to identify patterns and potential root causes. Use this when a single metric doesn't tell the full story."

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
                            "description": "The model identifier to correlate signals for",
                        },
                        "signal_types": {
                            "type": "ARRAY",
                            "items": {"type": "STRING", "enum": ["metrics", "traces", "alerts", "drift"]},
                            "description": "Types of signals to correlate",
                        },
                    },
                    "required": ["model_id", "signal_types"],
                },
            }]
        }

    def execute(
        self,
        model_id: str,
        signal_types: list[str],
    ) -> str:
        from .query import QueryMetrics, GetAlerts

        correlation = {
            "model_id": model_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "signals_analyzed": signal_types,
            "findings": [],
            "overall_severity": "low",
        }

        severities = []

        if "metrics" in signal_types:
            metrics_tool = QueryMetrics()
            metrics_data = json.loads(metrics_tool.execute(model_id=model_id))
            metrics = metrics_data.get("metrics", {})

            if "latency_p99" in metrics:
                change = metrics["latency_p99"].get("change_pct", 0)
                if change > 50:
                    correlation["findings"].append({
                        "signal": "latency_p99",
                        "severity": "critical" if change > 100 else "high",
                        "detail": f"P99 latency increased {change}% above baseline",
                    })
                    severities.append("critical" if change > 100 else "high")

            if "error_rate" in metrics:
                current = metrics["error_rate"].get("current", 0)
                baseline = metrics["error_rate"].get("baseline", 0)
                if baseline > 0 and current / baseline > 2:
                    correlation["findings"].append({
                        "signal": "error_rate",
                        "severity": "high",
                        "detail": f"Error rate {current:.1%} is {current/baseline:.1f}x baseline ({baseline:.1%})",
                    })
                    severities.append("high")

        if "drift" in signal_types:
            drift_tool = AnalyzeDrift()
            drift_data = json.loads(drift_tool.execute(model_id=model_id))

            if drift_data.get("drift_detected"):
                correlation["findings"].append({
                    "signal": "prediction_drift",
                    "severity": "high" if drift_data["drift_score"] > 0.3 else "medium",
                    "detail": f"Drift score {drift_data['drift_score']} exceeds threshold {drift_data['drift_threshold']}",
                    "affected_features": [f["feature"] for f in drift_data.get("affected_features", [])],
                })
                severities.append("high" if drift_data["drift_score"] > 0.3 else "medium")

        if "alerts" in signal_types:
            alerts_tool = GetAlerts()
            alerts_data = json.loads(alerts_tool.execute(model_id=model_id))

            for alert in alerts_data:
                if alert.get("status") == "active":
                    correlation["findings"].append({
                        "signal": f"alert_{alert['type']}",
                        "severity": alert.get("severity", "medium"),
                        "detail": alert.get("message", ""),
                    })
                    severities.append(alert.get("severity", "medium"))

        severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        if severities:
            correlation["overall_severity"] = max(severities, key=lambda s: severity_order.get(s, 0))

        if len(correlation["findings"]) > 1:
            correlation["pattern"] = (
                f"Multiple signals ({len(correlation['findings'])}) indicate a systemic issue. "
                "This is likely not an isolated anomaly but a broader problem affecting the model pipeline."
            )

        return json.dumps(correlation, indent=2)
