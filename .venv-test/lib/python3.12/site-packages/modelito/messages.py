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
