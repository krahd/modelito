"""Simple connector utilities to manage conversation history and system messages.

This module provides a small, framework-agnostic connector that maintains per-
conversation histories and prepares prompts for providers. The connector now
operates on `Message` dataclasses internally while preserving the legacy
dict-based public surface for compatibility.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Iterable, List, Optional, Union
from pathlib import Path

from .provider import Provider
from .exceptions import LLMProviderError
from .tokenizer import count_tokens
from .messages import Message, Response, to_message


def _estimate_tokens(text: str) -> int:
    try:
        return int(count_tokens(text or ""))
    except Exception:
        if not text:
            return 0
        return max(1, len(text) // 4)


def _msg_to_dict(m: Message) -> Dict[str, Any]:
    d: Dict[str, Any] = {"role": m.role, "content": m.content}
    if m.name is not None:
        d["name"] = m.name
    if m.metadata is not None:
        d["metadata"] = m.metadata
    return d


def _to_messages(messages: Optional[Iterable[Union[Dict[str, Any], Message]]]) -> List[Message]:
    msgs: List[Message] = []
    if not messages:
        return msgs
    for m in messages:
        if isinstance(m, Message):
            msgs.append(m)
        else:
            msgs.append(to_message(m))
    return msgs


class OllamaConnector:
    """Manage per-conversation history and build prompts for provider calls.

    The connector stores `Message` objects per conversation id and provides
    utilities to trim by message count or token budget. It exposes both the
    legacy dict-oriented surface and the newer `complete()`/`acomplete()`
    methods that return `Response` dataclasses.
    """

    def __init__(
        self,
        provider: Provider,
        shared_history: bool = False,
        system_message_file: Optional[str] = None,
        max_history_messages: int = 20,
        max_history_tokens: Optional[int] = None,
    ):
        self.provider: Provider = provider
        self.shared_history = shared_history
        self.max_history_messages = int(max_history_messages or 20)
        self.max_history_tokens = int(
            max_history_tokens) if max_history_tokens is not None else None
        self._histories: Dict[str, List[Message]] = {}
        self._system_message: Optional[str] = None
        if system_message_file:
            p = Path(system_message_file)
            if p.exists():
                try:
                    self._system_message = p.read_text(encoding="utf-8").strip()
                except Exception:
                    self._system_message = None

    def _conv_key(self, conv_id: Optional[str]) -> str:
        return "__shared__" if self.shared_history else (conv_id or "default")

    def clear_history(self, conv_id: Optional[str] = None) -> None:
        key = self._conv_key(conv_id)
        self._histories.pop(key, None)

    def set_system_message(self, text: Optional[str]) -> None:
        self._system_message = text

    def _ensure_system(self, messages: List[Message]) -> List[Message]:
        if not self._system_message:
            return messages
        if not messages:
            return [Message(role="system", content=self._system_message)]
        first = messages[0]
        if first.role == "system":
            return messages
        return [Message(role="system", content=self._system_message)] + messages

    def _message_tokens(self, message: Message) -> int:
        return _estimate_tokens(message.content or "") + 1

    def _total_tokens(self, messages: List[Message]) -> int:
        return sum(self._message_tokens(m) for m in messages)

    def add_to_history(self, conv_id: Optional[str], role: str, content: str) -> None:
        key = self._conv_key(conv_id)
        hist = self._histories.setdefault(key, [])
        hist.append(Message(role=role, content=content))
        if len(hist) > self.max_history_messages:
            del hist[: len(hist) - self.max_history_messages]
        if self.max_history_tokens is not None:
            while True:
                total = self._total_tokens(hist)
                if total <= self.max_history_tokens:
                    break
                if hist and hist[0].role == "system":
                    if len(hist) > 1:
                        del hist[1]
                    else:
                        break
                else:
                    del hist[0]

    def get_history(self, conv_id: Optional[str]) -> List[Dict[str, Any]]:
        return [_msg_to_dict(m) for m in list(self._histories.get(self._conv_key(conv_id), []))]

    def trim_history_by_tokens(self, messages: List[Dict[str, Any]], max_tokens: int) -> List[Dict[str, Any]]:
        if max_tokens is None or max_tokens <= 0:
            return messages
        msgs = _to_messages(messages)
        system: Optional[Message] = None
        if msgs and msgs[0].role == "system":
            system = msgs.pop(0)
        while self._total_tokens(([system] if system else []) + msgs) > max_tokens and msgs:
            del msgs[0]
        if system:
            result = [system] + msgs
        else:
            result = msgs
        return [_msg_to_dict(m) for m in result]

    def build_prompt(
        self,
        conv_id: Optional[str],
        new_messages: Optional[Iterable[Union[Dict[str, Any], Message]]] = None,
        include_history: bool = True,
        max_prompt_tokens: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        hist_msgs: List[Message] = []
        if include_history:
            hist_msgs = list(self._histories.get(self._conv_key(conv_id), []))
        if new_messages:
            hist_msgs = hist_msgs + _to_messages(new_messages)
        if len(hist_msgs) > self.max_history_messages:
            hist_msgs = hist_msgs[-self.max_history_messages:]
        if max_prompt_tokens is not None:
            trimmed = self.trim_history_by_tokens(
                [_msg_to_dict(m) for m in hist_msgs], max_prompt_tokens)
            hist_msgs = _to_messages(trimmed)
        hist_msgs = self._ensure_system(hist_msgs)
        return [_msg_to_dict(m) for m in hist_msgs]

    def send_sync(self, conv_id: Optional[str], new_messages: List[Dict[str, Any]], settings: Optional[Dict] = None) -> str:
        messages = self.build_prompt(conv_id, new_messages=new_messages, include_history=True, max_prompt_tokens=(
            settings or {}).get("max_prompt_tokens"))
        try:
            resp = self.provider.summarize(messages, settings=settings)
        except Exception as exc:
            raise LLMProviderError(f"Provider call failed: {exc}") from exc
        for m in (new_messages or []):
            role = (m.get("role") if isinstance(m, dict) else getattr(m, "role", "user")) or "user"
            content = (m.get("content") if isinstance(m, dict) else getattr(m, "content", "")) or ""
            self.add_to_history(conv_id, role, content)
        self.add_to_history(conv_id, "assistant", resp)
        return resp

    def complete(self, conv_id: Optional[str], new_messages: Optional[Iterable[Union[Dict[str, Any], Message]]] = None, settings: Optional[Dict] = None) -> Response:
        """Backward-compatible wrapper that returns a `Response` dataclass."""
        resp_text = self.send_sync(conv_id, list(new_messages or []), settings=settings)
        return Response(text=resp_text, raw=None)

    async def acomplete(self, conv_id: Optional[str], new_messages: Optional[Iterable[Union[Dict[str, Any], Message]]] = None, settings: Optional[Dict] = None) -> Response:
        msgs = self.build_prompt(conv_id, new_messages=new_messages, include_history=True,
                                 max_prompt_tokens=(settings or {}).get("max_prompt_tokens"))
        # If provider supplies an async API, prefer that.
        provider = self.provider
        try:
            acomplete = getattr(provider, "acomplete", None)
            if acomplete is not None:
                raw = await acomplete(msgs, settings=settings)
            else:
                loop = asyncio.get_running_loop()
                raw = await loop.run_in_executor(None, lambda: provider.summarize(msgs, settings=settings))
        except Exception as exc:
            raise LLMProviderError(f"Provider call failed: {exc}") from exc
        # update history with original new_messages
        for m in (new_messages or []):
            if isinstance(m, Message):
                self.add_to_history(conv_id, m.role, m.content)
            else:
                self.add_to_history(conv_id, m.get("role", "user"), m.get("content", ""))
        self.add_to_history(conv_id, "assistant", raw)
        return Response(text=raw if isinstance(raw, str) else str(raw), raw=raw)
