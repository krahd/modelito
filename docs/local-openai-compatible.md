# Using local OpenAI-compatible servers

Several high-performance local inference engines provide OpenAI Chat Completions API compatibility. modelito's `OpenAIProvider` works with any of them via the `base_url` parameter—no new provider implementation needed.

## Supported servers

- **[llama.cpp](https://github.com/ggerganov/llama.cpp)** — High-performance C++ LLM inference engine. The built-in `llama-server` provides an OpenAI-compatible HTTP server.
- **[vLLM](https://docs.vllm.ai/)** — High-throughput LLM serving framework with OpenAI API compatibility.
- **[LM Studio](https://lmstudio.ai/)** — Desktop application for running open-source LLMs with an OpenAI-compatible API.
- **[SGLang](https://sglang.run/)** — Efficient serving of language models with OpenAI API endpoints.
- **Others** — Any service that speaks the OpenAI Chat Completions API (e.g., LocalAI, Ollama in OpenAI-compat mode).

## Configuration

### llama.cpp / llama-server

1. **Download a GGUF model** (e.g., from [Hugging Face](https://huggingface.co/models?library=gguf)):
   ```sh
   # Example: download a quantized Llama model
   wget https://huggingface.co/.../model.gguf
   ```

2. **Start llama-server** on your machine:
   ```sh
   # llama-server listens on http://localhost:8080 by default
   llama-server -m path/to/model.gguf
   ```

3. **Use it with modelito**:
   ```python
   from modelito import OpenAIProvider, Message

   provider = OpenAIProvider(
       base_url="http://localhost:8080/v1",
       api_key="ignored"  # llama-server doesn't validate API keys
   )

   # Use it like any other provider
   response = provider.summarize([
       Message(role="user", content="What is 2+2?")
   ])
   print(response)
   ```

### vLLM

1. **Start vLLM server**:
   ```sh
   # vLLM listens on http://localhost:8000 by default
   python -m vllm.entrypoints.openai.api_server --model meta-llama/Llama-2-7b-hf
   ```

2. **Use it with modelito**:
   ```python
   from modelito import OpenAIProvider, Message

   provider = OpenAIProvider(
       base_url="http://localhost:8000/v1",
       api_key="dummy"  # vLLM doesn't validate keys without auth enabled
   )

   response = provider.summarize([
       Message(role="system", content="You are a helpful assistant."),
       Message(role="user", content="Explain machine learning in one sentence.")
   ])
   print(response)
   ```

### LM Studio

1. **Install [LM Studio](https://lmstudio.ai/)** and download a model.

2. **Start the local server** from the LM Studio UI (typically http://localhost:1234):
   ```
   Local Server → Start Server
   ```

3. **Use it with modelito**:
   ```python
   from modelito import OpenAIProvider, Message

   provider = OpenAIProvider(
       base_url="http://localhost:1234/v1",
       api_key="not-needed"
   )

   response = provider.summarize([
       Message(role="user", content="Hello!")
   ])
   print(response)
   ```

### SGLang

1. **Start SGLang server**:
   ```sh
   # SGLang listens on http://localhost:30000 by default
   python -m sglang.launch_server --model-path meta-llama/Llama-2-7b-hf --port 30000
   ```

2. **Use it with modelito**:
   ```python
   from modelito import OpenAIProvider, Message

   provider = OpenAIProvider(
       base_url="http://localhost:30000/v1",
       api_key="dummy"
   )

   response = provider.summarize([
       Message(role="user", content="What is AI?")
   ])
   print(response)
   ```

## Streaming

All local OpenAI-compatible servers support streaming via the same `stream()` interface:

```python
from modelito import OpenAIProvider, Message

provider = OpenAIProvider(
    base_url="http://localhost:8080/v1",
    api_key="ignored"
)

# Stream token-by-token
for chunk in provider.stream([
    Message(role="user", content="Tell me a story in 5 sentences.")
]):
    print(chunk, end="", flush=True)
print()
```

## Testing and offline development

For testing or development without a running server, use the deterministic fallback:

```python
from modelito import OpenAIProvider, Message

# No server running; falls back to deterministic behavior
provider = OpenAIProvider(base_url="http://nonexistent:9999/v1")

# Works offline; returns concatenated message contents
response = provider.summarize([
    Message(role="user", content="Hello"),
    Message(role="assistant", content="Hi there!")
])
print(response)  # Output: "Hello\nHi there!"
```

This is useful for CI pipelines and unit tests that should not depend on external services.

## Performance considerations

- **llama.cpp/llama-server**: Best for CPU-only inference; excellent for testing and edge devices. llama-server is single-threaded by default; use `--parallel` for multi-request concurrency.
- **vLLM**: Optimized for NVIDIA GPUs; supports batching and token-level operations.
- **LM Studio**: Desktop GUI; good for interactive exploration; see LM Studio docs for performance tuning.
- **SGLang**: Research-oriented; supports structured generation and schema-guided decoding.

For production use, consult each service's documentation on resource allocation, model quantization, and batching strategies.

## Troubleshooting

**Connection refused**
- Ensure the server is running on the configured host and port.
- Check firewall rules if accessing across networks.
- Verify the base_url matches the server's actual listening address.

**API errors or empty responses**
- Some servers may require specific headers or request formats. Check the server's OpenAI API compatibility docs.
- Ensure the model you're requesting is loaded on the server.
- Verify the `api_key` parameter (can be arbitrary strings for local servers).

**Slow responses**
- Local inference is slower than cloud APIs; set realistic timeouts.
- Consider model quantization (GGUF for llama.cpp, lower bit-widths for others) for speed.
- For high throughput, use vLLM or SGLang with batching.

## See also

- [ARCHITECTURE.md](ARCHITECTURE.md) — modelito's Provider Protocol and fallback hierarchy
- [USAGE.md](USAGE.md) — General usage guide
