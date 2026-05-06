About
=====

Modelito is a lightweight Python library that provides provider abstractions,
compatibility shims, and small utilities for interacting with both local and
cloud LLM runtimes (Ollama, OpenAI, Anthropic/Claude, Gemini). The project
is intentionally dependency-light: install optional extras when you need the
real SDKs, otherwise the shims provide deterministic fallbacks suitable for
testing and offline use.

Usage
=====

Quick examples showing how to import and use the public API in `modelito`.

Basic imports
-------------

```py
from modelito import (
    __version__,
    count_tokens,
    OllamaConnector,
    OllamaProvider,
)

print("modelito", __version__)

# token counting
print(count_tokens("Hello world"))

# create a provider instance (compatibility shim)
provider = OllamaProvider()

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

```sh
# Estimate timeout
python -m modelito.timeout_cli --model llama-2-13b --input-tokens 2048

# Write calibration prompts and (optionally) execute against a local Ollama server
python -m modelito.timeout_calibrate --model llama-2-13b --outdir ./calib
python -m modelito.timeout_calibrate --model llama-2-13b --execute
```

