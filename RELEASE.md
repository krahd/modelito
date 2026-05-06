# Releases

Note: historical release notes that are no longer the current release focus are
kept for traceability and treated as archived records (for example,
`RELEASE_NOTES_v1.0.3.md` and `RELEASE_ANNOUNCEMENT_v1.0.3.md`).

This file is a short, consumer-facing release summary. For detailed
release and publishing instructions (maintainers only), see
`MAINTAINER.md`.

Latest release: see the PyPI project page:

- https://pypi.org/project/modelito/

Installing the latest released version:

```bash
pip install modelito
```

Install a specific version:

```bash
pip install modelito==1.2.1
```

If you need a pre-release or testing artifact from TestPyPI (for previewing
changes), use the TestPyPI index. Note: packages on TestPyPI are not stable
releases and should only be used for testing:

```bash
python -m pip install --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple modelito==<version>
```

For maintainers: the full release and upload steps are in `MAINTAINER.md`.
