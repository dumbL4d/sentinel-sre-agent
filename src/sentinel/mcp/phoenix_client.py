"""Phoenix MCP Client - Real MCP protocol integration for agent self-introspection.

Spawns @arizeai/phoenix-mcp via npx and communicates using the MCP protocol over stdio.
Gracefully falls back to demo data when Phoenix isn't available.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


class PhoenixMCPClient:
    """Client for the Phoenix MCP server using the real MCP protocol."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        project_name: str | None = None,
    ):
        self.base_url = base_url or os.environ.get(
            "PHOENIX_MCP_BASE_URL",
            os.environ.get("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006"),
        )
        self.api_key = api_key or os.environ.get("PHOENIX_API_KEY", "")
        self.project_name = project_name or os.environ.get("SENTINEL_PROJECT_NAME", "sentinel-sre-agent")
        self._npx_available = shutil.which("npx") is not None
        self._demo_mode = os.environ.get("SENTINEL_DEMO_MODE", "false").lower() == "true"

    def _use_demo(self) -> bool:
        return self._demo_mode or not self._npx_available

    def _get_server_params(self) -> StdioServerParameters:
        args = [
            "-y", "@arizeai/phoenix-mcp@latest",
            "--baseUrl", self.base_url,
        ]
        if self.api_key:
            args.extend(["--apiKey", self.api_key])

        env = os.environ.copy()
        if self.api_key:
            env["PHOENIX_API_KEY"] = self.api_key
        env["PHOENIX_HOST"] = self.base_url
        env["PHOENIX_PROJECT"] = self.project_name

        return StdioServerParameters(command="npx", args=args, env=env)

    @asynccontextmanager
    async def _session(self):
        server_params = self._get_server_params()
        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session

    async def _call_mcp_tool(self, tool_name: str, arguments: dict) -> Any:
        async with self._session() as session:
            result = await session.call_tool(tool_name, arguments)
            return self._parse_tool_result(result)

    async def list_projects(self) -> list[dict[str, Any]]:
        return await self._call_mcp_tool("list-projects", {})

    async def list_traces(self, project_name: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        project = project_name or self.project_name
        return await self._call_mcp_tool("list-traces", {"project_name": project, "limit": limit})

    async def get_trace(self, trace_id: str) -> dict[str, Any]:
        return await self._call_mcp_tool("get-trace", {"trace_id": trace_id})

    async def get_spans(self, trace_id: str | None = None, span_kind: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if trace_id:
            params["trace_id"] = trace_id
        if span_kind:
            params["span_kind"] = span_kind
        return await self._call_mcp_tool("get-spans", params)

    async def list_sessions(self, project_name: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        project = project_name or self.project_name
        return await self._call_mcp_tool("list-sessions", {"project_name": project, "limit": limit})

    async def get_session(self, session_id: str) -> dict[str, Any]:
        return await self._call_mcp_tool("get-session", {"session_id": session_id})

    async def list_annotation_configs(self) -> list[dict[str, Any]]:
        return await self._call_mcp_tool("list-annotation-configs", {})

    async def list_prompts(self) -> list[dict[str, Any]]:
        return await self._call_mcp_tool("list-prompts", {})

    async def list_datasets(self) -> list[dict[str, Any]]:
        return await self._call_mcp_tool("list-datasets", {})

    # --- Sync wrappers with demo fallback ---

    def query_recent_traces(self, project_name: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        if self._use_demo():
            return self._demo_traces()[:limit]
        return self._run_async(self.list_traces(project_name, limit))

    def query_sessions(self, project_name: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        if self._use_demo():
            return self._demo_sessions()[:limit]
        return self._run_async(self.list_sessions(project_name, limit))

    def query_spans(self, trace_id: str | None = None, span_kind: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        if self._use_demo():
            return self._demo_spans()[:limit]
        return self._run_async(self.get_spans(trace_id=trace_id, span_kind=span_kind, limit=limit))

    def query_evaluations(self, project_name: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        if self._use_demo():
            return self._demo_evaluations()[:limit]
        return self._run_async(self.list_annotation_configs())

    def find_similar_incidents(self, query: str, project_name: str | None = None) -> list[dict[str, Any]]:
        if self._use_demo():
            return self._demo_similar_incidents(query)
        return self._run_async(self._find_similar_incidents_async(query, project_name))

    def get_self_improvement_context(self, current_query: str) -> str:
        if self._use_demo():
            return self._demo_self_improvement_context(current_query)
        return self._run_async(self._get_self_improvement_context_async(current_query))

    async def _find_similar_incidents_async(self, query: str, project_name: str | None = None) -> list[dict[str, Any]]:
        traces = await self.list_traces(project_name, limit=50)
        query_words = set(query.lower().split())
        similar = []
        for trace in traces:
            trace_text = json.dumps(trace).lower()
            overlap = len(query_words & set(trace_text.split()))
            if overlap >= 2:
                similar.append({
                    "trace": trace,
                    "similarity_score": overlap / max(len(query_words), 1),
                })
        similar.sort(key=lambda x: x["similarity_score"], reverse=True)
        return similar[:5]

    async def _get_self_improvement_context_async(self, current_query: str) -> str:
        context_parts = []
        try:
            similar = await self._find_similar_incidents_async(current_query)
            if similar:
                context_parts.append("## Past Similar Incidents (from Phoenix traces)")
                for i, item in enumerate(similar[:3], 1):
                    trace = item["trace"]
                    trace_id = trace.get("trace_id", trace.get("context", {}).get("trace_id", "N/A"))
                    context_parts.append(f"### Incident {i} (similarity: {item['similarity_score']:.2f})")
                    context_parts.append(f"- Trace ID: {trace_id}")
                    if trace.get("annotations"):
                        context_parts.append(f"- Annotations: {trace['annotations']}")
        except Exception as e:
            context_parts.append(f"Note: Could not query past traces: {e}")

        try:
            sessions = await self.list_sessions(limit=5)
            if sessions:
                context_parts.append(f"\n## Recent Sessions ({len(sessions)})")
                for s in sessions[:3]:
                    context_parts.append(f"- Session: {s.get('session_id', 'N/A')}")
        except Exception:
            pass

        return "\n".join(context_parts) if context_parts else "No historical data available yet."

    def _run_async(self, coro):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, coro)
                    return future.result(timeout=30)
            return loop.run_until_complete(coro)
        except Exception:
            return []

    @staticmethod
    def _parse_tool_result(result) -> list[dict] | dict:
        if hasattr(result, "content"):
            for content in result.content:
                if hasattr(content, "text") and content.text:
                    try:
                        return json.loads(content.text)
                    except json.JSONDecodeError:
                        return content.text
            return []
        return result

    # --- Demo data ---

    def _demo_traces(self) -> list[dict]:
        return [
            {
                "trace_id": "trace-001",
                "session_id": "session-alpha",
                "timestamp": "2026-05-05T14:23:00Z",
                "query": "Investigate latency spike in sentiment-classifier-v2",
                "tools_used": ["query_metrics", "correlate_signals"],
                "outcome": "identified_root_cause",
                "annotations": {"accuracy": 4.5, "completeness": 4.0},
            },
            {
                "trace_id": "trace-002",
                "session_id": "session-beta",
                "timestamp": "2026-05-05T10:15:00Z",
                "query": "Check for model drift in recommendation-engine",
                "tools_used": ["analyze_drift"],
                "outcome": "false_alarm",
                "annotations": {"accuracy": 3.0},
            },
            {
                "trace_id": "trace-003",
                "session_id": "session-gamma",
                "timestamp": "2026-05-04T16:45:00Z",
                "query": "Error rate spike in fraud-detection model",
                "tools_used": ["query_metrics", "query_traces", "correlate_signals"],
                "outcome": "identified_root_cause",
                "annotations": {"accuracy": 4.8, "actionability": 5.0},
            },
        ]

    def _demo_sessions(self) -> list[dict]:
        return [
            {"session_id": "session-alpha", "turns": 5, "tools_called": 3, "status": "resolved"},
            {"session_id": "session-beta", "turns": 3, "tools_called": 2, "status": "resolved"},
            {"session_id": "session-gamma", "turns": 8, "tools_called": 4, "status": "resolved"},
        ]

    def _demo_spans(self) -> list[dict]:
        return [
            {
                "span_id": "span-001",
                "trace_id": "trace-001",
                "span_kind": "LLM",
                "name": "generate_content",
                "start_time": "2026-05-05T14:23:00.123Z",
                "end_time": "2026-05-05T14:23:02.456Z",
                "duration_ms": 2333.0,
                "attributes": {"model": "gemini-2.0-flash", "temperature": 0.7},
            },
            {
                "span_id": "span-002",
                "trace_id": "trace-001",
                "span_kind": "TOOL",
                "name": "query_metrics",
                "start_time": "2026-05-05T14:23:02.500Z",
                "end_time": "2026-05-05T14:23:02.800Z",
                "duration_ms": 300.0,
                "attributes": {"tool": "query_metrics", "model_id": "sentiment-classifier-v2"},
            },
            {
                "span_id": "span-003",
                "trace_id": "trace-003",
                "span_kind": "LLM",
                "name": "generate_content",
                "start_time": "2026-05-04T16:45:10.000Z",
                "end_time": "2026-05-04T16:45:15.000Z",
                "duration_ms": 5000.0,
                "attributes": {"model": "gemini-2.0-flash", "temperature": 0.5},
            },
        ]

    def _demo_evaluations(self) -> list[dict]:
        return [
            {"config_id": "eval-001", "name": "accuracy", "kind": "LLM", "score": 4.5},
            {"config_id": "eval-002", "name": "completeness", "kind": "LLM", "score": 4.0},
            {"config_id": "eval-003", "name": "actionability", "kind": "LLM", "score": 4.2},
        ]

    def _demo_similar_incidents(self, query: str) -> list[dict]:
        traces = self._demo_traces()
        query_words = set(query.lower().split())
        similar = []
        for trace in traces:
            trace_text = json.dumps(trace).lower()
            trace_words = set(trace_text.split())
            overlap = len(query_words & trace_words)
            if overlap >= 2:
                similar.append({
                    "trace": trace,
                    "similarity_score": overlap / max(len(query_words), 1),
                })
        similar.sort(key=lambda x: x["similarity_score"], reverse=True)
        return similar[:5]

    def _demo_self_improvement_context(self, current_query: str) -> str:
        similar = self._demo_similar_incidents(current_query)
        parts = []
        if similar:
            parts.append("## Past Similar Incidents (from Phoenix traces)")
            for i, item in enumerate(similar[:3], 1):
                trace = item["trace"]
                parts.append(f"### Incident {i} (similarity: {item['similarity_score']:.2f})")
                parts.append(f"- Trace ID: {trace.get('trace_id', 'N/A')}")
                parts.append(f"- Outcome: {trace.get('outcome', 'Unknown')}")
                if trace.get("annotations"):
                    parts.append(f"- Annotations: {trace['annotations']}")

        sessions = self._demo_sessions()
        if sessions:
            parts.append(f"\n## Recent Sessions ({len(sessions)})")
            for s in sessions[:3]:
                parts.append(f"- Session: {s.get('session_id', 'N/A')} ({s.get('status', 'N/A')})")

        return "\n".join(parts) if parts else "No historical data available yet."
