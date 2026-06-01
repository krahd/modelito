"""Tests for OllamaProvider raw_complete and raw_stream methods.

These tests verify that OllamaProvider implements the RawChatProvider protocol
and correctly handles OpenAI-compatible payloads through Ollama's /v1/chat/completions
endpoint.
"""

import json
import pytest
from unittest.mock import Mock, MagicMock

from modelito.exceptions import ModelitoBadResponseError
from modelito.ollama import OllamaProvider
from modelito.provider import RawChatProvider


def test_ollama_provider_is_raw_chat_provider():
    """Verify that OllamaProvider satisfies the RawChatProvider protocol."""
    provider = OllamaProvider(model="llama3.2")
    assert isinstance(provider, RawChatProvider)


def test_raw_complete_sets_default_model_if_absent(monkeypatch):
    """raw_complete should set model to self.model if not in payload."""
    provider = OllamaProvider(model="llama3.2", strict=False)

    # Mock endpoint_url to track the URL
    monkeypatch.setattr(
        "modelito.ollama.endpoint_url",
        lambda h, p, e: "http://test/v1/chat/completions",
    )

    # Mock json_post to capture the request payload
    captured_payload = {}

    def mock_json_post(url, payload, timeout):
        captured_payload.update(payload)
        return {
            "id": "test",
            "object": "chat.completion",
            "model": "llama3.2",
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": "hello"}}
            ],
        }

    monkeypatch.setattr("modelito.ollama.json_post", mock_json_post)

    # Call with payload missing "model"
    payload = {"messages": [{"role": "user", "content": "hello"}]}
    provider.raw_complete(payload)

    # Verify the outbound request has model set
    assert captured_payload.get("model") == "llama3.2"
    # Verify original payload was not mutated
    assert "model" not in payload


def test_raw_complete_does_not_overwrite_explicit_model(monkeypatch):
    """raw_complete should not overwrite an explicitly supplied model."""
    provider = OllamaProvider(model="llama3.2", strict=False)

    monkeypatch.setattr(
        "modelito.ollama.endpoint_url",
        lambda h, p, e: "http://test/v1/chat/completions",
    )

    captured_payload = {}

    def mock_json_post(url, payload, timeout):
        captured_payload.update(payload)
        return {
            "id": "test",
            "object": "chat.completion",
            "model": "llama3.2:1b",
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": "hello"}}
            ],
        }

    monkeypatch.setattr("modelito.ollama.json_post", mock_json_post)

    # Call with explicit model
    payload = {
        "model": "llama3.2:1b",
        "messages": [{"role": "user", "content": "hello"}],
    }
    provider.raw_complete(payload)

    # Verify the outbound request preserves the explicit model
    assert captured_payload.get("model") == "llama3.2:1b"


def test_raw_complete_preserves_tool_payloads(monkeypatch):
    """raw_complete should preserve tools and tool_choice fields."""
    provider = OllamaProvider(model="llama3.2", strict=False)

    monkeypatch.setattr(
        "modelito.ollama.endpoint_url",
        lambda h, p, e: "http://test/v1/chat/completions",
    )

    captured_payload = {}

    def mock_json_post(url, payload, timeout):
        captured_payload.update(payload)
        return {
            "id": "test",
            "object": "chat.completion",
            "model": "llama3.2",
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": "hello"}}
            ],
        }

    monkeypatch.setattr("modelito.ollama.json_post", mock_json_post)

    # Call with tools payload
    payload = {
        "messages": [{"role": "user", "content": "hello"}],
        "tools": [{"type": "function", "function": {"name": "test_func"}}],
        "tool_choice": "auto",
    }
    provider.raw_complete(payload)

    # Verify tools and tool_choice are preserved
    assert captured_payload.get("tools") == payload["tools"]
    assert captured_payload.get("tool_choice") == "auto"


def test_raw_complete_uses_v1_endpoint(monkeypatch):
    """raw_complete should use /v1/chat/completions endpoint."""
    provider = OllamaProvider(model="llama3.2", strict=False)

    captured_endpoint = {}

    def mock_endpoint_url(host, port, endpoint):
        captured_endpoint["endpoint"] = endpoint
        return "http://test/v1/chat/completions"

    monkeypatch.setattr("modelito.ollama.endpoint_url", mock_endpoint_url)

    def mock_json_post(url, payload, timeout):
        return {
            "id": "test",
            "object": "chat.completion",
            "model": "llama3.2",
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": "hello"}}
            ],
        }

    monkeypatch.setattr("modelito.ollama.json_post", mock_json_post)

    payload = {"messages": [{"role": "user", "content": "hello"}]}
    provider.raw_complete(payload)

    # Verify the correct endpoint was used
    assert captured_endpoint.get("endpoint") == "/v1/chat/completions"


def test_raw_complete_returns_raw_dictionary(monkeypatch):
    """raw_complete should return the response dictionary as-is."""
    provider = OllamaProvider(model="llama3.2", strict=False)

    monkeypatch.setattr(
        "modelito.ollama.endpoint_url",
        lambda h, p, e: "http://test/v1/chat/completions",
    )

    expected_response = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "model": "llama3.2",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "hello",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        },
    }

    def mock_json_post(url, payload, timeout):
        return expected_response

    monkeypatch.setattr("modelito.ollama.json_post", mock_json_post)

    payload = {"messages": [{"role": "user", "content": "hello"}]}
    result = provider.raw_complete(payload)

    # Verify the result is the raw dictionary, not collapsed to text
    assert result == expected_response
    assert "choices" in result
    assert isinstance(result["choices"], list)


def test_raw_complete_strict_error_on_malformed_response(monkeypatch):
    """In strict mode, raw_complete should raise on malformed response."""
    from modelito.exceptions import ModelitoBadResponseError

    provider = OllamaProvider(model="llama3.2", strict=True)

    monkeypatch.setattr(
        "modelito.ollama.endpoint_url",
        lambda h, p, e: "http://test/v1/chat/completions",
    )

    def mock_json_post(url, payload, timeout):
        return {"error": "something went wrong"}  # Missing 'choices'

    monkeypatch.setattr("modelito.ollama.json_post", mock_json_post)

    payload = {"messages": [{"role": "user", "content": "hello"}]}

    with pytest.raises(ModelitoBadResponseError):
        provider.raw_complete(payload)


def test_raw_complete_non_strict_fallback_on_error(monkeypatch):
    """In non-strict mode, raw_complete should return fallback dict on error."""
    provider = OllamaProvider(model="llama3.2", strict=False)

    monkeypatch.setattr(
        "modelito.ollama.endpoint_url",
        lambda h, p, e: "http://test/v1/chat/completions",
    )

    def mock_json_post(url, payload, timeout):
        raise RuntimeError("Connection failed")

    monkeypatch.setattr("modelito.ollama.json_post", mock_json_post)

    payload = {"messages": [{"role": "user", "content": "hello"}]}
    result = provider.raw_complete(payload)

    # Verify it returns a fallback dict with the expected shape
    assert isinstance(result, dict)
    assert "id" in result
    assert result["object"] == "chat.completion"
    assert "choices" in result
    assert len(result["choices"]) > 0


def test_raw_stream_forces_stream_true(monkeypatch):
    """raw_stream should force stream=True in the request."""
    provider = OllamaProvider(model="llama3.2", strict=False)

    monkeypatch.setattr(
        "modelito.ollama.endpoint_url",
        lambda h, p, e: "http://test/v1/chat/completions",
    )

    captured_payload = {}

    # Mock urlopen to capture the request
    mock_response = MagicMock()
    mock_response.__enter__ = Mock(return_value=mock_response)
    mock_response.__exit__ = Mock(return_value=None)
    mock_response.readline = Mock(return_value=b"")

    def mock_urlopen(req, timeout):
        # Extract payload from request
        if hasattr(req, "data"):
            captured_payload.update(json.loads(req.data.decode("utf-8")))
        return mock_response

    monkeypatch.setattr("modelito.ollama.urlopen", mock_urlopen)

    payload = {"messages": [{"role": "user", "content": "hello"}]}
    list(provider.raw_stream(payload))

    # Verify stream=True was set
    assert captured_payload.get("stream") is True


def test_raw_stream_parses_sse_lines(monkeypatch):
    """raw_stream should parse Server-Sent Events correctly."""
    provider = OllamaProvider(model="llama3.2", strict=False)

    monkeypatch.setattr(
        "modelito.ollama.endpoint_url",
        lambda h, p, e: "http://test/v1/chat/completions",
    )

    # Prepare SSE response lines
    sse_lines = [
        b'data: {"id":"x","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}\n',
        b'data: {"id":"x","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"hel"},"finish_reason":null}]}\n',
        b'data: {"id":"x","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"lo"},"finish_reason":null}]}\n',
        b"data: [DONE]\n",
    ]

    mock_response = MagicMock()
    mock_response.__enter__ = Mock(return_value=mock_response)
    mock_response.__exit__ = Mock(return_value=None)
    mock_response.readline = Mock(side_effect=sse_lines + [b""])

    monkeypatch.setattr("modelito.ollama.urlopen", Mock(return_value=mock_response))

    payload = {"messages": [{"role": "user", "content": "hello"}]}
    events = list(provider.raw_stream(payload))

    # Verify we got 3 events and stopped at [DONE]
    assert len(events) == 3
    # Verify the events are dicts
    assert all(isinstance(e, dict) for e in events)
    # Verify no [DONE] was yielded
    assert not any("[DONE]" in str(e) for e in events)


def test_raw_stream_preserves_tool_calls_chunks(monkeypatch):
    """raw_stream should preserve tool_calls deltas from SSE events."""
    provider = OllamaProvider(model="llama3.2", strict=False)

    monkeypatch.setattr(
        "modelito.ollama.endpoint_url",
        lambda h, p, e: "http://test/v1/chat/completions",
    )

    sse_lines = [
        b'data: {"id":"x","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"tool_calls":[{"id":"call_1","type":"function","function":{"name":"lookup","arguments":"{}"}}]},"finish_reason":null}]}'
        + b"\n",
        b"data: [DONE]\n",
    ]

    mock_response = MagicMock()
    mock_response.__enter__ = Mock(return_value=mock_response)
    mock_response.__exit__ = Mock(return_value=None)
    mock_response.readline = Mock(side_effect=sse_lines + [b""])

    monkeypatch.setattr("modelito.ollama.urlopen", Mock(return_value=mock_response))

    events = list(
        provider.raw_stream({"messages": [{"role": "user", "content": "hello"}]})
    )

    assert len(events) == 1
    tool_calls = events[0]["choices"][0]["delta"]["tool_calls"]
    assert tool_calls[0]["function"]["name"] == "lookup"


def test_raw_stream_preserves_tool_fields(monkeypatch):
    """raw_stream should preserve tools and tool_choice fields."""
    provider = OllamaProvider(model="llama3.2", strict=False)

    monkeypatch.setattr(
        "modelito.ollama.endpoint_url",
        lambda h, p, e: "http://test/v1/chat/completions",
    )

    captured_payload = {}

    mock_response = MagicMock()
    mock_response.__enter__ = Mock(return_value=mock_response)
    mock_response.__exit__ = Mock(return_value=None)
    mock_response.readline = Mock(return_value=b"")

    def mock_urlopen(req, timeout):
        if hasattr(req, "data"):
            captured_payload.update(json.loads(req.data.decode("utf-8")))
        return mock_response

    monkeypatch.setattr("modelito.ollama.urlopen", mock_urlopen)

    payload = {
        "messages": [{"role": "user", "content": "hello"}],
        "tools": [{"type": "function", "function": {"name": "test_func"}}],
        "tool_choice": "auto",
    }
    list(provider.raw_stream(payload))

    # Verify tools and tool_choice are preserved
    assert captured_payload.get("tools") == payload["tools"]
    assert captured_payload.get("tool_choice") == "auto"


def test_raw_stream_preserves_response_format_and_generation_fields(monkeypatch):
    """raw_stream should preserve response_format and common generation fields."""
    provider = OllamaProvider(model="llama3.2", strict=False)

    monkeypatch.setattr(
        "modelito.ollama.endpoint_url",
        lambda h, p, e: "http://test/v1/chat/completions",
    )

    captured_payload = {}

    mock_response = MagicMock()
    mock_response.__enter__ = Mock(return_value=mock_response)
    mock_response.__exit__ = Mock(return_value=None)
    mock_response.readline = Mock(side_effect=[b"data: [DONE]\n", b""])

    def mock_urlopen(req, timeout):
        if hasattr(req, "data"):
            captured_payload.update(json.loads(req.data.decode("utf-8")))
        return mock_response

    monkeypatch.setattr("modelito.ollama.urlopen", mock_urlopen)

    payload = {
        "messages": [{"role": "user", "content": "return json"}],
        "response_format": {"type": "json_object"},
        "temperature": 0,
        "top_p": 0.9,
        "max_tokens": 128,
        "stop": ["END"],
    }
    original = dict(payload)

    list(provider.raw_stream(payload))

    assert captured_payload["model"] == "llama3.2"
    assert captured_payload["stream"] is True
    assert captured_payload["response_format"] == {"type": "json_object"}
    assert captured_payload["temperature"] == 0
    assert captured_payload["top_p"] == 0.9
    assert captured_payload["max_tokens"] == 128
    assert captured_payload["stop"] == ["END"]
    assert payload == original


def test_raw_stream_uses_v1_chat_completions_endpoint(monkeypatch):
    """raw_stream should use /v1/chat/completions endpoint."""
    provider = OllamaProvider(model="llama3.2", strict=False)

    captured = {}

    def mock_endpoint_url(host, port, endpoint):
        captured["endpoint"] = endpoint
        return "http://test/v1/chat/completions"

    monkeypatch.setattr("modelito.ollama.endpoint_url", mock_endpoint_url)

    mock_response = MagicMock()
    mock_response.__enter__ = Mock(return_value=mock_response)
    mock_response.__exit__ = Mock(return_value=None)
    mock_response.readline = Mock(side_effect=[b"data: [DONE]\n", b""])

    monkeypatch.setattr("modelito.ollama.urlopen", Mock(return_value=mock_response))

    list(provider.raw_stream({"messages": [{"role": "user", "content": "hello"}]}))

    assert captured["endpoint"] == "/v1/chat/completions"


def test_raw_stream_does_not_mutate_input_payload(monkeypatch):
    """raw_stream should not mutate the caller payload."""
    provider = OllamaProvider(model="llama3.2", strict=False)

    monkeypatch.setattr(
        "modelito.ollama.endpoint_url",
        lambda h, p, e: "http://test/v1/chat/completions",
    )

    mock_response = MagicMock()
    mock_response.__enter__ = Mock(return_value=mock_response)
    mock_response.__exit__ = Mock(return_value=None)
    mock_response.readline = Mock(side_effect=[b"data: [DONE]\n", b""])

    monkeypatch.setattr("modelito.ollama.urlopen", Mock(return_value=mock_response))

    payload = {"messages": [{"role": "user", "content": "hello"}]}
    original = dict(payload)

    list(provider.raw_stream(payload))

    assert payload == original
    assert "model" not in payload
    assert "stream" not in payload


def test_raw_stream_strict_rejects_non_dict_json_event(monkeypatch):
    """In strict mode, raw_stream should reject valid JSON events that are not objects."""
    provider = OllamaProvider(model="llama3.2", strict=True)

    monkeypatch.setattr(
        "modelito.ollama.endpoint_url",
        lambda h, p, e: "http://test/v1/chat/completions",
    )

    mock_response = MagicMock()
    mock_response.__enter__ = Mock(return_value=mock_response)
    mock_response.__exit__ = Mock(return_value=None)
    mock_response.readline = Mock(
        side_effect=[
            b'data: ["not", "an", "object"]\n',
            b"data: [DONE]\n",
            b"",
        ]
    )

    monkeypatch.setattr("modelito.ollama.urlopen", Mock(return_value=mock_response))

    with pytest.raises(ModelitoBadResponseError):
        list(provider.raw_stream({"messages": [{"role": "user", "content": "hello"}]}))


def test_raw_stream_strict_malformed_event(monkeypatch):
    """In strict mode, raw_stream should raise on malformed events."""
    provider = OllamaProvider(model="llama3.2", strict=True)

    monkeypatch.setattr(
        "modelito.ollama.endpoint_url",
        lambda h, p, e: "http://test/v1/chat/completions",
    )

    # Return a malformed event line
    mock_response = MagicMock()
    mock_response.__enter__ = Mock(return_value=mock_response)
    mock_response.__exit__ = Mock(return_value=None)
    mock_response.readline = Mock(
        side_effect=[
            b"data: {invalid json}\n",
            b"",
        ]
    )

    monkeypatch.setattr("modelito.ollama.urlopen", Mock(return_value=mock_response))

    payload = {"messages": [{"role": "user", "content": "hello"}]}

    with pytest.raises(ModelitoBadResponseError):
        list(provider.raw_stream(payload))


def test_raw_stream_non_strict_fallback(monkeypatch):
    """In non-strict mode, raw_stream should yield fallback events on error."""
    provider = OllamaProvider(model="llama3.2", strict=False)

    monkeypatch.setattr(
        "modelito.ollama.endpoint_url",
        lambda h, p, e: "http://test/v1/chat/completions",
    )

    def mock_urlopen(req, timeout):
        raise RuntimeError("Connection failed")

    monkeypatch.setattr("modelito.ollama.urlopen", mock_urlopen)

    payload = {"messages": [{"role": "user", "content": "hello"}]}
    events = list(provider.raw_stream(payload))

    # Verify we got fallback stream events
    assert len(events) > 0
    # Verify all events are dicts with proper structure
    for event in events:
        assert isinstance(event, dict)
        assert event["object"] == "chat.completion.chunk"
        assert "choices" in event
    # OpenAI-style streams keep a stable completion id across chunks.
    ids = {event["id"] for event in events}
    assert len(ids) == 1


def test_raw_complete_preserves_response_format_and_generation_fields(monkeypatch):
    """raw_complete should preserve response_format and common generation fields."""
    provider = OllamaProvider(model="llama3.2", strict=False)

    monkeypatch.setattr(
        "modelito.ollama.endpoint_url",
        lambda h, p, e: "http://test/v1/chat/completions",
    )

    captured = {}

    def mock_json_post(url, payload, timeout):
        captured["payload"] = dict(payload)
        return {
            "id": "test",
            "object": "chat.completion",
            "model": "llama3.2",
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": "ok"}}
            ],
        }

    monkeypatch.setattr("modelito.ollama.json_post", mock_json_post)

    payload = {
        "messages": [{"role": "user", "content": "return json"}],
        "response_format": {"type": "json_object"},
        "temperature": 0,
        "top_p": 0.9,
        "max_tokens": 128,
        "stop": ["END"],
    }

    provider.raw_complete(payload)

    assert captured["payload"]["model"] == "llama3.2"
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert captured["payload"]["temperature"] == 0
    assert captured["payload"]["top_p"] == 0.9
    assert captured["payload"]["max_tokens"] == 128
    assert captured["payload"]["stop"] == ["END"]
