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
