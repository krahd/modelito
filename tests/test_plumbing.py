import socket
from urllib.error import HTTPError

from modelito.plumbing import (
    TransportPolicy,
    envelope_error,
    envelope_ok,
    normalize_network_error,
    retry_with_backoff,
)


def test_retry_with_backoff_eventually_succeeds():
    calls = {"n": 0}
    waits = []

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise TimeoutError("transient")
        return "ok"

    out = retry_with_backoff(
        flaky,
        policy=TransportPolicy(max_attempts=4, base_delay=0.1, max_delay=1.0, backoff_factor=2.0),
        sleep_fn=waits.append,
        is_retryable=lambda exc: isinstance(exc, TimeoutError),
    )

    assert out == "ok"
    assert calls["n"] == 3
    assert waits == [0.1, 0.2]


def test_normalize_network_error_timeout_and_http():
    timeout_error = normalize_network_error(socket.timeout(
        "timed out"), provider="ollama", operation="probe")
    assert timeout_error.code == "timeout"
    assert timeout_error.retryable is True

    http_exc = HTTPError("https://example.test", 503, "unavailable", hdrs=None, fp=None)
    http_error = normalize_network_error(http_exc, provider="ollama", operation="json_get")
    assert http_error.code == "http_503"
    assert http_error.retryable is True


def test_envelope_helpers_build_consistent_shapes():
    ok = envelope_ok("ollama", "health", {"ready": True})
    assert ok.ok is True
    assert ok.error is None
    assert ok.data["ready"] is True

    err = normalize_network_error(ConnectionRefusedError(
        "no listener"), provider="ollama", operation="health")
    failed = envelope_error("ollama", "health", err)
    assert failed.ok is False
    assert failed.error is not None
    assert failed.error.code == "connection_error"
