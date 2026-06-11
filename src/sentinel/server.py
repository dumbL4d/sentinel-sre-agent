"""FastAPI web server for Sentinel SRE Agent with SSE streaming and web UI."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from sentinel.tracing import setup_tracing
from sentinel.agent import SentinelAdkAgent
from sentinel.mcp import PhoenixMCPClient
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
from sentinel.scenarios import SCENARIOS, list_scenarios
from sentinel.evaluation import LLMJudge

load_dotenv()
setup_tracing()

app = FastAPI(title="Sentinel SRE Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_agent = None


def get_agent() -> SentinelAdkAgent:
    global _agent
    if _agent is None:
        phoenix_client = PhoenixMCPClient()
        _agent = SentinelAdkAgent(phoenix_client=phoenix_client)
    return _agent


class MissionRequest(BaseModel):
    mission: str
    session_id: str | None = None
    max_iterations: int = 10


class ScenarioRequest(BaseModel):
    scenario_id: str


@app.get("/")
def root():
    return {"name": "Sentinel SRE Agent", "version": "0.1.0"}


@app.get("/health")
def health():
    """Health check endpoint for Cloud Run with Phoenix connectivity and model info."""
    phoenix_ok = False
    try:
        async def _check_phoenix_http() -> bool:
            try:
                import httpx
                phoenix_key = os.environ.get("PHOENIX_API_KEY", "")
                phoenix_url = os.environ.get(
                    "PHOENIX_COLLECTOR_ENDPOINT",
                    "https://app.phoenix.arize.com"
                ).rstrip("/")
                if not phoenix_key:
                    return False
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(
                        f"{phoenix_url}/v1/projects",
                        headers={"Authorization": f"Bearer {phoenix_key}"}
                    )
                    return resp.status_code in (200, 201)
            except Exception:
                return False

        phoenix_ok = asyncio.run(
            asyncio.wait_for(_check_phoenix_http(), timeout=8.0)
        )
    except Exception:
        phoenix_ok = False

    return {
        "status": "ok",
        "service": "sentinel-sre-agent",
        "phoenix_connected": phoenix_ok,
        "model": os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite"),
        "demo_mode": os.environ.get("SENTINEL_DEMO_MODE", "false").lower() == "true",
    }


@app.get("/scenarios")
def get_scenarios():
    return list_scenarios()


@app.post("/run")
def run_mission(req: MissionRequest):
    agent = get_agent()
    response = agent.run(
        req.mission,
        session_id=req.session_id,
    )

    evaluator = _get_evaluator()
    eval_result = None
    if evaluator and response:
        try:
            eval_result = evaluator.evaluate(mission=req.mission, response=response)
        except Exception:
            pass

    return {
        "content": response,
        "session_id": req.session_id,
        "evaluation": {
            "overall_score": eval_result.overall_score if eval_result else None,
            "accuracy": eval_result.accuracy if eval_result else None,
            "completeness": eval_result.completeness if eval_result else None,
            "actionability": eval_result.actionability if eval_result else None,
            "rationale": eval_result.rationale if eval_result else None,
        } if eval_result else None,
    }


@app.post("/run/stream")
async def run_mission_stream(req: MissionRequest):
    """SSE streaming endpoint for real-time agent investigation display."""
    agent = get_agent()

    async def event_generator():
        yield f"data: {json.dumps({'type': 'status', 'data': 'Starting investigation...'})}\n\n"

        mission = req.mission

        _self_reflection = '### Self-Reflection\n\nChecking Phoenix for similar past cases...'
        yield f"data: {json.dumps({'type': 'content', 'data': _self_reflection})}\n\n"
        await asyncio.sleep(0.3)

        try:
            final_response = agent.run(mission, session_id=req.session_id)
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'data': ''})}\n\n"
            return

        if final_response:
            yield f"data: {json.dumps({'type': 'content', 'data': final_response})}\n\n"

        evaluator = _get_evaluator()
        if evaluator and final_response:
            try:
                eval_result = evaluator.evaluate(mission=mission, response=final_response)
                eval_payload = {
                    'type': 'evaluation',
                    'data': {
                        'overall_score': eval_result.overall_score,
                        'accuracy': eval_result.accuracy,
                        'completeness': eval_result.completeness,
                        'actionability': eval_result.actionability,
                        'rationale': eval_result.rationale,
                    },
                }
                yield f"data: {json.dumps(eval_payload)}\n\n"
            except Exception:
                pass

        yield f"data: {json.dumps({'type': 'done', 'data': ''})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/scenario")
def run_scenario(req: ScenarioRequest):
    from sentinel.scenarios import get_scenario

    scenario = get_scenario(req.scenario_id)
    if not scenario:
        return {"error": f"Scenario '{req.scenario_id}' not found"}

    agent = get_agent()
    response = agent.run(scenario.mission, session_id=scenario.id)

    evaluator = _get_evaluator()
    eval_result = None
    if evaluator and response:
        try:
            eval_result = evaluator.evaluate(
                mission=scenario.mission,
                response=response,
            )
        except Exception:
            pass

    return {
        "scenario": {
            "id": scenario.id,
            "title": scenario.title,
        },
        "content": response,
        "evaluation": {
            "overall_score": eval_result.overall_score if eval_result else None,
            "accuracy": eval_result.accuracy if eval_result else None,
            "completeness": eval_result.completeness if eval_result else None,
            "actionability": eval_result.actionability if eval_result else None,
        } if eval_result else None,
    }


def _get_evaluator() -> LLMJudge | None:
    try:
        return LLMJudge()
    except Exception:
        return None


_static_served = False


def _serve_static():
    global _static_served
    if not _static_served:
        static_dir = Path(__file__).parent / "static"
        static_dir.mkdir(exist_ok=True)
        if static_dir.exists():
            app.mount("/ui", StaticFiles(directory=str(static_dir), html=True), name="ui")
        _static_served = True


def main():
    import uvicorn

    _serve_static()

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
