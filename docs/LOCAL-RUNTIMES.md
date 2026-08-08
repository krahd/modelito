# Local runtime profiles

This document describes Modelito's local-runtime selection policy.

The goal is to support two explicit paths without pretending that one runtime is universally fastest:

- **portable**: prefer Ollama, which runs on macOS, Linux, and Windows and provides the broadest common local path;
- **mac-performance**: on Apple Silicon, prefer oMLX and fall back to Ollama. Both are MLX-capable on current macOS systems, so applications should benchmark representative workloads and may override the order with `prefer=`.

The default **auto** local profile selects `mac-performance` on Apple Silicon and `portable` elsewhere.

## Python

```python
from modelito import Client

portable = Client.local(model="gemma4:12b-mlx", profile="portable")

mac = Client.local(
    model="your-loaded-mlx-model",
    profile="mac-performance",
)
```

`Client.local()` is strict about finding a local runtime: it does not silently fall back to a hosted provider. Existing `Client(provider="auto")` behaviour is unchanged.

To override the profile's order after benchmarking a machine:

```python
client = Client.local(
    model="your-model",
    profile="mac-performance",
    prefer=["ollama", "omlx"],
)
```

The `model` identifier is still provider-specific. An Ollama tag and an oMLX/Hugging Face model name are not assumed to be interchangeable.

## Environment

`MODELITO_LOCAL_PROFILE` can set the profile used by `Client.local()` when its `profile` argument is omitted. Accepted values are:

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
