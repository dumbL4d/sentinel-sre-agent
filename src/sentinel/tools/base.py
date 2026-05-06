"""Base tool class."""

from __future__ import annotations

from typing import Any


class BaseTool:
    """Base class for agent tools."""

    name: str = ""
    description: str = ""

    def to_gemini_tool(self) -> dict[str, Any]:
        """Convert tool to Gemini function declaration format."""
        raise NotImplementedError

    def execute(self, **kwargs) -> dict | list | str:
        """Execute the tool with given arguments."""
        raise NotImplementedError
