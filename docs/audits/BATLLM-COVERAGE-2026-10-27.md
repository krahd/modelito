# BatLLM consumer coverage audit

Audit date: 2026-10-27 (America/Denver).

## Conclusion and scope

Modelito already has the API surface needed by BatLLM. No new provider,
framework, runtime selector, orchestration layer or public API is justified by
this audit. However, coverage is not equivalent to correctness: remaining
warm-up, timeout and streaming validation defects prevent a clean sign-off.

Reviewed local Modelito `eab228e6e0de0b8a583411f5cc39bd2c7e574dea`
(package 1.4.7) against local BatLLM
`634ac5da97618cd398e434933f44ee66438e2203`. Both checkouts were clean initially.
These are local checkout findings, not claims about freshly fetched remote
branches or public package contents. BatLLM runtime and Homebrew requirements
both still pin 1.4.6.

The consumer contract was extracted from BatLLM's `src/llm/chat.py`,
`src/llm/service.py`, gameplay/research/editor call sites, configuration-screen
calls, tests, and the upstream handoffs in
`docs/ADVERSARIAL_AUDIT_2026_10_25.md` and
`docs/ADVERSARIAL_AUDIT_2026_10_26.md`.

The original audit changed documentation only. The findings below describe that
snapshot; the repair disposition records subsequent source changes and validation.

## Requirement coverage

| BatLLM need | Existing Modelito surface / evidence | Assessment |
| --- | --- | --- |
| Native role-preserving synchronous generation | `Message`, root `OllamaProvider.summarize`; `test_ollama_strict.py`, `test_ollama_provider_inputs.py`, `test_ollama_audit.py` | Covered; actual BatLLM adapter exercised against isolated HTTP server |
| Temperature, seed, context and output limits | Native `options` mapping in `_apply_ollama_settings` | Covered; unknown native settings can use existing nested `options` |
| Explicit model, host and port | Provider constructor and `endpoint_url` | Covered for BatLLM's normal explicit endpoints |
| Fail explicitly; never fabricate successful model output | Strict defaults, typed errors, one-attempt synchronous transport | Covered for inference; warm-up differs (F1) |
| Timeout override and no replay of failed inference | `_request_timeout`, strict single-attempt policy | Override covered; total deadline is not enforced (F2) |
| Completion and model identity validation | `done is True`, omitted-tag/`:latest` equivalence | Synchronous covered; final stream event gap (F3) |
| Incremental output and iterator closure | `stream`, context-managed HTTP response | Existing surface sufficient; no new cancellation framework needed |
| Explicit-endpoint inventory, pulls and deletion | `list_local_models`, `pull_model`, `download_model_progress`, `delete_model` | Covered in 1.4.7; BatLLM currently uses its own explicit SDK/HTTP facade |
| Bounded CLI/download operations | Timeout parameters, deadline loop, child cleanup | Covered by subprocess tests, including blocked output and iterator closure |
| Safe whole-service shutdown | Persisted PID, birth-time, executable and command receipt | Covered by synthetic tests; BatLLM currently owns its own receipts |
| Startup without implicit model download | `start_service` | Not compatible with BatLLM policy (F4); retain BatLLM orchestration |
| Warm-up and readiness reporting | `preload_model`, `wait_until_ready`, `server_is_up` | Present but insufficiently strict (F1, F5) |
| Remote model discovery | Bounded official-library HTML parser; catalogue errors propagate | Covered at family level; BatLLM deliberately disables it (F6) |
| Metadata snapshot | `Client.model_metadata`, `normalize_metadata` | Existing best-effort surface; Ollama has no provider metadata method, so unknown models return `{}`; no live model provenance claim |
| Explicit user confirmation, config persistence, UI progress and game/research provenance | BatLLM application code | Keep in BatLLM; no Modelito expansion required |

All five previous upstream handoff items and the unsupported remote CLI
catalogue defect have corresponding repairs and regression coverage in 1.4.7.
That does not close the narrower defects found below.

## Findings

### F1 — High: warm-up can report success for failed responses and replays timed-out POSTs

Location: `modelito/ollama_service.py:1756` (`preload_model`), `:1561`
(`json_post`); `modelito/plumbing.py:25` (`TransportPolicy`).

`preload_model` ignores the returned JSON entirely. Reproductions returned
`{"error":"failed"}`, `{"done":false}`, `{}`, and
`{"model":"wrong","done":true}`; all returned `None` as if successful.
Patching the transport to raise `TimeoutError` produced **three POST attempts**.
BatLLM calls this helper directly and can subsequently save the selected model
as successfully warmed. A timed-out warm-up can therefore also be replayed.

Smallest repair: validate the existing warm-up response contract (including
explicit completion, errors and model consistency), and use a single-attempt
policy for this POST. Empty generated text is valid for warm-up, so do not
require a nonempty conversational completion. Add focused regressions without
adding public methods.

### F2 — High: request timeout is a socket inactivity timeout, not a total deadline

Location: `modelito/ollama_service.py:1579–1581` and
`modelito/ollama.py:488–492`.

The transport passes `timeout` to `urlopen` then reads the body/lines without
tracking elapsed time. An isolated HTTP server delivered a JSON body in
four-byte chunks every 25 ms. The actual BatLLM chat adapter, configured with
`timeout=0.1`, successfully completed after **0.409 s**, instead of timing out.
The same absence of deadline accounting is present in the streaming loop.
This can keep a game turn or editor request active beyond its configured
request budget even though the delayed-first-byte regression passes.

Smallest repair: enforce a monotonic deadline across connect and all reads,
including a partial line/body that continually supplies bytes; keep retries
disabled for generation. Do not merely check the clock between complete lines.
Verify slow headers, trickling body, streaming and socket closure. If the
intended contract is inactivity only, documentation and BatLLM's deadline claims
must instead be corrected explicitly; the current implementation cannot be
called a total deadline.

### F3 — Medium: terminal streaming event bypasses text validation

Location: `modelito/ollama.py:532–538`.

A valid `foo` text event followed by
`{"model":"foo","message":{"content":42},"done":true}`
returns the preceding text successfully. The `done` return occurs before
checking the malformed terminal content. Synchronous inference rejects
non-string content, so the two strict paths disagree. BatLLM's aggregate
nonempty-text check does not catch this when earlier text exists.

Smallest repair: reject explicitly malformed terminal text/message fields
before accepting completion, while retaining any documented valid terminal
shape that omits content. Add tests for malformed terminal events following
valid text; preserve the existing iterator API.

### F4 — Medium, migration blocker: generic startup still pulls automatically

Location: `modelito/ollama_service.py:2010` (`start_service`).

When a model is configured, startup unconditionally executes `ollama pull`
before warming it, including when the daemon already runs. BatLLM's current
policy requires a separate confirmed download action, and its own startup
facade intentionally avoids this behaviour. This is source-confirmed; no real
model download was attempted.

Do not replace BatLLM's startup facade with `start_service` as part of dependency
upgrading. Existing low-level helpers already allow start/wait/preload without
a pull. Resolve any future generic-startup policy change separately, using the
existing explicit download controls; no additional lifecycle abstraction is
needed for BatLLM.

### F5 — Medium: liveness is used as readiness and can exceed the warm-up budget

Location: `modelito/ollama_service.py:315` (`server_is_up`) and `:1746`
(`wait_until_ready`).

`server_is_up` accepts any successful HTTP root response or TCP connection;
`wait_until_ready` uses it as the readiness condition. A non-Ollama listener can
therefore satisfy readiness. Its fixed two-second HTTP and one-second TCP
probes plus one-second sleep are not clamped to the remaining warm-up budget.
These are source-confirmed findings, not real-daemon failures observed here.
BatLLM delegates both calls to Modelito. Its subsequent preload ordinarily
provides another check, but F1 weakens that check.

Keep liveness and readiness meanings explicit. Tighten the existing readiness
path to validate an Ollama response with a remaining-time budget; do not change
all liveness callers to imply model readiness or add another public probe API.

### F6 — Medium: consumer adoption and test fixtures lag the repaired dependency

Locations in BatLLM: `requirements.txt:9`,
`packaging/homebrew/requirements.txt:1`,
`src/llm/service.py:578`, `src/tests/test_adversarial_audit.py:25`.

Both distribution pins are 1.4.6. The catalogue wrapper always raises
`RemoteCatalogueUnavailable`, so upgrading the package alone will not restore
catalogue selection. Existing successful HTTP fixtures omit `model`; 1.4.7
correctly rejects those fixtures. The fixture rejection was reproduced by
loading the actual BatLLM chat adapter against this Modelito checkout.

Update both pins together in a separate BatLLM change; restore catalogue
access through the existing explicit-endpoint API and translate its dataclass
entries to the UI's existing shape. Keep manual-name download and confirmation.
Update successful fixtures with the requested model identity; do not weaken
Modelito's validation. Ownership receipts belong to their creator: Modelito's
shutdown helper must not be substituted for BatLLM-owned process shutdown.

## Validation and limitations

- `.venv-ci/bin/python -m pytest -q --ignore=tests/integration tests`:
  **461 passed, 1 skipped, 2 failed** solely because the sandbox denied loopback
  binding. Reran those exact two tests with loopback permission:
  `.venv-ci/bin/python -m pytest -q tests/test_ollama_audit.py -k native_http_contract`:
  **2 passed**. Combined existing-suite result: **463 passed, 1 skipped**.
- `.venv-ci/bin/python -m ruff check .`: passed.
- `.venv-ci/bin/python -m mypy modelito --ignore-missing-imports`: passed,
  43 source files.
- Audit reproductions used patched responses/subprocess-free transport mocks
  and an isolated loopback HTTP server. The actual BatLLM `llm/chat.py` adapter
  preserved system/user roles, Unicode, temperature, seed, context options and
  `stream: false`, and returned a valid identity-bearing response successfully.
- Python for the Modelito suite and isolated reproductions: 3.14.9; this is
  outside the documented 3.10–3.12 CI matrix. No new matrix claim is made.
- Attempting BatLLM's selected adversarial tests under its Python 3.12 venv
  aborted during collection in Kivy SDL window initialisation. No BatLLM suite
  pass is claimed. The adapter-only reproduction avoids GUI imports but does
  not replace full application acceptance.
- `.venv` lacks pytest; `.venv-test` has a broken Python target. The usable
  `.venv-ci` interpreter was used explicitly.
- No real daemon start/stop, install/update, model pull/delete, hosted-provider
  calls, remote catalogue refresh, package build, publication or native UI
  acceptance was performed. Package/runtime source was not changed.

## Bounded follow-up

1. Repair F1–F3 within the existing functions and add behavioural regressions.
2. Correct readiness semantics/budget in F5 without introducing another helper
   family. Retain BatLLM's no-download startup and ownership boundaries (F4).
3. Upgrade and validate BatLLM separately (F6), including real native UI and an
   already-installed model before declaring consumer acceptance.
4. Freeze feature growth for this work. Hosted provider additions, embeddings,
   HTTP serving, raw tool calls, local runtime rankings, benchmarks, cassettes
   and speech orchestration are not requirements evidenced by BatLLM's current
   integration. Preserve existing public APIs; do not delete unrelated features
   as part of this audit.

## Repair disposition — 28 October 2026

F1–F6 are repaired in the local source candidates, with no new public API:

- F1: warm-up rejects errors, incomplete/non-object responses, mismatched models
  and malformed explicit text. Empty text is valid. POST transport uses one attempt.
- F2: private standard-library HTTP connections enforce a monotonic deadline over
  DNS wait, connection, TLS, headers and partial body/line reads. Expiry shuts down
  registered sockets. An uncancellable OS DNS call may finish in a daemon thread;
  it cannot send a request after the caller times out. Generation remains single-attempt.
- F3: explicit malformed terminal message/content/response fields are rejected
  before completion; a terminal event may omit text.
- F4: generic startup no longer pulls. BatLLM retains its own no-download startup
  and receipt-owned shutdown; no ownership boundary was substituted.
- F5: readiness validates a nonempty version response from `/api/version`, using
  single-attempt probes and remaining-time sleeps. `server_is_up` remains liveness.
- F6: BatLLM branch `fix/modelito-consumer-contract-20261027` coordinates both pins
  on 1.4.8, restores configured-endpoint catalogue discovery and UI entry shapes,
  attempts discovery from an empty selector, retains confirmed manual downloads,
  and fixes success fixtures to carry the requested model identity. The standalone
  editor forwards its edited endpoint when querying installed-state catalogue data.

Verification:

- Modelito non-live suite: **486 passed, 1 skipped**, Python 3.14.9, including
  real loopback trickling headers/body/partial stream, socket-disconnection and
  bounded-DNS tests. Ruff, mypy (44 files), focused Black, legacy-message and
  diff checks passed.
- Candidate wheel and sdist build and twine checks passed. Initial sandbox DNS
  blocked dependency fetching; the permitted build rerun passed.
- BatLLM full non-live suite against the local source: **307 passed, 2 skipped**,
  Python 3.12. Documentation validation passed. Kivy initialisation succeeded
  with native SDL2 and permitted desktop access.
- Existing Ollama and installed `smollm2:latest`: synchronous and streaming
  integration test passed with installation/download/update disabled.
- Native BatLLM source check with disposable application and Kivy homes:
  remote selector fetched and displayed **264 model families**; local inventory
  showed **18 models**; selecting `smollm2:latest` and pressing **Use Selected**
  completed strict warm-up, displayed the model as running and saved its name
  as model/last-served only in the disposable profile. Native-control attachment
  initially stalled and screen capture failed once; reattachment/capture recovered.

This is bounded source acceptance, not a new complete gameplay rehearsal or a
Windows/platform-matrix result. Modelito metadata targets **1.4.8**, which remains
unpublished; BatLLM's new pins cannot be installed normally until it is released.
No tag, publication, model download/deletion, service start/stop or model unload
was performed. Additional verification: supported Python 3.12 contract/audit
regressions passed **68 tests** (one existing pytest configuration warning).
The built wheel was installed without dependencies into a disposable target;
its 1.4.8 version/import path were verified and BatLLM's full suite passed again:
**307 passed, 2 skipped**. Fresh public-PyPI installation and supported-platform
CI remain release gates. Native test processes were closed after validation.

## Publication verification — 29 October 2026

Modelito **1.4.8** is published on public PyPI and GitHub. Tag `v1.4.8` points to
`58b9a41af4a3be0301a6ca896688bf80602fd8b9`.

- [Release-source CI](https://github.com/krahd/modelito/actions/runs/40834302530):
  Python 3.10, 3.11 and 3.12 each **486 passed, 1 skipped**; Windows **125 passed**;
  lint, mypy and docs passed. Windows exposed per-request TLS trust-store setup,
  budget-rounding and disconnect-observation portability issues; all are repaired.
- [Trusted publication](https://github.com/krahd/modelito/actions/runs/40834488142)
  succeeded; [GitHub release](https://github.com/krahd/modelito/releases/tag/v1.4.8)
  is public.
- Fresh uncached public-PyPI installation and `pip check` passed. All 44 installed
  package Python files match release source bytes. Both published artefact hashes
  match PyPI metadata:
  - Wheel: `09862d9e7a0b0f222a5efece5405e135681130597ecb225432683b20190a8da9`.
  - Sdist: `2f992156e494c20cf8edc83732d87a2f2104286cd775bcc4779f771021c7a54a`.
- Public-package readiness, strict warm-up, synchronous output, complete streaming
  and catalogue discovery (264 families) passed with existing `smollm2:latest`.
- BatLLM's complete isolated suite against that fresh public package passed:
  **307 passed, 2 skipped**, Python 3.12; version and import path verified.

No service start/stop, model download/deletion or platform-native gameplay
rehearsal was performed during publication. BatLLM integration proceeds through
its separate migration branch and pull request; no BatLLM release is implied.
