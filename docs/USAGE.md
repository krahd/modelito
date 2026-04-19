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

# create a connector (does not start any external process)
conn = OllamaConnector(host="localhost", port=11434)

# create a provider instance (compatibility shim)
provider = OllamaProvider(connector=conn)
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
