#!/usr/bin/env bash
set -euo pipefail

## See MAINTAINER.md for full release and publishing instructions.
## This script is a convenience wrapper for building and uploading packages.

OUTDIR="dist"
rm -rf "$OUTDIR"
python -m pip install --upgrade build twine
python -m build --sdist --wheel

if [ -n "${TEST_PYPI_TOKEN-}" ]; then
  echo "Uploading to TestPyPI..."
  python -m twine upload --repository testpypi -u __token__ -p "$TEST_PYPI_TOKEN" dist/*
else
  echo "Built packages are in dist/; set TEST_PYPI_TOKEN to upload to TestPyPI"
fi
