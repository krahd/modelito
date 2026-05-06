API Reference
=============

This file documents the public API provided by the `modelito` package.

Package exports
---------------

The package exposes a small, stable set of helpers and minimal provider
compatibility shims. The primary exports (also visible via `from modelito
import *`) are:

- `__version__` — package version string.
- `count_tokens(text: str) -> int` — estimate token count (uses `tiktoken` if available).
- `estimate_remote_timeout(model_name: Optional[str], input_tokens: int = 2048, concurrency: int = 1, with_source: bool = False) -> int | Tuple[int, Dict[str, Any]]` — conservative timeout estimator. When `with_source=True` the function returns a `(timeout_seconds, details_dict)` tuple with diagnostic metadata.
- `estimate_remote_timeout_details(model_name: Optional[str], input_tokens: int = 2048, concurrency: int = 1) -> Tuple[int, Dict[str, Any]]` — diagnostic timeout estimator returning both timeout and computation details.
- `OllamaConnector` — small conversation history manager and prompt builder. Connectors now prefer typed `Message`/`Response` dataclasses and provide both sync (`complete`) and async (`acomplete`) surfaces in addition to the legacy `send_sync` helper.
- `OllamaProvider` — HTTP-aware provider that will call a local Ollama HTTP
  API when available (via the bundled `ollama_service` helpers). If the HTTP
  API is not reachable it will attempt the Ollama CLI as a best-effort
  fallback (using `run_ollama_command`) before exposing a safe deterministic
  `summarize()` fallback useful for tests.
- `GeminiProvider`, `GrokProvider`, `OpenAIProvider`, `ClaudeProvider` — minimal provider shims with the same `list_models()` / `summarize()` surface.
- `normalize_models(raw) -> List[Dict[str, Any]]` — normalize provider model listings into dictionaries with an `id` field.
- `normalize_metadata(raw) -> Dict[str, Any]` — normalize provider metadata into a plain dictionary, wrapping scalar values when needed.
- `load_config(path: str) -> dict` — JSON/YAML loader for small config files.
- `load_config_data(*paths) -> dict` — merge multiple config files with later
  paths taking precedence; performs a deep merge of nested dicts and supports
  JSON/YAML parsing.
- `parse_host_port(host_url: str) -> Tuple[str, int]` — parse `host:port` or URL into `(host, port)`.
- `LLMProviderError` — base exception used by connector/provider helpers.
- Ollama helpers: `server_is_up`, `endpoint_url`, `ensure_ollama_running`, `get_ollama_binary`, `install_ollama`, `start_ollama`, `stop_ollama`, `update_ollama`, `list_local_models`, `list_remote_models`, `download_model`, `delete_model`, `serve_model`, `change_ollama_config`, `run_ollama_command`, etc.

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

Provider shims
--------------

Provider adapters implement the small provider surfaces used by the connectors. Implementations may choose to support the sync `summarize()` surface, the async `acomplete()` surface, streaming, and/or embeddings. The core convenience methods are:

- `list_models() -> List[str]` — best-effort model enumeration (may be an empty list in offline mode).
- `summarize(messages, settings: Optional[dict] = None) -> str` — synchronous completion surface.
- `acomplete(messages, settings: Optional[dict] = None) -> str` — asynchronous completion surface (optional).
- `stream(messages, settings: Optional[dict] = None) -> Iterable[str]` — streaming generator (optional).
- `embed(texts: Iterable[str], **kwargs) -> List[List[float]]` — embeddings surface (optional).

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

Ollama helpers
--------------

The `ollama_service` module contains a number of small helpers to interact with
the Ollama CLI and HTTP API. The most commonly used helpers are:

- `endpoint_url(host: str, port: int, path: str = "/api/generate") -> str`
- `server_is_up(host: str, port: int) -> bool`
- `ensure_ollama_running(host: str = "http://127.0.0.1", port: int = 11434, auto_start: bool = False, start_args: Optional[list] = None, timeout: float = 10.0) -> bool`
- `get_ollama_binary() -> Optional[str]`
- `list_local_models() -> List[str]` and `list_remote_models() -> List[str]`
- `download_model(model_name: str) -> bool` and `delete_model(model_name: str) -> bool`
- `serve_model(model_name: Optional[str] = None, start_args: Optional[list] = None, timeout: float = 10.0) -> bool`
- `ensure_model_available(model_name: str, allow_download: bool = False, timeout: float = 600.0) -> bool` — convenience helper to ensure a model is present locally, optionally downloading it.
- Async wrappers: `async_preload_model`, `async_list_local_models`, `async_list_remote_models`, `async_download_model`, `async_delete_model`, `async_serve_model`, `async_ensure_model_available` — simple asyncio-friendly wrappers that run the synchronous helpers in an executor.
- `change_ollama_config(config: dict, config_path: Optional[str] = None) -> bool`

Additional helpers and CLI
--------------------------

The module exposes a few additional convenience helpers and CLI entrypoints
useful for diagnostics and local workflows:

- `pull_model(model_name: str, timeout: float = 600.0) -> bool` — convenience wrapper for `download_model`.
- `preload_model(url: str, port: int, model: str, timeout: float = 120.0) -> None` — warm a model via the HTTP API.
- `load_remote_timeout_catalog(path: Optional[Path] = None) -> dict` — load the timeout catalog (falls back to the bundled catalog).
- `common_model_timeout(model_name: str) -> Optional[float]` — returns a conservative timeout in seconds for a given model.

CLI usage
---------

`modelito` exposes two small module-level CLIs useful during development:

- `python -m modelito.ollama_service` — minimal Ollama lifecycle CLI (`start`, `stop`, `install`, `inspect`, `pull`, `list-local`, `list-remote`, `version`).
- `python -m modelito.timeout_cli` — print estimated timeouts and diagnostic details for a model.
- `python -m modelito.timeout_calibrate` — write calibration prompts and (optionally) exercise a local Ollama server to collect timing samples.

 `endpoint_url(host: str, port: int, path: str = "/api/generate") -> str`
 - `server_is_up(host: str, port: int) -> bool`
 - `ensure_ollama_running(host: str = "http://127.0.0.1", port: int = 11434, auto_start: bool = False, start_args: Optional[List[str]] = None, timeout: float = 10.0) -> bool`
 - `get_ollama_binary() -> Optional[str]`
 - `list_local_models() -> List[str]` and `list_remote_models() -> List[str]`
 - `download_model(model_name: str) -> bool` and `delete_model(model_name: str) -> bool`
 - `serve_model(model_name: Optional[str] = None, start_args: Optional[List[str]] = None, timeout: float = 10.0) -> bool`
 - `change_ollama_config(config: dict, config_path: Optional[str] = None) -> bool`

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

Notes
-----

- The package intentionally keeps provider shims minimal; they are primarily
  intended for tests and simple local workflows.
- For production usage you should replace provider shims with real SDK-backed
  implementations that implement the same `list_models()` / `summarize()` surface.

Advanced API Features
--------------------

### Unified Provider Abstraction
- All providers (OpenAI, Anthropic, Google, Ollama, etc.) accessed via a consistent interface.
- Runtime provider/model switching: `from modelito.provider_registry import get_provider, list_providers`.

### Local Model Management
- Auto-discovery and health checks for local models (Ollama, etc.): `LocalModelManager`.
- Dynamic model selection without restart.

### API Key Management
- Secure, user-friendly API key management: `APIKeyManager`.
- Supports environment variable overrides and config files.
- Validation and error reporting.

### Streaming & Partial Results
- All streaming-capable providers expose a `stream()` method for incremental results.
- See `StreamingProvider` protocol.

### Error Handling & Diagnostics
- Standardized error messages and diagnostics: see `modelito.errors`.
- Structured error objects for troubleshooting.

### Model Capabilities Discovery
- Expose model metadata (context window, function/tool support, etc.): `get_model_metadata()`.

### Testing & Mocking
- Built-in mock mode for testing/CI/offline: `MockProvider`.

### Performance & Caching
- Optional in-memory response caching: `ResponseCache`.
- Batching utilities for embeddings and batchable operations: `batch_iterable`.

See the `tests/` directory for usage examples and coverage for all features.
