About
=====

Modelito is a lightweight Python library that provides provider abstractions,
compatibility shims, and small utilities for interacting with both local and
cloud and local LLM runtimes (Ollama, OpenAI, Anthropic/Claude, Gemini, oMLX). The project
is intentionally dependency-light: install optional extras when you need the
real SDKs, otherwise the shims provide deterministic fallbacks suitable for
testing and offline use.

Current state: `modelito-serve` exposes `/v1/models`, `/v1/chat/completions`,
and `/v1/embeddings`; raw-capable OpenAI-compatible providers are `OpenAICompatibleHTTPProvider`,
`OMLXProvider`, and hosted `OpenAIProvider`; `OllamaProvider` raw passthrough remains deferred.

Usage
-----

Quick examples showing how to import and use the public API in `modelito`.

Basic imports
-------------

```py
from modelito import (
    __version__,
    count_tokens,
    Embedder,
    OllamaConnector,
    OllamaProvider,
)

print("modelito", __version__)

# token counting
print(count_tokens("Hello world"))

# create a provider instance (compatibility shim)
provider = OllamaProvider()

# create an embeddings-only runtime wrapper
embedder = Embedder(provider="openai")
print(embedder.embed(["hello world"]))

# create a connector (does not start any external process)
conn = OllamaConnector(provider=provider)
```

Installation
-------------

- Install for development: `pip install -e .`
- Build artifacts: `python -m build` (requires `build` package)
- Install from wheel: `pip install dist/modelito-<version>-py3-none-any.whl`

Try the example
---------------

There is a small example script demonstrating the public API at:

[examples/quickstart.py](../examples/quickstart.py)

Run it with:

```sh
python examples/quickstart.py
```

Additional examples demonstrating specific provider shims are included:

- [examples/openai_example.py](../examples/openai_example.py)
- [examples/claude_example.py](../examples/claude_example.py)
- [examples/gemini_example.py](../examples/gemini_example.py)
- [examples/omlx_example.py](../examples/omlx_example.py)

Run any example from the repository root, for example:

```sh
python examples/openai_example.py
```

Timeout estimation and calibration

Modelito includes a small timeout estimator and diagnostic tooling useful for
choosing conservative network/RPC timeouts for remote models. Quick usage:

Ollama CLI helpers
------------------

Modelito provides a small set of helpers for interacting with the local
Ollama CLI and HTTP API. A few implementation details are useful for
callers so they don't reimplement CLI discovery or miss subtle
environment concerns:

- `resolve_ollama_command()` — Return the best available `ollama` CLI
    path or raise `FileNotFoundError`. The helper checks `shutil.which`
    and a short list of common platform locations (macOS app bundle
    paths, Homebrew paths, `/usr/local/bin`, `/usr/bin`, etc.). Prefer
    calling this rather than duplicating the path-fallback logic.

- `run_ollama_command(*args, host=None, env=None)` — Run the resolved
    `ollama` binary, merging the optional `env` mapping into the child
    process environment. The helper ensures the repository root is added
    to `PYTHONPATH` (best-effort) so invocations which spawn Python
    entrypoints (for example `python -m llm.service`) can import the
    package when executed from the helpers.

- `start_detached_ollama_serve(host, start_args=None, env=None)` —
    Start `ollama serve` in the background. Accepts an `env` mapping and
    similarly ensures `PYTHONPATH` contains the repository root for
    subprocesses.

- `start_service(config_path=None)` — Attempts to start `ollama serve`
    using the configured host/port. If no model is configured the helper
    will still start the server and return `0` on success; non-zero
    return codes indicate failures such as a missing CLI, CLI startup
    failure, or a startup timeout.

- `detect_install_method()` and `install_ollama(allow_install=True)` —
    choose and execute a platform-aware install flow. The helper now prefers
    `brew` on macOS, `apt` on Linux when available, and `choco` on Windows,
    falling back to the official Ollama install scripts when needed.

- `list_remote_model_catalog(query=None)` — Return structured remote model
    entries instead of a flat list when callers need stable metadata such as
    `family`, `tag`, and whether the model already exists locally.

- `download_model_progress(model_name)` and
    `get_model_lifecycle_state(model_name)` — Stream or poll structured
    lifecycle state for pull operations keyed by model name.

- `ensure_model_ready(model_name, auto_start=False, allow_download=False)` —
    ensure a specific model is installed, warmed, and responsive instead of
    only checking whether the Ollama server itself is reachable.

- `ensure_model_ready_detailed(model_name, auto_start=False, allow_download=False)` —
    like `ensure_model_ready()` but returns a structured `ReadinessResult` with
    success, phase, message, source, elapsed_seconds, and error details for
    richer diagnostics and UI integration.

Examples
--------

Run a CLI command with a custom environment mapping:

```py
from modelito.ollama_service import run_ollama_command

res = run_ollama_command("--version", env={"EXTRA_VAR": "1"})
print(res.stdout)
```

Start the service (from the repository root) and allow `python -m`
entrypoints to import local modules via the helper's PYTHONPATH handling:

```sh
python -m modelito.ollama_service start --config /path/to/config.json
```

Track a model download and then confirm readiness:

```py
from modelito import download_model_progress, ensure_model_ready

for state in download_model_progress("llama3.1:8b"):
    print(state.phase, state.progress, state.message)

print(ensure_model_ready("llama3.1:8b", auto_start=True, allow_download=False))
```
Check model readiness with detailed result and diagnostics:

```py
from modelito import ensure_model_ready_detailed

result = ensure_model_ready_detailed(\"llama3.1:8b\", auto_start=True, allow_download=False)
if result.success:
    print(f\"Model ready in {result.elapsed_seconds:.2f}s (phase: {result.phase})\")
else:
    print(f\"Failed ({result.phase}): {result.error}\")
    # UI can use result.phase to show: preparing, downloading, warming, error, etc.
```
```sh
# Estimate timeout
python -m modelito.timeout_cli --model llama-2-13b --input-tokens 2048

# Write calibration prompts and (optionally) execute against a local Ollama server
python -m modelito.timeout_calibrate --model llama-2-13b --outdir ./calib
python -m modelito.timeout_calibrate --model llama-2-13b --execute
```

OpenAI-compatible raw passthrough (tool calling)
-------------------------------------------------

The `raw_complete()` and `raw_stream()` methods enable direct OpenAI-compatible
passthrough, preserving tool definitions and function calling metadata. This is
especially useful with `OllamaProvider` when you want to forward structured
tool-calling requests directly to Ollama's `/v1/chat/completions` endpoint.

Example: Ollama with function calling

```python
from modelito import OllamaProvider

provider = OllamaProvider(model="llama2-uncensored:7b")

# Define a tool (function) that the model can call
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The location to get weather for"
                    }
                },
                "required": ["location"]
            }
        }
    }
]

# Raw passthrough preserves tools and tool_choice fields
payload = {
    "model": "llama2-uncensored:7b",
    "messages": [
        {"role": "user", "content": "What is the weather in New York?"}
    ],
    "tools": tools,
    "tool_choice": "auto",  # Let the model decide when to call tools
    "temperature": 0.7
}

# Get the complete response (tool calls preserved)
response = provider.raw_complete(payload)
print(response)

# Or stream the response
for chunk in provider.raw_stream(payload):
    if "choices" in chunk and chunk["choices"]:
        delta = chunk["choices"][0].get("delta", {})
        if "tool_calls" in delta:
            print("Tool call:", delta["tool_calls"])
```

All OpenAI-compatible request fields are preserved: `temperature`, `top_p`,
`max_tokens`, `stop`, `response_format`, etc. The response contains the full
OpenAI-compatible structure with `choices`, `message`, `tool_calls`, and
other metadata intact.

Future adapters: LiteLLM
------------------------

**Note**: LiteLLM support is planned as a future optional adapter (`modelito[litellm]`)
but is not yet implemented. The core `modelito` package maintains `dependencies = []`
to stay lightweight and independent. A LiteLLM adapter, if added, would be distributed
as an optional extra alongside other provider-specific integrations.

Recording and replay
--------------------

`RecordingProvider` and `ReplayProvider` in `modelito.recording` let you
capture real provider calls to a JSONL cassette file and replay them offline
with no network or API key.  They are stdlib-only and require no additional
dependencies.

**Record once, replay many times:**

```py
from modelito import Message
from modelito.mock_provider import MockProvider   # replace with any real provider
from modelito.recording import RecordingProvider, ReplayProvider

# Wrap any provider to record calls
provider = RecordingProvider(
    wrapped=MockProvider(),
    cassette="tests/cassettes/demo.jsonl",
)
result = provider.summarize([Message(role="user", content="hello")])

# Later (or in CI): replay without any network access
replay = ReplayProvider(cassette="tests/cassettes/demo.jsonl")
print(replay.summarize([Message(role="user", content="hello")]))
```

**Supported input forms** — all of the following are accepted by both
`RecordingProvider` and `ReplayProvider`:

```py
provider.summarize("hello")                                      # bare string
provider.summarize(["hello", "world"])                           # list of strings
provider.summarize([Message(role="user", content="hello")])     # Message objects
provider.summarize(iter([Message(role="user", content="hi")]))  # generator
```

Dict-shaped message inputs are also accepted for compatibility, but examples
prefer `Message(...)` dataclasses.

**V1 scope:** `list_models()`, `summarize()`, and `chat()` only.
`stream()` and `embed()` raise `NotImplementedError`.

**Error handling:**

- `CassetteFormatError` — raised on malformed JSONL lines (pass
  `strict_cassette=False` to skip them instead).
- `ReplayMissError` — raised when no cassette record matches a request
  (pass `strict=False` to return an empty response instead).

**Composability** — wrappers stack freely:

```py
from modelito.recording import RecordingProvider, ReplayProvider

outer = RecordingProvider(
    wrapped=ReplayProvider(cassette="base.jsonl"),
    cassette="outer.jsonl",
)
```
