# modelito architecture

Detailed architecture policy lives here. The compact SVGs in [STATUS.md](../STATUS.md) are intentionally current-state snapshots and are reused in the README for repo documentation.

## Design principles

modelito aims to provide a lightweight, deterministic abstraction layer for LLM providers. Key principles:

1. **Minimal core:** The Provider Protocol is small (list_models + summarize) so adapters can be written easily.
2. **Deterministic fallback:** Every provider has an offline-friendly shim, so tests and examples work without network or SDKs.
3. **Optional SDKs:** Hosted provider SDKs (openai, anthropic, google-generativeai, xai-sdk) are opt-in extras. The library works without them.
4. **Unified streaming:** Token/chunk-level streaming is normalized across providers so applications can use one code path.

## Core concepts

### Provider Protocol

A `Provider` (or `SyncProvider`) implements two methods:

```python
class Provider(Protocol):
    def list_models(self) -> List[str]: ...
    def summarize(self, messages: Iterable[Message], settings: Optional[Dict] = None) -> str: ...
```

This Protocol is marked `@runtime_checkable`, so `isinstance(obj, Provider)` works at runtime.

**Extension Protocols:**

- `AsyncProvider`: `async def acomplete(...) -> str`
- `StreamingProvider`: `def stream(...) -> Iterable[str]`
- `EmbeddingProvider`: `def embed(texts: Iterable[str]) -> List[List[float]]`

### Messages and Response

`Message` is a simple dataclass:
```python
@dataclass
class Message:
    role: str          # "user", "assistant", "system", etc.
    content: str       # text payload
```

`Response` normalizes output across providers:
```python
@dataclass
class Response:
    text: str          # completion text
    # Optional fields populated depending on provider
    finish_reason: Optional[str] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    model: Optional[str] = None
    raw: Optional[Dict] = None  # Original SDK response if available
```

### Current runtime surfaces

- `modelito-serve` exposes `/v1/models`, `/v1/chat/completions`, and `/v1/embeddings` for OpenAI-compatible consumers such as Pi.
- `RawChatProvider`, `OpenAICompatibleHTTPProvider`, `OMLXProvider`, and hosted `OpenAIProvider` preserve raw OpenAI-compatible passthrough where tool calls and structured payloads need fidelity.
- `Client.chat()` returns `Response`, while `Client.chat_json()` and `Client.chat_parsed()` provide structured output helpers for parsed dicts and dataclass / Pydantic-style objects.
- `flatten_message_inputs` is exported from the package root for callers that need OpenAI-style dict conversion.
- `ModelMetadata`, `get_model_info()`, `get_model_metadata()`, and `infer_model_metadata()` are exported for best-effort, conservative metadata lookups.
- Shared provider readiness probes live in `modelito/probes.py` and are surfaced via `check_provider_ready()` and `python -m modelito doctor`.
- `OllamaProvider` supports raw passthrough via Ollama's `/v1/chat/completions`; use raw-capable providers when tool-calling and payload fidelity are required.

## Provider implementations

### SDK-vs-HTTP-vs-Shim hierarchy

Each provider follows a fallback chain:

1. **SDK tier:** If the provider's optional extra is installed, use the official SDK (OpenAI, Anthropic, Google, etc.)
2. **HTTP tier (Ollama only):** If the Ollama HTTP API is reachable at the configured host:port, use it for requests.
3. **CLI tier (Ollama only):** If the Ollama CLI is installed, try calling `ollama run` or `ollama generate`.
4. **Deterministic shim:** Return a stub response suitable for testing (concatenate message contents, or return a mock response).

This Ollama fallback chain applies only when `strict=False`. With `strict=True`,
summary and streaming requests use the direct OpenAI-compatible HTTP transport;
transport or provider failures are raised without trying the CLI or shim.

Tool-calling integrations should prefer the raw-capable path only when full request/response fidelity is available. The fallback path remains the correct choice for offline tests and non-raw providers.

### Per-provider behavior

**OpenAIProvider:**
- SDK: Uses `openai` package (OpenAI or Azure endpoint)
- HTTP: None (would require manually hitting api.openai.com)
- CLI: None
- Raw: Preserves OpenAI-compatible request/response payloads for raw passthrough and server use
- Shim: Concatenates messages and returns as plain text

**ClaudeProvider (Anthropic):**
- SDK: Uses `anthropic` package
- HTTP: None
- CLI: None
- Shim: Deterministic concatenation

**GeminiProvider (Google):**
- SDK: Uses `google-generativeai` package
- HTTP: None
- CLI: None
- Shim: Deterministic fallback

**OMLXProvider (oMLX runtimes):**
- SDK: None required
- HTTP: Calls OpenAI-compatible `/v1/models`, `/v1/chat/completions`, and `/v1/embeddings`
- CLI: None
- Raw: Preserves OpenAI-compatible passthrough for Pi / OpenAI-compatible clients
- Shim: Deterministic fallback for offline tests

**OllamaProvider:**
- SDK: None (Ollama isn't shipped as a Python SDK)
- HTTP: Calls `/api/chat` for non-empty normalised messages and `/api/generate` for an empty prompt request
- Settings: Maps generation settings into the native API's `options` object and allowlists documented top-level controls separately for each endpoint
- Strict: Uses direct `/v1/chat/completions` HTTP transport and never falls back to CLI or deterministic output
- CLI: Calls `ollama run` or `ollama generate`
- Shim: Concatenates messages for testing

**GrokProvider:**
- SDK: Uses `xai-sdk` if available
- HTTP: None
- CLI: None
- Shim: Deterministic fallback

### Why the hierarchy?

- **Testing:** Tests run without network or binaries by hitting the shim tier.
- **Resilience:** If an API is down or a CLI isn't installed, the fallback keeps things working (degraded).
- **Flexibility:** Users can choose: bring your own SDK, use a local Ollama, or test offline.
- **Pi / tool-calling:** use raw-capable providers (`OpenAICompatibleHTTPProvider`, `OMLXProvider`, hosted `OpenAIProvider`, or `OllamaProvider`) when full request/response fidelity is required.

## Connectors and higher-level API

### OllamaConnector

`OllamaConnector` is a higher-level wrapper over `OllamaProvider` that adds conversation state management:

```python
from modelito import OllamaConnector, Message

conn = OllamaConnector(provider=provider)

# Conversation state is maintained internally
res = conn.complete(
    conv_id="my_conversation",
    new_messages=[Message(role="user", content="hello")]
)
print(res.text)
```

**When to use OllamaConnector:**
- You need multi-turn conversation tracking (turns are stored and replayed).
- You're building a chatbot with per-conversation history.

**When to use bare Provider:**
- You're implementing a custom conversation manager.
- You need streaming only (OllamaConnector.stream_complete is available but less common).
- You're testing or need minimal abstraction.

## Ollama readiness and lifecycle

### Readiness model

`ensure_model_ready(model_name)` checks if a model is ready for inference:

1. Check if Ollama is installed (`ollama_installed()`)
2. Check if the Ollama service is running (`server_is_up()`)
3. Check if the model is already loaded (`running_model_names()`)
4. If not loaded, download and load it (`download_model_progress()`)
5. Poll readiness via `/api/generate` or CLI

Current diagnostics are shared between the client and `modelito-doctor`, so readiness behaviour stays consistent across the CLI and library APIs.

### Detailed readiness

`ensure_model_ready_detailed(model_name)` returns a `ReadinessResult`:

```python
@dataclass
class ReadinessResult:
    success: bool                      # True if ready for inference
    phase: str                         # "installed" / "running" / "loaded" / "ready"
    message: str                       # Human-readable status
    source: str                        # Where the check ran ("http", "cli", "shim")
    elapsed_seconds: float             # How long the check took
    error: Optional[str] = None        # Error details if success=False
```

This is useful for diagnostics and detailed status reporting.

### Service lifecycle

`OllamaService` helpers manage the Ollama daemon:

```python
from modelito.ollama_service import start_service, stop_service

# Start the service (blocks until ready or timeout)
start_service(host="http://127.0.0.1", port=11434, warmup_timeout=30.0)

# Stop it when done
stop_service()
```

Install detection is platform-aware (prefers `brew` on macOS, `apt` on Linux, `choco` on Windows, with shell script fallback).

## Data flow

```
Application
    |
    v
Provider interface (list_models, summarize, stream)
    |
    +-- Client.chat()/chat_json()/chat_parsed()
    |
    +-- SDK tier (if optional extra installed)
    |   -> Uses openai, anthropic, google-generativeai, etc.
    |
    +-- Raw-capable OpenAI-compatible tier
    |   -> modelito-serve, OpenAICompatibleHTTPProvider, OMLXProvider, OpenAIProvider
    |
    +-- HTTP tier (Ollama only)
    |   -> Calls /api/chat or /api/generate
    |
    +-- CLI tier (Ollama only)
    |   -> Calls 'ollama run' or 'ollama generate'
    |
    +-- Shim tier (always available)
        -> Returns deterministic response for testing
```

## Integration testing

Integration tests for external providers require explicit environment setup:

- `RUN_OLLAMA_INTEGRATION=1`: Enable Ollama-specific tests
- `ALLOW_OLLAMA_INSTALL=1`: Allow tests to install Ollama if missing
- `ALLOW_OLLAMA_DOWNLOAD=1`: Allow tests to download models
- `ALLOW_OLLAMA_UPDATE=1`: Allow tests to update Ollama

This gates side-effectful operations so default CI remains fast and safe.

## Extension

### Provider addition policy

- Implement the smallest portable surface first: `list_models()`, `summarize()`, `stream()` where available, `embed()` where available, and `chat()` returning `Response` where practical.
- Hosted SDK dependencies must remain optional extras.
- Provider-specific helpers should not be added to the core protocol unless they generalise cleanly.
- OpenAI-compatible local runtimes should prefer thin presets over `OpenAICompatibleHTTPProvider`.
- Raw tool-call passthrough should use `RawChatProvider` only when full request/response fidelity can be preserved.
- The hosted OpenAI provider and oMLX runtime are the preferred raw-capable paths for Pi / OpenAI-compatible clients.
- `modelito-serve` should continue to expose only the documented OpenAI-compatible endpoints.
- Modelito should not absorb agent-harness responsibilities.

To add a new provider:

1. Create a class that implements the `Provider` Protocol
2. Implement `list_models()` and `summarize()` at minimum
3. Optionally implement `stream()`, `acomplete()`, or other protocols
4. Add an optional extra to `pyproject.toml` for the provider's SDK (if one exists)
5. Document the SDK-vs-HTTP-vs-shim hierarchy for your provider

Example:

```python
from modelito.provider import Provider
from modelito.messages import Message

class MyProvider:
    def list_models(self) -> List[str]:
        # Query your service
        return ["model-1", "model-2"]
    
    def summarize(self, messages, settings=None) -> str:
        # Call your service and return text
        return "response text"
    
    def stream(self, messages, settings=None):
        # Yield text chunks
        yield "chunk 1"
        yield " chunk 2"
```

Then it's automatically compatible with any code expecting a `Provider`.
