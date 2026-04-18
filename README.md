modelito
=======

Lightweight LLM provider abstractions and connectors extracted from the
`mail_summariser` project. This repository is a minimal scaffold to publish
`modelito` as a reusable package.

Quick start
-----------

Install in editable mode for development:

```sh
pip install -e .
pip install -r dev-requirements.txt
```

Run tests:

```sh
pytest -q
```

See the `docs/` folder for more details on calibration and migration.

Providers
---------

This package provides lightweight, compatibility shims for a few common
provider interfaces (for use in tests and simple local workflows):

- `OllamaProvider` (default compatibility shim)
- `GeminiProvider` (minimal shim)
- `GrokProvider` (minimal shim)

License / AS IS
---------------

This software is provided "AS IS" and without warranties of any kind. See
the included `LICENSE` file for the full MIT license text.

CI / Integration Tests
----------------------

This repository includes a GitHub Actions workflow at `.github/workflows/ci.yml`.
The workflow runs `mypy` and the unit test suite on push and pull requests.

Ollama integration tests are intentionally gated and will only run when you
explicitly enable them. To run integration tests locally or in CI set the
environment variable `RUN_OLLAMA_INTEGRATION=1`. Additional optional flags:

- `ALLOW_OLLAMA_INSTALL=1` — permit the integration tests to attempt installing Ollama when missing.
- `ALLOW_OLLAMA_DOWNLOAD=1` — permit downloading remote models during integration tests.
- `ALLOW_OLLAMA_UPDATE=1` — permit running update flows during integration tests.

Example (local):

```sh
RUN_OLLAMA_INTEGRATION=1 pytest tests/test_ollama_integration.py -q
```

