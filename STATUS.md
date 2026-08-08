# modelito – Project Status

Last updated: 2026-08-08 18:04

## Project purpose

modelito is a compact, dependency-light Python library for provider-agnostic LLM access. It supports hosted and local providers, OpenAI-compatible serving, streaming and structured responses, embeddings, readiness probes, token/timeout helpers, Ollama administration, and deterministic/offline-friendly test fallbacks.

## Current state

- Package metadata version: `1.4.6`.
- Python: 3.10–3.12.
- Licence: MIT.
- Hosted providers include OpenAI, Anthropic/Claude, Gemini, and Grok.
- Local providers include Ollama, oMLX, and generic OpenAI-compatible HTTP servers.
- `modelito-serve` exposes OpenAI-compatible models, chat-completions, and embeddings endpoints.
- `modelito-doctor` and `check_provider_ready()` provide read-only provider diagnostics.
- Raw OpenAI chat-completions passthrough is supported by raw-capable providers for tool-calling and metadata-preserving integrations.
- Ollama helpers cover installation detection, local service control, model lifecycle/readiness, download, preload, and diagnostics while keeping mutating operations explicit.
- `RecordingProvider` / `ReplayProvider` provide JSONL cassette recording and deterministic replay.

## Active focus

Branch `feature/local-runtime-profiles` adds explicit local deployment profiles without changing the established `Client(provider="auto")` contract.

The new local-runtime surface provides:

- `portable`: Ollama as the common macOS/Linux/Windows path;
- `mac-performance`: on Apple Silicon, oMLX first with Ollama fallback;
- `auto`: `mac-performance` on Apple Silicon and `portable` elsewhere;
- `MODELITO_LOCAL_PROFILE` environment configuration;
- `select_local_runtime()` for read-only selection and diagnostics;
- `local_client()` for a strict local-only client that never falls back to hosted APIs or deterministic shims;
- provider-specific model mappings so Ollama tags and oMLX/Hugging Face identifiers are not treated as interchangeable;
- explicit `prefer=` ordering so benchmark results can override defaults.

The selection order is a deployment policy, not a universal performance claim. Current Ollama releases use MLX on Apple Silicon and include significant caching/performance work; oMLX provides MLX-native serving with persistent paged KV caching and continuous batching. Representative workloads should therefore be benchmarked on the target machine.

## Architecture

The primary application surface is `modelito.Client`, backed by registered provider adapters. Providers implement a small common interface and may expose richer raw/streaming capabilities when available. Local runtime readiness is separated from provider construction:

1. application declares local deployment intent;
2. local-runtime selector chooses ordered candidate backends;
3. readiness probes check whether the requested provider-specific model is actually available;
4. a strict concrete provider is constructed only after readiness succeeds;
5. callers may continue to use the normal `Client` API.

This keeps local policy outside the provider protocol and preserves existing public APIs.

## Setup

Development installation:

```bash
python -m pip install -e '.[dev]'
```

Optional runtime extras remain separate, for example:

```bash
python -m pip install -e '.[ollama,serve,openai]'
```

Typical checks:

```bash
pytest -q
ruff check .
mypy modelito --ignore-missing-imports
python -m build
python -m twine check dist/*
```

Local runtime examples are documented in `docs/LOCAL-RUNTIMES.md`.

## Configuration

Relevant existing variables include provider credentials/endpoints plus Modelito provider/profile variables. The local-runtime branch adds:

- `MODELITO_LOCAL_PROFILE=auto|portable|mac-performance`

Aliases such as `mac` and `apple-silicon` normalise to `mac-performance`. Applications can bypass the environment and pass `profile=` and `prefer=` directly.

## Important files

- `modelito/client.py`: unified client and existing provider-auto selection.
- `modelito/provider.py`: provider protocols and common types.
- `modelito/provider_registry.py`: provider registration/factory.
- `modelito/local_runtime.py`: explicit local-runtime profiles and strict local selection.
- `modelito/omlx.py`: oMLX/OpenAI-compatible local provider.
- `modelito/ollama.py`: Ollama provider.
- `modelito/probes.py`: shared readiness probes.
- `modelito/serve.py`: OpenAI-compatible server.
- `tests/test_local_runtime.py`: local-profile selection tests.
- `docs/LOCAL-RUNTIMES.md`: local runtime policy, examples, benchmarking guidance, and upstream evidence.
- `AGENTS.md`: repository agent rules.

## Current decisions

1. Do not encode “oMLX is always faster than Ollama”. Both use MLX-capable paths on current Apple Silicon; actual performance is model/workload dependent.
2. Keep a portable Ollama path because it is the broadest cross-platform local backend.
3. Keep a Mac-oriented path because Apple-Silicon-specific runtimes can materially improve latency and memory behaviour.
4. Preserve existing `Client(provider="auto")` behaviour; use a new local-only selector rather than changing established fallback semantics.
5. A local-only client must fail explicitly when no requested local backend/model is ready.
6. Provider-specific model identifiers must be expressible independently.
7. Local runtime defaults remain benchmark-overridable with `prefer=`.
8. No release/tag/version bump is part of the current branch unless explicitly requested.

## Verification

The branch includes unit tests for profile normalisation, platform restrictions, local-only selection, oMLX/Ollama fallback order, provider-specific model identifiers, benchmark-driven ordering overrides, diagnostics, and strict provider construction.

Full repository CI has not yet been run for this branch at the time of this status snapshot. The next step is to open a pull request, run the existing lint/type/test matrix, and correct any failures before considering the branch complete.

## Risks and constraints

- Local backend performance changes quickly upstream; Modelito should not freeze transient benchmark conclusions into API semantics.
- Model availability differs between Ollama and oMLX; a shared string model name may be invalid for one provider.
- Readiness probes establish availability, not conversational latency, output quality, thermal behaviour, or memory pressure.
- CI cannot validate Apple-Silicon runtime performance on GitHub-hosted Linux runners.
- Local integration tests that install or download Ollama models remain explicitly gated.
- Provider deterministic fallbacks are useful for tests but inappropriate for a strict local runtime path; `local_client()` therefore defaults to strict provider behaviour.

## Pending work

1. Open the local-runtime profile pull request.
2. Run lint, mypy, Python-version test matrix, build checks as appropriate, and fix all branch failures.
3. Add a concise README pointer to `docs/LOCAL-RUNTIMES.md` if the PR remains otherwise focused and clean.
4. Benchmark portable Ollama and Mac-oriented oMLX/Ollama paths on representative conversational workloads before changing default ordering.
5. After review, decide whether the new API warrants a minor version bump and release; do not publish automatically.

## Longer-term possibilities

- A benchmark helper that reports TTFT, prompt processing, decode throughput and memory observations without declaring a provider winner.
- Richer local capability metadata if applications need to select by context length, structured output, tool support, or model format.
- Additional local backends only when they offer a real capability not already covered by the generic OpenAI-compatible provider.

Last updated: 2026-08-08 18:04