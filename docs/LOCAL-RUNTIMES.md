# Local runtime profiles

This document describes Modelito's local-runtime selection policy.

The goal is to support two explicit paths without pretending that one runtime is universally fastest:

- **portable**: prefer Ollama, which runs on macOS, Linux, and Windows and provides the broadest common local path;
- **mac-performance**: on Apple Silicon, try BaseRT, then oMLX, then Ollama. This is a practical current default, not a guarantee that the first backend is fastest for every model or workload.

The default **auto** local profile selects `mac-performance` on Apple Silicon and `portable` elsewhere.

## Python

```python
from modelito import local_client

portable = local_client(model="gemma4:12b-mlx", profile="portable")
```

For an application that can use provider-specific model identifiers:

```python
from modelito import local_client

client = local_client(
    profile="mac-performance",
    models={
        "basert": "basecompute/gemma-4-E4B-it",
        "omlx": "mlx-community/gemma-4-12B-4bit",
        "ollama": "gemma4:12b-mlx",
    },
)
```

`local_client()` is strict about finding and using a local runtime: it does not silently fall back to a hosted provider or to Modelito's deterministic offline shim. Existing `Client(provider="auto")` behaviour is unchanged.

OpenAI-compatible local backends can also have provider-specific endpoints and keys:

```python
client = local_client(
    profile="mac-performance",
    models={"basert": "my-base-model", "omlx": "my-mlx-model"},
    base_urls={
        "basert": "http://127.0.0.1:8080/v1",
        "omlx": "http://127.0.0.1:8000/v1",
    },
    api_keys={"basert": "local-key"},
)
```

To override the profile's order after benchmarking a machine:

```python
client = local_client(
    profile="mac-performance",
    models={
        "basert": "my-base-model",
        "omlx": "my-mlx-model",
        "ollama": "my-ollama-tag",
    },
    prefer=["ollama", "basert", "omlx"],
)
```

Use `select_local_runtime()` when an application wants to inspect the decision before constructing a client.

```python
from modelito import select_local_runtime

selection = select_local_runtime(
    profile="auto",
    models={
        "basert": "my-base-model",
        "omlx": "my-mlx-model",
        "ollama": "my-ollama-tag",
    },
)
print(selection.provider, selection.model, selection.endpoint)
```

The model mapping is intentional. BaseRT model identifiers, oMLX/Hugging Face model names, and Ollama tags are not assumed to be interchangeable.

## Environment

`MODELITO_LOCAL_PROFILE` can set the profile used when the `profile` argument is omitted. Accepted values are:

- `auto`
- `portable`
- `mac-performance`

Aliases `mac`, `macos`, and `apple-silicon` resolve to `mac-performance`.

## Runtime characteristics

### BaseRT

BaseRT is a native Metal runtime for Apple Silicon with an OpenAI-compatible server. Current releases support chat/completions, embeddings, transcription, tool calls, continuous batching, paged KV, and prefix caching. Its published 2026 benchmarks report higher decode throughput than MLX and llama.cpp on tested M-series hardware, with larger prefill gains on some models. Treat those numbers as upstream evidence, not as a guarantee for an arbitrary machine or conversation workload.

The default Modelito endpoint is `http://127.0.0.1:8080/v1`.

### oMLX

oMLX is MLX-native and particularly relevant to long-running conversational or agentic processes because it provides continuous batching and persistent paged KV/prefix caching. Its cache design can materially reduce repeated long-prefix prefill costs.

The default Modelito endpoint is `http://localhost:8000/v1`.

### Ollama

Ollama is the portability path and should not be treated as merely a slow fallback on modern Macs. Its 2026 Apple-Silicon engine uses MLX, supports current MLX model formats, and has received major TTFT, memory, quantisation, and model-specific acceleration work. It remains the easiest common path across macOS, Linux, and Windows.

## Benchmark the actual conversation workload

For latency-sensitive conversational applications, benchmark at least:

- time to first token;
- sustained generation speed;
- prompt-processing time as the conversation grows;
- prefix-cache effectiveness across repeated conversational history;
- memory pressure while ASR and TTS models are resident at the same time;
- cold-start versus warm-turn latency;
- output quality for the actual language/register being used;
- thermal behaviour over a long session.

Do not select a runtime solely from synthetic tokens-per-second figures. A conversational system cares heavily about prompt prefill, first-token latency, cache reuse, and co-resident speech models.

## Current upstream evidence

This policy was reviewed against current upstream material in August 2026:

- BaseRT documentation and server API: <https://docs.basecompute.co/serving> and <https://docs.basecompute.co/server-api>
- BaseRT Apple-Silicon performance paper: <https://arxiv.org/abs/2607.00501>
- Ollama's Apple-Silicon MLX engine and June 2026 performance update: <https://ollama.com/blog/mlx-performance>
- Ollama's current model/runtime updates: <https://ollama.com/blog>
- oMLX project discussion and current implementation: <https://github.com/ml-explore/mlx/discussions/3203>

These sources justify exposing several paths and a benchmark override. They do not establish a universal winner for arbitrary models or workloads.

## Licensing note

Modelito's BaseRT integration talks only to its documented local HTTP API. BaseRT's open ecosystem repository is Apache-2.0, while its distributed engine binary has its own licence. Applications that distribute or depend on that engine should review the upstream licence independently.
