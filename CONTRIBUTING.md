Integration runs and self-hosted gating
====================================

This project runs fast unit tests on GitHub-hosted runners, and keeps
long-running or environment-dependent integration tests gated to
self-hosted runners to avoid ad-hoc installs and protect resources.

How to trigger the gated integration workflow

- Manual dispatch: open the Actions tab and run the "Integration — Ollama"
  workflow via "Run workflow" (workflow_dispatch).

- From a pull request: add the label `run-integration` to the PR. The
  workflow will be allowed to run for PRs that carry that label.

Notes for maintainers

- The integration workflow is configured to run on runners labeled
  `self-hosted` + `linux`. Ensure your self-hosted runner carries those
  labels.
- By default the integration workflow sets `OLLAMA_ALLOW_INSTALL=0` to
  avoid running installers automatically. If you need automatic
  installation on your own runner, set the environment variable to
  `1` in your runner environment or modify the workflow.

Safety considerations

- Keep secrets and keys out of workflows that run on community-hosted
  or untrusted runners. Use `environments` and required reviewers for
  sensitive deployments.
