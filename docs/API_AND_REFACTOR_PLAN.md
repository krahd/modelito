API & Refactor Plan
====================

Goal
----
Design a small, stable public API for `modelito` so downstream projects
can depend on a minimal surface (providers, connectors, tokenizer, timeout).

Public API (proposed)
---------------------
- `modelito.tokenizer.count_tokens(text: str) -> int`
- `modelito.timeout.estimate_remote_timeout(model_name, input_tokens, concurrency) -> int`
- `modelito.connector.OllamaConnector` (constructor + `add_to_history`, `build_prompt`, `send_sync`, `trim_history_by_tokens`)
- `modelito.config.load_config` and `parse_host_port`
- `modelito.ollama_service.endpoint_url` and `server_is_up`
- Exceptions: `modelito.exceptions.LLMProviderError`

Refactor steps
--------------
1. Audit current modules and mark public symbols in `__all__`.
2. Move internal helpers behind a `_` prefix where not intended for public use.
3. Add small adapter shims for downstream APIs that expect previous function names.
4. Add unit tests that exercise only the public API surface.

Compatibility
-------------
- Provide lightweight shims for `ensure_ollama_running` and any name changes.
- Document breaking changes in `CHANGELOG.md` and `docs/MIGRATION.md`.

Tests & CI
---------
- Ensure CI runs the public-API unit tests on multiple Python versions.
- Add an optional integration job gated by `RUN_OLLAMA_INTEGRATION=1`.

CI & Integration
----------------

Add a GitHub Actions workflow to run static checks (`mypy`) and unit tests.
Integration tests that exercise the Ollama lifecycle are gated behind the
`RUN_OLLAMA_INTEGRATION` environment variable (or via the workflow_dispatch
input) to avoid accidental runs in CI.

Release plan
------------
1. Cut a TestPyPI release for downstream validation.
2. Run downstream integration tests in dependent repos.
3. Publish to PyPI and update downstream requirements to a pinned RC.

Next actions
------------
- Implement `__all__` and add public-API unit tests.
-- Create migration PRs for downstream projects to switch to the package.
