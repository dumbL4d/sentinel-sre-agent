"""Agent module - provides both custom google-genai and Vertex AI ADK agents."""

from .core import SentinelAgent
from .prompts import SYSTEM_PROMPT
from .adk_agent import SentinelAdkAgent

__all__ = ["SentinelAgent", "SentinelAdkAgent", "SYSTEM_PROMPT"]
