Ollama Install Helpers
======================

This document describes the platform install helper functions provided in `modelito.ollama_service`.

- `detect_install_method(platform_name: Optional[str] = None)`
  - Returns the preferred install backend for the current platform.
  - Current choices are:
    - macOS: `brew` when Homebrew is present, otherwise script fallback.
    - Linux: `apt` when `apt-get` is present, otherwise script fallback.
    - Windows: `choco` when Chocolatey is present, otherwise PowerShell script fallback.

- `install_command_for_current_platform(platform_name: Optional[str] = None)`
  - Returns a tuple `(command_list, display_string)` suitable for running the platform-specific installer.
  - On Windows it returns either a `choco install ollama -y` command or a `powershell.exe` invocation referencing the `install.ps1` script.
  - On Linux it returns either an `apt-get install -y ollama` flow or a `/bin/sh -lc "curl ... | sh"` style invocation.
  - On macOS it returns either `brew install ollama` or the script fallback.

- `install_ollama(allow_install: bool = True, method: Optional[str] = None, timeout: float = 30.0)`
  - Attempts to ensure an `ollama` binary is available on the PATH.
  - Behavior:
    - If `ollama` is already present, returns `True` immediately.
    - When `method is None`, the helper auto-detects a preferred backend via `detect_install_method()`.
    - On macOS it prefers `brew install ollama`.
    - On Linux it prefers `apt-get install -y ollama` when `apt-get` is available.
    - On Windows it prefers `choco install ollama -y` when Chocolatey is available.
    - Falls back to the official install script when package-manager installation is not appropriate or fails.
    - When `allow_install` is False, the function will not attempt to run installers and returns `False` if binary not found.
  - NOTE: The function executes external commands; tests and CI should mock subprocess execution. It will not start the Ollama service by default when using the official script (the function sets `OLLAMA_NO_START=1`).

- `install_service(reinstall: bool = False)`
  - A thin wrapper that runs the platform installer command and returns `(returncode, combined_output)` where `combined_output` contains stdout+stderr.
  - This is useful for diagnostic output in higher-level tooling.

Testing

- Unit tests for these helpers are provided in `tests/test_install_helpers.py`. The tests mock subprocess run calls and `get_ollama_binary` to avoid performing real installs.

Safety

- These helpers run external installer scripts; do not call them on shared CI runners without appropriate gating. Prefer mocking in automated tests.

Examples

- macOS (preferred using Homebrew):

  ```sh
  brew install ollama
  ```

  If you prefer the official installer script (or Homebrew isn't available):

  ```sh
  export OLLAMA_NO_START=1
  curl -fsSL https://ollama.com/install.sh | sh
  ```

- Linux (generic):

  ```sh
  export OLLAMA_NO_START=1
  curl -fsSL https://ollama.com/install.sh | sh
  ```

- Windows (PowerShell):

  ```powershell
  powershell.exe -NoExit -ExecutionPolicy Bypass -Command "irm https://ollama.com/install.ps1 | iex"
  ```

Running tests and CI notes

- Local unit tests (recommended):

  ```sh
  pytest -q -m 'not integration'
  ```

- Integration tests (require a running Ollama or explicit allow flags):

  ```sh
  # Enable integration marker tests; set allow flags as needed
  RUN_OLLAMA_INTEGRATION=1 ALLOW_OLLAMA_INSTALL=1 pytest -q -m integration
  ```

- CI behaviour: the repository's unit `CI` workflow runs `pytest -q -m 'not integration'` so that integration tests are executed only by gated integration workflows (manual or self-hosted runners). The gated workflows will refuse to run ad-hoc installers on GitHub-hosted runners; they must be run on self-hosted runners or via a manual process with appropriate permissions.
