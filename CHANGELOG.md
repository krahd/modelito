# Changelog

All notable changes to this project will be documented in this file.

## 1.0.0 - 2026-04-19

- Major release: break compatibility in favor of a cleaner, modern API.
- Add typed `Message`/`Response` dataclasses and expanded provider Protocols.
- Streaming `stream()` surface implemented for OpenAI, Claude, Gemini, Ollama, and Grok.
- SDK-aware integrations for OpenAI (async/streaming/embed), Claude and Gemini.
- Ollama HTTP streaming implemented with robust fallback behavior.
- Integration tests added (gated by environment variables).
- CI/type/lint updates and general cleanup.

## 0.2.2 - 2026-04-18

- Bump version to 0.2.2.
- All tests passing (24 passed, 1 skipped).

## v0.1.3 - 2026-04-18

- Merge `fix/ollama-compat`: Ollama compatibility improvements (CLI fallback, improved `list_models`).
- Documentation: update `README.md` and `docs/USAGE.md` with clearer overview and quickstart.
- Chore: small post-merge fix to `modelito/ollama.py`.

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
