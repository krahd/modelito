# modelito – Project Status

Last updated: 2026-08-25 06:39

## Project purpose

Modelito is a compact, dependency-light Python library for provider-agnostic
LLM access. It supports hosted and local providers, OpenAI-compatible serving,
streaming and structured responses, embeddings, readiness probes,
token/timeout helpers, Ollama administration, and deterministic/offline-friendly
test fallbacks.

## Current state

- Package metadata version: `1.4.6`.
- Python: 3.10–3.12.
- Licence: MIT.
- Hosted providers include OpenAI, Anthropic/Claude, Gemini, and Grok.
- Local providers include Ollama, BaseRT, vllm-mlx, oMLX, and generic
  OpenAI-compatible HTTP servers.
- `modelito-serve` exposes OpenAI-compatible models, chat-completions, and
  embeddings endpoints.
- `modelito-doctor` and `check_provider_ready()` provide read-only provider
  diagnostics.
- `modelito-benchmark-local` measures conversational latency for already-running
  OpenAI-compatible local runtimes.
- Raw OpenAI chat-completions passthrough is supported by raw-capable providers
  for tool-calling and metadata-preserving integrations.
- Ollama helpers cover installation detection, local service control, model
  lifecycle/readiness, download, preload, and diagnostics while keeping
  mutating operations explicit.
- `RecordingProvider` / `ReplayProvider` provide JSONL cassette recording and
  deterministic replay.

## Local runtime policy

The explicit local-only surface is separate from the established
`Client(provider="auto")` contract:

- `portable`: Ollama as the common macOS/Linux/Windows path;
- `mac-performance`: on Apple Silicon, BaseRT → vllm-mlx → oMLX → Ollama;
- `auto`: `mac-performance` on Apple Silicon and `portable` elsewhere;
- `MODELITO_LOCAL_PROFILE` environment configuration;
- `select_local_runtime()` for read-only selection and diagnostics;
- `local_client()` for a strict local-only client with no hosted or
  deterministic fallback;
- provider-specific model, endpoint, and API-key mappings;
- explicit `prefer=` ordering so benchmark results can override defaults;
- `local_runtime_capabilities()` for conservative runtime-family capability
  metadata.

The candidate order is a deployment starting point, not a universal performance
claim. Modelito does not encode a claim that any one local runtime is fastest
for every model or workload.

## Supported local runtime roles

### Ollama

The portable path. Current Apple-Silicon releases can use MLX and cache/snapshot
optimisations, while later 2026 releases also use llama.cpp paths to broaden
model and hardware support.

### BaseRT

An Apple-Silicon native-Metal runtime exposed through an OpenAI-compatible
server. Modelito integrates only through the local HTTP API.

### vllm-mlx

An Apple-Silicon MLX server with OpenAI-compatible serving, caching/batching,
structured-output and cancellation capabilities in current upstream releases.

### oMLX

An MLX-native server oriented towards persistent conversational/agent
workloads, including continuous batching and tiered prefix/KV caching.

### Generic OpenAI-compatible

The existing `OpenAICompatibleHTTPProvider` remains the escape hatch for
llama.cpp, LM Studio, vLLM, MLX-LM's HTTP server, and other compatible
endpoints. Arbitrary endpoints are not auto-selected.

### MLX-LM reference

Raw MLX-LM remains a benchmark/reference path rather than another automatic
runtime provider. Its prompt caching is useful for repeated conversational
contexts. The benchmark CLI recognises `mlx-lm` as a label for comparisons.

## Conversational benchmark

`modelito-benchmark-local` records:

- first-request TTFT;
- first phrase-like streamed latency;
- estimated decode tokens/s;
- warm-prefix TTFT over repeated requests;
- context-growth TTFT;
- client stream-close latency and a post-cancellation probe;
- optional sampled server process RSS.

The benchmark embeds its own caveats. First-request TTFT is only a cold-model
measurement when the server/model was actually cold. Token rate uses Modelito's
token-count helper, client stream-close time does not prove server-side
cancellation acknowledgement, and process RSS can under-report Metal/unified
memory on macOS.

This benchmark is intended to compare equivalent workloads on the target
machine. It does not replace runtime-specific instrumentation such as
vllm-mlx's `bench-serve` command.

## Architecture overview

The primary application surface is `modelito.Client`, backed by registered
provider adapters. Providers implement a small common interface and may expose
richer raw/streaming capabilities when available. The local-runtime selector is
policy layered above those providers rather than another provider protocol.

### Architecture diagram

<svg xmlns="http://www.w3.org/2000/svg" width="1040" height="390" viewBox="0 0 1040 390" role="img" aria-labelledby="modelito-arch-title modelito-arch-desc">
  <title id="modelito-arch-title">modelito current architecture</title>
  <desc id="modelito-arch-desc">Applications use Client or modelito-serve. Explicit local deployment may pass through the local runtime selector, which probes BaseRT, vllm-mlx, oMLX, or Ollama before constructing a strict provider. Hosted and generic providers remain available through the normal registry.</desc>
  <defs><marker id="archarrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0 L10 5 L0 10 z" /></marker></defs>
  <rect x="25" y="145" width="145" height="80" rx="10" fill="none" stroke="black"/><text x="97" y="178" text-anchor="middle" font-size="14">Applications</text><text x="97" y="199" text-anchor="middle" font-size="12">Client / HTTP callers</text>
  <rect x="205" y="55" width="170" height="80" rx="10" fill="none" stroke="black"/><text x="290" y="88" text-anchor="middle" font-size="14">modelito-serve</text><text x="290" y="109" text-anchor="middle" font-size="12">OpenAI-compatible API</text>
  <rect x="205" y="235" width="170" height="80" rx="10" fill="none" stroke="black"/><text x="290" y="268" text-anchor="middle" font-size="14">local runtime policy</text><text x="290" y="289" text-anchor="middle" font-size="12">select / probe / prefer</text>
  <rect x="420" y="55" width="180" height="80" rx="10" fill="none" stroke="black"/><text x="510" y="88" text-anchor="middle" font-size="14">Provider registry</text><text x="510" y="109" text-anchor="middle" font-size="12">hosted + generic</text>
  <rect x="420" y="235" width="180" height="80" rx="10" fill="none" stroke="black"/><text x="510" y="268" text-anchor="middle" font-size="14">Shared readiness probes</text><text x="510" y="289" text-anchor="middle" font-size="12">actual model availability</text>
  <rect x="645" y="35" width="170" height="100" rx="10" fill="none" stroke="black"/><text x="730" y="68" text-anchor="middle" font-size="14">Hosted providers</text><text x="730" y="90" text-anchor="middle" font-size="12">OpenAI / Claude</text><text x="730" y="109" text-anchor="middle" font-size="12">Gemini / Grok</text>
  <rect x="645" y="220" width="170" height="110" rx="10" fill="none" stroke="black"/><text x="730" y="252" text-anchor="middle" font-size="14">Strict local providers</text><text x="730" y="274" text-anchor="middle" font-size="12">BaseRT / vllm-mlx</text><text x="730" y="293" text-anchor="middle" font-size="12">oMLX / Ollama</text><text x="730" y="312" text-anchor="middle" font-size="12">OpenAI-compatible</text>
  <rect x="860" y="130" width="150" height="110" rx="10" fill="none" stroke="black"/><text x="935" y="164" text-anchor="middle" font-size="14">Common surfaces</text><text x="935" y="186" text-anchor="middle" font-size="12">chat / stream / raw</text><text x="935" y="205" text-anchor="middle" font-size="12">structured / embed</text>
  <line x1="170" y1="170" x2="205" y2="105" stroke="black" marker-end="url(#archarrow)"/><line x1="170" y1="200" x2="205" y2="270" stroke="black" marker-end="url(#archarrow)"/><line x1="375" y1="95" x2="420" y2="95" stroke="black" marker-end="url(#archarrow)"/><line x1="375" y1="275" x2="420" y2="275" stroke="black" marker-end="url(#archarrow)"/><line x1="600" y1="95" x2="645" y2="85" stroke="black" marker-end="url(#archarrow)"/><line x1="600" y1="275" x2="645" y2="275" stroke="black" marker-end="url(#archarrow)"/><line x1="815" y1="85" x2="860" y2="165" stroke="black" marker-end="url(#archarrow)"/><line x1="815" y1="275" x2="860" y2="210" stroke="black" marker-end="url(#archarrow)"/>
</svg>

### Local request flow

<svg xmlns="http://www.w3.org/2000/svg" width="1040" height="250" viewBox="0 0 1040 250" role="img" aria-labelledby="local-flow-title local-flow-desc">
  <title id="local-flow-title">strict local runtime request flow</title>
  <desc id="local-flow-desc">Local intent resolves a profile, orders candidates, probes model availability, selects a concrete model, constructs a strict provider, and then uses the normal Client API. If no candidate is usable, selection raises explicitly.</desc>
  <defs><marker id="flowarrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0 L10 5 L0 10 z" /></marker></defs>
  <rect x="20" y="85" width="125" height="65" rx="10" fill="none" stroke="black"/><text x="82" y="113" text-anchor="middle" font-size="12">local intent</text><text x="82" y="132" text-anchor="middle" font-size="12">profile + model</text>
  <rect x="170" y="85" width="125" height="65" rx="10" fill="none" stroke="black"/><text x="232" y="113" text-anchor="middle" font-size="12">ordered</text><text x="232" y="132" text-anchor="middle" font-size="12">candidates</text>
  <rect x="320" y="85" width="125" height="65" rx="10" fill="none" stroke="black"/><text x="382" y="113" text-anchor="middle" font-size="12">readiness +</text><text x="382" y="132" text-anchor="middle" font-size="12">model discovery</text>
  <rect x="470" y="85" width="125" height="65" rx="10" fill="none" stroke="black"/><text x="532" y="113" text-anchor="middle" font-size="12">resolved local</text><text x="532" y="132" text-anchor="middle" font-size="12">provider/model</text>
  <rect x="620" y="85" width="125" height="65" rx="10" fill="none" stroke="black"/><text x="682" y="113" text-anchor="middle" font-size="12">strict provider</text><text x="682" y="132" text-anchor="middle" font-size="12">no shim fallback</text>
  <rect x="770" y="85" width="125" height="65" rx="10" fill="none" stroke="black"/><text x="832" y="113" text-anchor="middle" font-size="12">normal Client</text><text x="832" y="132" text-anchor="middle" font-size="12">API</text>
  <rect x="470" y="180" width="275" height="45" rx="10" fill="none" stroke="black"/><text x="607" y="208" text-anchor="middle" font-size="12">no usable candidate → explicit selection error</text>
  <line x1="145" y1="117" x2="170" y2="117" stroke="black" marker-end="url(#flowarrow)"/><line x1="295" y1="117" x2="320" y2="117" stroke="black" marker-end="url(#flowarrow)"/><line x1="445" y1="117" x2="470" y2="117" stroke="black" marker-end="url(#flowarrow)"/><line x1="595" y1="117" x2="620" y2="117" stroke="black" marker-end="url(#flowarrow)"/><line x1="745" y1="117" x2="770" y2="117" stroke="black" marker-end="url(#flowarrow)"/><line x1="382" y1="150" x2="520" y2="180" stroke="black" marker-end="url(#flowarrow)"/>
</svg>

## Setup and verification

Development installation:

```bash
python -m pip install -e '.[dev]'
```

Typical checks:

```bash
python scripts/check_no_legacy_dicts.py
ruff check .
black --check .
mypy modelito --ignore-missing-imports
pytest -q --ignore=tests/integration tests
python -m build
```

Local runtime policy, benchmark usage, capability caveats, and upstream sources
are documented in `docs/LOCAL-RUNTIMES.md`.

## Current validation

- Full non-integration suite: 397 tests passed and 1 skipped on 2026-08-25.
- Focused Ollama/client regression suite: 68 tests passed on 2026-08-25.
- The available pytest configuration emits one warning because the installed
  pytest does not recognise `asyncio_default_fixture_loop_scope`.
- Ruff and mypy were not available in the current development environment, so
  lint and type checks could not be run.
- `python3 -m compileall -q modelito` passed. Black could not start because its
  installed version imports a removed private symbol from the installed Click.
- The package build was not run for the current Ollama settings change.

## Recent changes

- Ollama native `/api/chat` and `/api/generate` requests now preserve message
  roles, explicitly select synchronous or streaming responses, place known
  generation settings in the native `options` object, and use separate
  documentation-based allowlists for each endpoint's top-level controls.
  Undocumented and unknown flat settings are not guessed; `settings["options"]`
  remains the explicit escape hatch.
- Ollama strict enforcement now lives in the base provider as well as the
  package/registry compatibility export. `strict=True` summary and streaming
  requests use direct HTTP and never fall back to CLI or deterministic output;
  `strict=False` retains the resilient fallback chain.
- Added explicit `portable`, `mac-performance`, and `auto` local-runtime
  profiles without altering the established `Client(provider="auto")` contract.
- Added BaseRT and vllm-mlx OpenAI-compatible provider presets alongside oMLX
  and Ollama.
- Added provider-specific model/endpoint/key mappings, readiness-based model
  resolution, benchmark-overridable `prefer=` ordering, and conservative
  capability metadata.
- Added `modelito-benchmark-local` for first-turn, warm-prefix, context-growth,
  decode, cancellation-close, and approximate RSS measurements.
- Added a strict-aware Ollama surface so local-only clients propagate runtime
  failures instead of returning deterministic fallback text; the package-root
  export now uses the same class as the provider registry.
- Explicitly configured the historical Ruff lint contract after Ruff 0.16
  expanded its unconfigured default rule set. This prevents an unpinned tool
  update from silently redefining repository lint policy.
- Restored repository-wide pending work and inline current-state diagrams in
  this status snapshot.

## Current decisions

1. Do not encode a universal local-runtime performance ranking.
2. Keep Ollama as the portable path.
3. Keep a Mac-oriented path because Apple-Silicon-specific runtimes expose
   materially different caching, serving, and execution strategies.
4. Preserve existing `Client(provider="auto")` behaviour.
5. A local-only client must fail explicitly when no requested local backend or
   model is ready.
6. Provider-specific model identifiers and endpoints must be expressible
   independently.
7. Local runtime defaults remain benchmark-overridable with `prefer=`.
8. Capability metadata is conservative: `conditional` and `unknown` are used
   instead of guessing model- or version-specific support.
9. Speech/VAD/TTS/ASR orchestration does not belong in Modelito's LLM runtime
   abstraction.
10. No release, tag, or version bump is part of this work.

## Pending tasks

These repository-wide tasks remain open and are not superseded by the local
runtime work:

- `ClaudeProvider` still has no `raw_complete()` / `raw_stream()` surface, so it
  cannot serve as a Pi tool-calling backend through the Modelito HTTP server.
  Anthropic tool-call response translation requires a dedicated follow-up.
- `GeminiProvider` and `GrokProvider` still have no `chat()` implementation;
  they remain lower-priority compatibility shims.

## Remaining empirical work

The repository now contains the benchmark needed for workload-specific local
selection, but a real Apple-Silicon performance ranking must be measured on the
actual target machine with comparable model families, quantisations, runtime
configuration, and cache state. GitHub-hosted Linux CI cannot provide that
evidence.

Until those measurements exist, `mac-performance` is intentionally a curated
candidate order with an explicit `prefer=` override rather than an empirical
winner table.

## Next steps

1. Keep the current CI green and resolve all PR review findings before merging
   the local-runtime work.
2. Run the conversational benchmark on the target Apple-Silicon machine with
   equivalent models/configurations and record results separately from runtime
   marketing benchmarks.
3. Keep reviewing provider additions against the portable-common-surface rule.
4. Continue monitoring Ollama raw passthrough behaviour and keep docs/tests
   aligned with OpenAI-compatible payload expectations.
5. Address Claude raw passthrough and Gemini/Grok chat surfaces in dedicated,
   bounded follow-ups rather than expanding the local-runtime PR.

## Longer-term steps

1. Maintain a small stable provider protocol surface.
2. Keep hosted SDK dependencies optional.
3. Expand provider-specific helpers only when they are clearly useful and
   well-contained.

## Risks and constraints

- Local backend performance and model support change quickly upstream.
- Model identifiers and formats differ between runtimes.
- BaseRT, vllm-mlx, and oMLX are Apple-Silicon-oriented; hosted Linux CI can
  validate adapters and policy but not their native execution.
- Readiness probes establish availability, not latency, quality, memory
  pressure, cache effectiveness, or thermal behaviour.
- Capability metadata can become stale and should be reviewed when upstream
  runtime behaviour materially changes.
- Deterministic fallbacks remain useful for tests but are inappropriate for the
  strict local-only runtime path.

## Standing rationale

- API key storage should not move into a built-in encrypted database in the core
  package.
- Cloud-provider integrations should remain lightweight shims by default.
- The core value of the package is provider-agnostic normalisation, optional
  local tooling, and dependency-light embeddability.
- CI intentionally excludes integration tests by path/flags to keep default
  hosted CI fast and safe.

Last updated: 2026-08-25 06:39
