Examples
========

This folder contains small runnable examples demonstrating the `modelito`
public API. Run them with the repository virtualenv active (or from an
installed package).

Quickstart
----------

- `examples/quickstart.py`: basic usage (token counting, connector + provider).
- `examples/advanced.py`: conversation history, system messages, trimming.
- `examples/ollama_cli.py`: helpers to inspect the local Ollama CLI and models.
 - `examples/openai_example.py`, `examples/claude_example.py`, `examples/gemini_example.py`: per-provider quick examples.
 - `examples/provider_example.py`: demonstrates the `Provider` Protocol, switching providers, and using `OllamaConnector`.

Run an example:

```sh
python examples/advanced.py
```
