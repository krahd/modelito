# Release checklist

## Before tagging

- Update `pyproject.toml` version.
- Update `CHANGELOG.md` if needed.
- Update `STATUS.md`.
- Ensure `STATUS.md` uses the timestamp line format `Last updated: YYYY-MM-DD HH:MM` at top and bottom.
- Confirm default CI intentionally excludes gated Ollama integration tests.

Run the release validation set:

```bash
python scripts/check_no_legacy_dicts.py
ruff check .
mypy modelito --ignore-missing-imports
pytest -q
python -m build
python -m twine check dist/*
python -c "import modelito; print(modelito.__version__)"
```

## Trusted publishing

- PyPI publishing uses GitHub Actions trusted publishing, not a PyPI API token.
- Workflow: `.github/workflows/publish.yml`.
- Environment: `pypi`.
- PyPI project-side trusted publisher must match:
	- repository: `krahd/modelito`
	- workflow: `publish.yml`
	- environment: `pypi`
- Release tags must use `vX.Y.Z`.
- The publish workflow validates tag version against `pyproject.toml`.

## Before publishing

- Confirm the tag version matches `pyproject.toml`.
- Verify the PyPI project-side trusted publisher settings for `krahd/modelito`.
- Confirm the GitHub Actions publish workflow is targeting the `pypi` environment.

## Tag and publish

```bash
git status
git tag vX.Y.Z
git push origin vX.Y.Z
```

## After publishing

- Check the uploaded release files on PyPI.
- Confirm the release tag and published version match.
- Update `STATUS.md` if the release state changed.

Run clean environment install verification:

```bash
python -m venv /tmp/modelito-release-check
. /tmp/modelito-release-check/bin/activate
python -m pip install --upgrade pip
python -m pip install modelito
python -c "import modelito; print(modelito.__version__)"
```

Optional checks:

```bash
python -m modelito doctor
modelito-doctor --help
python -m pip install "modelito[serve]"
modelito-serve --help
```

## Deferred release-adjacent work

- Keep Ollama raw passthrough docs/tests aligned with current `/v1/chat/completions` behaviour.
- Continue applying provider-addition policy in `docs/ARCHITECTURE.md`.
- Keep FastAPI/Uvicorn optional under `[serve]`.
- PyPI project-side trusted publisher settings must be verified externally before tagging.