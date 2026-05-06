"""Action tools for alerts and remediation."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from .base import BaseTool


class CreateAlert(BaseTool):
    """Create a new alert or incident ticket."""

    name = "create_alert"
    description = "Create a new alert or incident ticket when an issue is identified that needs human attention or escalation."

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
                            "description": "The model this alert is for",
                        },
                        "severity": {
                            "type": "STRING",
                            "enum": ["critical", "high", "medium", "low"],
                            "description": "Alert severity level",
                        },
                        "title": {
                            "type": "STRING",
                            "description": "Short title for the alert",
                        },
                        "message": {
                            "type": "STRING",
                            "description": "Detailed alert message",
                        },
                        "recommended_action": {
                            "type": "STRING",
                            "description": "Recommended action to resolve",
                        },
                    },
                    "required": ["model_id", "severity", "message"],
                },
            }]
        }

    def execute(
        self,
        model_id: str,
        severity: str,
        message: str,
        title: str = "",
        recommended_action: str = "",
    ) -> str:
        alert_id = f"SENTINEL-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        alert = {
            "alert_id": alert_id,
            "title": title or f"Sentinel alert: {model_id}",
            "model_id": model_id,
            "severity": severity,
            "message": message,
            "recommended_action": recommended_action,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "created",
            "source": "sentinel-sre-agent",
        }
        return json.dumps(alert, indent=2)


class SuggestRemediation(BaseTool):
    """Suggest remediation actions based on identified issues."""

    name = "suggest_remediation"
    description = "Suggest specific remediation actions based on the type of issue detected. Includes runbook steps and prioritized actions."

    RUNBOOKS: dict[str, list[dict]] = {
        "latency_spike": [
            {
                "step": 1,
                "action": "Check infrastructure resource utilization",
                "detail": "Review CPU, memory, and GPU utilization on inference endpoints",
                "priority": "immediate",
            },
            {
                "step": 2,
                "action": "Review recent deployments",
                "detail": "Check if any model version updates or infrastructure changes coincide with the spike",
                "priority": "immediate",
            },
            {
                "step": 3,
                "action": "Analyze input payload sizes",
                "detail": "Check for unusually large requests that could cause latency outliers",
                "priority": "short-term",
            },
            {
                "step": 4,
                "action": "Scale inference endpoints",
                "detail": "Increase instance count or enable auto-scaling if resources are constrained",
                "priority": "short-term",
            },
            {
                "step": 5,
                "action": "Enable request queuing and rate limiting",
                "detail": "Implement graceful degradation under load",
                "priority": "long-term",
            },
        ],
        "error_rate_increase": [
            {
                "step": 1,
                "action": "Check model serving logs",
                "detail": "Review error logs for patterns, stack traces, and error types",
                "priority": "immediate",
            },
            {
                "step": 2,
                "action": "Validate input data schema",
                "detail": "Check for schema mismatches or malformed inputs",
                "priority": "immediate",
            },
            {
                "step": 3,
                "action": "Review model dependencies",
                "detail": "Check for version compatibility issues in model dependencies",
                "priority": "short-term",
            },
            {
                "step": 4,
                "action": "Roll back to stable version",
                "detail": "If errors persist, roll back to the previous stable model version",
                "priority": "short-term",
            },
            {
                "step": 5,
                "action": "Add input validation layer",
                "detail": "Implement robust input validation before model inference",
                "priority": "long-term",
            },
        ],
        "prediction_drift": [
            {
                "step": 1,
                "action": "Identify drifted features",
                "detail": "Review which input features show the highest drift scores",
                "priority": "immediate",
            },
            {
                "step": 2,
                "action": "Check upstream data sources",
                "detail": "Investigate data pipelines for schema changes or data quality issues",
                "priority": "immediate",
            },
            {
                "step": 3,
                "action": "Enable fallback model",
                "detail": "Switch to a previous stable model version if drift is severe",
                "priority": "short-term",
            },
            {
                "step": 4,
                "action": "Trigger model retraining",
                "detail": "Start retraining pipeline with recent data distribution",
                "priority": "short-term",
            },
            {
                "step": 5,
                "action": "Implement continuous drift monitoring",
                "detail": "Set up automated alerts for early drift detection",
                "priority": "long-term",
            },
        ],
        "throughput_degradation": [
            {
                "step": 1,
                "action": "Check infrastructure bottlenecks",
                "detail": "Review network, disk I/O, and compute resource utilization",
                "priority": "immediate",
            },
            {
                "step": 2,
                "action": "Review rate limiting config",
                "detail": "Check if throttling or rate limiting is causing the drop",
                "priority": "immediate",
            },
            {
                "step": 3,
                "action": "Analyze queue depth",
                "detail": "Check request queue depth and processing latency",
                "priority": "short-term",
            },
            {
                "step": 4,
                "action": "Scale horizontally",
                "detail": "Add more inference instances to handle load",
                "priority": "short-term",
            },
            {
                "step": 5,
                "action": "Optimize model inference",
                "detail": "Consider model quantization, batching, or caching optimizations",
                "priority": "long-term",
            },
        ],
    }

    def to_gemini_tool(self) -> dict[str, Any]:
        return {
            "function_declarations": [{
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "issue_type": {
                            "type": "STRING",
                            "enum": ["latency_spike", "error_rate_increase", "prediction_drift", "throughput_degradation"],
                            "description": "The type of issue detected",
                        },
                        "context": {
                            "type": "STRING",
                            "description": "Additional context about the specific issue",
                        },
                    },
                    "required": ["issue_type"],
                },
            }]
        }

    def execute(
        self,
        issue_type: str,
        context: str = "",
    ) -> str:
        runbook_steps = self.RUNBOOKS.get(issue_type, [
            {
                "step": 1,
                "action": "Investigate logs and metrics",
                "detail": "Review all available observability data for root cause",
                "priority": "immediate",
            },
        ])

        result = {
            "issue_type": issue_type,
            "context": context,
            "runbook": runbook_steps,
            "priority_overall": "high" if issue_type in ("prediction_drift", "error_rate_increase") else "medium",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        return json.dumps(result, indent=2)
