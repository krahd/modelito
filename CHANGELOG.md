# Changelog

All notable changes to this project will be documented in this file.

## 1.4.2 - 2026-05-12

- Add `base_url` parameter to `OpenAIProvider` for local OpenAI-compatible server support (llama.cpp, vLLM, LM Studio, SGLang).
- Add `docs/local-openai-compatible.md` with configuration examples for each supported local server.
- Update README to clarify OpenAI provider supports local servers and link to new documentation.

## 1.4.1 - 2026-05-12

- Fix: correct Ollama endpoint routing for message-based requests. Route `/api/chat` for Message instances and `/api/generate` for prompt strings. Extract response fields correctly for each endpoint type.
- Audit remediation: reconciled dev dependencies, added provider extras (gemini, grok), tidied root docs, backfilled CHANGELOG for v1.0.7/v1.0.8, cleaned `.venv-test` from history, included httpx in the `ollama` extra, added `ARCHITECTURE.md`, and clarified Provider/Connector usage in README and examples.

## 1.4.0 - 2026-05-06

- Add `ensure_model_ready_detailed()` function with structured `ReadinessResult`
  return type for richer readiness diagnostics (success, phase, message, source,
  elapsed_seconds, error). Async wrapper `async_ensure_model_ready_detailed()`
  also available.
- Make `start_service()` warmup timeout configurable via `warmup_timeout`
  parameter (default: 30.0 seconds) and CLI `--warmup-timeout` argument.
- Document platform-specific installer policies in API reference: macOS prefers
  `brew`, Linux prefers `apt`, Windows prefers `choco`, with script-based fallbacks.
- Refactor `ensure_model_ready()` to delegate to `ensure_model_ready_detailed()`
  internally for code reuse and consistency.

## 1.3.0 - 2026-05-06

- Add first-class embedder runtime API with `Embedder` wrapper, embedder
  registry lookups, and `available_embedders()` client method.
- Add provider-agnostic transport/retry/error plumbing with normalized
  response envelopes, network error handling, and exponential backoff.
- Extend Ollama API surface with envelope-wrapped operation helpers for
  health checks, readiness probes, model listing, and lifecycle operations.
- Improve Ollama service diagnostics surface with progress-tracked model
  downloads and structured model lifecycle state polling.
- Normalize and validate all markdown and diagnostics for docs, README,
  release notes, and API reference.
- Update STATUS.md with visual architecture and flow diagrams.

## 1.2.2 - 2026-05-06

- Add a broader Ollama administration surface for local model operations.
- Add platform-aware install backend detection with `brew`, `apt`, and
  `choco` support plus script fallback.
- Add structured remote catalog, download lifecycle tracking, and explicit
  model readiness helpers for Ollama.
- Export and document the new Ollama admin helpers across the package root,
  API docs, install docs, and usage docs.
- Add focused unit coverage for the new Ollama administration helpers.
- Set `asyncio_default_fixture_loop_scope = function` in `pytest.ini` to
  remove the local `pytest-asyncio` deprecation warning.

## 1.2.1 - 2026-05-06

- Fix package version fallback to avoid stale runtime version reporting when
  metadata is unavailable.
- Export `estimate_remote_timeout_details` in package exports and align API
  documentation with implementation.
- Fix `OllamaConnector` usage examples in docs to reflect current constructor
  signature.
- Fix mypy typing issue in `modelito/normalization.py`.
- Normalize changelog/release documentation and mark historical v1.0.3 release
  docs as archived records.
- Update project status reporting with comprehensive audit remediation results.

## 1.2.0 - 2026-05-06

- Current package metadata version in `pyproject.toml`.
- Runtime and docs consistency audit completed; release history normalization
  initiated for maintainability.

## 1.0.8 - 2026-04-22

- Stability and compatibility fixes for Ollama provider.
- Integration test improvements and edge-case handling.

## 1.0.7 - 2026-04-21

- Provider protocol refinements and documentation improvements.
- Enhanced streaming support across providers.

## 1.0.6 - 2026-04-21

- Fix: resolve stray git-merge conflict markers that caused import-time
  `SyntaxError`s.
- Fix: restore `estimate_remote_timeout` behavior and include
  `matched_model_override` in diagnostic details.
- Docs: document the `with_source` argument and diagnostic tuple behavior.

## 1.0.5 - 2026-04-21

- Version bump and release notes placeholder.

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

## Notes

- Historical entries between `1.0.6` and `1.2.0` are being backfilled from
  release records as available.
