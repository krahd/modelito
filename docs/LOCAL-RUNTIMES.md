# Local runtime profiles

Modelito separates local deployment policy from provider APIs. The selector
answers a narrow question: given an application's deployment intent, which
already-running local backend and model are ready to use?

The profiles are deliberately not performance rankings:

- **portable**: use Ollama as the common macOS/Linux/Windows path;
- **mac-performance**: on Apple Silicon, try BaseRT, vllm-mlx, oMLX, then
  Ollama;
- **auto**: choose `mac-performance` on Apple Silicon and `portable`
  elsewhere.

The `mac-performance` order is a practical starting policy. It does **not**
mean that BaseRT, vllm-mlx, oMLX, or Ollama is universally faster than the
others. Model family, quantisation, prompt length, cache state, concurrency,
memory pressure, and runtime version all matter. Benchmark the target workload
and pass `prefer=` when a different order is appropriate.

## Python

```python
from modelito import local_client

portable = local_client(model="gemma4:12b-mlx", profile="portable")
```

Provider-specific model identifiers are supported because an Ollama tag, an
MLX/Hugging Face model ID, and a BaseRT model ID should not be assumed to be
interchangeable:

```python
from modelito import local_client

client = local_client(
    profile="mac-performance",
    models={
        "basert": "basecompute/gemma-4-E4B-it",
        "vllm-mlx": "mlx-community/gemma-4-12B-4bit",
        "omlx": "mlx-community/gemma-4-12B-4bit",
        "ollama": "gemma4:12b-mlx",
    },
)
```

`local_client()` is strict about local execution: it does not silently fall
back to a hosted provider or Modelito's deterministic offline shim. Existing
`Client(provider="auto")` behaviour is unchanged.

OpenAI-compatible local backends can also have provider-specific endpoints and
keys:

```python
client = local_client(
    profile="mac-performance",
    models={
        "basert": "my-base-model",
        "vllm-mlx": "my-vllm-model",
        "omlx": "my-omlx-model",
    },
    base_urls={
        "basert": "http://127.0.0.1:8080/v1",
        "vllm-mlx": "http://127.0.0.1:8000/v1",
        "omlx": "http://127.0.0.1:8001/v1",
    },
    api_keys={"basert": "local-key"},
)
```

Two MLX servers commonly default to port 8000, so run them on distinct ports
when comparing them simultaneously.

To override the default order after benchmarking a machine:

```python
client = local_client(
    profile="mac-performance",
    models={
        "basert": "my-base-model",
        "vllm-mlx": "my-vllm-model",
        "omlx": "my-omlx-model",
        "ollama": "my-ollama-tag",
    },
    prefer=["vllm-mlx", "omlx", "ollama", "basert"],
)
```

Use `select_local_runtime()` when an application wants to inspect the decision
before constructing a client:

```python
from modelito import select_local_runtime

selection = select_local_runtime(
    profile="auto",
    models={
        "basert": "my-base-model",
        "vllm-mlx": "my-vllm-model",
        "omlx": "my-omlx-model",
        "ollama": "my-ollama-tag",
    },
)
print(selection.provider, selection.model, selection.endpoint)
```

## Runtime capabilities

`local_runtime_capabilities()` exposes conservative, coarse runtime metadata:

```python
from modelito import local_runtime_capabilities

caps = local_runtime_capabilities("vllm-mlx")
print(caps.streaming, caps.prefix_cache, caps.tool_calls)
```

Capabilities describe a runtime family, not every model or configuration.
`conditional` means that model support, a parser, a chat template, packaging,
or server configuration can affect the feature. `unknown` means Modelito does
not currently make the claim.

| Runtime | Streaming | Prefix cache | Cancellation | Structured output | Tool calls | Model discovery |
| --- | --- | --- | --- | --- | --- | --- |
| BaseRT | yes | yes | unknown | unknown | yes | yes |
| vllm-mlx | yes | yes | yes | yes | conditional | yes |
| oMLX | yes | yes | yes | conditional | conditional | yes |
| Ollama | yes | yes | unknown | yes | conditional | yes |

Do not use this table as a substitute for feature-testing the actual model and
server version used by an application.

## Runtime notes

### BaseRT

BaseRT is a native Metal runtime for Apple Silicon with an OpenAI-compatible
server. Current upstream material documents chat/completions, embeddings,
transcription, tool calls, continuous batching, paged KV cache, and prefix
caching. Base Compute also publishes performance comparisons against MLX and
llama.cpp; those are upstream benchmarks, not Modelito's evidence that BaseRT
wins on an arbitrary machine or workload.

Default Modelito endpoint: `http://127.0.0.1:8080/v1`.

### vllm-mlx

vllm-mlx is an Apple-Silicon MLX server with OpenAI- and
Anthropic-compatible APIs. Current upstream documentation includes continuous
batching, paged/prefix KV caching, structured JSON output, tool-call parsers,
request cancellation, and a `bench-serve` command. Several features are
configuration- or model-dependent.

Default Modelito endpoint: `http://localhost:8000/v1`.

### oMLX

oMLX is an MLX-native server oriented towards persistent local workflows. It
supports OpenAI- and Anthropic-compatible APIs, continuous batching, prefix
sharing, and a tiered hot-RAM/SSD KV cache. Tool calling and structured output
are available but can depend on the model's chat template and parser support.

Default Modelito endpoint: `http://localhost:8000/v1`.

### Ollama

Ollama is the portability path and should not be treated as merely a slow
fallback. Its current Apple-Silicon stack includes an MLX engine, prefix/cache
snapshot work for repeated agent contexts, and ongoing model-specific
optimisations. Ollama 0.30 and later also use llama.cpp paths to broaden model
and hardware support, so the engine used by a particular model can vary.

### Generic OpenAI-compatible servers

`OpenAICompatibleHTTPProvider` remains the generic route for llama.cpp, LM
Studio, vLLM, MLX-LM's HTTP server, and other compatible endpoints. Arbitrary
servers are **not** part of automatic local-runtime selection because Modelito
cannot infer an unknown endpoint safely.

## MLX-LM as a benchmark reference

Raw `mlx-lm` is intentionally not another `local_client()` provider. It is a
useful reference implementation for Apple-Silicon measurements and supports
prompt caching for repeated contexts and multi-turn dialogue. Its built-in HTTP
server is OpenAI-like, but MLX-LM itself cautions that the server is not
recommended for production use because it provides only basic security checks.

The benchmark CLI therefore accepts `--provider mlx-lm` as a **measurement
label/reference path**, without making it part of Modelito's runtime-selection
policy.

## Conversational benchmark

Modelito includes a small cross-runtime benchmark for an already-running
OpenAI-compatible server:

```bash
modelito-benchmark-local \
  --provider vllm-mlx \
  --model mlx-community/Qwen3-4B-Instruct-4bit \
  --repetitions 3 \
  --json \
  --output vllm-mlx.json
```

Other examples:

```bash
modelito-benchmark-local --provider basert --model my-model --json
modelito-benchmark-local --provider omlx --model my-model --json
modelito-benchmark-local --provider ollama --model my-model --json
modelito-benchmark-local --provider mlx-lm --model my-model --json
modelito-benchmark-local \
  --provider openai-compatible \
  --base-url http://127.0.0.1:9000/v1 \
  --model my-model \
  --json
```

If `--model` is omitted, the benchmark asks `/models` for the first advertised
model. To sample the server process's RSS, add `--pid <server-pid>`.

The benchmark records:

- first-request time to first streamed token (TTFT);
- time to the first phrase-like chunk useful to a UI;
- estimated decode tokens per second;
- repeated warm-prefix TTFT;
- TTFT as synthetic conversational history grows;
- client stream-close latency followed by a post-cancellation probe;
- approximate peak process RSS when a server PID is supplied.

The JSON embeds the measurement caveats. In particular:

1. `first_request` is a cold-model result only if the server/model was actually
   cold before the benchmark began.
2. Decode token rate uses Modelito's token-count helper, not the runtime's
   native tokenizer accounting, so use it for within-workload comparison rather
   than precision benchmarking.
3. Client stream-close latency does not prove that the server acknowledged or
   completed cancellation internally.
4. Process RSS can under-report Metal/unified-memory use on macOS.
5. The benchmark measures one client workload. It does not replace a runtime's
   own throughput/concurrency benchmark.

For vllm-mlx specifically, its upstream `bench-serve` command is a useful
second measurement because it reports TTFT, TPOT, throughput, cache deltas, and
Metal memory using runtime-specific instrumentation.

## What to compare for conversational systems

For a latency-sensitive conversational application, compare at least:

- first-turn and warm-turn TTFT;
- prompt-processing time as context grows;
- prefix-cache effectiveness across repeated history;
- sustained generation speed;
- memory pressure while other local models are resident;
- cancellation behaviour;
- output quality for the actual language and register;
- thermal behaviour over a long session.

Do not select a runtime solely from a headline tokens-per-second figure.

## Environment

`MODELITO_LOCAL_PROFILE` sets the profile used when `profile=` is omitted.
Accepted values are:

- `auto`
- `portable`
- `mac-performance`

Aliases `mac`, `macos`, and `apple-silicon` resolve to `mac-performance`.
Provider aliases `vllm_mlx`/`vllmmlx` resolve to `vllm-mlx`, and `om` resolves
to `omlx`.

## Upstream sources reviewed in August 2026

The runtime descriptions above were checked against current upstream material:

- BaseRT: <https://github.com/basecompute/baseRT>,
  <https://www.basecompute.co/getbasert>, and
  <https://huggingface.co/blog/basecompute/basert-release>
- vllm-mlx: <https://github.com/waybarrios/vllm-mlx> and
  <https://github.com/waybarrios/vllm-mlx/blob/main/docs/reference/cli.md>
- oMLX: <https://github.com/jundot/omlx>
- Ollama MLX/cache work: <https://ollama.com/blog/mlx-performance> and
  <https://ollama.com/blog/improved-performance-and-model-support-with-gguf>
- MLX-LM prompt caching and HTTP server:
  <https://github.com/ml-explore/mlx-lm> and
  <https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/SERVER.md>

These sources justify exposing several local paths and benchmark overrides.
They do not establish a universal runtime winner.

## Licensing note

Modelito integrates these runtimes through their documented local HTTP APIs and
does not redistribute their engines. Applications that redistribute or bundle a
runtime should review that runtime's current licence independently.
