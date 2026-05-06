"""Demo scenarios for hackathon presentation.

These scenarios simulate realistic SRE incidents that showcase the agent's
capabilities: multi-step investigation, self-improvement, and actionable outputs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DemoScenario:
    """A demo scenario for the hackathon."""
    id: str
    title: str
    mission: str
    description: str
    expected_tools: list[str]
    expected_findings: list[str]
    complexity: str = "medium"


SCENARIOS = [
    DemoScenario(
        id="scenario-001",
        title="Latency Spike Investigation",
        mission="Investigate the P99 latency spike in sentiment-classifier-v2. What's causing it and what should we do?",
        description=(
            "The sentiment-classifier-v2 model is experiencing a severe latency spike. "
            "P99 latency has jumped from 85ms to 210ms. The agent should investigate metrics, "
            "correlate signals, identify the root cause (upstream data source timeout), "
            "and recommend enabling a circuit breaker."
        ),
        expected_tools=["self_introspect", "query_metrics", "correlate_signals", "suggest_remediation"],
        expected_findings=[
            "P99 latency increased 147% above baseline",
            "Error rate also elevated (4x baseline)",
            "Prediction drift detected",
            "Root cause: upstream dependency timeout",
            "Recommendation: enable circuit breaker",
        ],
        complexity="medium",
    ),
    DemoScenario(
        id="scenario-002",
        title="Model Drift Analysis",
        mission="Check all models for prediction drift. Are any models degrading?",
        description=(
            "Routine drift check across all monitored models. The agent should check "
            "drift for each model, identify which features are drifting, and recommend "
            "retraining for affected models."
        ),
        expected_tools=["self_introspect", "analyze_drift", "get_alerts"],
        expected_findings=[
            "sentiment-classifier-v2: significant drift (score > threshold)",
            "Key drifted features identified",
            "Recommendation: trigger retraining pipeline",
        ],
        complexity="medium",
    ),
    DemoScenario(
        id="scenario-003",
        title="Critical Incident Response",
        mission="URGENT: Error rate on fraud-detection-v1 just spiked to 15%. Investigate immediately and tell me what to do.",
        description=(
            "Critical incident: fraud-detection model error rate has spiked dramatically. "
            "This is a high-stakes scenario where the agent needs to move fast, identify "
            "the root cause (input schema mismatch from upstream API change), and recommend "
            "immediate remediation."
        ),
        expected_tools=["self_introspect", "query_metrics", "query_traces", "analyze_drift", "correlate_signals", "suggest_remediation", "create_alert"],
        expected_findings=[
            "Error rate spike confirmed (15% vs baseline 1.2%)",
            "Input schema mismatch detected in failed requests",
            "Upstream API change broke payload format",
            "Immediate action: roll back to stable version",
            "Short-term: apply input validation patch",
        ],
        complexity="high",
    ),
    DemoScenario(
        id="scenario-004",
        title="Performance Health Check",
        mission="Give me a health check summary of all our production models. Any concerns?",
        description=(
            "Comprehensive health check across all models. Agent should query metrics, "
            "check alerts, assess drift, and provide a prioritized summary."
        ),
        expected_tools=["self_introspect", "query_metrics", "get_alerts", "analyze_drift", "correlate_signals"],
        expected_findings=[
            "Overall health summary per model",
            "Models with active alerts flagged",
            "Drift status for each model",
            "Prioritized list of concerns",
        ],
        complexity="low",
    ),
]


def get_scenario(scenario_id: str) -> DemoScenario | None:
    """Get a scenario by ID."""
    for s in SCENARIOS:
        if s.id == scenario_id:
            return s
    return None


def list_scenarios() -> list[dict[str, Any]]:
    """List all available scenarios."""
    return [
        {
            "id": s.id,
            "title": s.title,
            "mission": s.mission,
            "complexity": s.complexity,
        }
        for s in SCENARIOS
    ]


def run_demo_scenario(
    agent: Any,
    scenario: DemoScenario,
    evaluator: Any | None = None,
) -> dict[str, Any]:
    """Run a demo scenario through the agent and optionally evaluate it.

    Args:
        agent: SentinelAgent instance
        scenario: DemoScenario to run
        evaluator: Optional LLMJudge for evaluation

    Returns:
        Dictionary with scenario results
    """
    print(f"\n{'='*60}")
    print(f"  Scenario: {scenario.title}")
    print(f"  Complexity: {scenario.complexity}")
    print(f"{'='*60}")
    print(f"\nMission: {scenario.mission}\n")
    print("-" * 40)

    response = agent.run(scenario.mission)

    print(f"\n{response.content}")

    result = {
        "scenario_id": scenario.id,
        "title": scenario.title,
        "mission": scenario.mission,
        "response": response.content,
        "tools_used": response.tool_calls,
    }

    if evaluator and response.content:
        try:
            eval_result = evaluator.evaluate(
                mission=scenario.mission,
                response=response.content,
                tools_used=[t["tool"] for t in response.tool_calls],
            )
            result["evaluation"] = {
                "overall_score": eval_result.overall_score,
                "accuracy": eval_result.accuracy,
                "completeness": eval_result.completeness,
                "actionability": eval_result.actionability,
                "rationale": eval_result.rationale,
            }
            print(f"\n{'='*60}")
            print(f"  Evaluation: {eval_result.overall_score:.1f}/5.0")
            print(f"  Accuracy: {eval_result.accuracy:.1f} | Completeness: {eval_result.completeness:.1f} | Actionability: {eval_result.actionability:.1f}")
            print(f"  {eval_result.rationale}")
            print(f"{'='*60}")
        except Exception as e:
            print(f"\nEvaluation skipped: {e}")

    return result
