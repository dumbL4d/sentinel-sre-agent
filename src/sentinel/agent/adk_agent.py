"""Vertex AI ADK-based Sentinel Agent - uses google-adk framework for Google Cloud Agent Builder compliance.

Migrates from the custom google-genai tool-calling loop to Google's Agent Development Kit (ADK).
Preserves all 11 existing tools, self-improvement loop, and OpenInference tracing.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

from dotenv import load_dotenv
from google.adk import Agent as AdkAgent
from google.adk.runners import Runner
from google.adk.tools import FunctionTool
from google.genai import types as genai_types

from sentinel.tools import (
    QueryMetrics,
    QueryTraces,
    GetAlerts,
    AnalyzeDrift,
    CorrelateSignals,
    CreateAlert,
    SuggestRemediation,
    SelfIntrospect,
    QueryPhoenixTraces,
    QueryPhoenixSpans,
    QueryPhoenixSessions,
)
from sentinel.mcp import PhoenixMCPClient
from .prompts import SYSTEM_PROMPT

load_dotenv()


def _make_tool_wrappers(phoenix_client: PhoenixMCPClient | None = None) -> list[FunctionTool]:
    """Create ADK FunctionTools from existing Sentinel tool classes.

    Each wrapper function preserves the original tool's signature, docstring,
    and execution logic while exposing it to the ADK's tool system.
    """
    tools = []
    pc = phoenix_client or PhoenixMCPClient()

    # -- Phoenix introspection tools (require client) --
    def self_introspect(current_query: str) -> str:
        """Query your own past traces and evaluations from Phoenix via MCP to learn from previous incidents. Use this to find similar past cases, review what worked and what didn't, and improve your current investigation. Always call this at the start of a new investigation."""
        return SelfIntrospect(pc).execute(current_query=current_query)
    tools.append(FunctionTool(func=self_introspect))

    def query_phoenix_traces(project_name: str | None = None, limit: int = 20) -> str:
        """Query recent traces from Phoenix to analyze model behavior, latency patterns, error rates, and tool usage. Use this for real observability data."""
        return QueryPhoenixTraces(pc).execute(project_name=project_name, limit=limit)
    tools.append(FunctionTool(func=query_phoenix_traces))

    def query_phoenix_spans(trace_id: str | None = None, span_kind: str | None = None, limit: int = 50) -> str:
        """Query spans from Phoenix to inspect individual LLM calls, tool invocations, and their latency. Filter by span_kind (LLM, TOOL, CHAIN) to focus analysis."""
        return QueryPhoenixSpans(pc).execute(trace_id=trace_id, span_kind=span_kind, limit=limit)
    tools.append(FunctionTool(func=query_phoenix_spans))

    def query_phoenix_sessions(project_name: str | None = None, limit: int = 10) -> str:
        """Query conversation sessions from Phoenix to review past investigations and their outcomes. Useful for finding patterns across multiple incidents."""
        return QueryPhoenixSessions(pc).execute(project_name=project_name, limit=limit)
    tools.append(FunctionTool(func=query_phoenix_sessions))

    # -- SRE data query tools --
    def query_metrics(model_id: str, metric_names: list[str] | None = None, time_range_hours: int = 24) -> str:
        """Query real-time model performance metrics including accuracy, latency, throughput, and error rates. Use this to check current model health."""
        return QueryMetrics(phoenix_client=pc).execute(model_id=model_id, metric_names=metric_names, time_range_hours=time_range_hours)
    tools.append(FunctionTool(func=query_metrics))

    def query_traces(model_id: str, filter_criteria: dict[str, str] | None = None, limit: int = 50) -> str:
        """Query individual request traces from a model to analyze specific requests, errors, latency outliers, or patterns."""
        return QueryTraces().execute(model_id=model_id, filter_criteria=filter_criteria, limit=limit)
    tools.append(FunctionTool(func=query_traces))

    def get_alerts(model_id: str | None = None, severity: str | None = None) -> str:
        """Get active alerts for models. Use this to see what issues are currently being flagged by the monitoring system."""
        return GetAlerts().execute(model_id=model_id, severity=severity)
    tools.append(FunctionTool(func=get_alerts))

    # -- Analysis tools --
    def analyze_drift(model_id: str, reference_window_hours: int = 168, current_window_hours: int = 24) -> str:
        """Analyze prediction drift to detect if the model's input distribution or output behavior has changed significantly from baseline. Returns drift score, affected features, and severity."""
        return AnalyzeDrift().execute(model_id=model_id, reference_window_hours=reference_window_hours, current_window_hours=current_window_hours)
    tools.append(FunctionTool(func=analyze_drift))

    def correlate_signals(model_id: str, signal_types: list[str]) -> str:
        """Correlate metrics, traces, alerts, and drift data to identify patterns and potential root causes. Use this when a single metric doesn't tell the full story."""
        return CorrelateSignals().execute(model_id=model_id, signal_types=signal_types)
    tools.append(FunctionTool(func=correlate_signals))

    # -- Action tools --
    def create_alert(model_id: str, severity: str, message: str, title: str = "", recommended_action: str = "") -> str:
        """Create a new alert or incident ticket when an issue is identified that needs human attention or escalation."""
        return CreateAlert().execute(model_id=model_id, severity=severity, message=message, title=title, recommended_action=recommended_action)
    tools.append(FunctionTool(func=create_alert))

    def suggest_remediation(issue_type: str, context: str = "") -> str:
        """Suggest specific remediation actions based on the type of issue detected. Includes runbook steps and prioritized actions. Issue types: latency_spike, error_rate_increase, prediction_drift, throughput_degradation."""
        return SuggestRemediation().execute(issue_type=issue_type, context=context)
    tools.append(FunctionTool(func=suggest_remediation))

    return tools


class SentinelAdkAgent:
    """Vertex AI ADK-based Sentinel agent with self-improvement loop and Phoenix tracing.

    Uses Google's Agent Development Kit (google-adk) for the agent runtime,
    satisfying the 'Google Cloud Agent Builder' hackathon requirement while
    preserving Sentinel's 11 custom tools and Arize Phoenix MCP integration.
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        phoenix_client: PhoenixMCPClient | None = None,
        system_prompt: str | None = None,
        override_system_prompt: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required. Set it in your .env file or environment.")

        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
        self.pc = phoenix_client or PhoenixMCPClient()
        prompt_to_use = override_system_prompt or system_prompt or SYSTEM_PROMPT
        self.system_prompt = prompt_to_use

        self.adk_tools = _make_tool_wrappers(self.pc)

        self.adk_agent = AdkAgent(
            name="sentinel",
            model=self.model,
            instruction=self.system_prompt,
            tools=self.adk_tools,
            generate_content_config=genai_types.GenerateContentConfig(
                thinking_config=genai_types.ThinkingConfig(thinking_budget=0)
            ),
        )

        from google.adk.sessions import InMemorySessionService
        self.runner = Runner(
            agent=self.adk_agent,
            app_name="sentinel-sre-agent",
            session_service=InMemorySessionService(),
            auto_create_session=True,
        )

    def run(self, mission: str, session_id: str | None = None, max_iterations: int = 10) -> str:
        """Run a mission through the ADK agent synchronously.

        Args:
            mission: The user's query or incident description.
            session_id: Optional session ID for grouping related conversations.
            max_iterations: Maximum tool-use iterations (ADK manages this internally).

        Returns:
            The agent's final response text.
        """
        sid = session_id or str(uuid.uuid4())
        message = genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=mission)],
        )
        final_text = ""
        for event in self.runner.run(
            user_id="sentinel",
            session_id=sid,
            new_message=message,
        ):
            if event.is_final_response() and event.content:
                for part in event.content.parts or []:
                    if part.text:
                        final_text += part.text
        return final_text

    def run_stream(self, mission: str, session_id: str | None = None):
        """Run a mission and yield SSE-formatted events for streaming.

        Yields dicts with keys:
        - type: 'content', 'tool_call', 'tool_result', 'evaluation', 'done', 'error'
        - data: relevant payload

        Args:
            mission: The user's query.
            session_id: Optional session ID.
        """
        sid = session_id or str(uuid.uuid4())
        message = genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=mission)],
        )

        for event in self.runner.run(
            user_id="sentinel",
            session_id=sid,
            new_message=message,
        ):
            for fn_call in event.get_function_calls():
                yield {
                    "type": "tool_call",
                    "data": {
                        "name": fn_call.name,
                        "args": dict(fn_call.args) if fn_call.args else {},
                    },
                }
            for fn_resp in event.get_function_responses():
                yield {
                    "type": "tool_result",
                    "data": str(fn_resp.response)[:500] if fn_resp.response else "",
                }
            if event.is_final_response() and event.content:
                text = ""
                for part in event.content.parts or []:
                    if part.text:
                        text += part.text
                if text:
                    yield {"type": "content", "data": text}

        yield {"type": "done", "data": ""}
