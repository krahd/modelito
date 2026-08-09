# modelito – Project Status

Last updated: 2026-08-09

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

## Architecture

The primary application surface is `modelito.Client`, backed by registered
provider adapters. Providers implement a small common interface and may expose
richer raw/streaming capabilities when available. Local runtime policy remains
outside the provider protocol:

1. application declares local deployment intent;
2. selector chooses ordered candidate backends;
3. readiness probes check whether the requested provider-specific model is
   actually available;
4. a strict concrete provider is constructed only after readiness succeeds;
5. callers continue to use the normal `Client` API.

This preserves existing public APIs while making local deployment explicit.

## Setup and verification

Development installation:

```bash
python -m pip install -e '.[dev]'
```

Typical checks:

```bash
ruff check .
black --check .
mypy modelito --ignore-missing-imports
pytest -q --ignore=tests/integration tests
python -m build
```

Local runtime policy, benchmark usage, capability caveats, and upstream sources
are documented in `docs/LOCAL-RUNTIMES.md`.

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

## Remaining empirical work

The repository now contains the benchmark needed for workload-specific local
selection, but a real Apple-Silicon performance ranking must be measured on the
actual target machine with comparable model families, quantisations, runtime
configuration, and cache state. GitHub-hosted Linux CI cannot provide that
evidence.

Until those measurements exist, `mac-performance` is intentionally a curated
candidate order with an explicit `prefer=` override rather than an empirical
winner table.

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

Last updated: 2026-08-09
