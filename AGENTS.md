# AGENTS.md

Canonical guidance for automated coding agents working in this repository.
These instructions apply to GitHub Copilot, OpenAI Codex, Claude, and other
compatible agents.

## Project Shape

`modelito` is a dependency-light Python library that provides a unified,
provider-agnostic interface for LLM usage across hosted and local backends.
The codebase includes:

- Core provider abstractions and implementations under `modelito/`
- User and developer docs under `docs/`
- Examples under `examples/`
- Tests under `tests/`
- Release and maintenance metadata at repo root

## Important Paths

- `modelito/client.py`: primary client integration surface
- `modelito/provider.py`: provider protocol and interface contract
- `modelito/provider_registry.py`: provider lookup and registration logic
- `modelito/openai.py`, `modelito/claude.py`, `modelito/gemini.py`, `modelito/ollama.py`: provider adapters
- `modelito/ollama_api.py`, `modelito/ollama_service.py`: local Ollama API and service helpers
- `modelito/messages.py`: shared message datamodels
- `modelito/streaming.py`: streaming normalization helpers
- `modelito/timeout.py`, `modelito/timeout_calibrate.py`: timeout behavior and calibration
- `tests/`: unit and integration-style coverage
- `README.md`, `docs/`: user-facing and maintainer-facing documentation
- `STATUS.md`: complete, current project status report (mandatory upkeep; see below)

## Development Rules

- Preserve existing public APIs unless the task explicitly requires change.
- Keep edits focused and avoid unrelated refactors or formatting churn.
- Prefer deterministic, testable behavior and explicit error handling.
- Keep provider behavior consistent through shared abstractions rather than
  per-provider special cases when possible.
- Do not commit generated artifacts from `build/`, `dist/`, cache folders, or
  egg-info folders.

## STATUS.md Mandatory Upkeep

`STATUS.md` must be kept up to date at all times.

After every non-trivial change (bug fix, feature, refactor, release update,
test strategy change, or meaningful investigation result), update `STATUS.md`
in the same work session.

`STATUS.md` is required to be a complete project status report. At minimum it
must include:

- Current state and active focus
- What changed recently
- Validation performed (tests/checks run) and notable gaps
- Known risks, limitations, or open issues
- Next prioritized steps

Timestamp requirement (mandatory):

- Include a top-level timestamp line in this exact format:
  `Last updated: YYYY-MM-DD HH:MM`
- Use local wall-clock time.
- Never leave the timestamp stale when the report contents are changed.

Agents must not mark work complete until `STATUS.md` accurately reflects the
current project status.

## Validation

Run the narrowest checks that cover the change. For most Python changes:

```bash
pytest -q
```

For packaging or release-affecting changes, also run:

```bash
python -m build
```

Document what was run and what was not run in `STATUS.md`.

## Documentation Expectations

When behavior or public APIs change, update impacted docs in the same change:

- `README.md`
- `docs/API.md`
- `docs/USAGE.md`
- release notes/changelog files when release-relevant
- `STATUS.md`

## Git Hygiene

- Check `git status --short` before and after edits.
- Do not revert user-authored changes unless explicitly requested.
- Stage only intended file paths when the worktree is mixed.
- Commit/push only when explicitly requested by the user.