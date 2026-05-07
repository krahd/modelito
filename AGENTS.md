# AGENTS.md

Repository instructions for AI coding agents working in this project.

This file is the durable source of truth for GitHub Copilot, OpenAI Codex, Claude Code, and compatible coding agents. Read it before making changes.

## 1: Non-negotiable rules

- Keep `STATUS.md` accurate at all times.
- `STATUS.md` must exist in the repository root.
- Do not finish a task that changes the project without reviewing and, when needed, updating `STATUS.md`.
- Do not invent project facts. Inspect the repository and record uncertainty explicitly.
- Do not overwrite user work or unrelated changes.
- Do not commit secrets, credentials, tokens, private keys, local environment files, build artefacts, package artefacts, or generated sensitive data.
- Prefer small, focused changes over broad rewrites.
- Preserve public APIs unless the task explicitly requires change.
- Verify meaningful changes with the narrowest reliable command available.
- Do not claim tests passed unless they were actually run.

## 2: Communication style

Use terse, factual, technical communication. Do not use playful, whimsical, cute, decorative, or filler progress phrases such as "combobulating", "cooking", "thinking...", "working on it", "let me dive in", "I'll get started", or "working my magic".

Allowed status-update style: "Reading files." "Found the issue." "Applying patch." "Tests passed." "Tests failed: <reason>."

No jokes, metaphors, fake enthusiasm, anthropomorphising, or decorative progress messages. Prefer concise present-tense technical updates. Use British English for prose documentation unless the repository consistently uses another variant.

## 3: Standard work loop

1. Read this file and `STATUS.md` before editing.
2. Inspect relevant files, docs, tests, packaging metadata, and CI workflows.
3. Identify the smallest safe change.
4. Search call sites before changing provider protocols, public exports, adapters, streaming semantics, configuration, packaging metadata, or release workflows.
5. Make focused edits.
6. Run relevant verification when possible.
7. Update documentation when behaviour, setup, architecture, commands, public APIs, or release state change.
8. Update `STATUS.md` if project state changed.
9. Report changed files, verification, and remaining issues.

## 4: Project-specific map

### 4.1: Project shape

- Purpose: compact dependency-light Python library for provider-agnostic LLM access and local model helpers.
- Main runtime surfaces: provider protocols, provider adapters, connectors, streaming helpers, embeddings, Ollama administration helpers, timeout utilities.
- Primary language/framework: Python package with pytest, ruff, mypy, build, and twine validation.
- Integration posture: hosted SDKs are optional; fallbacks should remain safe for tests/offline use.

### 4.2: Important paths

- `README.md`: human-facing package overview.
- `STATUS.md`: complete current project status report; mandatory upkeep.
- `modelito/`: package source.
- `modelito/provider.py`: provider protocols/interface contract.
- `modelito/client.py`: primary client integration surface.
- `modelito/provider_registry.py`: provider lookup and registration.
- `modelito/openai.py`, `modelito/claude.py`, `modelito/gemini.py`, `modelito/ollama.py`: provider adapters.
- `modelito/ollama_api.py`, `modelito/ollama_service.py`: local Ollama API/service helpers.
- `modelito/messages.py`: shared message datamodels.
- `modelito/streaming.py`: streaming normalisation helpers.
- `modelito/timeout.py`, `modelito/timeout_calibrate.py`: timeout behaviour and calibration.
- `docs/`: API, usage, install, calibration, and migration docs.
- `tests/`: unit and integration-style coverage.
- `pyproject.toml`: package metadata and build configuration.
- `.github/workflows/`: CI and publishing workflows.

### 4.3: Safety invariants

- Keep provider abstractions small, stable, and duck-typing-friendly.
- Hosted SDK dependencies must remain optional unless explicitly changed.
- Offline/deterministic fallbacks must remain suitable for tests and examples.
- Ollama install/download/update flows must remain explicit and gated in tests.
- Secret handling should stay delegated to environment variables, OS keychains, orchestration secrets, or optional integrations, not mandatory core storage.
- Do not publish, tag, or release unless explicitly requested.

## 5: STATUS.md maintenance

`STATUS.md` is mandatory project state, not optional documentation.

Required timestamp line near the top:

```text
Last updated: YYYY-MM-DD HH:MM
```

Use 24-hour local time. If no other timezone is specified, use `America/Montevideo`. Duplicate the exact same line as the final line at the bottom of `STATUS.md`. Update both lines together.

`STATUS.md` must be a complete current snapshot, not a changelog. Include relevant sections for purpose, current state, active focus, architecture, setup/run instructions, configuration, important files, recent changes, tests, risks, pending tasks, next steps, longer-term steps, and decisions.

## 6: Diagrams in STATUS.md

Include useful inline SVG architecture and flow diagrams when the structure is meaningful enough. Keep text inside boxes and canvas bounds. Keep arrows out of unrelated boxes and labels. Prefer generous spacing and simple SVG primitives.

## 7: Validation

Typical validation commands:

```bash
pytest -q
ruff check .
mypy modelito --ignore-missing-imports
python -m build
python -m twine check dist/*
```

Run the narrowest relevant checks first. Record tests not run when relevant. For Ollama integration tests, keep explicit environment gates such as `RUN_OLLAMA_INTEGRATION=1`, `ALLOW_OLLAMA_INSTALL=1`, `ALLOW_OLLAMA_DOWNLOAD=1`, and `ALLOW_OLLAMA_UPDATE=1`.

## 8: Final response requirements

When finishing a task, report concisely: what changed, files changed, verification commands and results, whether `STATUS.md` was updated, and remaining issues or follow-up work.
