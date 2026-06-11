"""Debate mode — runs two agent instances with opposing strategies
and synthesizes results using a moderator Gemini call."""

from __future__ import annotations

import asyncio
import os
from typing import Optional

from google import genai
from google.genai import types as genai_types


class DebateRunner:
    """Runs two SentinelAdkAgent instances with opposing strategies
    and synthesizes the result using a moderator Gemini call."""

    def __init__(self, phoenix_client=None):
        from sentinel.agent.adk_agent import SentinelAdkAgent
        from sentinel.agent.prompts import (
            AGGRESSIVE_PROMPT,
            CONSERVATIVE_PROMPT,
            MODERATOR_PROMPT,
        )

        self.model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
        self.moderator_prompt = MODERATOR_PROMPT

        self.conservative = SentinelAdkAgent(
            phoenix_client=phoenix_client,
            override_system_prompt=CONSERVATIVE_PROMPT,
        )
        self.aggressive = SentinelAdkAgent(
            phoenix_client=phoenix_client,
            override_system_prompt=AGGRESSIVE_PROMPT,
        )

    async def run_debate_async(self, mission: str):
        """Run both agents in parallel and synthesize results.
        Yields SSE-formatted events for streaming.
        """
        yield {"type": "debate_status", "data": "agent_a_start"}
        yield {"type": "debate_status", "data": "agent_b_start"}

        loop = asyncio.get_event_loop()

        conservative_result = ""
        aggressive_result = ""

        def run_conservative():
            result = ""
            try:
                for event in self.conservative.run_stream(
                    mission=mission,
                    session_id="debate-conservative-" + str(id(self)),
                ):
                    if event.get("type") == "content":
                        result += event.get("data", "")
            except Exception as exc:
                result = "[Conservative agent error: " + str(exc) + "]"
            return result

        def run_aggressive():
            result = ""
            try:
                for event in self.aggressive.run_stream(
                    mission=mission,
                    session_id="debate-aggressive-" + str(id(self)),
                ):
                    if event.get("type") == "content":
                        result += event.get("data", "")
            except Exception as exc:
                result = "[Aggressive agent error: " + str(exc) + "]"
            return result

        results = await asyncio.gather(
            loop.run_in_executor(None, run_conservative),
            loop.run_in_executor(None, run_aggressive),
            return_exceptions=True,
        )

        conservative_result = results[0] if not isinstance(
            results[0], Exception
        ) else "[Conservative agent failed]"
        aggressive_result = results[1] if not isinstance(
            results[1], Exception
        ) else "[Aggressive agent failed]"

        yield {"type": "debate_result_a", "data": conservative_result}
        yield {"type": "debate_result_b", "data": aggressive_result}
        yield {"type": "debate_status", "data": "moderator_start"}

        api_key = os.environ.get("GEMINI_API_KEY", "")
        client = genai.Client(api_key=api_key)

        moderator_input = (
            "AGENT A (Conservative) analysis:\n"
            + conservative_result
            + "\n\nAGENT B (Aggressive) analysis:\n"
            + aggressive_result
            + "\n\nSynthesize these two analyses of the incident: "
            + mission
        )

        try:
            response = client.models.generate_content(
                model=self.model,
                contents=[
                    genai_types.Content(
                        role="user",
                        parts=[genai_types.Part(text=moderator_input)],
                    )
                ],
                config=genai_types.GenerateContentConfig(
                    system_instruction=self.moderator_prompt,
                    thinking_config=genai_types.ThinkingConfig(
                        thinking_budget=0
                    ),
                ),
            )
            synthesis = response.text or ""
        except Exception as exc:
            synthesis = "[Moderator synthesis error: " + str(exc) + "]"

        yield {"type": "debate_synthesis", "data": synthesis}
        yield {"type": "done", "data": ""}
