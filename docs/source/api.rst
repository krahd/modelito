API Reference
=============

This section provides a short overview of the `modelito` public surface and
links into the auto-generated module documentation.

Overview
--------

`modelito` is a small package exposing helpers and compatibility shims for a
variety of LLM providers. The public API includes:

- `count_tokens(text: str) -> int`
- `estimate_remote_timeout(model_name: Optional[str], input_tokens: int = 2048, concurrency: int = 1) -> int`
- `OllamaConnector` and a set of minimal provider shims (`OllamaProvider`,
  `OpenAIProvider`, `ClaudeProvider`, `GeminiProvider`, `GrokProvider`).
- A small collection of `ollama_service` helpers to interact with the Ollama
  CLI and HTTP API.

For full API details see the :mod:`modelito` module and the individual
submodules in the "Modules" page.
