"""Self-introspection tool - Agent queries Phoenix MCP for its own past traces.

This is the core of the self-improvement loop: the agent uses the Phoenix MCP
server (via the actual MCP protocol) to query its own past traces, sessions,
and evaluations, then uses that context to improve its current investigation.
"""

from __future__ import annotations

import json
from typing import Any

from ..mcp import PhoenixMCPClient
from .base import BaseTool


class SelfIntrospect(BaseTool):
    """Query Phoenix MCP to introspect the agent's own past performance.

    Uses the actual MCP protocol (via @arizeai/phoenix-mcp) to query
    Phoenix traces, sessions, and evaluations at runtime.
    """

    name = "self_introspect"
    description = (
        "Query your own past traces and evaluations from Phoenix via MCP to learn from "
        "previous incidents. Use this to find similar past cases, review what "
        "worked and what didn't, and improve your current investigation. "
        "Always call this at the start of a new investigation."
    )

    def __init__(self, phoenix_client: PhoenixMCPClient):
        self.phoenix_client = phoenix_client

    def to_gemini_tool(self) -> dict[str, Any]:
        return {
            "function_declarations": [{
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "current_query": {
                            "type": "STRING",
                            "description": "The current incident or question you are investigating",
                        },
                    },
                    "required": ["current_query"],
                },
            }]
        }

    def execute(
        self,
        current_query: str,
    ) -> str:
        result = {
            "self_improvement_context": "",
            "similar_past_cases": [],
            "recent_sessions": [],
            "insights": [],
        }

        try:
            context = self.phoenix_client.get_self_improvement_context(current_query)
            result["self_improvement_context"] = context
        except Exception as e:
            result["error"] = f"Could not query Phoenix MCP: {e}"
            result["self_improvement_context"] = (
                "Note: Phoenix MCP server not available. Using default investigation approach. "
                f"Error: {e}"
            )

        try:
            similar = self.phoenix_client.find_similar_incidents(current_query)
            result["similar_past_cases"] = similar[:5]
        except Exception:
            pass

        try:
            sessions = self.phoenix_client.query_sessions(limit=5)
            result["recent_sessions"] = sessions
        except Exception:
            pass

        result["insights"] = self._generate_insights(result)
        return json.dumps(result, indent=2)

    def _generate_insights(self, result: dict) -> list[str]:
        """Generate actionable insights from past performance."""
        insights = []

        similar = result.get("similar_past_cases", [])
        if similar:
            successful = [
                s for s in similar
                if s.get("trace", {}).get("outcome") == "identified_root_cause"
                or s.get("trace", {}).get("annotations")
            ]
            if successful:
                insights.append(
                    f"Found {len(successful)} similar past investigations in Phoenix traces. "
                    "Review these for patterns and successful approaches."
                )

        sessions = result.get("recent_sessions", [])
        if sessions:
            insights.append(f"Found {len(sessions)} recent sessions in Phoenix.")

        if not insights:
            insights.append("No historical traces found in Phoenix yet. Proceed with standard investigation.")

        return insights
