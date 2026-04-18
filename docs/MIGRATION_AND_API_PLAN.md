Migration and API Plan
======================

Purpose
-------
This document records the feature mapping, public API design, and an actionable plan
to finish extracting `modelito` as a standalone library and integrate it into
downstream projects (for example: `mail_summariser` and `BatLLM`). It is intended
to be a concise, executable checklist for maintainers.

Feature mapping (BatLLM -> modelito)
-----------------------------------
- Token counting
  - modelito: `tokenizer.count_tokens(text, model=None)` — lightweight wrapper
    around optional `tiktoken` with a safe fallback.
- Timeout estimation / catalog
  - modelito: `timeout.estimate_remote_timeout(prompt_size, model)` and
    `timeout.load_timeout_catalog(path)` (catalog-driven sensible defaults).
- Ollama helpers
  - modelito: `ollama_service.endpoint_url(host, port)`, `ollama_service.server_is_up()`,
    and `ollama_service.ensure_ollama_running()` for best-effort start/install flows.
- Connector abstraction
  - modelito: `connector.OllamaConnector(host, port, model_name, timeout_estimator)`
    provides `list_models()` and `complete(messages|prompt, **kwargs)`.
- Exceptions and contracts
  - modelito: `exceptions.LLMProviderError` and clearly typed return shapes (dicts)
    that downstream code can rely on.

Public API design (recommended signatures)
-----------------------------------------
- `tokenizer.count_tokens(text: str, model: str | None = None) -> int`
- `timeout.estimate_remote_timeout(token_count: int, model: str | None = None) -> float`
- `OllamaConnector` class
  - `__init__(self, host: str='localhost', port: int=11434, model: str|None=None, timeout_estimator: Callable|None=None)`
  - `list_models(self) -> list[str]`
  - `complete(self, prompt: str | list[dict], timeout: float | None = None, **kwargs) -> dict`
- `ollama_service` helpers
  - `endpoint_url(host, port) -> str`
  - `server_is_up(host, port) -> bool`
  - `ensure_ollama_running(host, port, allow_install=False) -> bool`

Refactor and extraction plan (steps)
-----------------------------------
1. Stabilize public API signatures in `modelito/__init__.py` and add docstrings and
   small usage examples for each exported symbol.
2. Add targeted unit tests that assert the public contracts (token counting, timeout
   estimates, connector calls returning shaped dicts).
3. Add lightweight integration tests that exercise the Ollama HTTP helpers using a
   local fake server (already in `tests/` as gated integration tests).
4. Publish a test release (TestPyPI) and update downstream `pyproject.toml` or
   CI to install the test release during migration validation.
5. Remove in-repo copies in downstream projects once tests are green and open PRs
   with the dependency update and small import changes.

Packaging and CI
----------------
- Keep `pyproject.toml` with optional extras (`ollama`, `tokenization`, `http`) so
  downstream projects can opt-in to heavier dependencies when needed.
- CI already exists at `.github/workflows/ci.yml`. Ensure the workflow installs the
  package in editable mode and runs `pytest` and docs build. Gate longer-running
  integration tests behind `RUN_OLLAMA_INTEGRATION=1`.

Downstream integration notes
----------------------------
- Replace in-repo imports like `from . import ollama_service` with `from modelito import ollama_service`.
- Prefer the connector API: e.g., `from modelito.connector import OllamaConnector` and
  instantiate with runtime settings saved in the downstream app.
- Keep temporary compatibility shims in downstream repos if immediate API parity
  can't be achieved; use them only as a short-term bridge.

Tests and validation
--------------------
- Unit tests: ensure all public functions have unit coverage and type-checking via `mypy`.
- Integration tests: gate Ollama-related tests and document how to run them locally.
- Downstream smoke: include a small smoke test in downstream CI that installs the
  published `modelito` wheel from TestPyPI and runs a subset of the app tests.

Next steps (short list)
-----------------------
1. Add or update public API docstrings and examples in `modelito/__init__.py` and
   `modelito/tokenizer.py`.
2. Add a CI job or step that runs the downstream smoke test (optional, performed
   as part of migration PRs in downstream repos).
3. Open migration PRs in downstream repositories that replace local imports and
   pin to a released `modelito` version.

Contact
-------
If you need help with automated import fixes or preparing the downstream PRs,
I can prepare the diffs and open PRs targeting the repositories you specify.
