modelito
=======

Modelito is a compact, dependency-light Python library that provides provider-
agnostic abstractions and connectors for large language models (LLMs). It
offers lightweight shims for OpenAI, Claude, Gemini and local Ollama
deployments, plus utilities for token counting, timeout estimation, and small
helpers to manage Ollama servers when needed. The library is designed for easy
integration into applications and CI pipelines.

Quick start
-----------

Install in editable mode for development (install optional extras as needed):

```sh
pip install -e .[dev]
pip install -r dev-requirements.txt

# Optional extras
pip install -e .[ollama,tokenization,openai,anthropic]
```

Run tests:

```sh
pytest -q
```

Build and install
-----------------

To build a source distribution and wheel locally:

```sh
python -m pip install --upgrade build
python -m build
```

Install from the built wheel:

```sh
pip install dist/modelito-0.2.3-py3-none-any.whl
```

See the `docs/` folder for more details on calibration and migration.

Providers
---------

This package provides compatibility shims and small, dependency-light
implementations for common provider interfaces. When optional extras are
installed the package will attempt to use real SDK clients; otherwise the
shims provide safe offline-friendly fallbacks suitable for testing.

Provided shims and utilities:

- `OllamaProvider` — HTTP-aware provider that will call a local Ollama
	HTTP API when available. If the HTTP API is unavailable the provider will
	attempt to use the local Ollama CLI as a best-effort fallback before
	returning a deterministic stub useful for tests and examples.
- `GeminiProvider`, `GrokProvider` — lightweight shims.
- `OpenAIProvider`, `ClaudeProvider` — will use the official SDKs when
	installed, falling back to deterministic behavior otherwise.

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

