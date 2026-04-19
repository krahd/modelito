from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class Role(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"


@dataclass(frozen=True)
class Message:
    role: str
    content: str
    name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class Response:
    text: str
    raw: Optional[Any] = None


Messages = List[Message]


def to_message(obj: Dict[str, Any]) -> Message:
    """Convert a legacy dict-like message into a `Message` dataclass.

    Accepts the common `{ 'role': .., 'content': .. }` shape used by
    provider adapters and examples.
    """
    role = obj.get("role", "user")
    content = obj.get("content", "")
    name = obj.get("name")
    meta = obj.get("metadata")
    return Message(role=str(role), content=str(content), name=name, metadata=meta)
