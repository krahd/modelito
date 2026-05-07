modelito
=======

Modelito is a compact, dependency-light Python library that provides provider-
agnostic abstractions and connectors for large language models (LLMs). It
offers lightweight shims for OpenAI, Claude, Gemini and local Ollama
deployments, plus utilities for token counting, timeout estimation, and small
helpers to manage Ollama servers when needed. The library is designed for easy
integration into applications and CI pipelines.

Quick start
-----------

Install
-------

To install the latest released version from PyPI:

```sh
pip install modelito
```

For development / contributor setup (editable install and dev dependencies):

```sh
pip install -e .[dev]
pip install -r dev-requirements.txt

# Optional extras
pip install -e .[ollama,tokenization,openai,anthropic]
```

Run tests (for contributors):

```sh
pytest -q
```

Install from TestPyPI (preview builds)
-------------------------------------

If you need to test a preview build published to TestPyPI, use the TestPyPI
index. TestPyPI packages are for testing only and may not be stable.

```sh
python -m pip install --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple modelito==<version>
```

If installation from the index fails, download the wheel from the TestPyPI
"Files" page and install it directly.

Build and install
-----------------

To build a source distribution and wheel locally:

```sh
python -m pip install --upgrade build
python -m build
```

Install from the built wheel:

```sh
pip install dist/*.whl
```

See the `docs/` folder for more details on calibration and migration.

Providers
---------

This package provides compatibility shims and small, dependency-light
implementations for common provider interfaces. When optional extras are
installed the package will attempt to use real SDK clients; otherwise the
shims provide safe offline-friendly fallbacks suitable for testing.

Provided shims and utilities:

- `OllamaProvider` — HTTP-aware provider that will call a local Ollama
  HTTP API when available. If the HTTP API is unavailable the provider will
  attempt to use the local Ollama CLI as a best-effort fallback before
  returning a deterministic stub useful for tests and examples.
- `GeminiProvider`, `GrokProvider` — lightweight shims.
- `OpenAIProvider`, `ClaudeProvider` — will use the official SDKs when
  installed, falling back to deterministic behavior otherwise.

The package also exposes a small Ollama administration layer for local model
operations, including install backend detection, remote catalog metadata,
download lifecycle tracking, and explicit model readiness confirmation through
helpers such as `detect_install_method`, `list_remote_model_catalog`,
`download_model_progress`, and `ensure_model_ready`.

License / AS IS
---------------

This software is provided "AS IS" and without warranties of any kind. See
the included `LICENSE` file for the full MIT license text.

CI / Integration Tests
----------------------

This repository includes a consolidated GitHub Actions workflow at
`.github/workflows/ci.yml`. It runs linting/type checks and unit tests for pull
requests and pushes to `main`, and builds docs on non-PR runs.

Ollama integration tests are intentionally gated and will only run when you
explicitly enable them. To run integration tests locally or in CI set the
environment variable `RUN_OLLAMA_INTEGRATION=1`. Additional optional flags:

- `ALLOW_OLLAMA_INSTALL=1` — permit the integration tests to attempt installing Ollama when missing.
- `ALLOW_OLLAMA_DOWNLOAD=1` — permit downloading remote models during integration tests.
- `ALLOW_OLLAMA_UPDATE=1` — permit running update flows during integration tests.

Example (local):

```sh
RUN_OLLAMA_INTEGRATION=1 pytest tests/test_ollama_integration.py -q
```

Provider integration tests for external services (OpenAI, Anthropic, etc.) are
intentionally not part of default hosted CI to keep pull requests fast and low
noise. Use local/manual execution for those checks when needed.

There is a dedicated self-hosted Ollama workflow at
`.github/workflows/integration-ollama.yml` for maintainers who want broader
integration checks on controlled infrastructure.

Provider interface
------------------

`modelito` exposes a minimal structural `Provider` Protocol that codifies the
small runtime surface expected from provider implementations and third-party
adapters. The Protocol is intentionally small to remain compatible with
existing duck-typed providers — it requires only:

- `list_models()` -> `list[str]`
- `summarize(messages, settings=None)` -> `str`

All built-in providers shipped with the package (`OpenAIProvider`,
`ClaudeProvider`, `GeminiProvider`, `OllamaProvider`, `GrokProvider`) now
explicitly subclass `Provider`. The `Provider` Protocol is decorated with
`@runtime_checkable`, so you can use `isinstance()` checks at runtime when
you need to enforce the contract in application code.

Example usage:

```py
from modelito import Provider, OllamaProvider

p: Provider = OllamaProvider()
if isinstance(p, Provider):
    from modelito.messages import Message
    resp = p.summarize([Message(role="user", content="hello")])
    print(resp)
```

The package provides typed `Message`/`Response` dataclasses and exposes a
small set of optional Protocols for provider surfaces:

- `SyncProvider` (alias: `Provider`) — existing synchronous `summarize()`/`list_models()` surface.
- `AsyncProvider` — async `acomplete()` surface for providers that support awaitable calls.
- `StreamingProvider` — streaming `stream()` generator surface.
- `EmbeddingProvider` — `embed()` surface for vector embeddings.

Embeddings can also be selected at runtime through the dedicated `Embedder`
wrapper when you only need the embedding surface instead of the full text
generation client:

```py
from modelito import Embedder

embedder = Embedder(provider="openai")
vectors = embedder.embed(["hello", "world"])
print(len(vectors), len(vectors[0]))
print(Embedder.available_embedders())
```

`modelito` exposes `Message` and `Response` dataclasses; connectors and
provider surfaces accept `Message` instances. Example usage with the current API:

```py
from modelito import Provider, Message, OllamaProvider, OllamaConnector

p: Provider = OllamaProvider()
if isinstance(p, Provider):
    resp_text = p.summarize([Message(role="user", content="hello")])
    print(resp_text)

conn = OllamaConnector(provider=p)
res = conn.complete(conv_id="example", new_messages=[Message(role="user", content="hello")])
print(res.text)
```

Streaming semantics
-------------------

Modelito normalizes provider streaming into a simple incremental text stream.
Providers may emit data at different granularities; the connector/streaming
helpers attempt to normalize these into a sequence of text chunks that are
safe to concatenate to form the final output. Common shapes you will encounter:

- **Token-level**: Backends (e.g., OpenAI SDK) may stream individual token
  deltas. These are emitted as short text fragments; consumers should append
  fragments in order to reconstruct the full output.
- **Chunk-level**: Some providers deliver logical chunks or events (for
  example, chunked JSON payloads). Modelito extracts the textual portion and
  yields it as incremental chunks.
- **Line-delimited / SSE**: HTTP services (like Ollama's `/api/generate`) may
  send newline-delimited JSON or SSE frames. Modelito reads and normalizes the
  frames and yields textual content as it becomes available.

Behavioral notes:

- The `stream()` generator yields `str` pieces; each yielded item is intended
  to be appended to reconstruct the response incrementally.
- When you need token-level control (e.g., streaming token-by-token), prefer
  providers that expose token deltas (OpenAI SDK). Modelito will still yield
  those token deltas as text fragments.
- Offline/deterministic fallbacks yield the full text in a single chunk.

Advanced Features
----------------

Unified Provider Abstraction:

- All providers (OpenAI, Anthropic, Google, Ollama, etc.) are accessed through a consistent interface.
- Runtime provider/model switching is supported via `modelito.provider_registry.get_provider()`.

Local Model Management:

- Auto-discovers local models (Ollama, etc.) and performs health checks.
- Dynamic model selection without restarting clients via `LocalModelManager`.

API Key Management:

- Secure, user-friendly API key management with environment variable and config file support.
- Validation utilities and error reporting via `APIKeyManager`.

Streaming & Partial Results:

- All streaming-capable providers expose a `stream()` method for incremental results.
- See `StreamingProvider` protocol and examples above.

Error Handling & Diagnostics:

- Standardized error messages and diagnostics for easier troubleshooting.
- Structured error objects (see `modelito.errors`).

Model Capabilities Discovery:

- Expose model metadata (context window, function/tool support, etc.) via `get_model_metadata()`.
- Normalize provider model lists and metadata for application APIs via `normalize_models()` and `normalize_metadata()`.

Testing & Mocking:

- Built-in mock mode for testing clients without real API calls (`MockProvider`).
- Useful for CI and offline development.

Performance & Caching:

- Optional in-memory response caching for repeated prompts (`ResponseCache`).
- Batching utilities for embeddings and other batchable operations.

See the `tests/` directory for comprehensive test coverage and usage examples for all features.
