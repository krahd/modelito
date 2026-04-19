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

Note: these docs are written for the repository owner / sole maintainer.

Install in editable mode for development (install optional extras as needed):

```sh
pip install -e .[dev]
pip install -r dev-requirements.txt

# Optional extras
pip install -e .[ollama,tokenization,openai,anthropic]
```

Run tests:

```sh
pytest -q
```

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

License / AS IS
---------------

This software is provided "AS IS" and without warranties of any kind. See
the included `LICENSE` file for the full MIT license text.

CI / Integration Tests
----------------------

This repository includes a GitHub Actions workflow at `.github/workflows/ci.yml`.
The workflow runs `mypy` and the unit test suite on push and pull requests.

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
```

