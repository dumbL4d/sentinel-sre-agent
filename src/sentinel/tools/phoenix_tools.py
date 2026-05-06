"""Phoenix observability tools - Query real Phoenix trace data for SRE analysis.

These tools query actual Phoenix traces and spans to extract model performance
metrics, error patterns, and latency data from real observability data.
"""

from __future__ import annotations

import json
from typing import Any

from ..mcp import PhoenixMCPClient
from .base import BaseTool


class QueryPhoenixTraces(BaseTool):
    """Query traces from Phoenix to analyze model behavior."""

    name = "query_phoenix_traces"
    description = (
        "Query recent traces from Phoenix to analyze model behavior, latency patterns, "
        "error rates, and tool usage. Use this for real observability data instead of metrics."
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
                        "project_name": {
                            "type": "STRING",
                            "description": "Phoenix project name to query",
                        },
                        "limit": {
                            "type": "INTEGER",
                            "description": "Maximum traces to return (default: 20)",
                        },
                    },
                },
            }]
        }

    def execute(
        self,
        project_name: str | None = None,
        limit: int = 20,
    ) -> str:
        traces = self.phoenix_client.query_recent_traces(project_name, limit)
        return json.dumps({
            "source": "phoenix_traces",
            "count": len(traces),
            "traces": traces,
        }, indent=2)


class QueryPhoenixSpans(BaseTool):
    """Query spans from Phoenix for detailed LLM call analysis."""

    name = "query_phoenix_spans"
    description = (
        "Query spans from Phoenix to inspect individual LLM calls, tool invocations, "
        "and their latency. Filter by span_kind (LLM, TOOL, CHAIN) to focus analysis."
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
                        "trace_id": {
                            "type": "STRING",
                            "description": "Filter spans by trace ID",
                        },
                        "span_kind": {
                            "type": "STRING",
                            "enum": ["LLM", "TOOL", "CHAIN", "RETRIEVER", "EMBEDDING"],
                            "description": "Filter by span kind",
                        },
                        "limit": {
                            "type": "INTEGER",
                            "description": "Maximum spans to return (default: 50)",
                        },
                    },
                },
            }]
        }

    def execute(
        self,
        trace_id: str | None = None,
        span_kind: str | None = None,
        limit: int = 50,
    ) -> str:
        spans = self.phoenix_client.run_sync(
            self.phoenix_client.get_spans(trace_id=trace_id, span_kind=span_kind, limit=limit)
        )

        analysis = {
            "source": "phoenix_spans",
            "count": len(spans),
            "spans": spans,
            "summary": self._summarize_spans(spans),
        }
        return json.dumps(analysis, indent=2)

    def _summarize_spans(self, spans: list[dict]) -> dict:
        """Create a summary of span data."""
        if not spans:
            return {"message": "No spans found"}

        llm_spans = [s for s in spans if s.get("span_kind") == "LLM"]
        tool_spans = [s for s in spans if s.get("span_kind") == "TOOL"]

        return {
            "total_spans": len(spans),
            "llm_calls": len(llm_spans),
            "tool_calls": len(tool_spans),
        }


class QueryPhoenixSessions(BaseTool):
    """Query conversation sessions from Phoenix."""

    name = "query_phoenix_sessions"
    description = (
        "Query conversation sessions from Phoenix to review past investigations "
        "and their outcomes. Useful for finding patterns across multiple incidents."
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
                        "project_name": {
                            "type": "STRING",
                            "description": "Phoenix project name",
                        },
                        "limit": {
                            "type": "INTEGER",
                            "description": "Maximum sessions to return (default: 10)",
                        },
                    },
                },
            }]
        }

    def execute(
        self,
        project_name: str | None = None,
        limit: int = 10,
    ) -> str:
        sessions = self.phoenix_client.query_sessions(project_name, limit)
        return json.dumps({
            "source": "phoenix_sessions",
            "count": len(sessions),
            "sessions": sessions,
        }, indent=2)
