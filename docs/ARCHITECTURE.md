# modelito architecture

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

## Provider implementations

### SDK-vs-HTTP-vs-Shim hierarchy

Each provider follows a fallback chain:

1. **SDK tier:** If the provider's optional extra is installed, use the official SDK (OpenAI, Anthropic, Google, etc.)
2. **HTTP tier (Ollama only):** If the Ollama HTTP API is reachable at the configured host:port, use it for requests.
3. **CLI tier (Ollama only):** If the Ollama CLI is installed, try calling `ollama run` or `ollama generate`.
4. **Deterministic shim:** Return a stub response suitable for testing (concatenate message contents, or return a mock response).

### Per-provider behavior

**OpenAIProvider:**
- SDK: Uses `openai` package (OpenAI or Azure endpoint)
- HTTP: None (would require manually hitting api.openai.com)
- CLI: None
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

**OllamaProvider:**
- SDK: None (Ollama isn't shipped as a Python SDK)
- HTTP: Calls `/api/chat` for Message instances, `/api/generate` for prompt strings
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
    +-- SDK tier (if optional extra installed)
    |   -> Uses openai, anthropic, google-generativeai, etc.
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
