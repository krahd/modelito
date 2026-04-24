# Audit Report — Codebase, Docs, and CI/Workflow Review

Date: 2026-04-24

## High-level understanding

Modelito is intentionally a compact, dependency-light compatibility layer for
LLM provider access. The project optimizes for:

- **Provider-agnostic APIs** with lightweight protocol surfaces.
- **Deterministic/offline-friendly fallback behavior** when SDKs/services are
  unavailable.
- **Practical CI safety** by gating external-service and side-effectful tests.

This philosophy is consistent across `README.md`, test structure, and provider
implementations.

## Current status assessment

### Strengths

- Broad provider and adapter coverage in tests and docs.
- Clear separation between unit/smoke and integration test intent.
- Maintainer-oriented release docs and publish workflows are present.

### Key issues identified (and fixed)

1. **Redundant/overlapping workflows**
   - `smoke-tests.yml` and `integration-tests.yml` overlapped with `ci.yml` and
     increased maintenance burden.
2. **Integration workflow duplication in `ci.yml`**
   - Integration checks were duplicated across jobs and included an inefficient
     matrix setup that could repeat provider checks unnecessarily.
3. **Marker consistency risk**
   - Integration tests under `tests/integration/` did not have explicit
     `@pytest.mark.integration` markers, which made marker-driven runs brittle.

## Improvements implemented in this audit pass

- Consolidated CI behavior in `.github/workflows/ci.yml`:
  - Maintains lint + mypy + unit tests on standard hosted runners.
  - Uses path-based exclusion for integration tests in default unit job.
  - Keeps docs builds on non-PR runs.
  - Keeps Ollama integration in a separate self-hosted workflow.
- Deleted unnecessary workflows:
  - `.github/workflows/smoke-tests.yml`
  - `.github/workflows/integration-tests.yml`
- Added explicit `pytest.mark.integration` to all tests in `tests/integration/`.
- Updated docs to match actual CI behavior:
  - `README.md`
  - `TESTING.md`

## Recommended next steps

1. Add branch protection to require `lint`, `test`, and `docs` jobs from `CI`.
2. Consider enforcing formatting checks (e.g., `black --check .`) in `lint`.
3. Consider moving provider integration checks to a dedicated scheduled workflow
   if runtime costs on PRs become high.
4. Add a short architecture note documenting the explicit tradeoff between
   deterministic fallbacks vs. strict SDK hard-fail behavior.
