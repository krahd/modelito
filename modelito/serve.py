"""OpenAI-compatible HTTP server for Modelito.

The server is intentionally optional: importing :mod:`modelito` does not pull
in FastAPI or Uvicorn.  Those dependencies are only required when running the
server entrypoint.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Iterator, List, Optional

from .client import Client
from .messages import Response
from .provider import RawChatProvider


LOGGER = logging.getLogger(__name__)


@dataclass
class ServeConfig:
    provider: str = "auto"
    model: Optional[str] = None
    host: str = "127.0.0.1"
    port: int = 11436
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    strict: bool = True
    profile: Optional[str] = None
    profile_path: Optional[str] = None
    timeout: float = 20.0
    log_level: str = "info"
    prefer: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class ServeRuntime:
    config: ServeConfig
    client: Client
    provider: Any
    raw_provider: Optional[RawChatProvider]


@dataclass(frozen=True)
class ChatCompletionResult:
    payload: Dict[str, Any]
    headers: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class EmbeddingResult:
    payload: Dict[str, Any]
    headers: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class StreamResult:
    events: List[Dict[str, Any]]
    headers: Dict[str, str] = field(default_factory=dict)


def _require_server_dependencies():
    try:
        from fastapi import FastAPI, HTTPException, Request
        from fastapi.responses import JSONResponse, StreamingResponse
        import uvicorn
    except Exception as exc:  # pragma: no cover - exercised via tests
        raise RuntimeError(
            'modelito-serve requires optional dependencies. Install them with '
            'pip install "modelito[serve]"'
        ) from exc
    return FastAPI, HTTPException, Request, JSONResponse, StreamingResponse, uvicorn


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="modelito-serve",
        description="Serve an OpenAI-compatible API backed by Modelito providers",
    )
    parser.add_argument("--provider", default="auto", help="Provider name to use")
    parser.add_argument("--model", default=None, help="Requested model name")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host for the HTTP server")
    parser.add_argument("--port", type=int, default=11436, help="Bind port for the HTTP server")
    parser.add_argument("--base-url", default=None, help="OpenAI-compatible provider base URL")
    parser.add_argument("--api-key", default=None, help="Provider API key")
    parser.add_argument("--profile", default=None, help="Profile file for provider selection")
    parser.add_argument("--profile-path", default=None, help="Explicit provider profile path")
    parser.add_argument("--timeout", type=float, default=20.0,
                        help="Provider request timeout in seconds")
    parser.add_argument("--log-level", default="info", help="Python logging level")
    parser.add_argument("--prefer", nargs="*", default=None,
                        help="Preferred providers for auto mode")
    strict_group = parser.add_mutually_exclusive_group()
    strict_group.add_argument("--strict", dest="strict", action="store_true",
                              help="Fail on tool requests without raw passthrough")
    strict_group.add_argument("--no-strict", dest="strict", action="store_false",
                              help="Allow text-only fallback when raw passthrough is unavailable")
    parser.set_defaults(strict=True)
    return parser


def build_config(args: argparse.Namespace) -> ServeConfig:
    profile_path = getattr(args, "profile_path", None) or getattr(args, "profile", None)
    prefer = list(getattr(args, "prefer", None) or [])
    return ServeConfig(
        provider=str(getattr(args, "provider", "auto") or "auto"),
        model=getattr(args, "model", None),
        host=str(getattr(args, "host", "127.0.0.1") or "127.0.0.1"),
        port=int(getattr(args, "port", 11436) or 11436),
        base_url=getattr(args, "base_url", None),
        api_key=getattr(args, "api_key", None),
        strict=bool(getattr(args, "strict", True)),
        profile=getattr(args, "profile", None),
        profile_path=profile_path,
        timeout=float(getattr(args, "timeout", 20.0) or 20.0),
        log_level=str(getattr(args, "log_level", "info") or "info"),
        prefer=prefer,
    )


def build_runtime(config: ServeConfig) -> ServeRuntime:
    client_kwargs: Dict[str, Any] = {
        "base_url": config.base_url,
        "api_key": config.api_key,
        "host": config.host,
        "port": config.port,
        "timeout": config.timeout,
        "strict": config.strict,
        "profile_path": config.profile_path or config.profile,
    }
    client = Client(
        provider=config.provider,
        model=config.model,
        prefer=config.prefer,
        **client_kwargs,
    )
    provider = client.provider
    raw_provider = provider if isinstance(provider, RawChatProvider) else None
    return ServeRuntime(config=config, client=client, provider=provider, raw_provider=raw_provider)


def _payload_model(runtime: ServeRuntime, payload: Dict[str, Any]) -> str:
    model = payload.get("model")
    if isinstance(model, str) and model.strip():
        return model
    if runtime.client.model:
        return str(runtime.client.model)
    return "modelito"


def _chat_settings(payload: Dict[str, Any]) -> Dict[str, Any]:
    excluded = {"model", "messages", "stream"}
    return {key: value for key, value in payload.items() if key not in excluded}


def _has_tools(payload: Dict[str, Any]) -> bool:
    tools = payload.get("tools")
    return isinstance(tools, list) and bool(tools)


def _fallback_warning(reason: str) -> Dict[str, str]:
    return {"X-Modelito-Warning": reason}


def _messages_from_payload(payload: Dict[str, Any]) -> List[Any]:
    messages = payload.get("messages")
    if isinstance(messages, list):
        return list(messages)
    if isinstance(messages, str):
        return [messages]
    return []


def _chat_completion_response(runtime: ServeRuntime, payload: Dict[str, Any]) -> ChatCompletionResult:
    request_payload = dict(payload or {})
    model = _payload_model(runtime, request_payload)
    request_payload.setdefault("model", model)

    if runtime.raw_provider is not None:
        raw = runtime.raw_provider.raw_complete(request_payload)
        if not isinstance(raw, dict):
            raise ValueError("raw_complete must return a JSON object")
        return ChatCompletionResult(payload=raw)

    if _has_tools(request_payload) and runtime.config.strict:
        raise ValueError(
            "tools require raw passthrough support; run with --no-strict to allow text-only fallback")

    settings = _chat_settings(request_payload)
    response = runtime.client.chat(_messages_from_payload(request_payload), settings=settings)
    if not isinstance(response, Response):
        raise ValueError("client.chat() did not return a Response")

    finish_reason = response.finish_reason or "stop"
    completion = {
        "id": f"chatcmpl-modelito-{int(time.time() * 1000)}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": response.model or model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": response.text},
                "finish_reason": finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": response.tokens_in or 0,
            "completion_tokens": response.tokens_out or 0,
            "total_tokens": (response.tokens_in or 0) + (response.tokens_out or 0),
        },
    }
    return ChatCompletionResult(payload=completion, headers=_fallback_warning("modelito fallback response; tool calls are not supported"))


def _stream_delta_text(delta: Dict[str, Any]) -> Optional[str]:
    content = delta.get("content")
    if isinstance(content, str) and content:
        return content
    return None


def _stream_completion_events(runtime: ServeRuntime, payload: Dict[str, Any]) -> StreamResult:
    request_payload = dict(payload or {})
    model = _payload_model(runtime, request_payload)
    request_payload.setdefault("model", model)
    request_payload["stream"] = True

    if runtime.raw_provider is not None:
        return StreamResult(events=list(runtime.raw_provider.raw_stream(request_payload)))

    if _has_tools(request_payload) and runtime.config.strict:
        raise ValueError(
            "tools require raw passthrough support; run with --no-strict to allow text-only fallback")

    settings = _chat_settings(request_payload)
    chunks = list(runtime.client.stream(_messages_from_payload(request_payload), settings=settings))
    events: List[Dict[str, Any]] = [
        {
            "id": f"chatcmpl-modelito-{int(time.time() * 1000)}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}
            ],
        }
    ]
    for chunk in chunks:
        if not chunk:
            continue
        events.append(
            {
                "id": f"chatcmpl-modelito-{int(time.time() * 1000)}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [
                    {"index": 0, "delta": {"content": chunk}, "finish_reason": None}
                ],
            }
        )
    events.append(
        {
            "id": f"chatcmpl-modelito-{int(time.time() * 1000)}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {"index": 0, "delta": {}, "finish_reason": "stop"}
            ],
        }
    )
    return StreamResult(events=events, headers=_fallback_warning("modelito fallback stream; tool calls are not supported"))


def _embedding_response(runtime: ServeRuntime, payload: Dict[str, Any]) -> EmbeddingResult:
    request_payload = dict(payload or {})
    model = _payload_model(runtime, request_payload)
    raw_input = request_payload.get("input")
    if isinstance(raw_input, str):
        inputs = [raw_input]
    elif isinstance(raw_input, list):
        inputs = [str(item) for item in raw_input]
    else:
        inputs = []

    vectors = runtime.client.embed(inputs, model=model)
    data = [
        {"object": "embedding", "embedding": vector, "index": index}
        for index, vector in enumerate(vectors)
    ]
    response = {
        "object": "list",
        "data": data,
        "model": model,
        "usage": {"prompt_tokens": 0, "total_tokens": 0},
    }
    return EmbeddingResult(payload=response)


def _models_response(runtime: ServeRuntime) -> Dict[str, Any]:
    models = runtime.client.list_models()
    return {
        "object": "list",
        "data": [
            {"id": model, "object": "model", "created": 0, "owned_by": "modelito"}
            for model in models
        ],
    }


def _sse_frame(payload: Dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, separators=(',', ':'), ensure_ascii=False)}\n\n"


def _sse_done() -> str:
    return "data: [DONE]\n\n"


def _stream_response_body(events: Iterable[Dict[str, Any]]) -> Iterator[str]:
    for event in events:
        yield _sse_frame(event)
    yield _sse_done()


def create_app(runtime: ServeRuntime):
    FastAPI, HTTPException, Request, JSONResponse, StreamingResponse, _uvicorn = _require_server_dependencies()
    app = FastAPI(title="Modelito", version="1.4.4")

    @app.get("/v1/models")
    async def list_models() -> Any:
        return JSONResponse(_models_response(runtime))

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Any) -> Any:
        payload = await request.json()
        if payload.get("stream"):
            try:
                stream_result = _stream_completion_events(runtime, payload)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            headers = dict(stream_result.headers)
            return StreamingResponse(
                _stream_response_body(stream_result.events),
                media_type="text/event-stream",
                headers=headers,
            )
        try:
            result = _chat_completion_response(runtime, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return JSONResponse(result.payload, headers=result.headers)

    @app.post("/v1/embeddings")
    async def embeddings(request: Any) -> Any:
        payload = await request.json()
        try:
            result = _embedding_response(runtime, payload)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return JSONResponse(result.payload, headers=result.headers)

    return app


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    config = build_config(args)
    runtime = build_runtime(config)

    try:
        FastAPI, HTTPException, Request, JSONResponse, StreamingResponse, uvicorn = _require_server_dependencies()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    app = create_app(runtime)
    uvicorn.run(app, host=config.host, port=config.port, log_level=str(config.log_level).lower())
    return 0


__all__ = [
    "ServeConfig",
    "ServeRuntime",
    "ChatCompletionResult",
    "EmbeddingResult",
    "StreamResult",
    "build_parser",
    "build_config",
    "build_runtime",
    "create_app",
    "main",
    "_models_response",
    "_chat_completion_response",
    "_stream_completion_events",
    "_embedding_response",
]
