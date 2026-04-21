**Ollama Install Helpers**

This document describes the platform install helper functions provided in `modelito.ollama_service`.

- `install_command_for_current_platform(platform_name: Optional[str] = None)`
  - Returns a tuple `(command_list, display_string)` suitable for running the platform-specific installer.
  - On Windows it returns a `powershell.exe` invocation referencing the `install.ps1` script.
  - On Unix-like platforms it returns a `/bin/sh -lc "curl ... | sh"` style invocation.

- `install_ollama(allow_install: bool = True, method: Optional[str] = None, timeout: float = 30.0)`
  - Attempts to ensure an `ollama` binary is available on the PATH.
  - Behavior:
    - If `ollama` is already present, returns `True` immediately.
    - On macOS, when `method=="brew"` (or `method is None` and `brew` is available), a `brew install ollama` is attempted first.
    - Falls back to the official install script (cross-platform) if package-manager installation is not appropriate or fails.
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
