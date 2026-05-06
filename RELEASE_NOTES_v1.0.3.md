# Release v1.0.3

Archived historical release record. Current release status is tracked in
`RELEASE.md`, `CHANGELOG.md`, and `STATUS.md`.

Release date: 2026-04-19

Summary
-------
- Bump package version to `1.0.3`.
- Performed a deeper code/docs audit and added `AUDIT_REPORT.md`.
- CI: tightened `scripts/check_no_legacy_dicts.py` to only scan docs/examples/tests.
- Fix: `modelito/openai.py` deterministic fallback now uses flattened messages; improves consistency.
- Removed saved local CI run logs from `run_logs/`.

Published artifacts
-------------------
- Git tag: `v1.0.3`
- GitHub Release: https://github.com/krahd/modelito/releases/tag/v1.0.3
- PyPI: https://pypi.org/project/modelito/1.0.3/

Notes for reviewers
-------------------
- All unit tests, linters, and mypy checks passed locally prior to publishing.
- Integration/provider tests require provider credentials and a self-hosted runner; these were not run here.

If approved, merge to `main` to keep the release branch in sync with the repository release record.
