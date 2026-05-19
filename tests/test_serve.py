import asyncio
from types import SimpleNamespace

from modelito.exceptions import (
    ModelitoBadResponseError,
    ModelitoConnectionError,
    ModelitoModelNotFoundError,
    ModelitoProviderError,
    ModelitoTimeoutError,
)
from modelito.messages import Response
from modelito.serve import (
    ServeConfig,
    ServeRuntime,
    _chat_completion_response,
    _embedding_response,
    _error_payload,
    _http_status_for_exception,
    _messages_from_payload,
    _models_response,
    _requires_raw_tool_support,
    _stream_completion_events,
    _stream_response_body,
    build_runtime,
    build_config,
    build_parser,
    create_app,
)


class _FakeRequest:
    def __init__(self, payload):
        self._payload = payload

    async def json(self):
        return self._payload


class _InvalidJSONRequest:
    async def json(self):
        raise ValueError("invalid json")


class _FakeJSONResponse:
    def __init__(self, payload, headers=None, status_code=200):
        self.payload = payload
        self.headers = dict(headers or {})
        self.status_code = status_code


class _FakeStreamingResponse:
    def __init__(self, body_iterator, media_type=None, headers=None):
        self.body = list(body_iterator)
        self.media_type = media_type
        self.headers = dict(headers or {})


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


def _patch_server_deps(monkeypatch):
    monkeypatch.setattr(
        "modelito.serve._require_server_dependencies",
        lambda: (
            _FakeApp,
            Exception,
            _FakeRequest,
            _FakeJSONResponse,
            _FakeStreamingResponse,
            SimpleNamespace(run=lambda *args, **kwargs: None),
        ),
    )


def _assert_openai_error(resp, status_code):
    assert resp.status_code == status_code
    assert "error" in resp.payload
    err = resp.payload["error"]
    assert isinstance(err.get("message"), str)
    assert isinstance(err.get("type"), str)
    assert isinstance(err.get("code"), str)
    assert err["type"] == err["code"]


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


def test_messages_from_payload_validation():
    try:
        _messages_from_payload({})
    except ValueError as exc:
        assert "must include messages" in str(exc)
    else:
        raise AssertionError("missing messages should fail")

    try:
        _messages_from_payload({"messages": {"role": "user", "content": "hello"}})
    except ValueError as exc:
        assert "must be a list or string" in str(exc)
    else:
        raise AssertionError("dict messages should fail")

    assert _messages_from_payload({"messages": [{"role": "user", "content": "hello"}]}) == [
        {"role": "user", "content": "hello"}
    ]
    assert _messages_from_payload({"messages": "hello"}) == ["hello"]


def test_requires_raw_tool_support_detection():
    assert _requires_raw_tool_support({}) is False
    assert _requires_raw_tool_support({"tools": []}) is True
    assert _requires_raw_tool_support({"tools": [{"type": "function"}]}) is True
    assert _requires_raw_tool_support({"tool_choice": "auto"}) is True


def test_http_status_mapping_for_exceptions():
    assert _http_status_for_exception(ValueError("bad")) == 400
    assert _http_status_for_exception(TypeError("bad")) == 400
    assert _http_status_for_exception(ModelitoBadResponseError("bad upstream")) == 502
    assert _http_status_for_exception(ModelitoModelNotFoundError("missing")) == 404
    assert _http_status_for_exception(ModelitoTimeoutError("timeout")) == 504
    assert _http_status_for_exception(TimeoutError("timeout")) == 504
    assert _http_status_for_exception(ModelitoConnectionError("offline")) == 503
    assert _http_status_for_exception(ModelitoProviderError("provider")) == 502
    assert _http_status_for_exception(RuntimeError("boom")) == 500


def test_models_response_returns_openai_shape():
    runtime = _build_runtime()
    response = _models_response(runtime)

    assert response["object"] == "list"
    assert response["data"][0]["object"] == "model"
    assert response["data"][0]["owned_by"] == "modelito"


def test_models_route_success(monkeypatch):
    runtime = _build_runtime()
    _patch_server_deps(monkeypatch)
    app = create_app(runtime)

    response = asyncio.run(app.routes[("GET", "/v1/models")]())
    assert response.status_code == 200
    assert response.payload["object"] == "list"
    assert isinstance(response.payload["data"], list)


def test_models_route_provider_failure_returns_openai_error(monkeypatch):
    runtime = _build_runtime()
    runtime.client.list_models = lambda: (_ for _ in ()).throw(
        ModelitoProviderError("upstream failure"))
    _patch_server_deps(monkeypatch)
    app = create_app(runtime)

    response = asyncio.run(app.routes[("GET", "/v1/models")]())
    _assert_openai_error(response, 502)


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

    _patch_server_deps(monkeypatch)
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

    _patch_server_deps(monkeypatch)
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


def test_tool_choice_without_raw_provider_fails_in_strict_mode():
    runtime = _build_runtime(strict=True, raw_provider=None)

    try:
        _chat_completion_response(
            runtime,
            {
                "model": "omlx",
                "messages": [{"role": "user", "content": "tool use"}],
                "tool_choice": "auto",
            },
        )
    except ValueError as exc:
        assert "raw passthrough" in str(exc).lower()
    else:
        raise AssertionError("expected tool_choice request without raw provider to fail")


def test_non_strict_tools_fallback_sets_warning_header():
    runtime = _build_runtime(strict=False, raw_provider=None)
    completion = _chat_completion_response(
        runtime,
        {
            "model": "omlx",
            "messages": [{"role": "user", "content": "tool use"}],
            "tools": [{"type": "function", "function": {"name": "lookup"}}],
        },
    )
    assert completion.payload["choices"][0]["message"]["content"] == "fallback text"
    assert "fallback" in completion.headers.get("X-Modelito-Warning", "")


def test_non_strict_tool_choice_fallback_sets_warning_header():
    runtime = _build_runtime(strict=False, raw_provider=None)
    completion = _chat_completion_response(
        runtime,
        {
            "model": "omlx",
            "messages": [{"role": "user", "content": "tool use"}],
            "tool_choice": "auto",
        },
    )
    assert completion.payload["choices"][0]["message"]["content"] == "fallback text"
    assert "fallback" in completion.headers.get("X-Modelito-Warning", "")


def test_chat_missing_messages_returns_openai_error(monkeypatch):
    runtime = _build_runtime()
    _patch_server_deps(monkeypatch)
    app = create_app(runtime)
    handler = app.routes[("POST", "/v1/chat/completions")]

    response = asyncio.run(handler(_FakeRequest({"model": "omlx"})))
    _assert_openai_error(response, 400)


def test_chat_invalid_messages_type_returns_openai_error(monkeypatch):
    runtime = _build_runtime()
    _patch_server_deps(monkeypatch)
    app = create_app(runtime)
    handler = app.routes[("POST", "/v1/chat/completions")]

    response = asyncio.run(handler(_FakeRequest(
        {"model": "omlx", "messages": {"role": "user", "content": "hello"}})))
    _assert_openai_error(response, 400)


def test_chat_invalid_json_body_returns_openai_error(monkeypatch):
    runtime = _build_runtime()
    _patch_server_deps(monkeypatch)
    app = create_app(runtime)
    handler = app.routes[("POST", "/v1/chat/completions")]

    response = asyncio.run(handler(_InvalidJSONRequest()))
    _assert_openai_error(response, 400)


def test_chat_array_body_returns_openai_error(monkeypatch):
    runtime = _build_runtime()
    _patch_server_deps(monkeypatch)
    app = create_app(runtime)
    handler = app.routes[("POST", "/v1/chat/completions")]

    response = asyncio.run(handler(_FakeRequest([{"messages": []}])))
    _assert_openai_error(response, 400)


def test_chat_messages_list_works(monkeypatch):
    runtime = _build_runtime()
    _patch_server_deps(monkeypatch)
    app = create_app(runtime)
    handler = app.routes[("POST", "/v1/chat/completions")]

    response = asyncio.run(handler(_FakeRequest(
        {"model": "omlx", "messages": [{"role": "user", "content": "hello"}]})))
    assert response.status_code == 200
    assert response.payload["choices"][0]["message"]["content"] == "fallback text"


def test_chat_messages_string_works_for_backwards_compatibility(monkeypatch):
    runtime = _build_runtime()
    _patch_server_deps(monkeypatch)
    app = create_app(runtime)
    handler = app.routes[("POST", "/v1/chat/completions")]

    response = asyncio.run(handler(_FakeRequest({"model": "omlx", "messages": "hello"})))
    assert response.status_code == 200
    assert response.payload["choices"][0]["message"]["content"] == "fallback text"


def test_chat_timeout_returns_openai_style_504(monkeypatch):
    runtime = _build_runtime()
    runtime.client.chat = lambda *_args, **_kwargs: (_ for _ in ()
                                                     ).throw(ModelitoTimeoutError("timed out"))
    _patch_server_deps(monkeypatch)
    app = create_app(runtime)
    handler = app.routes[("POST", "/v1/chat/completions")]

    response = asyncio.run(handler(_FakeRequest(
        {"model": "omlx", "messages": [{"role": "user", "content": "hello"}]})))
    _assert_openai_error(response, 504)


def test_chat_connection_returns_openai_style_503(monkeypatch):
    runtime = _build_runtime()
    runtime.client.chat = lambda *_args, **_kwargs: (_ for _ in ()
                                                     ).throw(ModelitoConnectionError("offline"))
    _patch_server_deps(monkeypatch)
    app = create_app(runtime)
    handler = app.routes[("POST", "/v1/chat/completions")]

    response = asyncio.run(handler(_FakeRequest(
        {"model": "omlx", "messages": [{"role": "user", "content": "hello"}]})))
    _assert_openai_error(response, 503)


def test_chat_model_not_found_returns_openai_style_404(monkeypatch):
    runtime = _build_runtime()
    runtime.client.chat = lambda *_args, **_kwargs: (_ for _ in ()
                                                     ).throw(ModelitoModelNotFoundError("missing model"))
    _patch_server_deps(monkeypatch)
    app = create_app(runtime)
    handler = app.routes[("POST", "/v1/chat/completions")]

    response = asyncio.run(handler(_FakeRequest(
        {"model": "omlx", "messages": [{"role": "user", "content": "hello"}]})))
    _assert_openai_error(response, 404)


def test_serve_import_does_not_require_optional_deps():
    import modelito

    assert hasattr(modelito, "Client")


def test_embeddings_input_and_output_validation():
    runtime = _build_runtime(strict=False, raw_provider=None)

    # input validation
    try:
        _embedding_response(runtime, {"model": "omlx"})
    except ValueError:
        pass
    else:
        raise AssertionError("missing embeddings input should fail")

    try:
        _embedding_response(runtime, {"model": "omlx", "input": {"bad": "shape"}})
    except ValueError:
        pass
    else:
        raise AssertionError("dict embeddings input should fail")

    # string input works
    single = _embedding_response(runtime, {"model": "omlx", "input": "alpha"})
    assert len(single.payload["data"]) == 1

    # list input works
    many = _embedding_response(runtime, {"model": "omlx", "input": ["alpha", "beta"]})
    assert len(many.payload["data"]) == 2


def test_embeddings_bad_request_returns_openai_error(monkeypatch):
    runtime = _build_runtime()
    _patch_server_deps(monkeypatch)
    app = create_app(runtime)
    handler = app.routes[("POST", "/v1/embeddings")]

    response = asyncio.run(handler(_FakeRequest({"model": "omlx", "input": {"bad": "shape"}})))
    _assert_openai_error(response, 400)


def test_embeddings_invalid_json_returns_openai_error(monkeypatch):
    runtime = _build_runtime()
    _patch_server_deps(monkeypatch)
    app = create_app(runtime)
    handler = app.routes[("POST", "/v1/embeddings")]

    response = asyncio.run(handler(_InvalidJSONRequest()))
    _assert_openai_error(response, 400)


def test_embeddings_array_body_returns_openai_error(monkeypatch):
    runtime = _build_runtime()
    _patch_server_deps(monkeypatch)
    app = create_app(runtime)
    handler = app.routes[("POST", "/v1/embeddings")]

    response = asyncio.run(handler(_FakeRequest(["alpha"])))
    _assert_openai_error(response, 400)


def test_embeddings_provider_output_non_list_fails():
    runtime = _build_runtime()
    runtime.client.embed = lambda *_args, **_kwargs: "not-a-list"

    try:
        _embedding_response(runtime, {"input": ["alpha"]})
    except Exception as exc:
        assert "non-list" in str(exc)
    else:
        raise AssertionError("non-list embeddings output should fail")


def test_embeddings_provider_output_wrong_count_fails():
    runtime = _build_runtime()
    runtime.client.embed = lambda *_args, **_kwargs: [[1.0, 2.0], [3.0, 4.0]]

    try:
        _embedding_response(runtime, {"input": ["alpha"]})
    except Exception as exc:
        assert "wrong number" in str(exc)
    else:
        raise AssertionError("mismatched embeddings output size should fail")


def test_embeddings_provider_output_non_numeric_fails():
    runtime = _build_runtime()
    runtime.client.embed = lambda *_args, **_kwargs: [[1.0, "bad"]]

    try:
        _embedding_response(runtime, {"input": ["alpha"]})
    except Exception as exc:
        assert "non-numeric" in str(exc)
    else:
        raise AssertionError("non-numeric embeddings output should fail")


def test_embeddings_provider_tuples_and_ints_normalize_to_floats():
    runtime = _build_runtime()
    runtime.client.embed = lambda *_args, **_kwargs: [(1, 2, 3)]

    result = _embedding_response(runtime, {"input": ["alpha"]})
    embedding = result.payload["data"][0]["embedding"]
    assert embedding == [1.0, 2.0, 3.0]
    assert all(isinstance(item, float) for item in embedding)


def test_stream_completion_events_raw_provider_is_lazy():
    side_effects = []

    class LazyRawProvider:
        def raw_complete(self, payload):
            return payload

        def raw_stream(self, payload):
            side_effects.append("iterated")
            yield {
                "id": "chunk-1",
                "object": "chat.completion.chunk",
                "choices": [{"index": 0, "delta": {"content": "hi"}, "finish_reason": None}],
            }

    runtime = _build_runtime(raw_provider=LazyRawProvider())
    stream_result = _stream_completion_events(
        runtime, {"messages": [{"role": "user", "content": "hello"}], "stream": True})

    assert side_effects == []
    iterator = iter(stream_result.events)
    first = next(iterator)
    assert side_effects == ["iterated"]
    body = list(_stream_response_body([first]))
    assert body[0].startswith("data: {")
    assert body[-1] == "data: [DONE]\n\n"


def test_build_runtime_does_not_forward_server_bind_host_port(monkeypatch):
    captured = {}

    class FakeClientForRuntime:
        def __init__(self, provider, model=None, prefer=None, **kwargs):
            captured["provider"] = provider
            captured["model"] = model
            captured["prefer"] = prefer
            captured["kwargs"] = dict(kwargs)
            self.provider = self
            self.model = model

    monkeypatch.setattr("modelito.serve.Client", FakeClientForRuntime)

    config = ServeConfig(
        provider="omlx",
        host="0.0.0.0",
        port=11436,
        base_url="http://localhost:8000/v1",
        timeout=7.5,
        strict=True,
        profile_path="profile.json",
    )
    _ = build_runtime(config)

    kwargs = captured["kwargs"]
    assert "host" not in kwargs
    assert "port" not in kwargs
    assert kwargs["base_url"] == "http://localhost:8000/v1"
    assert kwargs["timeout"] == 7.5
    assert kwargs["strict"] is True
    assert kwargs["profile_path"] == "profile.json"


def test_error_payload_shape_is_openai_style():
    payload = _error_payload(ModelitoProviderError("provider failed"))
    assert payload == {
        "error": {
            "message": "provider failed",
            "type": "modelito_provider_error",
            "code": "modelito_provider_error",
        }
    }


def test_error_payload_for_bad_response_uses_dedicated_code():
    payload = _error_payload(ModelitoBadResponseError("bad upstream"))
    assert payload == {
        "error": {
            "message": "bad upstream",
            "type": "modelito_bad_response_error",
            "code": "modelito_bad_response_error",
        }
    }
