"""Agent module - provides both custom google-genai and Vertex AI ADK agents."""

from .core import SentinelAgent
from .prompts import SYSTEM_PROMPT, CONSERVATIVE_PROMPT, AGGRESSIVE_PROMPT, MODERATOR_PROMPT
from .adk_agent import SentinelAdkAgent
from .debate import DebateRunner

__all__ = [
    "SentinelAgent",
    "SentinelAdkAgent",
    "DebateRunner",
    "SYSTEM_PROMPT",
    "CONSERVATIVE_PROMPT",
    "AGGRESSIVE_PROMPT",
    "MODERATOR_PROMPT",
]
