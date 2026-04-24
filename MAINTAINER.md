# MAINTAINER: Release and publish instructions

This file contains detailed release and publishing instructions for maintainers.
It is intended for repository owners and team members performing releases.

> NOTE: Consumers and package users do not need these details. See `RELEASE.md`
> (consumer-facing) or the `README.md` for install/usage instructions.

---

## Build

Install build tools and create distributions:

```bash
python -m pip install --upgrade build twine
python -m build
```

## Upload to TestPyPI

Preferred: use the GitHub Actions workflow
`.github/workflows/publish-testpypi.yml` (OIDC trusted publishing).

If pip can't find the version via the simple index, download the wheel from
TestPyPI's "Files" page and install it locally. Example:

```bash
# Visit https://test.pypi.org/project/modelito/<version>/#files and download the
# appropriate wheel file, then:
python -m pip install --no-deps /path/to/modelito-<version>-py3-none-any.whl
```

## Verify install from TestPyPI

Create a fresh venv and attempt to install the released version:

```bash
python3 -m venv .venv_testpypi
. .venv_testpypi/bin/activate
python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple modelito==<version>
python - <<'PY'
import modelito
print('installed', modelito.__version__)
PY
```

## Upload to PyPI

Preferred: push a version tag (`v*`) so `.github/workflows/publish.yml`
publishes via OIDC trusted publishing.

## Pre-release checklist

Before tagging a release:

1. Ensure required CI checks pass on `main` (`Lint` + unit matrix).
2. Trigger the self-hosted Ollama integration workflow (or apply
   `run-integration` on the release PR) and confirm pass.
3. Verify build metadata locally with:

```bash
python -m build
python -m twine check dist/*
```

## Verify install from PyPI

```bash
python3 -m venv .venv_pypi
. .venv_pypi/bin/activate
python -m pip install modelito==<version>
python - <<'PY'
import modelito
print('installed', modelito.__version__)
PY
```

## Notes

- Keep trusted publishing configured for both TestPyPI and PyPI in repository
  settings.
- TestPyPI's `simple` index may show older cached versions; installing the
  wheel directly works if index resolution fails.

## Links

- TestPyPI: https://test.pypi.org/
- PyPI: https://pypi.org/
