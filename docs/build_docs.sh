#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip
python -m pip install -r docs/requirements.txt

echo "Building docs into docs/build/"
sphinx-build -b html docs/source docs/build
echo "Docs built: docs/build/index.html"
