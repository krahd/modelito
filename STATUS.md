# modelito – Project Status

Last updated: 2026-05-12 12:35

## Project purpose

modelito is a compact, dependency-light Python library that provides provider-agnostic abstractions and connectors for large language model usage. It supports hosted and local providers, lightweight shims, token/timeout helpers, embeddings, streaming normalisation, and Ollama administration utilities.

## Current implementation state

Current package metadata version is `1.2.2` in `pyproject.toml`.

The package provides:

- core provider protocols and dataclasses
- adapters/shims for OpenAI, Anthropic/Claude, Gemini, Grok, and Ollama
- synchronous, asynchronous, streaming, and embedding provider surfaces
- `OllamaConnector` and provider registry helpers
- Ollama install detection, local service helpers, remote catalog metadata, lifecycle/download tracking, and model readiness helpers
- optional SDK-backed behaviour with deterministic fallback support for offline tests/examples
- docs under `docs/`
- pytest, ruff, mypy, build, twine, CI, and publishing workflows

Release `v1.2.2` has been completed and manually published to PyPI after automatic trusted publishing failed with `invalid-publisher`.

## Active focus

Current focus is stabilising the post-`1.2.2` release pipeline, fixing PyPI trusted publishing, keeping release artefacts aligned, preserving a small portable provider surface as optional provider-specific helpers expand, and correcting endpoint routing in the Ollama provider to properly use `/api/chat` for message-based requests.

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

- Fixed `OllamaProvider.summarize()` and `stream()` endpoint routing to use `/api/chat` for structured Message instances and `/api/generate` for prompt-based requests, correcting the contract violation where messages were being sent to the prompt-only `/api/generate` endpoint.
- Updated response field extraction in both methods to properly handle `/api/chat` responses (`message.content`) and `/api/generate` responses (`response` field).
- Package version `1.2.2` was released.
- Ollama administration helpers were expanded to include install detection, richer remote catalog entries, lifecycle/download state tracking, and explicit model readiness confirmation.
- Public exports and docs were updated for the new admin helpers.
- Unit coverage was added for Ollama admin helpers.
- Release-history and docs inconsistencies were cleaned up.
- Automatic PyPI trusted publishing failed with `invalid-publisher`; manual `twine upload` succeeded.

After Ollama endpoint routing fix:

- focused Ollama provider tests: 4 passed
- full `pytest -q`: 109 passed, 3 skipped
- `ruff check .`: not run post-fix
- `mypy modelito --ignore-missing-imports`: not run post-fix
- `python -m build`: not run post-fix
- `python -m twine check dist/*`: not run post-fix

Previously recorded validation for the release/audit pass:

- focused Ollama/admin helper tests: 17 passed
- full `pytest -q`: 96 passed, 3 skipped
- `ruff check .`: passed
- `mypy modelito --ignore-missing-imports`: passed
- `python -m build`: built sdist and wheel successfully
- `python -m twine check dist/*`: passed
- PyPI fresh install verification for `modelito==1.2.2`: succeeded

No tests were run while creating this documentation-only status normalisation.

## Known issues, risks, and limitations

- PyPI trusted publishing is misconfigured for `.github/workflows/publish.yml` and currently requires manual fallback.
- Lifecycle tracking is in-memory only and not suitable for cross-process persistent operation tracking.
- CI intentionally excludes integration tests by path/flags to keep default hosted CI fast and safe.
- Deeper cloud-provider features should remain optional unless they map cleanly across providers.

## Pending tasks

- Fix PyPI trusted publishing for future tag-based releases.
- Consider persistent lifecycle-storage support if downstream tooling needs cross-process tracking.
- Consider optional pluggable key-provider interfaces only if secret-storage demand grows.

## Next steps

1. Fix PyPI trusted publisher configuration for `.github/workflows/publish.yml`.
2. Keep reviewing provider additions against the portable-common-surface rule.
3. Design persistent lifecycle storage only if a concrete downstream need appears.

## Longer-term steps

1. Maintain a small stable provider protocol surface.
2. Keep hosted SDK dependencies optional.
3. Expand provider-specific helpers only when they are clearly useful and well-contained.

## Decisions and rationale

- API key storage should not move into a built-in encrypted database in the core package.
- Cloud-provider integrations should remain lightweight shims by default.
- The core value of the package is provider-agnostic normalisation, optional local tooling, and dependency-light embeddability.

---

Last updated: 2026-05-12 12:35
