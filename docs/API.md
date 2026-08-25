API Reference
=============

This file documents the public API provided by the `modelito` package.

Package exports
---------------

The package exposes a small, stable set of helpers and a Client-first chat
surface. The primary exports (also visible via `from modelito import *`) are:

- `__version__` — package version string.
- `count_tokens(text: str) -> int` — estimate token count (uses `tiktoken` if available).
- `estimate_remote_timeout(model_name: Optional[str], input_tokens: int = 2048, concurrency: int = 1, with_source: bool = False) -> int | Tuple[int, Dict[str, Any]]` — conservative timeout estimator. When `with_source=True` the function returns a `(timeout_seconds, details_dict)` tuple with diagnostic metadata.
- `estimate_remote_timeout_details(model_name: Optional[str], input_tokens: int = 2048, concurrency: int = 1) -> Tuple[int, Dict[str, Any]]` — diagnostic timeout estimator returning both timeout and computation details.
- `OllamaConnector` — small conversation history manager and prompt builder. Connectors now prefer typed `Message`/`Response` dataclasses and provide both sync (`complete`) and async (`acomplete`) surfaces in addition to the legacy `send_sync` helper.
- `Embedder` — small embeddings-only runtime wrapper that mirrors the provider-selection behavior of `Client` for callers that only need vector embeddings.
- `Client` — primary application entry point with `chat()`, `chat_json()`, `chat_parsed()`, `stream()`, and provider auto-selection support.
- `Provider`, `SyncProvider`, `AsyncProvider`, `StreamingProvider`, `EmbeddingProvider`, `ChatProvider`, `RawChatProvider` — structural provider protocols for legacy, chat-first, and raw OpenAI-compatible code.
- `Message`, `Response`, `MessageInput`, `OpenAIMessageDict` — message and response dataclasses / type helpers.
- `ProviderStatus`, `check_provider_ready()`, `format_provider_status()` — readiness diagnostics helpers for local and hosted providers.
- `LocalRuntimeSelection`, `select_local_runtime()`, `local_client()` — explicit local-only runtime selection and client construction.
- `LocalRuntimeCapabilities`, `local_runtime_capabilities()` — conservative capability metadata for supported local runtime families.
- `LOCAL_PROFILE_AUTO`, `LOCAL_PROFILE_PORTABLE`, `LOCAL_PROFILE_MAC_PERFORMANCE`, `LOCAL_PROFILES`, `normalize_local_profile()`, `local_provider_candidates()`, `is_macos_apple_silicon()` — local deployment-profile helpers.
- `OpenAICompatibleHTTPProvider` — shared HTTP base class for local OpenAI-compatible runtimes.
- `OllamaProvider` — HTTP-aware provider that will call a local Ollama HTTP
  API when available (via the bundled `ollama_service` helpers). If the HTTP
  API is not reachable it will attempt the Ollama CLI as a best-effort
  fallback (using `run_ollama_command`) before exposing a safe deterministic
  `summarize()` fallback useful for tests. For native `/api/chat` and
  `/api/generate` requests, flat generation settings such as `temperature`,
  `seed`, and `num_predict` are placed in Ollama's `options` object. An explicit
  `settings["options"]` mapping is also supported; `format`, `keep_alive`,
  `think`, `tools`, and other recognised native request fields remain top-level
  controls. Unknown flat settings are not guessed or forwarded; use
  `settings["options"]` for additional model-specific Ollama options. The
  common `max_tokens` and JSON `response_format` settings are translated to
  `num_predict` and Ollama's native `format`, respectively.
- `OpenAIProvider` — SDK-backed hosted OpenAI provider; can also target hosted OpenAI-compatible APIs via `base_url`.
- `BaseRTProvider` — thin preset for a local BaseRT OpenAI-compatible server.
- `VLLMMLXProvider` — thin preset for a local vllm-mlx OpenAI-compatible server.
- `OMLXProvider` — thin preset for local oMLX runtimes, built on `OpenAICompatibleHTTPProvider`.
- `GeminiProvider`, `GrokProvider`, `ClaudeProvider` — minimal provider shims with the legacy `list_models()` / `summarize()` surface.
- `EmbeddingProvider` — structural protocol for provider implementations that expose `embed(texts, **kwargs)`.
- `embed_texts(texts, dim=8) -> List[List[float]]` and `StubEmbeddingProvider` — deterministic test-friendly embedding helpers.
- `normalize_models(raw) -> List[Dict[str, Any]]` — normalize provider model listings into dictionaries with an `id` field.
- `normalize_metadata(raw) -> Dict[str, Any]` — normalize provider metadata into a plain dictionary, wrapping scalar values when needed.
- `load_config(path: str) -> dict` — JSON/YAML loader for small config files.
- `load_config_data(*paths) -> dict` — merge multiple config files with later
  paths taking precedence; performs a deep merge of nested dicts and supports
  JSON/YAML parsing.
- `parse_host_port(host_url: str) -> Tuple[str, int]` — parse `host:port` or URL into `(host, port)`.
- `LLMProviderError` — base exception used by connector/provider helpers.
- Ollama helpers: `server_is_up`, `endpoint_url`, `ensure_ollama_running`, `get_ollama_binary`, `install_ollama`, `start_ollama`, `stop_ollama`, `update_ollama`, `list_local_models`, `list_remote_models`, `download_model`, `delete_model`, `serve_model`, `change_ollama_config`, `run_ollama_command`, etc.

Namespaced public helpers
-------------------------

Some functionality is grouped into namespaced submodules to keep the primary
`modelito` namespace focused and stable. These helpers are part of the public
API and are safe to import directly from their namespace:

- **Recording and Replay**: `from modelito.recording import RecordingProvider, ReplayProvider, CassetteFormatError, ReplayMissError`
  - `RecordingProvider` — wraps any modelito provider and persists request/response pairs to a JSONL cassette file for offline testing.
  - `ReplayProvider` — reads a cassette file and returns stored responses without touching the network.
  - Both are zero-dependency and work entirely with stdlib, making them suitable for tests and examples.

Example usage:

```python
from modelito.mock_provider import MockProvider
from modelito.messages import Message
from modelito.recording import RecordingProvider, ReplayProvider

# Record calls to a cassette
provider = RecordingProvider(
    wrapped=MockProvider(),
    cassette="tests/cassettes/demo.jsonl"
)
response = provider.summarize(messages=[Message(role="user", content="Hello")])

# Replay from cassette
replay = ReplayProvider(cassette="tests/cassettes/demo.jsonl")
cached_response = replay.summarize(messages=[Message(role="user", content="Hello")])
```

Key classes and functions
-------------------------

`count_tokens(text: str) -> int`
: Returns an estimated token count. If `tiktoken` is installed it uses a real
  encoding; otherwise a conservative heuristic is used.

`estimate_remote_timeout(model_name: Optional[str], input_tokens: int = 2048, concurrency: int = 1, with_source: bool = False) -> int | Tuple[int, Dict[str, Any]]`
: Returns an integer number of seconds to use as a conservative request timeout
  for remote LLM calls. Reads a small catalog shipped in `modelito/data` and
  applies family/keyword multipliers when present. For a diagnostic breakdown
  use `estimate_remote_timeout_details(...)`; a CLI wrapper is available at
  `modelito.timeout_cli`, and a small calibration harness lives at
  `modelito.timeout_calibrate`.

You can request diagnostic details about how a timeout was computed by
calling the function with `with_source=True`. This returns a tuple
`(timeout_seconds, source_dict)` where `source_dict` contains the matched
catalog band, any model overrides, multipliers and other metadata useful
for debugging and calibrating timeouts. Example:

```py
from modelito import estimate_remote_timeout

timeout, info = estimate_remote_timeout("llama-2-70b", input_tokens=1000, concurrency=1, with_source=True)
print(timeout)
print(info)
```

`OllamaConnector(provider, shared_history: bool = False, system_message_file: Optional[str] = None, max_history_messages: int = 20, max_history_tokens: Optional[int] = None)`
: Lightweight stateful connector that manages per-conversation histories and
  prepares `messages` lists suitable for provider `.summarize()` calls.

Important `OllamaConnector` methods

- `clear_history(conv_id: Optional[str] = None) -> None`
- `set_system_message(text: Optional[str]) -> None`
- `add_to_history(conv_id: Optional[str], role: str, content: str) -> None`
- `get_history(conv_id: Optional[str]) -> List[Dict[str, str]]`
- `build_prompt(conv_id: Optional[str], new_messages: Optional[List[Dict[str, str]]]=None, include_history: bool=True, max_prompt_tokens: Optional[int]=None) -> List[Dict[str,str]]`
- `send_sync(conv_id: Optional[str], new_messages: List[Dict[str,str]], settings: Optional[dict]=None) -> str` — convenience helper that builds the prompt, calls `provider.summarize(messages, settings=settings)` and updates local history (returns `str`).
- `complete(conv_id: Optional[str], new_messages: Optional[Iterable]=None, settings: Optional[dict]=None) -> Response` — typed convenience wrapper returning a `Response` dataclass.
- `acomplete(conv_id: Optional[str], new_messages: Optional[Iterable]=None, settings: Optional[dict]=None) -> Response` — asynchronous variant.

Local runtime selection
-----------------------

`local_client(model=None, *, models=None, profile=None, prefer=None, host=None, port=None, base_url=None, base_urls=None, api_key=None, api_keys=None, probe_timeout=1.5, **provider_kwargs)`
: Construct a strict local-only `Client` after probing the configured local
  runtime candidates. It does not fall back to hosted providers or to the
  deterministic offline shim when no requested local runtime/model is ready.

`select_local_runtime(...) -> LocalRuntimeSelection`
: Run the same read-only local selection logic without constructing a client.
  The result records the resolved profile, provider, model, and endpoint.

`local_runtime_capabilities(provider: str) -> LocalRuntimeCapabilities`
: Return coarse runtime-family metadata for streaming, prefix caching,
  cancellation, structured output, tool calls, and model discovery. Values are
  `yes`, `no`, `conditional`, or `unknown`; they do not replace feature-testing
  the actual model/runtime configuration.

Profiles:

- `portable` — Ollama as the cross-platform path.
- `mac-performance` — Apple Silicon only; default candidate order is BaseRT,
  vllm-mlx, oMLX, then Ollama.
- `auto` — resolves to `mac-performance` on Apple Silicon and `portable`
  elsewhere.

The candidate order is a deployment policy, not a universal performance
ranking. Pass `prefer=` to reorder candidates after benchmarking the target
workload. `models`, `base_urls`, and `api_keys` can map provider names to
runtime-specific values.

See `docs/LOCAL-RUNTIMES.md` for benchmark usage, capability caveats, and the
upstream-source audit.

Provider shims
--------------

Provider adapters implement the small provider surfaces used by the connectors. Implementations may choose to support the sync `summarize()` surface, the async `acomplete()` surface, streaming, `chat()`, raw OpenAI-compatible passthrough, and/or embeddings. The core convenience methods are:

- `list_models() -> List[str]` — best-effort model enumeration (may be an empty list in offline mode).
- `summarize(messages, settings: Optional[dict] = None) -> str` — synchronous completion surface.
- `acomplete(messages, settings: Optional[dict] = None) -> str` — asynchronous completion surface (optional).
- `stream(messages, settings: Optional[dict] = None) -> Iterable[str]` — streaming generator (optional).
- `chat(messages, settings: Optional[dict] = None) -> Response` — structured response surface with metadata when supported.
- `raw_complete(payload: dict[str, Any]) -> dict[str, Any]` — OpenAI-compatible completion passthrough that preserves tool calls and arbitrary fields when supported.
- `raw_stream(payload: dict[str, Any]) -> Iterable[dict[str, Any]]` — OpenAI-compatible streaming passthrough that yields parsed JSON chunks when supported.
- `embed(texts: Iterable[str], **kwargs) -> List[List[float]]` — embeddings surface (optional).

Embeddings-only wrapper
-----------------------

`Embedder(provider: str | EmbeddingProvider = "openai", model: Optional[str] = None, **kwargs)`
: Small embeddings-only runtime selector. It resolves a named embedder from
  `modelito.provider_registry` and exposes the narrow `embed()` surface.

Important `Embedder` methods and attributes:

- `embed(texts: Iterable[str], **kwargs) -> List[List[float]]`
- `provider_name -> str`
- `available_embedders() -> List[str]`

Registry helpers:

- `from modelito.provider_registry import get_embedder, list_embedders`

Example:

```py
from modelito import Embedder

embedder = Embedder(provider="mock")
vectors = embedder.embed(["one", "two"])
print(vectors)
print(Embedder.available_embedders())
```

Streaming semantics
-------------------

Providers may stream outputs at different granularities; modelito normalizes
these into a simple incremental `stream()` generator that yields `str` pieces.
Typical provider streaming shapes:

- **Token-level**: SDKs may provide token deltas. Modelito yields these as
  short text fragments suitable for concatenation.
- **Chunk-level**: Providers that emit logical chunks or JSON events are
  parsed and the textual payload is yielded as chunks.
- **Line-delimited / SSE**: HTTP services (e.g., Ollama `/api/generate`) may
  send newline-delimited JSON/SSE frames; modelito reads and normalizes these
  to textual chunks.

The `stream(messages, settings=None)` generator returns an iterable of
`str` fragments which, when concatenated, form the final response. Offline
fallbacks emit a single full-text chunk.

Structured output helpers
-------------------------

`Client.chat_json(messages, schema=None, settings=None, strict_schema=False) -> dict`
: Request structured JSON output and return a parsed `dict`; optionally apply
  key-presence schema checks and stricter runtime validation when
  `strict_schema=True`.

`Client.chat_parsed(messages, schema, settings=None, strict_schema=True) -> Any`
: Request structured JSON output and return a parsed schema object when
  supported (dataclass or Pydantic-style model hooks).

OpenAI-compatible raw passthrough
----------------------------------

The `raw_complete()` and `raw_stream()` methods enable direct passthrough of
OpenAI-compatible request payloads to supported providers. These methods preserve
all request fields (including `tools`, `tool_choice`, `response_format`, etc.)
and return raw OpenAI-compatible response dicts or streams without transformation.

**Availability**: `OpenAIProvider`, `BaseRTProvider`, `VLLMMLXProvider`,
`OMLXProvider`, `OpenAICompatibleHTTPProvider`, and `OllamaProvider` support raw
passthrough.

`raw_complete(payload: dict[str, Any]) -> dict[str, Any]`
: Send a raw OpenAI-compatible request payload and return the complete response
  dict. All standard OpenAI request fields are preserved: `model`, `messages`,
  `tools`, `tool_choice`, `temperature`, `max_tokens`, etc.
  Raises `ModelitoBadResponseError` or `ModelitoConnectionError` in strict mode;
  non-strict mode returns a deterministic fallback response dict.

`raw_stream(payload: dict[str, Any]) -> Iterable[dict[str, Any]]`
: Send a raw OpenAI-compatible request with `stream=True` and yield parsed JSON
  chunks from the Server-Sent Events (SSE) stream. The generator yields `dict`
  objects with keys like `choices`, `delta`, etc., stopping at the `[DONE]` marker.
  Raises on malformed events in strict mode; non-strict mode yields fallback chunks.

**Tool preservation**: These methods are designed to preserve tool definitions and
function calling metadata. When using `OllamaProvider` with `modelito-serve`, you can
forward OpenAI-compatible tool-calling requests directly to the underlying Ollama
instance via `/v1/chat/completions`, enabling tool-calling workflows with local models.

Example with `OllamaProvider`:

```python
from modelito import OllamaProvider

provider = OllamaProvider(model="llama3.2")

# Raw passthrough preserves tools and tool_choice
payload = {
    "model": "llama3.2",
    "messages": [
        {"role": "user", "content": "What is the weather?"}
    ],
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"}
                    }
                }
            }
        }
    ],
    "tool_choice": "auto"
}

response = provider.raw_complete(payload)
# response["choices"][0]["message"]["tool_calls"] contains function calls if generated
```

Ollama helpers
--------------

The `ollama_service` module contains a number of small helpers to interact with
the Ollama CLI and HTTP API. The most commonly used helpers are:

- `endpoint_url(host: str, port: int, path: str = "/api/generate") -> str`
- `server_is_up(host: str, port: int) -> bool`
- `ensure_ollama_running(host: str = "http://127.0.0.1", port: int = 11434, auto_start: bool = False, start_args: Optional[list] = None, timeout: float = 10.0) -> bool`
- `get_ollama_binary() -> Optional[str]`
- `list_local_models() -> List[str]`, `list_remote_models() -> List[str]`, and `list_remote_model_catalog(query: Optional[str] = None) -> List[RemoteModelCatalogEntry]`
- `download_model(model_name: str) -> bool`, `download_model_progress(model_name: str) -> Iterable[ModelLifecycleState]`, and `delete_model(model_name: str) -> bool`
- `serve_model(model_name: Optional[str] = None, start_args: Optional[list] = None, timeout: float = 10.0) -> bool`
- `ensure_model_available(model_name: str, allow_download: bool = False, timeout: float = 600.0) -> bool` — convenience helper to ensure a model is present locally, optionally downloading it.
- `ensure_model_ready(model_name: str, host: str = "http://127.0.0.1", port: int = 11434, auto_start: bool = False, allow_download: bool = False, timeout: float = 120.0) -> bool` — ensure a specific model is downloaded, warmed, and responsive.
- `ensure_model_ready_detailed(model_name: str, host: str = "http://127.0.0.1", port: int = 11434, auto_start: bool = False, allow_download: bool = False, timeout: float = 120.0) -> ReadinessResult` — like `ensure_model_ready()` but returns a structured `ReadinessResult` object with success status, lifecycle phase, message, source, elapsed_seconds, and error details for cleaner UI integration.
- `get_model_lifecycle_state(model_name: str) -> Optional[ModelLifecycleState]`, `list_model_lifecycle_states() -> Dict[str, ModelLifecycleState]`, and `clear_model_lifecycle_state(model_name: str) -> bool` — inspect or reset the in-memory per-model lifecycle tracker.
- Async wrappers: `async_preload_model`, `async_list_local_models`, `async_list_remote_models`, `async_download_model`, `async_delete_model`, `async_serve_model`, `async_ensure_model_available`, `async_ensure_model_ready`, `async_ensure_model_ready_detailed` — simple asyncio-friendly wrappers that run the synchronous helpers in an executor.
- `change_ollama_config(config: dict, config_path: Optional[str] = None) -> bool`

Additional helpers and CLI
--------------------------

The module exposes a few additional convenience helpers and CLI entrypoints
useful for diagnostics and local workflows:

- `detect_install_method(platform_name: Optional[str] = None) -> str` — pick the preferred install backend (`brew`, `apt`, `choco`, or script-based fallback) for the current platform.
- `pull_model(model_name: str, timeout: float = 600.0) -> bool` — convenience wrapper for `download_model`.
- `preload_model(url: str, port: int, model: str, timeout: float = 120.0) -> None` — warm a model via the HTTP API.
- `load_remote_timeout_catalog(path: Optional[Path] = None) -> dict` — load the timeout catalog (falls back to the bundled catalog).
- `common_model_timeout(model_name: str) -> Optional[float]` — returns a conservative timeout in seconds for a given model.

Platform-specific installer policies
-------------------------------------

The `detect_install_method()` and `install_ollama()` helpers implement a
platform-aware preference order to ensure consistent behavior across environments:

- **macOS:** `brew` (if available) → script-based fallback
- **Linux:** `apt` (if available) → script-based fallback  
- **Windows:** `choco` (if available) → PowerShell-based fallback

This policy ensures the most commonly available package manager is preferred on
each platform. To override and use a specific method, pass the `method` parameter
explicitly to `install_ollama(method="script")` or `detect_install_method()` will
return the best-effort choice for your platform.

Structured admin helpers
------------------------

For higher-level tooling, `ollama_service` now exposes two small dataclasses:

- `RemoteModelCatalogEntry` — structured remote catalog item with `name`, `family`, `tag`, `installed`, and `raw` fields.
- `ModelLifecycleState` — in-memory state snapshot with `phase`, `message`, `progress`, `error`, and `updated_at` fields.

CLI usage
---------

`modelito` exposes small module-level CLIs useful during development:

- `python -m modelito doctor` — diagnose provider readiness and report setup hints.
- `modelito-serve` — optional OpenAI-compatible server (`/v1/models`, `/v1/chat/completions`, `/v1/embeddings`) requiring `pip install "modelito[serve]"`.
- `modelito-benchmark-local` — compare conversational latency against an already-running local OpenAI-compatible server; see `docs/LOCAL-RUNTIMES.md` for measurement caveats.
- `python -m modelito.ollama_service` — minimal Ollama lifecycle CLI (`start`, `stop`, `install`, `inspect`, `pull`, `list-local`, `list-remote`, `version`).
- `python -m modelito.timeout_cli` — print estimated timeouts and diagnostic details for a model.
- `python -m modelito.timeout_calibrate` — write calibration prompts and (optionally) exercise a local Ollama server to collect timing samples.

Examples
--------

Use the `OllamaConnector` together with a provider shim for local tests:

```py
from modelito import OllamaProvider, OllamaConnector
from modelito.messages import Message

provider = OllamaProvider()
conn = OllamaConnector(provider=provider)
resp = conn.send_sync(conv_id="example", new_messages=[Message(role="user", content="Summarize: Hello world")])
print(resp)
```

Recording and replay
--------------------

`RecordingProvider(wrapped, cassette: str | Path)`
: Wraps any modelito provider and persists each call to a JSONL cassette file.
  Returns the wrapped provider's result unchanged, so it is a pure passthrough
  with side-effect persistence only.  Normalises `str`, `dict`, and `Message`
  inputs — and exhausts generators exactly once — before delegating to the
  wrapped provider.

`ReplayProvider(cassette: str | Path, *, strict: bool = True, model: str | None = None, strict_cassette: bool = True)`
: Reads a JSONL cassette written by `RecordingProvider` and returns stored
  responses without touching the network or any model runtime.  By default
  replay is model-agnostic (``model=None``): records are matched by
  kind + messages + settings, ignoring the recorded provider's model name.
  Pass ``model="..."`` for exact model-aware lookup.

`CassetteFormatError(path, line_number, line)`
: Raised when a cassette file contains malformed JSON.  Attributes: `path`,
  `line_number`, `line`.

`ReplayMissError(kind, request_hash)`
: Raised by `ReplayProvider` (in strict mode) when no cassette record matches
  the request.  Attributes: `kind`, `request_hash`.

V1 scope: supports `list_models()`, `summarize()`, and `chat()` only.
`stream()` and `embed()` raise `NotImplementedError`.  All inputs are
stdlib-only; no additional package is required.

Example::

    from modelito import Message
    from modelito.mock_provider import MockProvider
    from modelito.recording import RecordingProvider, ReplayProvider

    # Record
    p = RecordingProvider(wrapped=MockProvider(), cassette="/tmp/demo.jsonl")
    p.summarize([Message(role="user", content="hello")])

    # Replay offline
    r = ReplayProvider(cassette="/tmp/demo.jsonl")
    print(r.summarize([Message(role="user", content="hello")]))

Notes
-----

- The package intentionally keeps provider shims minimal; they are primarily
  intended for tests and simple local workflows.
- For production usage you should replace provider shims with real SDK-backed
  implementations that implement the same `list_models()` / `summarize()` surface.
- Static model metadata in `modelito.model_metadata` is best-effort fallback
  data. Prefer provider-reported model information when available.
- Unknown metadata fields are intentionally represented as `None`, and static
  metadata should not be treated as authoritative for safety-critical routing.

Advanced API Features
--------------------

Unified Provider Abstraction:

- All providers (OpenAI, Anthropic, Google, Ollama, etc.) accessed via a consistent interface.
- Runtime provider/model switching: `from modelito.provider_registry import get_provider, list_providers`.
- Runtime embedder selection: `from modelito.provider_registry import get_embedder, list_embedders`.

Local Model Management:

- Auto-discovery and health checks for local models (Ollama, etc.): `LocalModelManager`.
- Dynamic model selection without restart.

API Key Management:

- Secure, user-friendly API key management: `APIKeyManager`.
- Supports environment variable overrides and config files.
- Validation and error reporting.

Streaming & Partial Results:

- All streaming-capable providers expose a `stream()` method for incremental results.
- See `StreamingProvider` protocol.

Error Handling & Diagnostics:

- Standardized error messages and diagnostics: see `modelito.errors`.
- Structured error objects for troubleshooting.

Model Capabilities Discovery:

- Expose model metadata (context window, function/tool support, etc.): `get_model_metadata()`.

Testing & Mocking:

- Built-in mock mode for testing/CI/offline: `MockProvider`.

Performance & Caching:

- Optional in-memory response caching: `ResponseCache`.
- Batching utilities for embeddings and batchable operations: `batch_iterable`.

See the `tests/` directory for usage examples and coverage for all features.
