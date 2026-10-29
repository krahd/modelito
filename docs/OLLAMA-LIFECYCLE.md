# Ollama endpoint, lifecycle and completion contracts

## Explicit configuration

Applications that already resolve configuration should supply it directly:

```python
from modelito.ollama_service import inspect_service_state, start_service, stop_service

config = {
    "url": "http://127.0.0.1:11435",
    "port": 11435,
    "model": "example:latest",
}
state = inspect_service_state(config=config)
# Starting, downloading and stopping are explicit operations:
# start_service(config=config, timeout=600)
# stop_service(config=config)
```

`config` is a flat effective LLM configuration mapping. It bypasses user-file
configuration discovery and startup selection persistence. Supplying both
`config` and `config_path` raises `ValueError`. Legacy calls without `config`
retain configuration-file discovery. Defaults for omitted effective fields are
loopback, port 11434 and no startup model.

`list_local_models`, `list_remote_models`, `list_remote_model_catalog`,
`ensure_model_available`, `download_model_progress`, `download_model`,
`pull_model` and `delete_model` accept keyword-only `host` and `port` arguments.
An explicit port in `host` takes precedence over `port`; bare hostnames and
bracketed IPv6 URLs are accepted. Explicit local inventory uses `/api/tags`
and returns model names. CLI operations set `OLLAMA_HOST` in the child process;
they do not change the parent environment. With no host, legacy CLI helpers
inherit the caller's environment. Async inventory, download and deletion
wrappers accept the same endpoint arguments.

Provider model discovery, readiness checks, `LocalModelManager` and HTTP-adapter
management fallbacks use their configured endpoint. A failed explicit endpoint
is never retried against a discovered user endpoint. Remote catalogue installed
flags use that endpoint's inventory; use `include_installed=False` to avoid
inventory discovery entirely.

Remote discovery fetches [Ollama's public library](https://ollama.com/library)
over HTTPS and extracts model-family links. It needs no installed CLI or running
local server. Ollama's CLI does not provide the previously attempted `--remote`
listing flags; `/api/remote-models` is not used either. For `list_remote_models`,
retained `host`/`port` arguments do not select a registry; only installed-state
inventory in `list_remote_model_catalog` uses those endpoint arguments.

The result covers the official library's listed families, not every tag or
community namespace. Bare family names select Ollama's default tag when pulled;
installed-state matching treats a bare name and `:latest` as equivalent. HTML
parsing depends on the public site's link structure, not a documented catalogue
API. HTTP/timeout failures, oversized responses and pages with no recognised
model links raise `ProviderError`, including through the adapter and
`api_list_remote`; the envelope API reports an error. These failures never
masquerade as successful empty catalogues. Fetches have a finite I/O timeout
(default 30 seconds) and a 4 MiB response limit.

## Ownership and shutdown

`start_detached_ollama_serve` records the child PID, creation time, executable
and exact command in an endpoint-specific receipt under `~/.modelito/servers/`.
Identity inspection requires the optional `psutil` dependency (`modelito[ollama]`).
If it is unavailable, startup can proceed but automatic shutdown is disabled.

`stop_service` only terminates a local server with a matching receipt, creation
time, executable and exact `ollama serve` command. It never unloads models,
searches for listener PIDs or kills unrelated processes. Existing external
servers, stale receipts, reused PIDs, remote endpoints and unverifiable identity
return a non-zero result and preserve the server. Success returns zero and
removes the receipt. A graceful termination timeout permits killing only the
same verified process. `stop_ollama(force=...)` delegates to this ownership
policy; the retained `force` argument does not broaden shutdown scope.

This intentionally tightens historical shutdown behaviour. Servers started
outside Modelito, including servers started before receipt support, must be
stopped by their owner.

## Deadlines and cancellation

`run_ollama_command(..., timeout=30)` bounds subprocess execution and propagates
`subprocess.TimeoutExpired`. CLI inventory and deletion accept a total timeout
across command variants (defaults: 30 and 60 seconds). Pull/download defaults
to 600 seconds. `start_service` never pulls models; use an explicit download
action before warming a missing model. Its `timeout` bounds the CLI version probe.
`install_service(timeout=600)` also bounds its installer subprocess.

Download progress uses a deadline across stdout reading, command variants and
process exit. A silent child cannot block indefinitely. Timeouts yield a terminal
`ModelLifecycleState(phase="error")`; `download_model` and `pull_model` return
`False`. Closing the progress iterator kills and reaps its child, including when
closed early. Consumers stopping iteration early should call `close()` in a
`finally` block. The HTTP adapter exposes error states as exceptions and never
restarts a failed or cancelled download against another endpoint. Async wrappers
run in an executor: cancelling the awaiting task does not stop that worker;
its configured subprocess deadline still applies.

Timeout values must be finite and positive. Strict provider summary and streaming
calls use `settings["timeout"]` when supplied, otherwise the constructor timeout.
This is an HTTP I/O timeout, not a server-side cancellation acknowledgement or
a total generation deadline. The value is never sent as a model option.

## Strict completion validation

Strict synchronous summary calls require a JSON object, no provider error,
`done: true` and textual completion content. Empty text remains valid for an
explicitly completed response. Missing or false completion markers are rejected.
When a model is requested, synchronous responses and each streaming event must
identify that model. Only an omitted tag and `:latest` are treated as equivalent;
other tags, namespaces and aliases must match exactly. Model identity is a
response consistency check, not authentication of the server or model weights.

Malformed, incomplete and mismatched responses raise `ModelitoBadResponseError`;
strict requests never replay through CLI or synthetic inference fallbacks.
Strict synchronous summaries also disable automatic HTTP retries to avoid
replaying a generation after a timeout.

Native Ollama HTTP requests enforce a total monotonic deadline across connection,
headers and body/stream reads; expiry shuts down the request socket. Warm-up uses
one POST attempt and requires completion and matching model identity (empty text
is valid). Readiness validates `/api/version` within the remaining startup budget;
`server_is_up` remains a liveness probe.
