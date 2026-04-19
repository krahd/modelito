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
- `estimate_remote_timeout(model_name: Optional[str], input_tokens: int = 2048, concurrency: int = 1) -> int` — conservative timeout estimator.
- `OllamaConnector` — small conversation history manager and prompt builder. Connectors now prefer typed `Message`/`Response` dataclasses and provide both sync (`complete`) and async (`acomplete`) surfaces in addition to the legacy `send_sync` helper.
- `OllamaProvider` — HTTP-aware provider that will call a local Ollama HTTP
- `OllamaProvider` — HTTP-aware provider that will call a local Ollama HTTP
  API when available (via the bundled `ollama_service` helpers). If the HTTP
  API is not reachable it will attempt the Ollama CLI as a best-effort
  fallback (using `run_ollama_command`) before exposing a safe deterministic
  `summarize()` fallback useful for tests.
- `GeminiProvider`, `GrokProvider`, `OpenAIProvider`, `ClaudeProvider` — minimal provider shims with the same `list_models()` / `summarize()` surface.
- `load_config(path: str) -> dict` — JSON/YAML loader for small config files.
- `parse_host_port(host_url: str) -> Tuple[str, int]` — parse `host:port` or URL into `(host, port)`.
- `LLMProviderError` — base exception used by connector/provider helpers.
- Ollama helpers: `server_is_up`, `endpoint_url`, `ensure_ollama_running`, `get_ollama_binary`, `install_ollama`, `start_ollama`, `stop_ollama`, `update_ollama`, `list_local_models`, `list_remote_models`, `download_model`, `delete_model`, `serve_model`, `change_ollama_config`, `run_ollama_command`, etc.

Key classes and functions
-------------------------

`count_tokens(text: str) -> int`
: Returns an estimated token count. If `tiktoken` is installed it uses a real
  encoding; otherwise a conservative heuristic is used.

`estimate_remote_timeout(model_name: Optional[str], input_tokens: int = 2048, concurrency: int = 1) -> int`
: Returns an integer number of seconds to use as a conservative request timeout
  for remote LLM calls. Reads a small catalog shipped in `modelito/data` and
  applies family/keyword multipliers when present.

`OllamaConnector(provider, shared_history: bool = False, system_message_file: Optional[str] = None, max_history_messages: int = 20, max_history_tokens: Optional[int] = None)`
: Lightweight stateful connector that manages per-conversation histories and
  prepares `messages` lists suitable for provider `.summarize()` calls.

Important `OllamaConnector` methods

- `clear_history(conv_id: Optional[str] = None) -> None`
- `set_system_message(text: Optional[str]) -> None`
- `add_to_history(conv_id: Optional[str], role: str, content: str) -> None`
- `get_history(conv_id: Optional[str]) -> List[Dict[str, str]]`
- `build_prompt(conv_id: Optional[str], new_messages: Optional[List[Dict[str, str]]]=None, include_history: bool=True, max_prompt_tokens: Optional[int]=None) -> List[Dict[str,str]]`
- `send_sync(conv_id: Optional[str], new_messages: List[Dict[str,str]], settings: Optional[dict]=None) -> str` — legacy helper that builds the prompt, calls `provider.summarize(messages, settings=settings)` and updates local history (returns `str`).
- `complete(conv_id: Optional[str], new_messages: Optional[Iterable]=None, settings: Optional[dict]=None) -> Response` — new, typed convenience wrapper returning a `Response` dataclass.
- `acomplete(conv_id: Optional[str], new_messages: Optional[Iterable]=None, settings: Optional[dict]=None) -> Response` — asynchronous variant.

Provider shims
--------------

Provider adapters implement the small provider surfaces used by the connectors. Implementations may choose to support the sync `summarize()` surface, the async `acomplete()` surface, streaming, and/or embeddings. The core convenience methods are:

- `list_models() -> List[str]` — best-effort model enumeration (may be an empty list in offline mode).
- `summarize(messages, settings: Optional[dict] = None) -> str` — synchronous completion surface.
- `acomplete(messages, settings: Optional[dict] = None) -> str` — asynchronous completion surface (optional).
- `stream(messages, settings: Optional[dict] = None) -> Iterable[str]` — streaming generator (optional).
- `embed(texts: Iterable[str], **kwargs) -> List[List[float]]` — embeddings surface (optional).

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
- `change_ollama_config(config: dict, config_path: Optional[str] = None) -> bool`

Examples
--------

Use the `OllamaConnector` together with a provider shim for safe local tests:

```py
from modelito import OllamaProvider, OllamaConnector

provider = OllamaProvider()
conn = OllamaConnector(provider=provider)
resp = conn.send_sync(conv_id="example", new_messages=[{"role": "user", "content": "Summarize: Hello world"}])
print(resp)
```

Notes
-----

- The package intentionally keeps provider shims minimal; they are primarily
  intended for tests and simple local workflows.
- For production usage you should replace provider shims with real SDK-backed
  implementations that implement the same `list_models()` / `summarize()` surface.
