from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional


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
    model: Optional[str] = None
    finish_reason: Optional[str] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None


Messages = List[Message]


def flatten_message_inputs(messages: Iterable[Any]) -> List[Dict[str, str]]:
    """Convert supported message inputs into OpenAI-style dicts.

    Accepts ``Message`` instances, plain strings, and dict-like values with
    ``role``/``content`` keys. This helper is intentionally lightweight and
    shared by the OpenAI-compatible providers.
    """
    out: List[Dict[str, str]] = []
    for message in messages or []:
        if isinstance(message, Message):
            out.append({"role": message.role, "content": message.content})
        elif isinstance(message, str):
            out.append({"role": "user", "content": message})
        elif isinstance(message, dict):
            out.append(
                {
                    "role": str(message.get("role", "user")),
                    "content": str(message.get("content", "")),
                }
            )
        else:
            raise TypeError(
                "Messages must be Message, str, or dict with role/content; "
                f"got {type(message).__name__}"
            )
    return out
