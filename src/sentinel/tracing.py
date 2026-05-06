"""Tracing setup - OpenInference instrumentation with Phoenix exporter."""

from __future__ import annotations

import os

from dotenv import load_dotenv


def setup_tracing(project_name: str | None = None) -> None:
    """Set up OpenInference tracing with Phoenix collector.

    Instruments all google-genai SDK calls and sends traces to Phoenix
    for observability, evaluation, and agent self-introspection via MCP.

    Args:
        project_name: Phoenix project name for organizing traces
    """
    load_dotenv()

    endpoint = os.environ.get("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006")
    api_key = os.environ.get("PHOENIX_API_KEY")
    project = project_name or os.environ.get("SENTINEL_PROJECT_NAME", "sentinel-sre-agent")

    is_cloud = "app.phoenix.arize.com" in endpoint

    if is_cloud and api_key:
        _setup_cloud_tracing(endpoint, api_key, project)
    else:
        _setup_local_tracing(endpoint)


def _setup_cloud_tracing(endpoint: str, api_key: str, project: str) -> None:
    """Set up tracing for Phoenix Cloud."""
    try:
        from phoenix.otel import register

        register(
            project_name=project,
            auto_instrument=True,
        )
    except ImportError:
        _setup_manual_tracing(f"{endpoint}/v1/traces", api_key)


def _setup_local_tracing(endpoint: str) -> None:
    """Set up tracing for local Phoenix server."""
    try:
        from phoenix.otel import register

        register(
            project_name="sentinel-sre-agent",
            auto_instrument=True,
        )
    except ImportError:
        _setup_manual_tracing(f"{endpoint}/v1/traces", None)


def _setup_manual_tracing(endpoint: str, api_key: str | None) -> None:
    """Manual tracing setup using OpenTelemetry directly."""
    from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    headers = {"api_key": api_key} if api_key else None
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(
        SimpleSpanProcessor(OTLPSpanExporter(endpoint=endpoint, headers=headers))
    )

    GoogleGenAIInstrumentor().instrument(tracer_provider=tracer_provider)
