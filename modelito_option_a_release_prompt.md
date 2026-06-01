# Implementation Prompt: Option A Release Consistency Fixes for `feature/ollama-raw-passthrough-and-docs`

You are working in the GitHub repository:

```text
krahd/modelito
```

Use the branch:

```text
feature/ollama-raw-passthrough-and-docs
```

Do **not** work on `main`.

The branch is close to mergeable. Apply **Option A**: treat this branch as the release-preparation branch for version `1.4.6`.

Your task is small and precise. Do not redesign anything. Do not add new features beyond the items below.

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

   They must remain namespaced:

   ```python
   from modelito.recording import RecordingProvider, ReplayProvider
   ```

4. Do not refactor Ollama raw passthrough.

   Do not redesign:

   - `OllamaProvider.raw_complete()`
   - `OllamaProvider.raw_stream()`

   Only touch their surrounding documentation/docstrings if needed.

5. Do not refactor unrelated Ollama code.

   Do not clean up unrelated imports or old smells in:

   ```python
   OllamaProvider.stream()
   OllamaProvider.summarize()
   ```

   unless CI fails specifically because of them.

6. Do not change public semantics except where explicitly instructed below.

---

# Task 1 — Align version metadata to `1.4.6`

`pyproject.toml` already says:

```toml
version = "1.4.6"
```

Keep that.

Now update all stale version references so the branch is internally consistent.

## 1.1 Update `modelito/__init__.py`

Find the fallback version:

```python
__version__ = "1.4.5"
```

Change it to:

```python
__version__ = "1.4.6"
```

Do not otherwise alter root exports.

Specifically confirm that these are still not exported from `modelito.__init__`:

```python
RecordingProvider
ReplayProvider
CassetteFormatError
ReplayMissError
```

## 1.2 Update `STATUS.md`

Find the current package metadata/version statement.

If it says:

```text
1.4.5
```

change it to:

```text
1.4.6
```

Also ensure the status summary says that `OllamaProvider` now supports raw passthrough via Ollama’s OpenAI-compatible `/v1/chat/completions` endpoint.

Do not rewrite the whole status file. Make the minimal version/status corrections.

## 1.3 Add a `CHANGELOG.md` entry for `1.4.6`

At the top of `CHANGELOG.md`, above the existing `1.4.5` entry, add a new section:

```md
## 1.4.6

- Added OpenAI-compatible raw passthrough support to `OllamaProvider` via Ollama's `/v1/chat/completions` endpoint.
- Added `OllamaProvider.raw_complete()` and `OllamaProvider.raw_stream()` for preserving raw OpenAI-compatible chat payloads, including tool-call metadata.
- Added tests for Ollama raw passthrough, including endpoint selection, stream parsing, payload immutability, strict malformed-event handling, fallback behaviour, and preservation of OpenAI-compatible generation fields.
- Updated raw fallback responses in `OpenAICompatibleHTTPProvider` to preserve the requested model.
- Updated documentation for Ollama raw passthrough, namespaced recording/replay helpers, and LiteLLM as a future optional adapter rather than a core dependency.
```

Keep the changelog style consistent with the existing file. If existing entries include dates, add the appropriate date in the same format. If they do not, do not invent one.

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

That is stale.

Update docstrings so they accurately mention the current surface without overexplaining.

## 2.1 Module docstring

Replace the stale module docstring with something like:

```python
"""Ollama provider and local runtime helpers.

The provider exposes the standard modelito provider surface for listing models,
summarising messages, streaming text, and embeddings. It also implements raw
OpenAI-compatible chat passthrough through Ollama's `/v1/chat/completions`
endpoint so `modelito-serve` can preserve tool-call metadata and other raw
OpenAI-compatible fields.
"""
```

Keep wording concise.

## 2.2 Class docstring

Replace the stale `OllamaProvider` class docstring with something like:

```python
"""Provider for local Ollama runtimes.

`OllamaProvider` supports the standard modelito provider methods, local Ollama
HTTP/CLI fallbacks, embeddings, and raw OpenAI-compatible chat passthrough via
Ollama's `/v1/chat/completions` endpoint.
"""
```

Do not change runtime logic.

---

# Task 3 — Verify docs remain consistent

Check these files:

```text
docs/USAGE.md
docs/API.md
README.md
STATUS.md
```

Confirm all of the following:

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

Make only minimal corrections where these checks fail.

---

# Task 4 — Run the exact CI commands

The CI workflow runs these checks.

Run them locally:

```bash
python scripts/check_no_legacy_dicts.py
ruff check .
mypy modelito --ignore-missing-imports
pytest -q --ignore=tests/integration tests
```

Do not invent new tooling.

If any command fails, fix the smallest concrete issue causing the failure.

---

# Task 5 — Do not make these changes

Do not do any of the following:

1. Do not change `pyproject.toml` away from `version = "1.4.6"`.
2. Do not add dependencies.
3. Do not implement LiteLLM.
4. Do not implement `modelito.testing`.
5. Do not export recording/replay from `modelito.__init__`.
6. Do not refactor Ollama raw passthrough.
7. Do not refactor unrelated Ollama methods.
8. Do not remove raw OpenAI-compatible dict payload examples from tests.
9. Do not remove docs about LiteLLM as a future optional adapter.

---

# Expected final state

After these changes:

1. `pyproject.toml`, `modelito/__init__.py`, `STATUS.md`, and `CHANGELOG.md` all consistently describe version `1.4.6`.
2. `CHANGELOG.md` contains a clear `1.4.6` entry.
3. `OllamaProvider` docstrings accurately describe raw passthrough support.
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
3. Exact commands run.
4. Full pass/fail results.
5. Confirmation that `dependencies = []` remains unchanged.
6. Confirmation that no LiteLLM dependency or implementation was added.
7. Confirmation that recording/replay were not added to `modelito/__init__.py`.
8. Any remaining known limitations.

Do not claim checks passed unless you actually ran them and they passed.
