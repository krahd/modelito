# Release checklist

## Before tagging

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

## Before publishing

- Confirm the tag version matches `pyproject.toml`.
- Verify the PyPI project-side trusted publisher settings for `krahd/modelito`.
- Confirm the GitHub Actions publish workflow is targeting the `pypi` environment.

## After publishing

- Check the uploaded release files on PyPI.
- Confirm the release tag and published version match.
- Update `STATUS.md` if the release state changed.