modelito
=======

Modelito is a compact, dependency-light Python library that provides provider-
agnostic abstractions and connectors for large language models (LLMs). It
offers lightweight shims for OpenAI, Claude, Gemini, oMLX, local Ollama deployments,
and local OpenAI-compatible servers (llama.cpp, vLLM, LM Studio), plus
utilities for token counting, timeout estimation, and small helpers to manage
Ollama servers when needed. The library is designed for easy integration into
applications and CI pipelines. 

Quick start
-----------

Install
-------

To install the latest released version from PyPI:

```sh
pip install modelito
```

`pip install modelito` does not install FastAPI/Uvicorn. Those are optional
and only needed for `modelito-serve`.

Release publishing uses PyPI trusted publishing through
`.github/workflows/publish.yml`. The PyPI project must have a matching trusted
publisher configured for repository `krahd/modelito`, workflow `publish.yml`,
and environment `pypi`. The workflow also checks that the tag version matches
`pyproject.toml` before building or publishing.

For development / contributor setup (editable install and dev dependencies):

```sh
pip install -e .[dev]

# Optional: add runtime extras for full functionality
pip install -e .[ollama,tokenization,openai,anthropic,gemini,grok]
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

See the `docs/` folder for more details:
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — Core design, Provider Protocol, and SDK hierarchy
- [USAGE.md](docs/USAGE.md) — Usage guide and examples
- [local-openai-compatible.md](docs/local-openai-compatible.md) — Using local OpenAI-compatible servers
- [INSTALL.md](docs/INSTALL.md), [API.md](docs/API.md) — Installation and API reference
- [RELEASE.md](docs/RELEASE.md) — Release checklist and publication steps

### Architecture snapshot

The diagrams below are intentionally compact and current-state oriented.
Detailed architecture policy lives in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

<svg xmlns="http://www.w3.org/2000/svg" width="1040" height="500" viewBox="0 0 1040 500" role="img" aria-labelledby="modelito-arch-title modelito-arch-desc">
  <title id="modelito-arch-title">modelito architecture</title>
  <desc id="modelito-arch-desc">Core protocols connect clients, Pi and OpenAI-compatible callers, modelito-serve, provider adapters, shared probes, model metadata helpers, and package documentation/tests.</desc>
  <defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0 L10 5 L0 10 z" /></marker></defs>
  <rect x="30" y="185" width="145" height="85" rx="10" fill="none" stroke="black" /><text x="102" y="218" text-anchor="middle" font-size="14">Pi / OpenAI</text><text x="102" y="240" text-anchor="middle" font-size="12">compatible clients</text>
  <rect x="200" y="55" width="165" height="85" rx="10" fill="none" stroke="black" /><text x="282" y="88" text-anchor="middle" font-size="14">modelito-serve</text><text x="282" y="110" text-anchor="middle" font-size="12">/v1/models</text><text x="282" y="128" text-anchor="middle" font-size="12">/v1/chat/completions</text>
  <rect x="200" y="190" width="165" height="85" rx="10" fill="none" stroke="black" /><text x="282" y="223" text-anchor="middle" font-size="14">Client</text><text x="282" y="245" text-anchor="middle" font-size="12">chat / json / parsed</text><text x="282" y="263" text-anchor="middle" font-size="12">package-root exports</text>
  <rect x="400" y="55" width="170" height="85" rx="10" fill="none" stroke="black" /><text x="485" y="88" text-anchor="middle" font-size="14">Raw-capable path</text><text x="485" y="110" text-anchor="middle" font-size="12">RawChatProvider,</text><text x="485" y="128" text-anchor="middle" font-size="12">OpenAICompat, OMLX, OpenAI</text>
  <rect x="400" y="190" width="170" height="85" rx="10" fill="none" stroke="black" /><text x="485" y="223" text-anchor="middle" font-size="14">Fallback path</text><text x="485" y="245" text-anchor="middle" font-size="12">summarize / stream</text><text x="485" y="263" text-anchor="middle" font-size="12">Response / dict output</text>
  <rect x="600" y="40" width="180" height="95" rx="10" fill="none" stroke="black" /><text x="690" y="74" text-anchor="middle" font-size="14">Hosted adapters</text><text x="690" y="96" text-anchor="middle" font-size="12">OpenAI, Claude,</text><text x="690" y="114" text-anchor="middle" font-size="12">Gemini, Grok</text>
  <rect x="600" y="155" width="180" height="95" rx="10" fill="none" stroke="black" /><text x="690" y="189" text-anchor="middle" font-size="14">Shared probes</text><text x="690" y="211" text-anchor="middle" font-size="12">modelito/probes.py</text><text x="690" y="229" text-anchor="middle" font-size="12">modelito-doctor</text>
  <rect x="600" y="270" width="180" height="95" rx="10" fill="none" stroke="black" /><text x="690" y="304" text-anchor="middle" font-size="14">Local Ollama</text><text x="690" y="326" text-anchor="middle" font-size="12">provider and admin</text><text x="690" y="344" text-anchor="middle" font-size="12">raw passthrough deferred</text>
  <rect x="815" y="40" width="180" height="95" rx="10" fill="none" stroke="black" /><text x="905" y="74" text-anchor="middle" font-size="14">Metadata helpers</text><text x="905" y="96" text-anchor="middle" font-size="12">ModelMetadata,</text><text x="905" y="114" text-anchor="middle" font-size="12">get_model_info, infer</text>
  <rect x="815" y="270" width="180" height="95" rx="10" fill="none" stroke="black" /><text x="905" y="304" text-anchor="middle" font-size="14">docs and tests</text><text x="905" y="326" text-anchor="middle" font-size="12">CI, build, release</text><text x="905" y="344" text-anchor="middle" font-size="12">current-state snapshot</text>
  <line x1="175" y1="227" x2="200" y2="227" stroke="black" marker-end="url(#arrow)" /><line x1="365" y1="97" x2="400" y2="97" stroke="black" marker-end="url(#arrow)" /><line x1="365" y1="232" x2="400" y2="232" stroke="black" marker-end="url(#arrow)" /><line x1="570" y1="97" x2="600" y2="87" stroke="black" marker-end="url(#arrow)" /><line x1="570" y1="232" x2="600" y2="202" stroke="black" marker-end="url(#arrow)" /><line x1="780" y1="87" x2="815" y2="87" stroke="black" marker-end="url(#arrow)" /><line x1="780" y1="202" x2="815" y2="202" stroke="black" marker-end="url(#arrow)" /><line x1="690" y1="250" x2="690" y2="270" stroke="black" marker-end="url(#arrow)" />
</svg>

<svg xmlns="http://www.w3.org/2000/svg" width="1040" height="350" viewBox="0 0 1040 350" role="img" aria-labelledby="modelito-flow-title modelito-flow-desc">
  <title id="modelito-flow-title">modelito provider request flow</title>
  <desc id="modelito-flow-desc">Pi or OpenAI-compatible clients call modelito-serve or the Client API, modelito chooses a raw-capable or fallback provider path, shared probes assist detection, and responses are returned as parsed data or text.</desc>
  <defs><marker id="flowarrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0 L10 5 L0 10 z" /></marker></defs>
  <rect x="20" y="135" width="120" height="70" rx="10" fill="none" stroke="black" /><text x="80" y="163" text-anchor="middle" font-size="12">Pi / OpenAI</text><text x="80" y="181" text-anchor="middle" font-size="12">clients</text>
  <rect x="165" y="135" width="120" height="70" rx="10" fill="none" stroke="black" /><text x="225" y="163" text-anchor="middle" font-size="12">modelito-serve</text><text x="225" y="181" text-anchor="middle" font-size="12">/v1/models</text>
  <rect x="310" y="135" width="120" height="70" rx="10" fill="none" stroke="black" /><text x="370" y="163" text-anchor="middle" font-size="12">/chat/completions</text><text x="370" y="181" text-anchor="middle" font-size="12">/embeddings</text>
  <rect x="455" y="135" width="120" height="70" rx="10" fill="none" stroke="black" /><text x="515" y="163" text-anchor="middle" font-size="12">Raw-capable</text><text x="515" y="181" text-anchor="middle" font-size="12">providers</text>
  <rect x="600" y="135" width="120" height="70" rx="10" fill="none" stroke="black" /><text x="660" y="163" text-anchor="middle" font-size="12">RawChatProvider</text><text x="660" y="181" text-anchor="middle" font-size="12">OpenAICompat</text>
  <rect x="745" y="135" width="120" height="70" rx="10" fill="none" stroke="black" /><text x="805" y="163" text-anchor="middle" font-size="12">OMLX / OpenAI</text><text x="805" y="181" text-anchor="middle" font-size="12">raw passthrough</text>
  <rect x="890" y="135" width="120" height="70" rx="10" fill="none" stroke="black" /><text x="950" y="163" text-anchor="middle" font-size="12">Response</text><text x="950" y="181" text-anchor="middle" font-size="12">or parsed dict</text>
  <rect x="455" y="240" width="120" height="65" rx="10" fill="none" stroke="black" /><text x="515" y="267" text-anchor="middle" font-size="12">Fallback path</text><text x="515" y="285" text-anchor="middle" font-size="12">summarize / stream</text>
  <rect x="600" y="240" width="120" height="65" rx="10" fill="none" stroke="black" /><text x="660" y="267" text-anchor="middle" font-size="12">Non-raw</text><text x="660" y="285" text-anchor="middle" font-size="12">Response / text</text>
  <rect x="745" y="240" width="120" height="65" rx="10" fill="none" stroke="black" /><text x="805" y="267" text-anchor="middle" font-size="12">Shared probes</text><text x="805" y="285" text-anchor="middle" font-size="12">modelito-doctor</text>
  <rect x="890" y="240" width="120" height="65" rx="10" fill="none" stroke="black" /><text x="950" y="267" text-anchor="middle" font-size="12">Package root</text><text x="950" y="285" text-anchor="middle" font-size="12">exports</text>
  <line x1="140" y1="170" x2="165" y2="170" stroke="black" marker-end="url(#flowarrow)" /><line x1="285" y1="170" x2="310" y2="170" stroke="black" marker-end="url(#flowarrow)" /><line x1="430" y1="170" x2="455" y2="170" stroke="black" marker-end="url(#flowarrow)" /><line x1="575" y1="170" x2="600" y2="170" stroke="black" marker-end="url(#flowarrow)" /><line x1="720" y1="170" x2="745" y2="170" stroke="black" marker-end="url(#flowarrow)" /><line x1="865" y1="170" x2="890" y2="170" stroke="black" marker-end="url(#flowarrow)" /><line x1="515" y1="205" x2="515" y2="240" stroke="black" marker-end="url(#flowarrow)" /><line x1="575" y1="273" x2="600" y2="273" stroke="black" marker-end="url(#flowarrow)" /><line x1="720" y1="273" x2="745" y2="273" stroke="black" marker-end="url(#flowarrow)" /><line x1="865" y1="273" x2="890" y2="273" stroke="black" marker-end="url(#flowarrow)" />
</svg>

Providers
---------

This package provides compatibility shims and small, dependency-light
implementations for common provider interfaces. When optional extras are
installed the package will attempt to use real SDK clients; otherwise the
shims provide safe offline-friendly fallbacks suitable for testing.

Recommended entry point:

```py
from modelito import Client
from modelito.messages import Message

client = Client(provider="auto", prefer=["omlx", "ollama"], model="omlx")
response = client.chat([Message(role="user", content="Hello")])
print(response.text)
```

Provided shims and utilities:

- `OpenAIProvider` — hosted OpenAI / SDK-backed provider that can also target
  OpenAI-compatible APIs via `base_url`.
- `OpenAICompatibleHTTPProvider` — shared HTTP base class for local or
  OpenAI-compatible runtimes.
- `RawChatProvider` — protocol for preserving raw OpenAI chat completion
  payloads without collapsing them into text.
- `ClaudeProvider` — will use the official Anthropic SDK when installed,
  falling back to deterministic behavior otherwise.
- `GeminiProvider`, `GrokProvider` — lightweight shims.
- `OMLXProvider` — thin oMLX preset built on `OpenAICompatibleHTTPProvider`.
- `OllamaProvider` — HTTP-aware provider that can call a local Ollama HTTP API
  through stdlib helpers and can fall back to the local Ollama CLI or
  deterministic test behavior when needed. The `modelito[ollama]` extra installs
  optional support dependencies used by the broader Ollama service-management
  helpers.

The client layer recognises the same provider stack through `ChatProvider`,
`MessageInput`, and structured response helpers such as `Client.chat()` and
`Client.chat_json()`.

`OpenAICompatibleHTTPProvider`, `OMLXProvider`, and `OpenAIProvider` also
expose `raw_complete()` and `raw_stream()` for OpenAI-compatible passthrough.
`Client.chat_parsed()` remains the structured JSON convenience path for Python
applications.

For quick diagnostics, use the provider readiness API or CLI:

```py
from modelito import check_provider_ready

status = check_provider_ready("omlx", model="omlx")
print(status.ready, status.reason)
```
The shared message normaliser is exported as `flatten_message_inputs` from
both `modelito` and `modelito.messages` for callers that need OpenAI-style
dict conversion.

```sh
python -m modelito doctor --provider omlx --model omlx
```

Server mode for non-Python clients:

```sh
pip install "modelito[serve]"
modelito-serve --provider omlx --port 11436 --host 127.0.0.1 --strict
```

`--profile` and `--profile-path` are currently treated as profile file paths;
`--profile-path` takes precedence when both are provided.

`modelito-serve` exposes OpenAI-compatible `/v1/models`,
`/v1/chat/completions`, and `/v1/embeddings` endpoints.

Pi integration uses HTTP only. Pi is a TypeScript/Node harness and does not
import Modelito directly; point Pi at the `modelito-serve` base URL via its
OpenAI-compatible custom provider configuration.

Example `~/.pi/agent/models.json` provider entry:

```json
{
  "providers": {
    "modelito": {
      "baseUrl": "http://localhost:11436/v1",
      "api": "openai-completions",
      "apiKey": "modelito",
      "authHeader": false,
      "compat": {
        "supportsDeveloperRole": false,
        "supportsReasoningEffort": false
      },
      "models": [
        {
          "id": "omlx",
          "name": "oMLX via Modelito",
          "reasoning": false,
          "input": ["text"],
          "contextWindow": 8192,
          "maxTokens": 4096,
          "cost": {
            "input": 0,
            "output": 0,
            "cacheRead": 0,
            "cacheWrite": 0
          }
        }
      ]
    }
  }
}
```

Tool-calling workflows require raw passthrough support. Modelito currently
implements that on `OpenAICompatibleHTTPProvider` and the hosted
`OpenAIProvider`; `OMLXProvider` inherits it automatically. `OllamaProvider`
raw passthrough is deferred. For tool-calling integrations today, prefer
oMLX/OpenAI-compatible raw providers or hosted OpenAI.

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

This repository includes a consolidated GitHub Actions workflow at
`.github/workflows/ci.yml`. It runs linting/type checks and unit tests for pull
requests and pushes to `main`, and builds docs on non-PR runs.

Release publishing uses PyPI trusted publishing through
`.github/workflows/publish.yml`. The PyPI project must have a matching trusted
publisher configured for repository `krahd/modelito`, workflow `publish.yml`,
and environment `pypi`. The workflow also checks that the tag version matches
`pyproject.toml` before building or publishing.

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

`modelito` exposes a minimal structural `Provider` Protocol for the legacy
synchronous surface, but the recommended application entry point is `Client`
and its richer chat API. The Protocol is intentionally small to remain
compatible with existing duck-typed providers — it requires only:

- `list_models()` -> `list[str]`
- `summarize(messages, settings=None)` -> `str`

All built-in providers shipped with the package (`OpenAIProvider`,
`ClaudeProvider`, `GeminiProvider`, `OMLXProvider`, `OllamaProvider`, `GrokProvider`) satisfy
the `Provider` protocol structurally. The `Provider` Protocol is decorated with
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

`modelito` exposes `Message` and `Response` dataclasses; client and provider
helpers accept `Message`, plain strings, and OpenAI-style dict inputs.

### Using bare Provider (recommended for most cases)

```py
from modelito import Provider, Message, OllamaProvider

# Create a provider
provider: Provider = OllamaProvider()

# Single request
resp = provider.summarize([Message(role="user", content="hello")])
print(resp)

# Streaming
for chunk in provider.stream([Message(role="user", content="tell me a story")]):
    print(chunk, end="", flush=True)
```

Use a bare Provider when:
- You manage conversation state yourself
- You're doing single-shot or stateless inference
- You need minimal abstraction
- You're building a custom application architecture

### Using OllamaConnector (for conversation management)

```py
from modelito import Message, OllamaConnector, OllamaProvider

# Create a connector
conn = OllamaConnector(provider=OllamaProvider())

# Multi-turn conversation (state is tracked automatically)
res = conn.complete(
    conv_id="chat_session_1", 
    new_messages=[Message(role="user", content="what's 2+2?")]
)
print(res.text)

# Second turn (history is remembered)
res = conn.complete(
    conv_id="chat_session_1", 
    new_messages=[Message(role="user", content="and 3+3?")]
)
print(res.text)
```

Use OllamaConnector when:
- You need automatic conversation history tracking
- You're building a multi-turn chatbot
- You want to manage per-conversation state without writing it yourself

For more details, see [ARCHITECTURE.md](docs/ARCHITECTURE.md)

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

Notes on additional modules
---------------------------

Modelito includes internal/helper modules such as local model management,
API key helpers, mock providers, cache helpers, and batching utilities.
These modules are not currently presented as stable top-level package exports
in this README. Prefer the documented `Client`, provider adapters, connector,
and server entrypoints for application integrations.

See the `tests/` directory for comprehensive coverage and usage examples.
