# modelito status report

Last updated: 2026-05-06 09:07

## Current state

modelito remains a compact, provider-agnostic Python library with optional
SDK integrations and strong local/offline fallback behavior.

Current package metadata version is `1.2.1` (`pyproject.toml`).

Repository health after implementing all previously listed remediation steps:

- Runtime tests pass locally.
- Lint checks pass locally.
- Packaging build succeeds locally.
- Type checking now passes cleanly.
- Previously identified docs/release-history inconsistencies were remediated.

## Current focus

- Prepare and publish release `v1.2.1` (commit, tag, push, GitHub release).
- Keep release artifacts (`CHANGELOG.md`, `RELEASE.md`, `STATUS.md`) aligned.

## Audit scope

Comprehensive code and docs audit completed across:

- Package/runtime code in `modelito/`
- Tests and CI workflows
- User and API documentation (`README.md`, `docs/`)
- Release/versioning artifacts (`pyproject.toml`, `CHANGELOG.md`, release notes)
- Agent governance files (`AGENTS.md`, `STATUS.md`)

## Remediation summary

All six previously listed next steps have been implemented.

Completed items:

1. Fixed package version fallback mismatch.
   - `modelito/__init__.py` fallback now uses `1.2.0` instead of `1.0.0`.

2. Fixed incorrect connector usage docs.
   - Updated `docs/USAGE.md` to show `OllamaConnector(provider=provider)`.

3. Resolved API export/documentation mismatch.
   - Exported `estimate_remote_timeout_details` from `modelito/__init__.py`.
   - Updated `docs/API.md` package export section accordingly.

4. Fixed mypy failure in normalization helper.
   - Refactored `_normalize_model_item` local variable usage in
     `modelito/normalization.py` to avoid incompatible assignment typing.

5. Normalized release history structure.
   - Reordered and clarified `CHANGELOG.md` with a current `1.2.0` section and
     explicit historical backfill note.

6. Implemented archival strategy for old release notes.
   - Marked `RELEASE_NOTES_v1.0.3.md` and `RELEASE_ANNOUNCEMENT_v1.0.3.md` as
     archived historical records.
   - Added archival policy note in `RELEASE.md`.

Additional quality cleanup completed:

- Removed duplicate `OllamaProvider` bullet in `docs/API.md`.

## Validation

Validation executed during this audit:

- `pytest -q` -> 91 passed, 3 skipped.
- `ruff check .` -> all checks passed.
- `mypy modelito --ignore-missing-imports` -> success (no issues found).
- `python -m build` -> sdist and wheel build completed successfully.

Observed non-failing warning:

- `pytest-asyncio` deprecation warning about unset
  `asyncio_default_fixture_loop_scope`.

## Code/docs consistency assessment

Confirmed consistent:

- Core API narratives in `README.md` generally match implementation behavior.
- CI workflow and testing docs are largely aligned on integration gating.
- Packaging metadata and build system operate correctly.

Outstanding minor observations:

- `pytest-asyncio` emits a deprecation warning for unset
  `asyncio_default_fixture_loop_scope` in local runs.
- CI intentionally excludes integration tests by path (`--ignore`) instead of
  marker selection; behavior is correct and documented.

## Next prioritized steps

1. Complete publish flow for `v1.2.1` (commit, tag, push, GitHub release).
2. Optionally set `asyncio_default_fixture_loop_scope` in `pytest.ini` to
   silence the deprecation warning proactively.
3. Continue backfilling detailed changelog entries between `1.0.6` and `1.2.0`
   from release records.