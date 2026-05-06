"""LLM-as-a-Judge evaluation for agent responses.

Implements the evaluation pipeline recommended by Arize for the hackathon.
Evaluates agent responses on accuracy, completeness, and actionability.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()


@dataclass
class EvaluationResult:
    """Result of an LLM-as-a-judge evaluation."""
    mission: str
    response: str
    tools_used: list[str]
    accuracy: float
    completeness: float
    actionability: float
    overall_score: float
    rationale: str
    criteria_scores: dict[str, float]


EVALUATION_PROMPT = """You are an expert evaluator assessing the quality of an AI SRE agent's incident investigation response.

Evaluate the response on these criteria (1-5 scale):

**Accuracy (1-5)**: Are the findings factually correct? Does the analysis correctly interpret the data?
- 5: Perfectly accurate analysis with correct data interpretation
- 4: Mostly accurate with minor issues
- 3: Generally correct but with some inaccuracies
- 2: Significant inaccuracies in the analysis
- 1: Fundamentally incorrect analysis

**Completeness (1-5)**: Does the response cover all relevant aspects of the issue?
- 5: Comprehensive analysis covering all signals and providing thorough root cause
- 4: Good coverage with minor gaps
- 3: Covers main points but misses some important aspects
- 2: Significant gaps in the analysis
- 1: Very incomplete, misses critical aspects

**Actionability (1-5)**: Are the recommendations specific, practical, and prioritized?
- 5: Clear, specific, prioritized recommendations with concrete steps
- 4: Good recommendations with minor gaps in specificity
- 3: General recommendations that need more detail
- 2: Vague recommendations that are hard to act on
- 1: No actionable recommendations

Return your evaluation as JSON:
```json
{
  "accuracy": <1-5>,
  "completeness": <1-5>,
  "actionability": <1-5>,
  "overall_score": <1-5>,
  "rationale": "<2-3 sentence explanation of your scores>"
}
```"""


class LLMJudge:
    """LLM-as-a-judge evaluator using Gemini."""

    def __init__(self, model: str | None = None):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY required for LLM-as-a-judge evaluation")

        self.client = genai.Client(api_key=api_key)
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

    def evaluate(
        self,
        mission: str,
        response: str,
        tools_used: list[str] | None = None,
    ) -> EvaluationResult:
        """Evaluate an agent's response using LLM-as-a-judge.

        Args:
            mission: The original user query/mission
            response: The agent's response
            tools_used: List of tools the agent used

        Returns:
            EvaluationResult with scores and rationale
        """
        prompt = f"""Mission: {mission}

Agent's Response:
{response}

Tools Used: {', '.join(tools_used) if tools_used else 'None'}

Evaluate this response according to the criteria."""

        eval_response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=EVALUATION_PROMPT,
                response_mime_type="application/json",
            ),
        )

        return self._parse_evaluation(
            mission, response, tools_used or [], eval_response.text
        )

    def evaluate_batch(
        self,
        cases: list[dict[str, Any]],
    ) -> list[EvaluationResult]:
        """Evaluate multiple cases in batch.

        Args:
            cases: List of dicts with 'mission', 'response', 'tools_used'

        Returns:
            List of EvaluationResult
        """
        results = []
        for case in cases:
            result = self.evaluate(
                mission=case["mission"],
                response=case["response"],
                tools_used=case.get("tools_used"),
            )
            results.append(result)
        return results

    def _parse_evaluation(
        self,
        mission: str,
        response: str,
        tools_used: list[str],
        raw_text: str,
    ) -> EvaluationResult:
        """Parse the LLM judge's JSON response."""
        try:
            json_start = raw_text.find("{")
            json_end = raw_text.rfind("}") + 1
            json_str = raw_text[json_start:json_end]
            data = json.loads(json_str)
        except (json.JSONDecodeError, ValueError):
            data = {
                "accuracy": 3.0,
                "completeness": 3.0,
                "actionability": 3.0,
                "overall_score": 3.0,
                "rationale": "Failed to parse evaluation response",
            }

        return EvaluationResult(
            mission=mission,
            response=response,
            tools_used=tools_used,
            accuracy=float(data.get("accuracy", 3.0)),
            completeness=float(data.get("completeness", 3.0)),
            actionability=float(data.get("actionability", 3.0)),
            overall_score=float(data.get("overall_score", 3.0)),
            rationale=data.get("rationale", ""),
            criteria_scores={
                "accuracy": float(data.get("accuracy", 3.0)),
                "completeness": float(data.get("completeness", 3.0)),
                "actionability": float(data.get("actionability", 3.0)),
            },
        )


def evaluate_response(
    mission: str,
    response: str,
    tools_used: list[str] | None = None,
) -> EvaluationResult:
    """Convenience function for single evaluation."""
    judge = LLMJudge()
    return judge.evaluate(mission, response, tools_used)
