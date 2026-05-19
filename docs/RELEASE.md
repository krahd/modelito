# Release Checklist

## Before tagging

- Run `pytest -q`.
- Run `ruff check .`.
- Run `mypy modelito --ignore-missing-imports`.
- Run `python -m build`.
- Run `python -m twine check dist/*`.
- Run `python -c "import modelito; print(modelito.__version__)"`.
- Verify `pyproject.toml` version.
- Update `CHANGELOG.md` if needed.
- Update `STATUS.md`.

## PyPI trusted publishing

- Verify PyPI project-side trusted publisher settings:
	- repository: `krahd/modelito`
	- workflow: `publish.yml`
	- environment: `pypi`
- Do not use PyPI API tokens for trusted publishing.
- Ensure the release tag matches `pyproject.toml`.

## Tagging

- Create a tag like `v1.4.4`.
- Push the tag.
- Monitor the GitHub Actions publish workflow.

## After publishing

- Verify the PyPI project page.
- Install from PyPI in a clean environment.
- Import `modelito`.
- Optionally run `modelito-serve --help`.
