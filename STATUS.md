# modelito – Project Status

Last updated: 2026-05-18 23:16

## Project purpose

modelito is a compact, dependency-light Python library that provides provider-agnostic abstractions and connectors for large language model usage. It supports hosted and local providers, lightweight shims, token/timeout helpers, embeddings, streaming normalisation, and Ollama administration utilities.

## Current implementation state

Current package metadata version is `1.4.4` in `pyproject.toml`.

The package provides:

- core provider protocols and dataclasses
- adapters/shims for OpenAI (with local OpenAI-compatible server support), Anthropic/Claude, Gemini, Grok, oMLX, and Ollama
- synchronous, asynchronous, streaming, and embedding provider surfaces
- `OllamaConnector` and provider registry helpers
- Ollama install detection, local service helpers, remote catalog metadata, lifecycle/download tracking, and model readiness helpers
- optional SDK-backed behaviour with deterministic fallback support for offline tests/examples
- provider readiness diagnostics via `check_provider_ready()` and `python -m modelito doctor`
- optional OpenAI-compatible server mode via `modelito-serve` for non-Python clients such as Pi, with bind settings kept separate from provider backend configuration
- raw OpenAI chat-completions passthrough via `RawChatProvider`, `OpenAICompatibleHTTPProvider`, `OMLXProvider`, and `OpenAIProvider`
- comprehensive docs under `docs/` including architecture, usage, API reference, install guide, and local server integration
- pytest, ruff, mypy, build, twine, CI, and publishing workflows

Release `v1.4.3` was tagged in git and published to PyPI after the local OpenAI-compatible server support landed in `v1.4.2`.

## Active focus

Phase 4 server-contract hardening pass complete:

1. `modelito-serve` now keeps bind `host`/`port` separate from provider backend configuration, and its raw streaming path forwards provider generators lazily instead of buffering them.
2. `OpenAIProvider.raw_complete()` and `raw_stream()` are strict in strict mode, and `OpenAIProvider.chat()` now returns `Response` metadata for server use.
3. `OllamaProvider` accepts dict-style `MessageInput` values consistently through the shared flattening helper.
4. Server endpoints now return OpenAI-style error payloads (`{"error": {...}}`) with mapped HTTP status codes for provider, timeout, connection, not-found, bad-response, and bad-request/internal failures.
5. Chat payload validation now rejects missing/malformed `messages` fields while preserving string-message backward compatibility.
6. Tool-gated fallback checks now trigger on both `tools` and `tool_choice` when raw passthrough is unavailable in strict mode.
7. Embeddings input validation rejects unsupported shapes, and embeddings output validation enforces vector count/type correctness while normalizing numeric values to floats.
8. Request parsing now rejects malformed JSON and non-object request bodies for `/v1/chat/completions` and `/v1/embeddings`, returning OpenAI-style 400 payloads.
9. `ModelitoBadResponseError` now maps to 502 (bad upstream/provider response) and is classified as `modelito_bad_response`.
10. Raw-provider non-dict completion payloads are treated as upstream bad responses (`ModelitoBadResponseError`) and return 502 errors.
11. Regression tests now cover lazy raw streaming, runtime config separation (server bind host/port are not forwarded to provider constructors), payload validators, error-shape/status helpers, malformed JSON handling, OpenAI provider raw/chat behavior, and Ollama dict/string message normalization.
12. The legacy dict-style docs checker now ignores tests because dict `MessageInput` compatibility is intentionally tested there, and the README example now uses `Message(...)`.
13. README wording was tightened for Ollama extra semantics and `--profile`/`--profile-path` path handling, and Ollama raw passthrough remains explicitly deferred.
14. Publish workflow now includes a tag/version gate plus explicit trusted-publishing prerequisites and PyPI environment URL metadata.
15. `ChatProvider` — `@runtime_checkable` Protocol in `modelito/provider.py` formalising the `chat()` interface returning `Response`; exported from package root.
16. `MessageInput` type alias (`Union[Message, str, Mapping[str, Any]]`) added to `provider.py` and exported; `Client` method signatures broadened from `Iterable[Message]` to `Iterable[MessageInput]`; `SyncProvider.summarize()` and `AsyncProvider.acomplete()` signatures similarly broadened.
17. Provider readiness diagnostics added through `check_provider_ready()` / `ProviderStatus` and the `python -m modelito doctor` CLI.
18. OpenAI-compatible server support is provided through `modelito.serve`, `modelito-serve`, `RawChatProvider`, raw passthrough on the OpenAI-compatible HTTP base, and the hosted OpenAI provider.

- `modelito-serve` exposes `/v1/models`, `/v1/chat/completions`, and `/v1/embeddings` for Pi and other OpenAI-compatible consumers.
- Validation completed locally in this session: `python scripts/check_no_legacy_dicts.py` -> no literal dict-shaped message examples found in docs/examples; `ruff check .` clean; `mypy modelito --ignore-missing-imports` clean; `pytest -q` -> `231 passed, 2 skipped`.

## Architecture overview

modelito exposes a small common provider protocol, concrete adapters, connectors, and helper modules. Optional provider SDKs are used when installed; otherwise providers fall back to deterministic behaviour. Ollama service and API helpers provide local-model administration while remaining explicitly gated for integration tests.

### Architecture diagram

<svg xmlns="http://www.w3.org/2000/svg" width="1040" height="500" viewBox="0 0 1040 500" role="img" aria-labelledby="modelito-arch-title modelito-arch-desc">
  <title id="modelito-arch-title">modelito architecture</title>
  <desc id="modelito-arch-desc">Core protocols connect clients to provider adapters, streaming and embedding surfaces, Ollama administration helpers, and package documentation/tests.</desc>
  <defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0 L10 5 L0 10 z" /></marker></defs>
  <rect x="40" y="190" width="170" height="75" rx="10" fill="none" stroke="black" /><text x="125" y="220" text-anchor="middle" font-size="14">Applications</text><text x="125" y="242" text-anchor="middle" font-size="12">and examples</text>
  <rect x="280" y="170" width="200" height="105" rx="10" fill="none" stroke="black" /><text x="380" y="205" text-anchor="middle" font-size="14">Core API</text><text x="380" y="228" text-anchor="middle" font-size="12">Provider, Message,</text><text x="380" y="246" text-anchor="middle" font-size="12">Response, registry</text>
  <rect x="560" y="40" width="190" height="80" rx="10" fill="none" stroke="black" /><text x="655" y="72" text-anchor="middle" font-size="14">Hosted adapters</text><text x="655" y="94" text-anchor="middle" font-size="12">OpenAI, Claude,</text><text x="655" y="112" text-anchor="middle" font-size="12">Gemini, Grok</text>
  <rect x="560" y="160" width="190" height="80" rx="10" fill="none" stroke="black" /><text x="655" y="192" text-anchor="middle" font-size="14">Local Ollama</text><text x="655" y="214" text-anchor="middle" font-size="12">provider and API</text>
  <rect x="560" y="280" width="190" height="80" rx="10" fill="none" stroke="black" /><text x="655" y="312" text-anchor="middle" font-size="14">Streaming and</text><text x="655" y="334" text-anchor="middle" font-size="12">embeddings</text>
  <rect x="805" y="150" width="190" height="100" rx="10" fill="none" stroke="black" /><text x="900" y="184" text-anchor="middle" font-size="14">Ollama admin</text><text x="900" y="206" text-anchor="middle" font-size="12">install, lifecycle,</text><text x="900" y="224" text-anchor="middle" font-size="12">catalog, readiness</text>
  <rect x="280" y="365" width="200" height="70" rx="10" fill="none" stroke="black" /><text x="380" y="394" text-anchor="middle" font-size="14">docs and tests</text><text x="380" y="414" text-anchor="middle" font-size="12">CI, build, release</text>
  <line x1="210" y1="227" x2="280" y2="222" stroke="black" marker-end="url(#arrow)" /><line x1="480" y1="195" x2="560" y2="80" stroke="black" marker-end="url(#arrow)" /><line x1="480" y1="220" x2="560" y2="200" stroke="black" marker-end="url(#arrow)" /><line x1="480" y1="250" x2="560" y2="320" stroke="black" marker-end="url(#arrow)" /><line x1="750" y1="200" x2="805" y2="200" stroke="black" marker-end="url(#arrow)" /><line x1="380" y1="275" x2="380" y2="365" stroke="black" marker-end="url(#arrow)" />
</svg>

### Flow chart

<svg xmlns="http://www.w3.org/2000/svg" width="1040" height="350" viewBox="0 0 1040 350" role="img" aria-labelledby="modelito-flow-title modelito-flow-desc">
  <title id="modelito-flow-title">modelito provider request flow</title>
  <desc id="modelito-flow-desc">An application builds messages, selects a provider, modelito normalises the request, calls an SDK/local backend or fallback, then returns normalised text or chunks.</desc>
  <defs><marker id="flowarrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0 L10 5 L0 10 z" /></marker></defs>
  <rect x="30" y="140" width="135" height="65" rx="10" fill="none" stroke="black" /><text x="97" y="168" text-anchor="middle" font-size="12">Build</text><text x="97" y="186" text-anchor="middle" font-size="12">messages</text>
  <rect x="210" y="140" width="135" height="65" rx="10" fill="none" stroke="black" /><text x="277" y="168" text-anchor="middle" font-size="12">Select</text><text x="277" y="186" text-anchor="middle" font-size="12">provider</text>
  <rect x="390" y="140" width="135" height="65" rx="10" fill="none" stroke="black" /><text x="457" y="168" text-anchor="middle" font-size="12">Normalise</text><text x="457" y="186" text-anchor="middle" font-size="12">request</text>
  <rect x="570" y="140" width="135" height="65" rx="10" fill="none" stroke="black" /><text x="637" y="168" text-anchor="middle" font-size="12">Call SDK,</text><text x="637" y="186" text-anchor="middle" font-size="12">Ollama, fallback</text>
  <rect x="750" y="140" width="135" height="65" rx="10" fill="none" stroke="black" /><text x="817" y="168" text-anchor="middle" font-size="12">Normalise</text><text x="817" y="186" text-anchor="middle" font-size="12">response</text>
  <rect x="930" y="140" width="90" height="65" rx="10" fill="none" stroke="black" /><text x="975" y="168" text-anchor="middle" font-size="12">Return</text><text x="975" y="186" text-anchor="middle" font-size="12">text</text>
  <line x1="165" y1="172" x2="210" y2="172" stroke="black" marker-end="url(#flowarrow)" /><line x1="345" y1="172" x2="390" y2="172" stroke="black" marker-end="url(#flowarrow)" /><line x1="525" y1="172" x2="570" y2="172" stroke="black" marker-end="url(#flowarrow)" /><line x1="705" y1="172" x2="750" y2="172" stroke="black" marker-end="url(#flowarrow)" /><line x1="885" y1="172" x2="930" y2="172" stroke="black" marker-end="url(#flowarrow)" />
</svg>

## Setup and run instructions

Install latest release:

```bash
pip install modelito
```

Development setup:

```bash
pip install -e .[dev]
pip install -r dev-requirements.txt
pip install -e .[ollama,tokenization,openai,anthropic]
```

Validation:

```bash
pytest -q
ruff check .
mypy modelito --ignore-missing-imports
python -m build
python -m twine check dist/*
```

## Configuration and environment variables

- `RUN_OLLAMA_INTEGRATION=1`: enables Ollama integration tests.
- `ALLOW_OLLAMA_INSTALL=1`: permits integration tests to attempt Ollama installation.
- `ALLOW_OLLAMA_DOWNLOAD=1`: permits remote model downloads during integration tests.
- `ALLOW_OLLAMA_UPDATE=1`: permits update flows during integration tests.
- Provider SDK/API keys are optional and should be supplied through environment or external secret-management mechanisms.

## Important files and directories

- `modelito/`: package source.
- `tests/`: test suite.
- `docs/`: user and API documentation.
- `examples/`: usage examples.
- `pyproject.toml`: package metadata and build configuration.
- `.github/workflows/ci.yml`: lint/type/test/doc workflow.
- `.github/workflows/integration-ollama.yml`: dedicated self-hosted Ollama integration workflow.
- `.github/workflows/publish.yml`: PyPI publishing workflow.

## Recent changes

- Current release line is `1.4.4`.
- Current oMLX stack uses `OpenAICompatibleHTTPProvider` with strict-mode typed error handling.
- Current provider typing includes `ChatProvider`, `MessageInput`, and `OpenAIMessageDict` exports, with `Client` chat-related methods accepting broadened message input types; provider protocols are aligned so `SyncProvider`, `AsyncProvider`, `StreamingProvider`, and `ChatProvider` all accept `Iterable[MessageInput]`.
- `Client.chat_json()` now supports optional stronger schema validation via `strict_schema=True` using dataclass construction or Pydantic-style `model_validate`/`parse_obj` hooks, while preserving lightweight key-presence checks by default.
- Validation should be confirmed by CI; local development most recently ran targeted `tests/test_serve.py` plus the full `pytest -q` suite, `ruff check .`, `mypy modelito --ignore-missing-imports`, and `python -c "import modelito; print(modelito.__version__)"`.
- Trusted publishing note: the workflow is configured for PyPI trusted publishing, but PyPI project-side trusted publisher settings must be verified before release, and the release tag must match `pyproject.toml`.
- Historical release narratives are maintained in `CHANGELOG.md`; STATUS.md is kept as a current-state snapshot.

## Pending tasks

- Verify PyPI project-side trusted publisher settings before the next release.

## Next steps

1. Verify PyPI project-side trusted publisher settings before the next release.
2. Keep reviewing provider additions against the portable-common-surface rule.
3. Decide whether to add optional Ollama raw passthrough in a later milestone.

## Longer-term steps

1. Maintain a small stable provider protocol surface.
2. Keep hosted SDK dependencies optional.
3. Expand provider-specific helpers only when they are clearly useful and well-contained.


## Decisions and rationale

- API key storage should not move into a built-in encrypted database in the core package.
- Cloud-provider integrations should remain lightweight shims by default.
- The core value of the package is provider-agnostic normalisation, optional local tooling, and dependency-light embeddability.
- Consider persistent lifecycle-storage support if downstream tooling needs cross-process tracking.
- Consider optional pluggable key-provider interfaces only if secret-storage demand grows.
- Deeper cloud-provider features should remain optional unless they map cleanly across providers.
- CI intentionally excludes integration tests by path/flags to keep default hosted CI fast and safe.


---

Last updated: 2026-05-18 23:59
