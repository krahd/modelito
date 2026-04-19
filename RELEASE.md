# Release: modelito 0.2.2

Date: 2026-04-18

This file documents the commands used to test TestPyPI and publish `modelito` v0.2.2.

## Build

Install build tools and create distributions:

```bash
python -m pip install --upgrade build twine
python -m build
```

## Upload to TestPyPI

Use a token stored in `TESTPYPI_API_TOKEN`:

```bash
TWINE_USERNAME="__token__" TWINE_PASSWORD="$TESTPYPI_API_TOKEN" \
  python -m twine upload --repository testpypi dist/*
```

If pip can't find the version via the simple index, download the wheel from
TestPyPI's "Files" page and install it locally. Example:

```bash
# Visit https://test.pypi.org/project/modelito/0.2.2/#files and download the
# appropriate wheel file, then:
python -m pip install --no-deps /path/to/modelito-0.2.2-py3-none-any.whl
```

## Verify install from TestPyPI

Create a fresh venv and attempt to install the released version:

```bash
python3 -m venv .venv_testpypi
. .venv_testpypi/bin/activate
python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple modelito==0.2.2
python - <<'PY'
import modelito
print('installed', modelito.__version__)
PY
```

## Upload to PyPI

Use a token stored in `PYPI_API_TOKEN`:

```bash
TWINE_USERNAME="__token__" TWINE_PASSWORD="$PYPI_API_TOKEN" \
  python -m twine upload dist/modelito-0.2.2*
```

## Verify install from PyPI

```bash
python3 -m venv .venv_pypi
. .venv_pypi/bin/activate
python -m pip install modelito==0.2.2
python - <<'PY'
import modelito
print('installed', modelito.__version__)
PY
```

## Notes

- Ensure `TESTPYPI_API_TOKEN` and `PYPI_API_TOKEN` are exported in your environment before running `twine upload`.
- Use the `TWINE_USERNAME="__token__" TWINE_PASSWORD="$TOKEN"` pattern for token authentication.
- TestPyPI's `simple` index may show older cached versions; installing the wheel directly works if index resolution fails.

## Links

- TestPyPI: https://test.pypi.org/project/modelito/0.2.2/
- PyPI:     https://pypi.org/project/modelito/0.2.2/
