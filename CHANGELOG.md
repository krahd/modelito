# Changelog

All notable changes to this project will be documented in this file.

## 0.2.0 - Unreleased

- Export fixes and API consistency (`install_service`, `ensure_ollama_running_verbose`).
- `OllamaProvider` now attempts to use the local Ollama HTTP API when available and falls back to a deterministic shim.
- `OllamaProvider` now attempts to use the local Ollama HTTP API when available and falls back to the Ollama CLI (when present) before using a deterministic shim.
- Add unit tests covering SDK detection for `OpenAIProvider`, `ClaudeProvider`, `GeminiProvider`, and `OllamaProvider`.
- CI workflow updated to run package tests only for more stable runs.
- Documentation and README updated to reflect a production-ready library and optional extras.

## 0.1.0 - Unreleased

- Initial extraction of core helpers: tokenizer, timeout, connector, config, ollama_service
- Add tests, CI, and publish workflow
 
## 0.1.1 - Release

- Add packaging metadata and setuptools discovery in `pyproject.toml`
- Export runtime `__version__` from the package
- Build wheel and sdist artifacts
- Add concise usage docs and install/build instructions
