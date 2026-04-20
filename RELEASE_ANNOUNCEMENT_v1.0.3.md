# modelito v1.0.3 — Audit and small fixes

Release date: 2026-04-19

Summary
-------
modelito v1.0.3 focuses on a deeper repository audit, CI hardening, and a few small, user-facing fixes.

Highlights
----------
- Audit: Performed a deeper code & docs audit and added `AUDIT_REPORT.md` with findings and recommendations.
- CI: `scripts/check_no_legacy_dicts.py` now targets only docs/examples/tests to avoid false positives in code.
- Fix: `modelito/openai.py` deterministic fallback now uses the flattened messages list for consistent summarization.
- Packaging & release: bumped package to `1.0.3` and published to PyPI.
- Tooling: unit tests, `ruff`, and `mypy` ran clean in the release validation.

Breaking changes
----------------
None. Backward-compatible changes only.

Upgrade
-------
Run one of these commands to upgrade:

```bash
pip install -U modelito
# or pin to this release
pip install modelito==1.0.3
```

Links
-----
- GitHub Release: https://github.com/krahd/modelito/releases/tag/v1.0.3
- PyPI: https://pypi.org/project/modelito/1.0.3/
- Audit report: https://github.com/krahd/modelito/blob/main/AUDIT_REPORT.md

Notes
-----
- Provider integration tests (OpenAI/Anthropic/Ollama) require credentials and a self-hosted runner; these were not executed in this release run.
- Report regressions or issues at https://github.com/krahd/modelito/issues/new

Thank you to everyone who contributed and tested this release.
