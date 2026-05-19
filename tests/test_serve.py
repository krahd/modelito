import asyncio
from types import SimpleNamespace

from modelito.messages import Response
from modelito.serve import (
    ServeConfig,
    ServeRuntime,
    _chat_completion_response,
    _embedding_response,
    _models_response,
    build_config,
    build_parser,
    create_app,
)


class _FakeRequest:
    def __init__(self, payload):
        self._payload = payload

    async def json(self):
        return self._payload


class _FakeJSONResponse:
    def __init__(self, payload, headers=None):
        self.payload = payload
        self.headers = dict(headers or {})


class _FakeStreamingResponse:
    def __init__(self, body_iterator, media_type=None, headers=None):
        self.body = list(body_iterator)
        self.media_type = media_type
        self.headers = dict(headers or {})


class _FakeHTTPException(Exception):
    def __init__(self, status_code, detail):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class _FakeApp:
    def __init__(self, *args, **kwargs):
        self.routes = {}

    def get(self, path):
        def decorator(func):
            self.routes[("GET", path)] = func
            return func

        return decorator

    def post(self, path):
        def decorator(func):
            self.routes[("POST", path)] = func
            return func

        return decorator


class _FakeRawProvider:
    def __init__(self, response_payload, stream_events):
        self.response_payload = response_payload
        self.stream_events = stream_events
        self.last_payload = None

    def raw_complete(self, payload):
        self.last_payload = dict(payload)
        return self.response_payload

    def raw_stream(self, payload):
        self.last_payload = dict(payload)
        yield from self.stream_events


class _FakeClient:
    def __init__(self):
        self.model = "omlx"
        self.list_models_result = ["omlx", "other"]

    def list_models(self):
        return self.list_models_result

    def chat(self, messages, settings=None):
        return Response(text="fallback text", raw={"choices": [{"message": {"content": "fallback text"}}]}, model="omlx", finish_reason="stop", tokens_in=3, tokens_out=4)

    def stream(self, messages, settings=None):
        yield "fallback"
        yield " stream"

    def embed(self, texts, **kwargs):
        return [[float(index), float(index) + 0.5] for index, _ in enumerate(texts)]


def _build_runtime(strict=True, raw_provider=None):
    client = _FakeClient()
    config = ServeConfig(strict=strict)
    return ServeRuntime(config=config, client=client, provider=raw_provider or client, raw_provider=raw_provider)


def test_serve_parser_and_config_parsing():
    parser = build_parser()
    args = parser.parse_args([
        "--provider", "omlx",
        "--model", "llama3",
        "--host", "127.0.0.1",
        "--port", "11436",
        "--base-url", "http://localhost:8000/v1",
        "--strict",
        "--profile", "profile.json",
        "--profile-path", "override.json",
        "--timeout", "3.5",
        "--log-level", "debug",
    ])
    config = build_config(args)

    assert config.provider == "omlx"
    assert config.model == "llama3"
    assert config.host == "127.0.0.1"
    assert config.port == 11436
    assert config.base_url == "http://localhost:8000/v1"
    assert config.strict is True
    assert config.profile == "profile.json"
    assert config.profile_path == "override.json"
    assert config.timeout == 3.5
    assert config.log_level == "debug"


def test_models_response_returns_openai_shape():
    runtime = _build_runtime()
    response = _models_response(runtime)

    assert response["object"] == "list"
    assert response["data"][0]["object"] == "model"
    assert response["data"][0]["owned_by"] == "modelito"


def test_raw_chat_completion_route_preserves_tool_calls(monkeypatch):
    raw_response = {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "created": 0,
        "model": "omlx",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {"id": "call_1", "type": "function", "function": {
                            "name": "lookup", "arguments": "{}"}},
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
    }
    raw_provider = _FakeRawProvider(raw_response, [])
    runtime = _build_runtime(raw_provider=raw_provider)

    monkeypatch.setattr("modelito.serve._require_server_dependencies", lambda: (_FakeApp, _FakeHTTPException,
                        _FakeRequest, _FakeJSONResponse, _FakeStreamingResponse, SimpleNamespace(run=lambda *args, **kwargs: None)))
    app = create_app(runtime)
    handler = app.routes[("POST", "/v1/chat/completions")]

    request = _FakeRequest(
        {
            "model": "omlx",
            "messages": [{"role": "user", "content": "use the tool"}],
            "tools": [{"type": "function", "function": {"name": "lookup"}}],
            "tool_choice": "auto",
            "stream": False,
        }
    )
    response = asyncio.run(handler(request))

    assert response.payload == raw_response
    assert raw_provider.last_payload["tool_choice"] == "auto"
    assert raw_provider.last_payload["tools"][0]["function"]["name"] == "lookup"


def test_raw_chat_completion_stream_route_emits_sse(monkeypatch):
    raw_events = [
        {"id": "chunk-1", "object": "chat.completion.chunk",
            "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}]},
        {"id": "chunk-1", "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {"tool_calls": [
            {"id": "call_1", "type": "function", "function": {"name": "lookup", "arguments": "{}"}}]}, "finish_reason": None}]},
        {"id": "chunk-1", "object": "chat.completion.chunk",
            "choices": [{"index": 0, "delta": {"content": "done"}, "finish_reason": None}]},
    ]
    raw_provider = _FakeRawProvider({}, raw_events)
    runtime = _build_runtime(raw_provider=raw_provider)

    monkeypatch.setattr("modelito.serve._require_server_dependencies", lambda: (_FakeApp, _FakeHTTPException,
                        _FakeRequest, _FakeJSONResponse, _FakeStreamingResponse, SimpleNamespace(run=lambda *args, **kwargs: None)))
    app = create_app(runtime)
    handler = app.routes[("POST", "/v1/chat/completions")]

    request = _FakeRequest(
        {
            "model": "omlx",
            "messages": [{"role": "user", "content": "use the tool"}],
            "tools": [{"type": "function", "function": {"name": "lookup"}}],
            "tool_choice": "auto",
            "stream": True,
        }
    )
    response = asyncio.run(handler(request))

    assert response.media_type == "text/event-stream"
    assert response.body[-1] == "data: [DONE]\n\n"
    assert "tool_calls" in response.body[1]
    assert raw_provider.last_payload["stream"] is True


def test_fallback_text_only_completion_and_embeddings(monkeypatch):
    runtime = _build_runtime(strict=False, raw_provider=None)

    completion = _chat_completion_response(
        runtime,
        {"model": "omlx", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert completion.payload["choices"][0]["message"]["content"] == "fallback text"
    assert "fallback" in completion.headers.get("X-Modelito-Warning", "")

    embedding = _embedding_response(runtime, {"model": "omlx", "input": ["alpha", "beta"]})
    assert embedding.payload["object"] == "list"
    assert len(embedding.payload["data"]) == 2
    assert embedding.payload["data"][0]["object"] == "embedding"


def test_tools_without_raw_provider_fail_in_strict_mode():
    runtime = _build_runtime(strict=True, raw_provider=None)

    try:
        _chat_completion_response(
            runtime,
            {
                "model": "omlx",
                "messages": [{"role": "user", "content": "tool use"}],
                "tools": [{"type": "function", "function": {"name": "lookup"}}],
            },
        )
    except ValueError as exc:
        assert "tool calls" in str(exc).lower() or "raw passthrough" in str(exc).lower()
    else:
        raise AssertionError("expected tool request without raw provider to fail")


def test_serve_import_does_not_require_optional_deps():
    import modelito

    assert hasattr(modelito, "Client")
