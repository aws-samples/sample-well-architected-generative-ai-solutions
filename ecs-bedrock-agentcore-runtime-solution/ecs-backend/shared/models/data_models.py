"""
Data models re-export module.
Centralizes imports from actual model locations for backward compatibility.
"""

from dataclasses import dataclass, field
from typing import Any, Dict

from agentcore.models.agentcore_models import AgentInfo, CommandResponse
from shared.models.chat_models import ChatMessage, ChatSession, ToolExecution


@dataclass
class QueryRoute:
    """Routing decision for a query."""
    route_type: str  # "agent", "model", "command"
    target: str = ""
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
