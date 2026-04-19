"""Simple connector utilities to manage conversation history and system messages.

This module provides a small, framework-agnostic connector that maintains per-
conversation histories and prepares prompts for providers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pathlib import Path
from .exceptions import LLMProviderError
from .tokenizer import count_tokens


def _estimate_tokens(text: str) -> int:
    try:
        return int(count_tokens(text or ""))
    except Exception:
        if not text:
            return 0
        return max(1, len(text) // 4)


class OllamaConnector:
    """Manage per-conversation history and build prompts for provider calls.

    The connector stores simple role/content messages per conversation id and
    provides utilities to trim by message count or token budget. Use
    `send_sync()` to build a prompt, call the provider's `summarize()` method,
    and update local history.
    """

    def __init__(self, provider: Any, shared_history: bool = False, system_message_file: Optional[str] = None, max_history_messages: int = 20, max_history_tokens: Optional[int] = None):
        self.provider = provider
        self.shared_history = shared_history
        self.max_history_messages = int(max_history_messages or 20)
        self.max_history_tokens = int(
            max_history_tokens) if max_history_tokens is not None else None
        self._histories: Dict[str, List[Dict[str, str]]] = {}
        self._system_message = None
        if system_message_file:
            p = Path(system_message_file)
            if p.exists():
                try:
                    self._system_message = p.read_text(encoding="utf-8").strip()
                except Exception:
                    self._system_message = None

    def _conv_key(self, conv_id: Optional[str]) -> str:
        """Return the internal history key for a conversation id.

        When ``shared_history`` is enabled, a single shared key is used. For
        non-shared histories the provided ``conv_id`` (or the literal
        ``"default"``) is returned.
        """
        return "__shared__" if self.shared_history else (conv_id or "default")

    def clear_history(self, conv_id: Optional[str] = None) -> None:
        """Clear stored history for ``conv_id`` (or the default key).

        This removes any messages stored for the given conversation.
        """
        key = self._conv_key(conv_id)
        self._histories.pop(key, None)

    def set_system_message(self, text: Optional[str]) -> None:
        """Set or clear the system message that will be injected into prompts.

        When set, the system message is automatically prepended to built
        prompts unless the first message already has role="system".
        """
        self._system_message = text

    def _ensure_system(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Return ``messages`` with the system message injected when needed.

        If ``self._system_message`` is set and the first message is not a
        system message, it will be prepended.
        """
        if not self._system_message:
            return messages
        if not messages:
            return [{"role": "system", "content": self._system_message}]
        first = messages[0]
        if first.get("role") == "system":
            return messages
        return [{"role": "system", "content": self._system_message}] + messages

    def _message_tokens(self, message: Dict[str, str]) -> int:
        """Estimate token contribution of a single message.

        Adds a small fixed overhead (``+1``) to account for role/meta tokens.
        """
        return _estimate_tokens(message.get("content", "")) + 1

    def _total_tokens(self, messages: List[Dict[str, str]]) -> int:
        """Return the total estimated token count for a list of messages."""
        return sum(self._message_tokens(m) for m in messages)

    def add_to_history(self, conv_id: Optional[str], role: str, content: str) -> None:
        """Append a message to the conversation history and enforce limits.

        The history will be trimmed to ``max_history_messages`` and, if
        ``max_history_tokens`` is set, also by token budget (preferring to
        preserve the system message when possible).
        """
        key = self._conv_key(conv_id)
        hist = self._histories.setdefault(key, [])
        hist.append({"role": role, "content": content})
        if len(hist) > self.max_history_messages:
            del hist[: len(hist) - self.max_history_messages]
        if self.max_history_tokens is not None:
            while True:
                total = self._total_tokens(hist)
                if total <= self.max_history_tokens:
                    break
                if hist and hist[0].get("role") == "system":
                    if len(hist) > 1:
                        del hist[1]
                    else:
                        break
                else:
                    del hist[0]

    def get_history(self, conv_id: Optional[str]) -> List[Dict[str, str]]:
        """Return a shallow copy of the stored history for ``conv_id``."""
        return list(self._histories.get(self._conv_key(conv_id), []))

    def trim_history_by_tokens(self, messages: List[Dict[str, str]], max_tokens: int) -> List[Dict[str, str]]:
        """Trim a list of messages so their estimated token count <= max_tokens.

        The system message (if present as the first message) is preserved and
        re-prepended after trimming other messages from the front.
        """
        if max_tokens is None or max_tokens <= 0:
            return messages
        msgs = list(messages)
        system = None
        if msgs and msgs[0].get("role") == "system":
            system = msgs.pop(0)
        while self._total_tokens(([system] if system else []) + msgs) > max_tokens and msgs:
            del msgs[0]
        if system:
            return [system] + msgs
        return msgs

    def build_prompt(self, conv_id: Optional[str], new_messages: Optional[List[Dict[str, str]]] = None, include_history: bool = True, max_prompt_tokens: Optional[int] = None) -> List[Dict[str, str]]:
        """Build the final prompt messages list combining history and new messages.

        Args:
            conv_id: Conversation identifier used to select stored history.
            new_messages: Additional messages to append to the prompt.
            include_history: When False, only ``new_messages`` are used.
            max_prompt_tokens: Optional token budget for the final prompt; if
                set, history will be trimmed to fit.

        Returns:
            A list of role/content message dictionaries suitable for passing to
            a provider's ``summarize()`` method.
        """
        hist = self.get_history(conv_id) if include_history else []
        if new_messages:
            hist = hist + new_messages
        if len(hist) > self.max_history_messages:
            hist = hist[-self.max_history_messages:]
        if max_prompt_tokens is not None:
            hist = self.trim_history_by_tokens(hist, max_prompt_tokens)
        hist = self._ensure_system(hist)
        return hist

    def send_sync(self, conv_id: Optional[str], new_messages: List[Dict[str, str]], settings: Optional[Dict] = None) -> str:
        """Synchronously call the provider with the built prompt and update history.

        This builds the prompt with :meth:`build_prompt`, calls
        ``provider.summarize(messages, settings=settings)`` and appends both the
        new user messages and the provider response to the stored history.

        Raises:
            LLMProviderError: If the provider call raises an exception.

        Returns:
            The provider response string.
        """
        messages = self.build_prompt(conv_id, new_messages=new_messages, include_history=True, max_prompt_tokens=(
            settings or {}).get("max_prompt_tokens"))
        try:
            resp = self.provider.summarize(messages, settings=settings)
        except Exception as exc:
            raise LLMProviderError(f"Provider call failed: {exc}") from exc
        for m in (new_messages or []):
            role = m.get("role", "user")
            self.add_to_history(conv_id, role, m.get("content", ""))
        self.add_to_history(conv_id, "assistant", resp)
        return resp
