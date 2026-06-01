# Implementation Prompt: Final Merge Fixes for `feature/ollama-raw-passthrough-and-docs`

You are working in the GitHub repository:

```text
krahd/modelito
```

Use this branch:

```text
feature/ollama-raw-passthrough-and-docs
```

Do **not** work on `main`.

The branch is very close to mergeable. The Ollama raw passthrough implementation and tests are already mostly in place. Your task is to apply the remaining small, precise fixes identified during review.

Do not redesign the branch. Do not add new features. Do not make unrelated cleanups.

---

## Non-negotiable constraints

1. Preserve zero core dependencies.

   `pyproject.toml` must continue to contain:

   ```toml
   dependencies = []
   ```

2. Do not add LiteLLM.

   Do not add:

   - `litellm`
   - `[project.optional-dependencies].litellm`
   - `LiteLLMProvider`
   - any LiteLLM implementation

3. Do not export recording/replay from the package root.

   Do **not** add these to `modelito/__init__.py`:

   - `RecordingProvider`
   - `ReplayProvider`
   - `CassetteFormatError`
   - `ReplayMissError`

   They must remain imported as:

   ```python
   from modelito.recording import RecordingProvider, ReplayProvider
   ```

4. Do not refactor Ollama raw passthrough.

   Do not redesign or rewrite:

   - `OllamaProvider.raw_complete()`
   - `OllamaProvider.raw_stream()`

   Only touch docstrings or comments if needed.

5. Do not refactor unrelated Ollama code.

   Do not clean up unrelated imports or old smells in:

   - `OllamaProvider.stream()`
   - `OllamaProvider.summarize()`

   unless CI fails specifically because of them.

6. Do not alter the already-added Ollama raw passthrough tests unless CI requires it.

---

# Task 1 — Fix version metadata consistency for `1.4.6`

The branch is now being prepared as release `1.4.6`.

`pyproject.toml` already says:

```toml
version = "1.4.6"
```

Keep that unchanged.

## 1.1 Fix `modelito/__init__.py`

Open:

```text
modelito/__init__.py
```

Find all fallback occurrences of:

```python
__version__ = "1.4.5"
```

Change every fallback occurrence to:

```python
__version__ = "1.4.6"
```

There may be more than one fallback branch. Update all of them.

Do not alter `__all__` except to verify the following remain absent:

```python
RecordingProvider
ReplayProvider
CassetteFormatError
ReplayMissError
```

They must not become root exports.

## 1.2 Fix `STATUS.md`

Open:

```text
STATUS.md
```

Find the current package metadata/version statement.

If it says:

```text
Current package metadata version is `1.4.5` in `pyproject.toml`.
```

change it to:

```text
Current package metadata version is `1.4.6` in `pyproject.toml`.
```

Also confirm that the status text says `OllamaProvider` supports raw passthrough via Ollama’s OpenAI-compatible `/v1/chat/completions` endpoint.

Do not rewrite the whole file. Make minimal corrections.

## 1.3 Add `CHANGELOG.md` entry for `1.4.6`

Open:

```text
CHANGELOG.md
```

Add a new section above the existing `1.4.5` section.

Use the existing changelog style. If existing entries use:

```md
## 1.4.5 - 2026-05-19
```

then add:

```md
## 1.4.6 - 2026-05-19
```

If the actual current date convention in the file differs, match the file’s existing convention. Do not invent a different style.

Add this entry:

```md
## 1.4.6 - 2026-05-19

- Added OpenAI-compatible raw passthrough support to `OllamaProvider` via Ollama's `/v1/chat/completions` endpoint.
- Added `OllamaProvider.raw_complete()` and `OllamaProvider.raw_stream()` for preserving raw OpenAI-compatible chat payloads, including tool-call metadata.
- Added tests for Ollama raw passthrough, including endpoint selection, stream parsing, payload immutability, strict malformed-event handling, fallback behaviour, and preservation of OpenAI-compatible generation fields.
- Updated raw fallback responses in `OpenAICompatibleHTTPProvider` to preserve the requested model.
- Updated documentation for Ollama raw passthrough, namespaced recording/replay helpers, and LiteLLM as a future optional adapter rather than a core dependency.
```

If the existing changelog uses a different date for recent entries, use that same date style and format, but keep the content above.

---

# Task 2 — Update stale `OllamaProvider` docstrings

Open:

```text
modelito/ollama.py
```

The module and class docstrings still describe the provider as exposing only:

```text
list_models()
summarize()
```

This is now stale because the provider also has:

- `stream()`
- `embed()`
- `raw_complete()`
- `raw_stream()`

Update only the docstrings. Do not change runtime logic.

## 2.1 Module docstring

Replace the stale module docstring at the top of `modelito/ollama.py` with:

```python
"""Ollama provider and local runtime helpers.

The provider exposes the standard modelito provider surface for listing models,
summarising messages, streaming text, and embeddings. It also implements raw
OpenAI-compatible chat passthrough through Ollama's `/v1/chat/completions`
endpoint so `modelito-serve` can preserve tool-call metadata and other raw
OpenAI-compatible fields.
"""
```

## 2.2 Class docstring

Replace the stale `OllamaProvider` class docstring with:

```python
"""Provider for local Ollama runtimes.

`OllamaProvider` supports the standard modelito provider methods, local Ollama
HTTP/CLI fallbacks, embeddings, and raw OpenAI-compatible chat passthrough via
Ollama's `/v1/chat/completions` endpoint.
"""
```

Do not alter method bodies.

---

# Task 3 — Verify documentation consistency

Check these files:

```text
docs/USAGE.md
docs/API.md
README.md
STATUS.md
```

Confirm all of the following are true:

1. They no longer say Ollama raw passthrough is deferred.
2. They describe `OllamaProvider.raw_complete()` and `OllamaProvider.raw_stream()` as implemented.
3. They do not claim `LiteLLMProvider` exists.
4. They describe LiteLLM only as a possible future optional adapter / escape hatch.
5. They keep recording/replay namespaced under:

   ```python
   from modelito.recording import RecordingProvider, ReplayProvider
   ```

6. They do not claim `RecordingProvider` / `ReplayProvider` are root exports.
7. They do not use `llama2-uncensored:7b` as an example model.
8. They use `llama3.2` or another neutral current example model instead.

Make only minimal corrections where any of these checks fail.

---

# Task 4 — Verify the already-added raw passthrough tests remain intact

Do not remove or weaken the tests in:

```text
tests/test_ollama_raw_provider.py
```

Confirm the file still covers at least:

- `OllamaProvider` satisfying `RawChatProvider`
- default model insertion
- original-payload immutability for `raw_complete()`
- explicit model preservation
- tool payload preservation
- `/v1/chat/completions` endpoint for `raw_complete()`
- `/v1/chat/completions` endpoint for `raw_stream()`
- `raw_stream()` original-payload immutability
- preservation of `response_format`, `temperature`, `top_p`, `max_tokens`, and `stop`
- strict rejection of non-dict JSON stream events
- fallback stream behaviour

If any of these tests were accidentally removed, restore them. Otherwise, do not change them.

---

# Task 5 — Run the exact CI commands

The repository CI workflow runs these checks:

```bash
python scripts/check_no_legacy_dicts.py
ruff check .
mypy modelito --ignore-missing-imports
pytest -q --ignore=tests/integration tests
```

Run exactly these commands locally.

If any command fails, fix the smallest concrete issue causing the failure. Do not make unrelated cleanups.

---

# Task 6 — Do not make these changes

Do **not** do any of the following:

1. Do not change `pyproject.toml` away from `version = "1.4.6"`.
2. Do not add any dependency.
3. Do not implement LiteLLM.
4. Do not add a `litellm` optional extra.
5. Do not implement `modelito.testing`.
6. Do not export recording/replay from `modelito.__init__`.
7. Do not refactor Ollama raw passthrough.
8. Do not refactor unrelated Ollama methods.
9. Do not remove raw OpenAI-compatible dict payload examples from tests.
10. Do not remove docs about LiteLLM as a future optional adapter.
11. Do not rewrite the changelog beyond adding the `1.4.6` section.

---

# Expected final state

After these changes:

1. `pyproject.toml`, `modelito/__init__.py`, `STATUS.md`, and `CHANGELOG.md` all consistently describe version `1.4.6`.
2. `CHANGELOG.md` contains a clear `1.4.6` entry above `1.4.5`.
3. `OllamaProvider` module and class docstrings accurately describe raw passthrough support.
4. Documentation remains consistent with implemented behaviour.
5. `dependencies = []` remains unchanged.
6. Recording/replay remain namespaced and are not root exports.
7. LiteLLM remains documentation-only as a future optional adapter.
8. The exact CI commands pass.

---

# Deliverable

When done, report:

1. Files changed.
2. Exact version references updated.
3. Exact docstrings updated.
4. Exact commands run.
5. Full pass/fail results.
6. Confirmation that `dependencies = []` remains unchanged.
7. Confirmation that no LiteLLM dependency, optional extra, or implementation was added.
8. Confirmation that recording/replay were not added to `modelito/__init__.py`.
9. Any remaining known limitations.

Do not claim checks passed unless you actually ran them and they passed.
