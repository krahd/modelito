"""Provider-agnostic transport/retry and envelope helpers.

This module keeps runtime plumbing lightweight and dependency-free while
providing stable structures for retries, normalized network failures, and
command response envelopes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import socket
import subprocess
import time
from typing import Any, Callable, Dict, Optional, TypeVar
from urllib.error import HTTPError, URLError


T = TypeVar("T")


@dataclass(frozen=True)
class TransportPolicy:
    """Transport behavior settings for networked operations."""

    timeout: float = 5.0
    max_attempts: int = 3
    base_delay: float = 0.2
    max_delay: float = 2.0
    backoff_factor: float = 2.0


@dataclass(frozen=True)
class ErrorEnvelope:
    """Normalized error shape used by command wrappers."""

    code: str
    message: str
    retryable: bool = False
    provider: Optional[str] = None
    operation: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResponseEnvelope:
    """Stable response envelope for wrapper-style command surfaces."""

    ok: bool
    provider: str
    operation: str
    data: Any = None
    error: Optional[ErrorEnvelope] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


def normalize_network_error(
    exc: Exception,
    *,
    provider: Optional[str] = None,
    operation: Optional[str] = None,
) -> ErrorEnvelope:
    """Normalize common transport/network exceptions into a stable shape."""
    details: Dict[str, Any] = {"exception_type": type(exc).__name__}

    if isinstance(exc, (TimeoutError, socket.timeout, subprocess.TimeoutExpired)):
        details["reason"] = "timeout"
        return ErrorEnvelope(
            code="timeout",
            message=str(exc) or "operation timed out",
            retryable=True,
            provider=provider,
            operation=operation,
            details=details,
        )

    if isinstance(exc, HTTPError):
        details["status"] = getattr(exc, "code", None)
        status = int(getattr(exc, "code", 0) or 0)
        retryable = status >= 500 or status == 429
        return ErrorEnvelope(
            code=f"http_{status}" if status else "http_error",
            message=str(exc),
            retryable=retryable,
            provider=provider,
            operation=operation,
            details=details,
        )

    if isinstance(exc, (URLError, ConnectionRefusedError, ConnectionResetError, ConnectionAbortedError)):
        details["reason"] = "connection"
        return ErrorEnvelope(
            code="connection_error",
            message=str(exc) or "connection failed",
            retryable=True,
            provider=provider,
            operation=operation,
            details=details,
        )

    if isinstance(exc, OSError):
        details["errno"] = getattr(exc, "errno", None)
        return ErrorEnvelope(
            code="network_os_error",
            message=str(exc),
            retryable=True,
            provider=provider,
            operation=operation,
            details=details,
        )

    return ErrorEnvelope(
        code="network_unknown",
        message=str(exc) or "unknown network error",
        retryable=False,
        provider=provider,
        operation=operation,
        details=details,
    )


def retry_with_backoff(
    fn: Callable[[], T],
    *,
    policy: Optional[TransportPolicy] = None,
    is_retryable: Optional[Callable[[Exception], bool]] = None,
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> T:
    """Execute `fn` with bounded retries and exponential backoff."""
    policy = policy or TransportPolicy()
    attempts = max(1, int(policy.max_attempts))
    delay = max(0.0, float(policy.base_delay))
    backoff = max(1.0, float(policy.backoff_factor))
    max_delay = max(0.0, float(policy.max_delay))

    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:
            retryable = is_retryable(exc) if is_retryable else True
            if attempt >= attempts or not retryable:
                raise
            wait = min(delay, max_delay) if max_delay > 0 else delay
            if on_retry is not None:
                on_retry(attempt, exc, wait)
            if wait > 0:
                sleep_fn(wait)
            delay = delay * backoff

    # unreachable, but keeps type checkers happy
    raise RuntimeError("retry_with_backoff exhausted without returning or raising")


def envelope_ok(provider: str, operation: str, data: Any, *, metadata: Optional[Dict[str, Any]] = None) -> ResponseEnvelope:
    """Build a successful response envelope."""
    return ResponseEnvelope(
        ok=True,
        provider=provider,
        operation=operation,
        data=data,
        error=None,
        metadata=dict(metadata or {}),
    )


def envelope_error(
    provider: str,
    operation: str,
    error: ErrorEnvelope,
    *,
    metadata: Optional[Dict[str, Any]] = None,
) -> ResponseEnvelope:
    """Build a failed response envelope."""
    return ResponseEnvelope(
        ok=False,
        provider=provider,
        operation=operation,
        data=None,
        error=error,
        metadata=dict(metadata or {}),
    )
