"""FastAPI web server for Sentinel SRE Agent demo."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

from sentinel.tracing import setup_tracing
from sentinel.agent import SentinelAgent
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

load_dotenv()
setup_tracing()

app = FastAPI(title="Sentinel SRE Agent", version="0.1.0")

_agent = None


def get_agent() -> SentinelAgent:
    global _agent
    if _agent is None:
        phoenix_client = PhoenixMCPClient()
        tools = [
            SelfIntrospect(phoenix_client),
            QueryMetrics(),
            QueryTraces(),
            GetAlerts(),
            AnalyzeDrift(),
            CorrelateSignals(),
            SuggestRemediation(),
            CreateAlert(),
        ]
        _agent = SentinelAgent(tools=tools)
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


@app.get("/scenarios")
def get_scenarios():
    return list_scenarios()


@app.post("/run")
def run_mission(req: MissionRequest):
    agent = get_agent()
    response = agent.run(
        req.mission,
        session_id=req.session_id,
        max_iterations=req.max_iterations,
    )
    return {
        "content": response.content,
        "tool_calls": response.tool_calls,
        "session_id": response.session_id,
    }


@app.post("/scenario")
def run_scenario(req: ScenarioRequest):
    from sentinel.scenarios import get_scenario

    scenario = get_scenario(req.scenario_id)
    if not scenario:
        return {"error": f"Scenario '{req.scenario_id}' not found"}

    agent = get_agent()
    response = agent.run(scenario.mission, session_id=scenario.id)

    return {
        "scenario": {
            "id": scenario.id,
            "title": scenario.title,
        },
        "content": response.content,
        "tool_calls": response.tool_calls,
    }


def main():
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
