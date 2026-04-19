API Design & Roadmap (internal)
================================

Purpose
-------
This document records the feature mapping, public API design, and an actionable
plan for further development and extraction of `modelito`. It is maintained as
internal notes for the repository owner.

Core features
-------------
- Token counting: `tokenizer.count_tokens(text, model=None)` — lightweight wrapper
  around optional `tiktoken` with a safe fallback.
- Timeout estimation / catalog: `timeout.estimate_remote_timeout(model_name, input_tokens, concurrency)` and
  `timeout.load_catalog()` provide conservative request timeouts.
- Ollama helpers: `ollama_service.endpoint_url(host, port)`, `ollama_service.server_is_up()`,
  and `ollama_service.ensure_ollama_running()` for best-effort start/install flows.
- Connector abstraction: `connector.OllamaConnector` provides conversation history
  management and `complete()`/`acomplete()` convenience methods.
- Exceptions and contracts: `exceptions.LLMProviderError` and typed return shapes
  used by connectors and providers.

Public API design (current)
--------------------------
- `tokenizer.count_tokens(text: str, model: str | None = None) -> int`
- `timeout.estimate_remote_timeout(model_name: str | None, input_tokens: int = 2048, concurrency: int = 1) -> int`
- `OllamaConnector` class
  - `__init__(self, provider, shared_history: bool = False, system_message_file: Optional[str] = None, max_history_messages: int = 20, max_history_tokens: Optional[int] = None)`
  - `list_models(self) -> list[str]`
  - `send_sync(self, conv_id: Optional[str], new_messages: List[Message], settings: Optional[dict] = None) -> str` — convenience helper returning a string.
  - `complete(self, conv_id: Optional[str], new_messages: Optional[Iterable[Message]] = None, settings: Optional[dict] = None) -> Response` — typed wrapper returning a `Response` dataclass.
  - `acomplete(self, conv_id: Optional[str], new_messages: Optional[Iterable[Message]] = None, settings: Optional[dict] = None) -> Response` — asynchronous variant.

Refactor and extraction notes
----------------------------
This section captures practical steps for preparing `modelito` for reuse or extraction.

1. Stabilize public API signatures and document the exported symbols in `modelito/__init__.py`.
2. Add and maintain unit tests that assert the public contracts (token counting, timeout estimates, connector behaviors).
3. Keep longer-running integration tests gated behind CI checks and environment variables.

Packaging and CI
----------------
- Keep `pyproject.toml` with optional extras (`ollama`, `tokenization`, `http`) to allow downstream projects to opt into heavier dependencies when required.
- CI at `.github/workflows/ci.yml` runs linters, type checks, unit tests, and a gated integration matrix that runs when integration secrets are configured.

Next actions (internal)
-----------------------
- Update remaining docs/examples to use `Message` and `Response` dataclasses consistently.
- Consider a tighter mypy configuration after addressing typing gaps in helper modules.
- Maintain a short migration note separately if and when external users require upgrade guidance.
