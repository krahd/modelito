# Local runtime profiles

This document describes Modelito's local-runtime selection policy.

The goal is to support two explicit paths without pretending that one runtime is universally fastest:

- **portable**: prefer Ollama, which runs on macOS, Linux, and Windows and provides the broadest common local path;
- **mac-performance**: on Apple Silicon, prefer oMLX and fall back to Ollama. Both are MLX-capable on current macOS systems, so applications should benchmark representative workloads and may override the order with `prefer=`.

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
        "omlx": "mlx-community/your-mlx-model",
        "ollama": "your-ollama-tag",
    },
)
```

`local_client()` is strict about finding and using a local runtime: it does not silently fall back to a hosted provider or to Modelito's deterministic offline shim. Existing `Client(provider="auto")` behaviour is unchanged.

To override the profile's order after benchmarking a machine:

```python
client = local_client(
    profile="mac-performance",
    models={"omlx": "your-mlx-model", "ollama": "your-ollama-tag"},
    prefer=["ollama", "omlx"],
)
```

Use `select_local_runtime()` when an application wants to inspect the decision before constructing a client.

```python
from modelito import select_local_runtime

selection = select_local_runtime(
    profile="auto",
    models={"omlx": "your-mlx-model", "ollama": "your-ollama-tag"},
)
print(selection.provider, selection.model, selection.endpoint)
```

The model mapping is intentional. An Ollama tag and an oMLX/Hugging Face model name are not assumed to be interchangeable.

## Environment

`MODELITO_LOCAL_PROFILE` can set the profile used when the `profile` argument is omitted. Accepted values are:

- `auto`
- `portable`
- `mac-performance`

Aliases `mac`, `macos`, and `apple-silicon` resolve to `mac-performance`.

## Why the profiles are deliberately modest

Current Apple-Silicon runtimes are moving quickly. oMLX provides MLX-native serving, continuous batching, and persistent paged KV caching. Current Ollama releases also include an MLX engine and model-specific acceleration. Modelito therefore treats the profile as a practical default order, not as a benchmark claim.

For latency-sensitive conversational applications, benchmark at least:

- time to first token;
- sustained generation speed;
- prompt-processing time as the conversation grows;
- memory pressure while ASR/TTS models are resident;
- behaviour after repeated prefixes and conversation branches.

Do not select a runtime solely from synthetic tokens-per-second figures if the application is conversational.

## Current upstream evidence

This policy was reviewed against the current upstream runtime documentation in August 2026:

- Ollama's Apple-Silicon MLX engine and June 2026 performance update: <https://ollama.com/blog/mlx-performance>
- Ollama's Gemma 4 multi-token-prediction acceleration: <https://ollama.com/blog/faster-gemma-4-mlx-mtp>
- oMLX features and hardware guidance: <https://omlx.ai/>

These sources justify exposing both paths; they do not establish a universal winner for arbitrary models or workloads.
