# Running tests and CI smoke tests

Local steps to run quick smoke checks and to mirror CI behavior:

1. Create and activate a virtualenv (optional but recommended):

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install the package in editable mode and dev requirements:

```bash
python -m pip install -U pip
python -m pip install -e .
python -m pip install -r dev-requirements.txt
```

3. Run only the smoke tests (fast):

```bash
pytest -q -m smoke
```

4. Run the import check:

```bash
pytest -q tests/test_import_modelito.py
```

Notes:
- CI runs the consolidated workflow in `.github/workflows/ci.yml`, which installs the package and runs hosted unit tests (including smoke tests) while excluding `tests/integration/` by default.  
- We limit test collection to `tests/` using `pytest.ini` to avoid executing external test suites under `_external/`.  
- To run the full test suite locally:

```bash
pytest -q
```

Integration tests
-----------------

Integration tests that exercise a local `ollama` installation are marked with the `integration` pytest marker and are skipped by default. To run them you must explicitly enable them and accept any side-effects (installing or starting `ollama`). Example:

```bash
# Run only the integration tests (may attempt to install/start ollama)
RUN_OLLAMA_INTEGRATION=1 pytest -q -m integration

# Optionally allow installation/update/download steps (use with caution)
RUN_OLLAMA_INTEGRATION=1 ALLOW_OLLAMA_INSTALL=1 ALLOW_OLLAMA_UPDATE=1 ALLOW_OLLAMA_DOWNLOAD=1 pytest -q -m integration
```

CI note: integration tests are intentionally excluded from default hosted CI to keep pull-request feedback fast and side-effect free; use the self-hosted integration workflow for CI-based integration coverage.
