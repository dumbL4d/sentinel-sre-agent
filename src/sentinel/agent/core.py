"""Sentinel Agent - Core reasoning loop with google-genai SDK, tool calling, and self-improvement."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

from .prompts import SYSTEM_PROMPT


load_dotenv()


@dataclass
class ToolResult:
    """Result from a tool execution."""
    tool_name: str
    success: bool
    data: Any
    error: str | None = None


@dataclass
class AgentResponse:
    """Response from the agent after processing a mission."""
    content: str
    tool_calls: list[dict] = field(default_factory=list)
    confidence: str = "Medium"
    session_id: str | None = None


class SentinelAgent:
    """Main agent using google-genai SDK with tool calling and Phoenix tracing.

    Every LLM call is automatically traced via OpenInference and sent to Phoenix.
    The agent can use Phoenix MCP to introspect its own past traces for self-improvement.
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        tools: list | None = None,
        system_prompt: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY is required. Set it in your .env file or environment."
            )

        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
        self.client = genai.Client(api_key=self.api_key)
        self.tools = tools or []
        self.system_prompt = system_prompt or SYSTEM_PROMPT
        self._tool_map: dict[str, Any] = {}
        self._chat = None

        for tool in self.tools:
            self._tool_map[tool.name] = tool

    def run(self, mission: str, session_id: str | None = None, max_iterations: int = 10) -> AgentResponse:
        """Execute a mission with iterative tool use.

        Each call is traced to Phoenix via OpenInference instrumentation.

        Args:
            mission: The user's query or mission
            session_id: Optional session ID for grouping related conversations
            max_iterations: Maximum tool-use iterations

        Returns:
            AgentResponse with findings and tool call history
        """
        tool_calls_made = []
        messages = []

        if session_id:
            messages.append({
                "role": "user",
                "parts": [types.Part.from_text(text=f"[Session: {session_id}]")]
            })

        messages.append({
            "role": "user",
            "parts": [types.Part.from_text(text=mission)]
        })

        for iteration in range(max_iterations):
            response = self._generate(messages)

            if not response.candidates:
                return AgentResponse(
                    content="No response from model.",
                    tool_calls=tool_calls_made,
                    session_id=session_id,
                )

            candidate = response.candidates[0]
            content_parts = candidate.content.parts

            has_tool_call = False
            for part in content_parts:
                if part.function_call:
                    has_tool_call = True
                    tool_result = self._execute_tool(part.function_call)
                    tool_calls_made.append({
                        "tool": part.function_call.name,
                        "args": dict(part.function_call.args) if part.function_call.args else {},
                        "success": tool_result.success,
                    })

                    messages.append({"role": "model", "parts": content_parts})
                    messages.append({
                        "role": "user",
                        "parts": [
                            types.Part.from_function_response(
                                name=part.function_call.name,
                                response={"output": tool_result.data if tool_result.success else tool_result.error}
                            )
                        ],
                    })
                    break

            if not has_tool_call:
                final_text = " ".join(
                    p.text for p in content_parts if p.text
                )
                return AgentResponse(
                    content=final_text,
                    tool_calls=tool_calls_made,
                    session_id=session_id,
                )

        return AgentResponse(
            content="Maximum iterations reached. The investigation is still ongoing.",
            tool_calls=tool_calls_made,
            session_id=session_id,
        )

    def chat(self, message: str, session_id: str | None = None) -> str:
        """Multi-turn chat conversation with tracing.

        Args:
            message: User message
            session_id: Optional session ID

        Returns:
            Agent response text
        """
        if self._chat is None:
            self._chat = self.client.chats.create(
                model=self.model,
                config=types.GenerateContentConfig(
                    system_instruction=self.system_prompt,
                    tools=self._build_tool_declarations(),
                ),
            )

        response = self._chat.send_message(message)
        return response.text or ""

    def _generate(self, messages: list[dict]) -> Any:
        """Generate content with tool support."""
        contents = self._build_contents(messages)

        return self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=self.system_prompt,
                tools=self._build_tool_declarations(),
            ),
        )

    def _build_contents(self, messages: list[dict]) -> list:
        """Build google-genai contents from message list."""
        contents = []
        for msg in messages:
            if msg["role"] == "user":
                contents.append(types.Content(
                    role="user",
                    parts=msg["parts"],
                ))
            elif msg["role"] == "model":
                contents.append(types.Content(
                    role="model",
                    parts=msg["parts"],
                ))
        return contents

    def _build_tool_declarations(self) -> list:
        """Build tool declarations for google-genai."""
        declarations = []
        for tool in self.tools:
            decl = tool.to_gemini_tool()
            if "function_declarations" in decl:
                declarations.extend(decl["function_declarations"])
        return declarations if declarations else None

    def _execute_tool(self, function_call: types.FunctionCall) -> ToolResult:
        """Execute a tool call."""
        tool_name = function_call.name
        args = dict(function_call.args) if function_call.args else {}

        if tool_name not in self._tool_map:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                data=None,
                error=f"Unknown tool: {tool_name}",
            )

        try:
            result = self._tool_map[tool_name].execute(**args)
            return ToolResult(tool_name=tool_name, success=True, data=result)
        except Exception as e:
            return ToolResult(tool_name=tool_name, success=False, data=None, error=str(e))
