# modelito – Project Status

Last updated: 2026-05-19 01:32

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
- shared readiness probes in `modelito/probes.py`, with `modelito-doctor` as a console script and `flatten_message_inputs` exported from the package root for convenience
- comprehensive docs under `docs/` including architecture, usage, API reference, install guide, and local server integration
- concise release checklist documentation in `docs/RELEASE.md`
- pytest, ruff, mypy, build, twine, CI, and publishing workflows

Release `v1.4.3` was tagged in git and published to PyPI after the local OpenAI-compatible server support landed in `v1.4.2`.

## Active focus

Phase 4 server-contract hardening and provider cleanup pass complete:

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
19. Latest review-feedback fixes made fallback streaming lazy, scoped warning headers to tool fallbacks, shared readiness probes between client and doctor, and cleaned up package exports.

- `modelito-serve` exposes `/v1/models`, `/v1/chat/completions`, and `/v1/embeddings` for Pi and other OpenAI-compatible consumers.
- Pi/tool-calling should use raw-capable OpenAI-compatible providers such as `OMLXProvider` or hosted `OpenAIProvider`; Ollama raw passthrough remains explicitly deferred.
- Validation status is recorded in the current session snapshot under Recent changes.

## Architecture overview

modelito exposes a small common provider protocol, concrete adapters, connectors, and helper modules. Optional provider SDKs are used when installed; otherwise providers fall back to deterministic behaviour. Detailed architecture policy lives in `docs/ARCHITECTURE.md`. The SVGs below are intentionally compact and current-state oriented. Ollama service and API helpers provide local-model administration while remaining explicitly gated for integration tests.

### Architecture diagram

<svg xmlns="http://www.w3.org/2000/svg" width="1040" height="500" viewBox="0 0 1040 500" role="img" aria-labelledby="modelito-arch-title modelito-arch-desc">
  <title id="modelito-arch-title">modelito architecture</title>
  <desc id="modelito-arch-desc">Core protocols connect clients, Pi and OpenAI-compatible callers, modelito-serve, provider adapters, shared probes, model metadata helpers, and package documentation/tests.</desc>
  <defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0 L10 5 L0 10 z" /></marker></defs>
  <rect x="30" y="185" width="145" height="85" rx="10" fill="none" stroke="black" /><text x="102" y="218" text-anchor="middle" font-size="14">Pi / OpenAI</text><text x="102" y="240" text-anchor="middle" font-size="12">compatible clients</text>
  <rect x="200" y="55" width="165" height="85" rx="10" fill="none" stroke="black" /><text x="282" y="88" text-anchor="middle" font-size="14">modelito-serve</text><text x="282" y="110" text-anchor="middle" font-size="12">/v1/models</text><text x="282" y="128" text-anchor="middle" font-size="12">/v1/chat/completions</text>
  <rect x="200" y="190" width="165" height="85" rx="10" fill="none" stroke="black" /><text x="282" y="223" text-anchor="middle" font-size="14">Client</text><text x="282" y="245" text-anchor="middle" font-size="12">chat / json / parsed</text><text x="282" y="263" text-anchor="middle" font-size="12">package-root exports</text>
  <rect x="400" y="55" width="170" height="85" rx="10" fill="none" stroke="black" /><text x="485" y="88" text-anchor="middle" font-size="14">Raw-capable path</text><text x="485" y="110" text-anchor="middle" font-size="12">RawChatProvider,</text><text x="485" y="128" text-anchor="middle" font-size="12">OpenAICompat, OMLX, OpenAI</text>
  <rect x="400" y="190" width="170" height="85" rx="10" fill="none" stroke="black" /><text x="485" y="223" text-anchor="middle" font-size="14">Fallback path</text><text x="485" y="245" text-anchor="middle" font-size="12">summarize / stream</text><text x="485" y="263" text-anchor="middle" font-size="12">Response / dict output</text>
  <rect x="600" y="40" width="180" height="95" rx="10" fill="none" stroke="black" /><text x="690" y="74" text-anchor="middle" font-size="14">Hosted adapters</text><text x="690" y="96" text-anchor="middle" font-size="12">OpenAI, Claude,</text><text x="690" y="114" text-anchor="middle" font-size="12">Gemini, Grok</text>
  <rect x="600" y="155" width="180" height="95" rx="10" fill="none" stroke="black" /><text x="690" y="189" text-anchor="middle" font-size="14">Shared probes</text><text x="690" y="211" text-anchor="middle" font-size="12">modelito/probes.py</text><text x="690" y="229" text-anchor="middle" font-size="12">modelito-doctor</text>
  <rect x="600" y="270" width="180" height="95" rx="10" fill="none" stroke="black" /><text x="690" y="304" text-anchor="middle" font-size="14">Local Ollama</text><text x="690" y="326" text-anchor="middle" font-size="12">provider and admin</text><text x="690" y="344" text-anchor="middle" font-size="12">raw passthrough deferred</text>
  <rect x="815" y="40" width="180" height="95" rx="10" fill="none" stroke="black" /><text x="905" y="74" text-anchor="middle" font-size="14">Metadata helpers</text><text x="905" y="96" text-anchor="middle" font-size="12">ModelMetadata,</text><text x="905" y="114" text-anchor="middle" font-size="12">get_model_info, infer</text>
  <rect x="815" y="270" width="180" height="95" rx="10" fill="none" stroke="black" /><text x="905" y="304" text-anchor="middle" font-size="14">docs and tests</text><text x="905" y="326" text-anchor="middle" font-size="12">CI, build, release</text><text x="905" y="344" text-anchor="middle" font-size="12">current-state snapshot</text>
  <line x1="175" y1="227" x2="200" y2="227" stroke="black" marker-end="url(#arrow)" /><line x1="365" y1="97" x2="400" y2="97" stroke="black" marker-end="url(#arrow)" /><line x1="365" y1="232" x2="400" y2="232" stroke="black" marker-end="url(#arrow)" /><line x1="570" y1="97" x2="600" y2="87" stroke="black" marker-end="url(#arrow)" /><line x1="570" y1="232" x2="600" y2="202" stroke="black" marker-end="url(#arrow)" /><line x1="780" y1="87" x2="815" y2="87" stroke="black" marker-end="url(#arrow)" /><line x1="780" y1="202" x2="815" y2="202" stroke="black" marker-end="url(#arrow)" /><line x1="690" y1="250" x2="690" y2="270" stroke="black" marker-end="url(#arrow)" />
</svg>

### Flow chart

<svg xmlns="http://www.w3.org/2000/svg" width="1040" height="350" viewBox="0 0 1040 350" role="img" aria-labelledby="modelito-flow-title modelito-flow-desc">
  <title id="modelito-flow-title">modelito provider request flow</title>
  <desc id="modelito-flow-desc">Pi or OpenAI-compatible clients call modelito-serve or the Client API, modelito chooses a raw-capable or fallback provider path, shared probes assist detection, and responses are returned as parsed data or text.</desc>
  <defs><marker id="flowarrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0 L10 5 L0 10 z" /></marker></defs>
  <rect x="20" y="135" width="120" height="70" rx="10" fill="none" stroke="black" /><text x="80" y="163" text-anchor="middle" font-size="12">Pi / OpenAI</text><text x="80" y="181" text-anchor="middle" font-size="12">clients</text>
  <rect x="165" y="135" width="120" height="70" rx="10" fill="none" stroke="black" /><text x="225" y="163" text-anchor="middle" font-size="12">modelito-serve</text><text x="225" y="181" text-anchor="middle" font-size="12">/v1/models</text>
  <rect x="310" y="135" width="120" height="70" rx="10" fill="none" stroke="black" /><text x="370" y="163" text-anchor="middle" font-size="12">/chat/completions</text><text x="370" y="181" text-anchor="middle" font-size="12">/embeddings</text>
  <rect x="455" y="135" width="120" height="70" rx="10" fill="none" stroke="black" /><text x="515" y="163" text-anchor="middle" font-size="12">Raw-capable</text><text x="515" y="181" text-anchor="middle" font-size="12">providers</text>
  <rect x="600" y="135" width="120" height="70" rx="10" fill="none" stroke="black" /><text x="660" y="163" text-anchor="middle" font-size="12">RawChatProvider</text><text x="660" y="181" text-anchor="middle" font-size="12">OpenAICompat</text>
  <rect x="745" y="135" width="120" height="70" rx="10" fill="none" stroke="black" /><text x="805" y="163" text-anchor="middle" font-size="12">OMLX / OpenAI</text><text x="805" y="181" text-anchor="middle" font-size="12">raw passthrough</text>
  <rect x="890" y="135" width="120" height="70" rx="10" fill="none" stroke="black" /><text x="950" y="163" text-anchor="middle" font-size="12">Response</text><text x="950" y="181" text-anchor="middle" font-size="12">or parsed dict</text>
  <rect x="455" y="240" width="120" height="65" rx="10" fill="none" stroke="black" /><text x="515" y="267" text-anchor="middle" font-size="12">Fallback path</text><text x="515" y="285" text-anchor="middle" font-size="12">summarize / stream</text>
  <rect x="600" y="240" width="120" height="65" rx="10" fill="none" stroke="black" /><text x="660" y="267" text-anchor="middle" font-size="12">Non-raw</text><text x="660" y="285" text-anchor="middle" font-size="12">Response / text</text>
  <rect x="745" y="240" width="120" height="65" rx="10" fill="none" stroke="black" /><text x="805" y="267" text-anchor="middle" font-size="12">Shared probes</text><text x="805" y="285" text-anchor="middle" font-size="12">modelito-doctor</text>
  <rect x="890" y="240" width="120" height="65" rx="10" fill="none" stroke="black" /><text x="950" y="267" text-anchor="middle" font-size="12">Package root</text><text x="950" y="285" text-anchor="middle" font-size="12">exports</text>
  <line x1="140" y1="170" x2="165" y2="170" stroke="black" marker-end="url(#flowarrow)" /><line x1="285" y1="170" x2="310" y2="170" stroke="black" marker-end="url(#flowarrow)" /><line x1="430" y1="170" x2="455" y2="170" stroke="black" marker-end="url(#flowarrow)" /><line x1="575" y1="170" x2="600" y2="170" stroke="black" marker-end="url(#flowarrow)" /><line x1="720" y1="170" x2="745" y2="170" stroke="black" marker-end="url(#flowarrow)" /><line x1="865" y1="170" x2="890" y2="170" stroke="black" marker-end="url(#flowarrow)" /><line x1="515" y1="205" x2="515" y2="240" stroke="black" marker-end="url(#flowarrow)" /><line x1="575" y1="273" x2="600" y2="273" stroke="black" marker-end="url(#flowarrow)" /><line x1="720" y1="273" x2="745" y2="273" stroke="black" marker-end="url(#flowarrow)" /><line x1="865" y1="273" x2="890" y2="273" stroke="black" marker-end="url(#flowarrow)" />
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

- Latest cleanup pass fixed fallback streaming laziness, provider warning header scope, shared probe reuse, and `flatten_message_inputs` / `modelito-doctor` export surface.
- Added a concise release checklist document and linked it from the README docs index.
- Install-helper Unix test now accepts apt-based Linux install commands as well as script install commands.
- Python 3.10 test compatibility fixed by using `tomli` as fallback for `tomllib` (available from Python 3.11+).
- Model metadata registry was made conservative and typed using a frozen dataclass, stale hardcoded entries were removed/downgraded, and modern model-family inference was added.
- Provider APIs remain the source of truth for model capabilities; static metadata is now explicitly treated as best-effort fallback only.
- Model metadata inference no longer treats every `o...` model name as OpenAI; only `gpt-*` and known OpenAI reasoning prefixes (`o1*`, `o3*`, `o4*`) infer OpenAI.
- Model metadata helpers are now exported from the package root (`ModelMetadata`, `get_model_info`, `get_model_metadata`, `infer_model_metadata`).
- Release checklist now includes explicit trusted publishing requirements, tag/publish commands, and clean-environment install checks.
- Current release line is `1.4.4`.
- Current oMLX stack uses `OpenAICompatibleHTTPProvider` with strict-mode typed error handling.
- Current provider typing includes `ChatProvider`, `MessageInput`, and `OpenAIMessageDict` exports, with `Client` chat-related methods accepting broadened message input types; provider protocols are aligned so `SyncProvider`, `AsyncProvider`, `StreamingProvider`, and `ChatProvider` all accept `Iterable[MessageInput]`.
- `Client.chat_json()` now supports optional stronger schema validation via `strict_schema=True` using dataclass construction or Pydantic-style `model_validate`/`parse_obj` hooks, while preserving lightweight key-presence checks by default.
- Validation completed locally in this session:
  - `python scripts/check_no_legacy_dicts.py` -> clean
  - `ruff check .` -> clean
  - `mypy modelito --ignore-missing-imports` -> clean
  - `pytest -q --ignore=tests/integration tests` -> `257 passed, 1 skipped`
  - `python -c "import modelito; print(modelito.__version__)"` -> `1.4.4`
  - `python -m build` -> succeeded
  - `python -m twine check dist/*` -> passed
- Trusted publishing note: the workflow is configured for PyPI trusted publishing, but PyPI project-side trusted publisher settings must be verified before release, and the release tag must match `pyproject.toml`.
- Historical release narratives are maintained in `CHANGELOG.md`; STATUS.md is kept as a current-state snapshot.

## Pending tasks

- Verify PyPI project-side trusted publisher settings before the next release.
- ClaudeProvider still has no raw_complete()/raw_stream() — it can't serve as a pi tool-calling backend through the modelito HTTP server. Implementing these requires the Anthropic SDK's tool-call response format, which is non-trivial and would need a dedicated follow-up.
- GeminiProvider and GrokProvider have no chat() — same pattern as Claude, lower priority since they're compatibility shims.


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

Last updated: 2026-05-19 01:32
