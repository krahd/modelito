# Release checklist

## Before tagging

- Run `pytest -q`.
- Run `ruff check .`.
- Run `mypy modelito --ignore-missing-imports`.
- Run `python -m build`.
- Run `python -m twine check dist/*`.
- Run `python -c "import modelito; print(modelito.__version__)"`.
- Verify the `pyproject.toml` version.
- Update `CHANGELOG.md` if needed.
- Update `STATUS.md`.
- Ensure `STATUS.md` uses `Last updated: YYYY-MM-DD HH:MM`.
- Confirm Ollama integration tests are intentionally gated and not part of default hosted CI.

## PyPI trusted publishing

- Verify PyPI project-side trusted publisher settings:
  - repository: `krahd/modelito`
  - workflow: `publish.yml`
  - environment: `pypi`
- Do not use PyPI API tokens for trusted publishing.
- Ensure the release tag matches `pyproject.toml`.

## Tag and publish

- `git status`
- `git tag vX.Y.Z`
- `git push origin vX.Y.Z`

Then monitor the GitHub Actions `Publish` workflow and verify that the tag/version gate, build, `twine check`, wheel import check, and PyPI publish all pass.

## After publishing

- Verify the PyPI project page.
- Install from PyPI in a clean environment:

```sh
python -m venv /tmp/modelito-release-check
. /tmp/modelito-release-check/bin/activate
python -m pip install --upgrade pip
python -m pip install modelito
python -c "import modelito; print(modelito.__version__)"
```

- Optionally test `python -m modelito doctor`.
- Optionally test `modelito-serve --help` with `modelito[serve]` installed.

## Deferred release-adjacent work

- Ollama raw passthrough/tool-call preservation remains deferred.
- Continue applying the provider-addition policy in `docs/ARCHITECTURE.md`.
- Keep FastAPI/Uvicorn optional under `[serve]`.
