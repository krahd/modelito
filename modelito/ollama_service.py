"""Small Ollama HTTP helpers (lightweight) used by the calibration tool.

This module intentionally provides only thin helpers (endpoint builder and
server liveness check) so the package can be used without requiring full
external lifecycle helpers.
"""

from __future__ import annotations

import socket
from urllib.request import urlopen
from urllib.request import Request
import time
import asyncio
import shutil
import subprocess
import os
import sys
import shlex
from typing import Optional, List, Dict, Any, Callable, Iterable, cast
from pathlib import Path
import json
import logging
import argparse


ROOT = Path(__file__).resolve().parents[1]
UNIX_INSTALL_URL = "https://ollama.com/install.sh"
WINDOWS_INSTALL_URL = "https://ollama.com/install.ps1"
DEFAULT_URL = "http://127.0.0.1"
DEFAULT_PORT = 11434

# Module logger
logger = logging.getLogger(__name__)


def endpoint_url(host: str, port: int, path: str = "/api/generate") -> str:
    """Return a fully-qualified endpoint URL for the Ollama HTTP API.

    Args:
        host: Host string; may include scheme (e.g. "http://127.0.0.1").
        port: TCP port to use when the host does not already include one.
        path: API path to append (defaults to "/api/generate").

    Returns:
        A string containing the full URL to the requested API path.
    """
    h = host.rstrip("/")
    # if host already contains a port, don't append
    if ":" in h.split("/")[2] if "/" in h else ":" in h:
        return f"{h}{path}"
    return f"{h}:{port}{path}"


def server_is_up(host: str, port: int) -> bool:
    """Return True if the Ollama HTTP API or TCP port is reachable.

    The function first attempts an HTTP request to the root path. If that
    fails it will attempt a TCP connect to the provided host/port as a
    fallback. This avoids depending on an HTTP server response for simple
    liveness checks.

    Args:
        host: Host string (may include scheme).
        port: TCP port number to check.

    Returns:
        ``True`` if either an HTTP request or TCP connect succeeds, else
        ``False``.
    """
    try:
        url = endpoint_url(host, port, "/")
        with urlopen(url, timeout=2) as _:
            return True
    except Exception:
        # Try TCP connect as a fallback
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)
            s.connect((host.replace("http://", "").replace("https://", ""), port))
            s.close()
            return True
        except Exception:
            return False


def ensure_ollama_running(host: str = DEFAULT_URL, port: int = DEFAULT_PORT, auto_start: bool = False, start_args: Optional[List[str]] = None, timeout: float = 10.0) -> bool:
    """Ensure an Ollama server is reachable at `host:port`.

    If `auto_start` is True and the `ollama` binary is available on PATH,
    attempt to start `ollama serve` in a detached process and wait up to
    `timeout` seconds for the server to become available.

    Returns True if the server is reachable, False otherwise.
    """
    # Delegate to the verbose variant and return only the boolean result.
    ok, _msg = ensure_ollama_running_verbose(
        host=host, port=port, auto_start=auto_start, start_args=start_args, timeout=timeout)
    return bool(ok)


def ensure_ollama_running_verbose(host: str = DEFAULT_URL, port: int = DEFAULT_PORT, auto_start: bool = False, start_args: Optional[List[str]] = None, timeout: float = 10.0) -> tuple[bool, str]:
    """Ensure an Ollama server is reachable and return (success, message).

    The verbose variant returns a human-readable message describing the
    outcome which is useful for UI and logging flows.
    """
    # Quick check: server already up
    try:
        if server_is_up(host, port):
            return True, f"Ollama already running at {host}:{port}"
    except Exception:
        pass

    if not auto_start:
        return False, "Ollama not running and auto_start is disabled"

    # Ensure we have an executable to start
    try:
        _ = resolve_ollama_command()
    except FileNotFoundError:
        return False, "ollama CLI not found on PATH"

    # Build host env string expected by the CLI
    host_env = f"{host.replace('http://', '').replace('https://', '')}:{port}"

    # Attempt to start detached serve using the platform helper
    try:
        start_detached_ollama_serve(host_env, start_args=start_args)
    except FileNotFoundError as exc:
        return False, f"Failed to launch ollama serve: {exc}"
    except Exception as exc:
        return False, f"Failed to launch ollama serve: {exc}"

    # Wait for the server to become ready
    deadline = time.time() + float(timeout)
    while time.time() < deadline:
        try:
            if server_is_up(host, port):
                return True, f"Ollama is ready at {host}:{port}"
        except Exception:
            pass
        time.sleep(0.5)

    return False, f"Timeout waiting for ollama serve at {host}:{port}"


def get_ollama_binary() -> Optional[str]:
    """Return the path to the ``ollama`` binary if available on PATH.

    Returns:
        The path to the executable as a string or ``None`` if not found.
    """
    return shutil.which("ollama")


def install_ollama(allow_install: bool = False, method: Optional[str] = None, timeout: float = 600.0) -> bool:
    """Attempt to install the ``ollama`` CLI using a supported installer.

    This helper only performs an installation when ``allow_install`` is
    ``True``. On macOS the default installer is Homebrew when available.

    Args:
        allow_install: When ``True`` permit attempting an installation.
        method: Optional installer method (e.g. ``"brew"``).
        timeout: Timeout for installer subprocesses in seconds.

    Returns:
        ``True`` when ``ollama`` is present after the call, else ``False``.
    """
    if get_ollama_binary():
        return True
    if not allow_install:
        return False

    try:
        import sys

        # Prefer platform-specific package manager when appropriate, but
        # fall back to the official install script which is cross-platform.
        if sys.platform == "darwin":
            if method == "brew" or (method is None and shutil.which("brew")):
                try:
                    subprocess.run(["brew", "install", "ollama"], check=True,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout)
                    return get_ollama_binary() is not None
                except Exception:
                    # fall through to script fallback
                    pass
            # fallback to the official script installer
            cmd, _ = install_command_for_current_platform()
            try:
                subprocess.run(cmd, cwd=str(ROOT), text=True,
                               capture_output=True, check=False, timeout=timeout)
                return get_ollama_binary() is not None
            except Exception:
                return False

        # For other UNIX-like systems prefer the official script; package
        # managers may not provide an `ollama` package.
        cmd, _ = install_command_for_current_platform()
        try:
            subprocess.run(cmd, cwd=str(ROOT), text=True,
                           capture_output=True, check=False, timeout=timeout)
            return get_ollama_binary() is not None
        except Exception:
            return False
    except Exception:
        return False


def start_ollama(host: str = DEFAULT_URL, port: int = DEFAULT_PORT, start_args: Optional[List[str]] = None, timeout: float = 10.0) -> bool:
    """Start `ollama serve` and wait for it to become available."""
    return ensure_ollama_running(host=host, port=port, auto_start=True, start_args=start_args, timeout=timeout)


def stop_ollama(force: bool = False) -> bool:
    """Attempt to stop running ``ollama`` processes.

    The function prefers using :mod:`psutil` to find and terminate processes
    gracefully. If ``psutil`` is not available and ``force`` is True, a
    platform ``pkill`` may be attempted as a best-effort fallback.

    Args:
        force: When ``True`` attempt a more forceful kill via ``pkill`` if
            :mod:`psutil` is unavailable.

    Returns:
        ``True`` on success, ``False`` otherwise.
    """
    try:
        import importlib
        psutil = importlib.import_module("psutil")
    except Exception:
        psutil = None

    if psutil:
        try:
            for p in psutil.process_iter(["name", "cmdline"]):
                try:
                    name = p.info.get("name") or ""
                    cmdline = " ".join(p.info.get("cmdline") or [])
                    if "ollama" in name or "ollama" in cmdline:
                        try:
                            p.terminate()
                            p.wait(3)
                        except Exception:
                            try:
                                p.kill()
                            except Exception:
                                pass
                except Exception:
                    pass
            return True
        except Exception:
            return False

    if force and shutil.which("pkill"):
        try:
            subprocess.run(["pkill", "-f", "ollama"], check=False)
            return True
        except Exception:
            return False
    return False


def update_ollama(allow_upgrade: bool = False, timeout: float = 120.0) -> bool:
    """Try to update the installed ``ollama`` CLI.

    Attempts ``ollama update`` first. If that fails and ``allow_upgrade`` is
    True, falls back to ``brew upgrade ollama`` when Homebrew is available.

    Args:
        allow_upgrade: Permit using Homebrew to attempt an upgrade.
        timeout: Subprocess timeout in seconds.

    Returns:
        ``True`` if an update step succeeded, ``False`` otherwise.
    """
    binp = get_ollama_binary()
    if not binp:
        return False
    try:
        res = subprocess.run([binp, "update"], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, timeout=timeout, check=False)
        if res.returncode == 0:
            return True
    except Exception:
        pass
    if allow_upgrade and shutil.which("brew"):
        try:
            subprocess.run(["brew", "upgrade", "ollama"], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout)
            return True
        except Exception:
            return False
    return False


def list_local_models() -> List[str]:
    """Return a best-effort list of locally installed Ollama models.

    The helper attempts common CLI variants (``ollama list``, ``ollama ls``,
    etc.) and parses any output into a list of non-empty lines. If the
    ``ollama`` binary is not present or the calls fail, an empty list is
    returned.
    """
    def _looks_like_error_or_header(line: str) -> bool:
        if not line:
            return True
        low = line.strip().lower()
        error_indicators = ("error", "failed", "unable", "not found", "no such",
                            "denied", "unauthorized", "forbidden", "exception")
        for tok in error_indicators:
            if tok in low:
                return True
        first = low.split()[0].rstrip(":")
        if first in ("name", "model", "models", "llms", "description"):
            return True
        return False

    def _try_parse_json_models(out: str) -> Optional[List[str]]:
        try:
            data = json.loads(out)
        except Exception:
            return None
        names: List[str] = []
        # Handle obvious structures
        if isinstance(data, list):
            for item in data:
                if isinstance(item, str):
                    names.append(item)
                elif isinstance(item, dict):
                    if "name" in item:
                        names.append(str(item.get("name")))
                    elif "model" in item:
                        names.append(str(item.get("model")))
                    else:
                        # fallback to any key that looks like a name
                        for k in ("name", "model"):
                            if k in item:
                                names.append(str(item.get(k)))
                                break
        elif isinstance(data, dict):
            # common: {"models": [...]}
            for key in ("models", "llms", "data"):
                if key in data and isinstance(data[key], list):
                    for item in data[key]:
                        if isinstance(item, str):
                            names.append(item)
                        elif isinstance(item, dict):
                            if "name" in item:
                                names.append(str(item.get("name")))
                            elif "model" in item:
                                names.append(str(item.get("model")))
                    if names:
                        break
            # If dict keys are model names
            if not names:
                for k in data.keys():
                    if isinstance(k, str) and k and not k.lower().startswith("error"):
                        names.append(k)
        return names if names else None

    binp = get_ollama_binary()
    if not binp:
        return []

    # Try JSON-capable invocations first, falling back to plain text parsing.
    cmds = [[binp, "list", "--json"], [binp, "ls", "--json"], [binp, "models", "--json"],
            [binp, "list"], [binp, "ls"], [binp, "models"]]
    for cmd in cmds:
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True, timeout=15, check=False)
            out = (res.stdout or "").strip() or (res.stderr or "").strip()
            if not out:
                continue
            # If JSON flag used try parsing structured output
            if "--json" in cmd:
                parsed = _try_parse_json_models(out)
                if parsed:
                    logger.debug("Parsed JSON model list from %s: %s", cmd, parsed)
                    return parsed
                else:
                    logger.debug(
                        "Failed to parse JSON output from %s; stdout/stderr: %s", cmd, out[:1000])
                    continue

            # Plain text fallback: filter out obvious error/header lines
            lines = [line.strip() for line in out.splitlines() if line.strip()]
            good = [line for line in lines if not _looks_like_error_or_header(line)]
            if good:
                return good
        except Exception as exc:
            logger.debug("Exception while listing local models with %s: %s", cmd, exc)
            continue
    return []


def list_remote_models() -> List[str]:
    """Return a best-effort list of remote models available to download.

    Similar to :func:`list_local_models` but queries the remote model listing
    variants of the CLI (``--remote``). Returns an empty list if the CLI is
    not available or the calls fail.
    """
    def _looks_like_error_or_header(line: str) -> bool:
        if not line:
            return True
        low = line.strip().lower()
        error_indicators = ("error", "failed", "unable", "not found", "no such",
                            "denied", "unauthorized", "forbidden", "exception")
        for tok in error_indicators:
            if tok in low:
                return True
        first = low.split()[0].rstrip(":")
        if first in ("name", "model", "models", "llms", "description"):
            return True
        return False

    def _try_parse_json_models(out: str) -> Optional[List[str]]:
        try:
            data = json.loads(out)
        except Exception:
            return None
        names: List[str] = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, str):
                    names.append(item)
                elif isinstance(item, dict):
                    if "name" in item:
                        names.append(str(item.get("name")))
                    elif "model" in item:
                        names.append(str(item.get("model")))
        elif isinstance(data, dict):
            for key in ("models", "llms", "data"):
                if key in data and isinstance(data[key], list):
                    for item in data[key]:
                        if isinstance(item, str):
                            names.append(item)
                        elif isinstance(item, dict):
                            if "name" in item:
                                names.append(str(item.get("name")))
                            elif "model" in item:
                                names.append(str(item.get("model")))
                    if names:
                        break
            if not names:
                for k in data.keys():
                    if isinstance(k, str) and k and not k.lower().startswith("error"):
                        names.append(k)
        return names if names else None

    binp = get_ollama_binary()
    if not binp:
        return []

    cmds = [[binp, "list", "--remote", "--json"], [binp, "ls", "--remote", "--json"],
            [binp, "models", "--remote", "--json"], [binp, "llms", "--remote", "--json"],
            [binp, "list", "--remote"], [binp, "ls", "--remote"],
            [binp, "models", "--remote"], [binp, "llms", "--remote"]]
    for cmd in cmds:
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True, timeout=20, check=False)
            out = (res.stdout or "").strip() or (res.stderr or "").strip()
            if not out:
                continue
            if "--json" in cmd:
                parsed = _try_parse_json_models(out)
                if parsed:
                    logger.debug("Parsed JSON remote model list from %s: %s", cmd, parsed)
                    return parsed
                else:
                    logger.debug(
                        "Failed to parse JSON remote output from %s; stdout/stderr: %s", cmd, out[:1000])
                    continue

            lines = [line.strip() for line in out.splitlines() if line.strip()]
            good = [line for line in lines if not _looks_like_error_or_header(line)]
            if good:
                return good
        except Exception as exc:
            logger.debug("Exception while listing remote models with %s: %s", cmd, exc)
            continue
    return []


def download_model(model_name: str, timeout: float = 600.0) -> bool:
    """Download a remote model into the local Ollama cache using the CLI.

    Tries common command names (``pull``, ``download``) and returns ``True``
    when the subprocess exit code indicates success.

    Args:
        model_name: Name of the model to download.
        timeout: Subprocess timeout in seconds.

    Returns:
        ``True`` on success, else ``False``.
    """
    binp = get_ollama_binary()
    if not binp:
        logger.debug("download_model: ollama binary not found")
        return False
    cmds = [[binp, "pull", model_name], [binp, "download", model_name]]
    for cmd in cmds:
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True, timeout=timeout, check=False)
            if res.returncode == 0:
                logger.debug("download_model succeeded for %s via %s", model_name, cmd)
                return True
            else:
                logger.warning("download_model failed for %s via %s: returncode=%s stdout=%s stderr=%s",
                               model_name, cmd, res.returncode, (res.stdout or '')[:1000], (res.stderr or '')[:1000])
        except Exception as exc:
            logger.debug("Exception running download command %s for %s: %s", cmd, model_name, exc)
            continue
    return False


def delete_model(model_name: str) -> bool:
    """Delete a locally cached model using the Ollama CLI.

    Tries multiple possible subcommands (``rm``, ``remove``, ``delete``) and
    returns ``True`` when any of them report success.
    """
    binp = get_ollama_binary()
    if not binp:
        logger.debug("delete_model: ollama binary not found")
        return False
    cmds = [[binp, "rm", model_name], [binp, "remove", model_name], [binp, "delete", model_name]]
    for cmd in cmds:
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True, timeout=60, check=False)
            if res.returncode == 0:
                logger.debug("delete_model succeeded for %s via %s", model_name, cmd)
                return True
            else:
                logger.debug("delete_model attempt for %s via %s returned %s; stdout=%s stderr=%s",
                             model_name, cmd, res.returncode, (res.stdout or '')[:1000], (res.stderr or '')[:1000])
        except Exception as exc:
            logger.debug("Exception running delete command %s for %s: %s", cmd, model_name, exc)
            continue
    return False


def serve_model(model_name: Optional[str] = None, start_args: Optional[List[str]] = None, timeout: float = 10.0) -> bool:
    """Start ``ollama serve`` and wait until a server is reachable.

    Uses :func:`start_detached_ollama_serve` so environment and detachment
    semantics are consistent across helpers.
    """
    if not ollama_installed():
        return False

    host_env = f"{DEFAULT_URL.replace('http://', '').replace('https://', '')}:{DEFAULT_PORT}"
    args: List[str] = []
    if model_name:
        args.extend(["--model", model_name])
    if start_args:
        args.extend(start_args)

    try:
        start_detached_ollama_serve(host_env, start_args=args)
    except Exception:
        return False

    deadline = time.time() + timeout
    while time.time() < deadline:
        if server_is_up(DEFAULT_URL, DEFAULT_PORT):
            return True
        time.sleep(0.5)
    return False


def ensure_model_available(model_name: str, allow_download: bool = False, timeout: float = 600.0) -> bool:
    """Ensure a model is available locally, optionally attempting to download it.

    Args:
        model_name: Name of the model to check.
        allow_download: If True, try to download the model when missing.
        timeout: Timeout for download operations in seconds.

    Returns:
        True if the model is available locally (or successfully downloaded), else False.
    """
    try:
        local = list_local_models()
    except Exception:
        local = []
    if model_name in local:
        return True
    if not allow_download:
        return False
    return download_model(model_name, timeout=timeout)


async def async_ensure_model_available(model_name: str, allow_download: bool = False, timeout: float = 600.0) -> bool:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, ensure_model_available, model_name, allow_download, timeout)


def change_ollama_config(config: Dict[str, Any], config_path: Optional[str] = None) -> bool:
    """Write the provided configuration dictionary to the Ollama config file.

    The function writes JSON to the supplied ``config_path`` or falls back to
    ``~/.ollama/config.json``.

    Args:
        config: Dictionary to write as JSON.
        config_path: Optional path override for the config file.

    Returns:
        ``True`` on success, ``False`` on failure.
    """
    p = Path(config_path) if config_path else (Path.home() / ".ollama" / "config.json")
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(config, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def ollama_binary_candidates() -> List[Path]:
    """Return common CLI locations to probe when PATH lookup is not enough."""
    candidates: List[Path] = []

    discovered = shutil.which("ollama")
    if discovered:
        candidates.append(Path(discovered))

    if os.name == "nt":
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            candidates.append(Path(local_appdata) / "Programs" / "Ollama" / "ollama.exe")
        candidates.append(Path.home() / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe")
    elif sys.platform == "darwin":
        candidates.extend(
            [
                Path("/Applications/Ollama.app/Contents/Resources/ollama"),
                Path("/Applications/Ollama.app/Contents/MacOS/Ollama"),
                Path("/usr/local/bin/ollama"),
                Path("/opt/homebrew/bin/ollama"),
            ]
        )
    else:
        candidates.extend(
            [
                Path("/usr/local/bin/ollama"),
                Path("/usr/bin/ollama"),
                Path("/bin/ollama"),
            ]
        )

    unique: List[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique.append(candidate)
    return unique


def resolve_ollama_command() -> str:
    """Find the best available `ollama` CLI path or raise FileNotFoundError."""
    for candidate in ollama_binary_candidates():
        if candidate.exists():
            return str(candidate)
    raise FileNotFoundError("ollama")


def ollama_installed() -> bool:
    try:
        resolve_ollama_command()
    except FileNotFoundError:
        return False
    return True


def run_ollama_command(*args: str, host: Optional[str] = None) -> subprocess.CompletedProcess[str]:
    """Run an Ollama CLI command and capture the Result.

    Args:
        *args: Arguments to pass to the resolved ``ollama`` binary.
        host: Optional host string to set as ``OLLAMA_HOST`` in the subprocess
            environment (e.g. ``"127.0.0.1:11434"``).

    Returns:
        A :class:`subprocess.CompletedProcess` instance containing stdout/stderr
        and return code.
    """
    env = os.environ.copy()
    if host:
        env["OLLAMA_HOST"] = host
    command = resolve_ollama_command()
    return subprocess.run([command, *args], cwd=str(ROOT), text=True, capture_output=True, check=False, env=env)


def start_detached_ollama_serve(host: str, start_args: Optional[List[str]] = None) -> subprocess.Popen[Any]:
    """Start `ollama serve` in the background for the current platform.

    `start_args` are appended to the serve command and can include options
    such as `--model <name>`.
    """
    command = resolve_ollama_command()
    cmd = [command, "serve"]
    if start_args:
        cmd.extend(start_args)

    # Build common parameters explicitly to satisfy strict typing of subprocess.Popen
    common_env: Dict[str, str] = {**os.environ, "OLLAMA_HOST": host}
    if os.name == "nt":
        creationflags_val = (
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        return cast(
            subprocess.Popen[Any],
            subprocess.Popen(
                cmd,
                cwd=str(ROOT),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                env=common_env,
                text=True,
                creationflags=creationflags_val,
            ),
        )
    else:
        return cast(
            subprocess.Popen[Any],
            subprocess.Popen(
                cmd,
                cwd=str(ROOT),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                env=common_env,
                text=True,
                start_new_session=True,
            ),
        )


def json_post(url: str, payload: Dict[str, Any], timeout: float = 60.0) -> Dict[str, Any]:
    request = Request(url, data=json.dumps(payload).encode("utf-8"),
                      headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    return json.loads(body) if body else {}


def json_get(url: str, timeout: float = 5.0) -> Dict[str, Any]:
    """Read JSON from an HTTP GET endpoint and decode it to a dict."""
    with urlopen(url, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    return json.loads(body) if body else {}


async def async_preload_model(url: str, port: int, model: str, timeout: float = 120.0) -> None:
    """Async wrapper around :func:`preload_model` using an executor."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, preload_model, url, port, model, timeout)


async def async_list_local_models() -> List[str]:
    """Async wrapper for :func:`list_local_models`."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, list_local_models)


async def async_list_remote_models() -> List[str]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, list_remote_models)


async def async_download_model(model_name: str, timeout: float = 600.0) -> bool:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, download_model, model_name, timeout)


async def async_delete_model(model_name: str) -> bool:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, delete_model, model_name)


async def async_serve_model(model_name: Optional[str] = None, start_args: Optional[List[str]] = None, timeout: float = 10.0) -> bool:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, serve_model, model_name, start_args, timeout)


def wait_until_ready(url: str, port: int, timeout_seconds: float = 60.0) -> None:
    """Wait until the Ollama HTTP API becomes reachable."""
    deadline = time.time() + float(timeout_seconds)
    while time.time() < deadline:
        if server_is_up(url, port):
            return
        time.sleep(1)
    raise RuntimeError(f"ollama serve did not become ready at {url}:{port}/api/version")


def preload_model(url: str, port: int, model: str, timeout: float = 120.0) -> None:
    """Warm the selected model through the local Ollama API."""
    json_post(endpoint_url(url, port, "/api/generate"),
              {"model": model, "keep_alive": "30m"}, timeout=timeout)


def running_model_names(host: str) -> List[str]:
    """Return the names reported by `ollama ps` (best-effort)."""
    try:
        proc = run_ollama_command("ps", host=host)
    except FileNotFoundError:
        return []
    if proc.returncode != 0:
        return []
    names: List[str] = []
    for line in (proc.stdout or "").splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        names.append(line.split()[0])
    return names


def load_llm_config(path: Optional[str] = None) -> Dict[str, Any]:
    """Load a minimal LLM runtime config from common locations.

    Returns a dict with keys: last_served_model, model, model_timeouts, timeout, url, port
    """
    # Prefer the new ``load_config_data`` helper which supports overlay
    # semantics; fall back to the older ``load_config`` when unavailable.
    try:
        from .config import load_config_data as _load_config_data  # type: ignore
    except Exception:
        _load_config_data = None

    try:
        from .config import load_config as _load_config  # type: ignore
    except Exception:
        _load_config = None

    data: dict[str, Any] = {}
    if path:
        try:
            if _load_config_data:
                data = _load_config_data(path) or {}
            elif _load_config:
                data = _load_config(path) or {}
            else:
                p = Path(path)
                if p.exists():
                    data = json.loads(p.read_text(encoding="utf-8")) or {}
        except Exception:
            data = {}
    else:
        # probe common locations
        candidates = [
            Path.home() / ".modelito" / "config.json",
            Path.home() / ".modelito" / "config.yaml",
            Path.home() / ".ollama" / "config.json",
        ]
        for c in candidates:
            if c.exists():
                try:
                    if _load_config_data:
                        data = _load_config_data(str(c)) or {}
                    elif _load_config:
                        data = _load_config(str(c)) or {}
                    else:
                        data = json.loads(c.read_text(encoding="utf-8")) or {}
                except Exception:
                    data = {}
                break

    if not isinstance(data, dict):
        data = {}
    llm = data.get("llm") or {}
    raw_model_timeouts = llm.get("model_timeouts")
    if isinstance(raw_model_timeouts, dict):
        model_timeouts: dict[str, Any] = dict(raw_model_timeouts)
    else:
        model_timeouts = {}
    return {
        "last_served_model": str(llm.get("last_served_model") or "").strip(),
        "model": str(llm.get("model") or "").strip(),
        "model_timeouts": dict(model_timeouts),
        "timeout": llm.get("timeout"),
        "url": str(llm.get("url") or "http://127.0.0.1").strip().rstrip("/"),
        "port": int(llm.get("port") or 11434),
    }


def preferred_start_model(llm: Dict[str, Any]) -> str:
    last = str(llm.get("last_served_model") or "").strip()
    model = str(llm.get("model") or "").strip()
    return last or model


def save_last_served_model(model: str, path: Optional[str] = None) -> bool:
    try:
        target = Path(path) if path else (Path.home() / ".modelito" / "config.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        # load existing data if possible
        data: dict[str, Any] = {}
        if target.exists():
            try:
                data = json.loads(target.read_text(encoding="utf-8")) or {}
            except Exception:
                data = {}
        llm = data.setdefault("llm", {})
        llm["last_served_model"] = str(model)
        target.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def ollama_version_text(host: Optional[str] = None) -> str:
    try:
        proc = run_ollama_command("--version", host=host)
    except FileNotFoundError:
        return ""
    return (proc.stdout or proc.stderr or "").strip()


def install_command_for_current_platform(platform_name: Optional[str] = None) -> tuple[List[str], str]:
    platform_name = platform_name or sys.platform
    if platform_name.startswith("win"):
        command = [
            "powershell.exe",
            "-NoExit",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            f"irm {WINDOWS_INSTALL_URL} | iex",
        ]
        return command, f"irm {WINDOWS_INSTALL_URL} | iex"
    install_command = f"export OLLAMA_NO_START=1; curl -fsSL {shlex.quote(UNIX_INSTALL_URL)} | sh"
    return ["/bin/sh", "-lc", install_command], install_command


def install_service(reinstall: bool = False) -> tuple[int, str]:
    action = "reinstall" if reinstall else "install"
    command, display = install_command_for_current_platform()
    try:
        proc = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True, check=False)
        combined = ((proc.stdout or "") + (proc.stderr or "")).strip()
        if proc.returncode == 0:
            return 0, combined or f"Completed the official Ollama {action} workflow."
        return proc.returncode, combined or f"Ollama {action} failed."
    except FileNotFoundError as exc:
        return 1, f"Unable to launch the Ollama installer command ({display}): {exc}"


def inspect_service_state(config_path: Optional[str] = None) -> Dict[str, Any]:
    llm = load_llm_config(config_path)
    url = str(llm["url"])
    port = int(llm["port"])
    host = f"{url.replace('http://', '').replace('https://', '')}:{port}"
    return {
        "installed": ollama_installed(),
        "version": ollama_version_text(host=host),
        "running": server_is_up(url, port),
        "configured_model": str(llm["model"]),
        "last_served_model": str(llm["last_served_model"]),
        "startup_model": preferred_start_model(llm),
        "url": url,
        "port": port,
    }


def start_service(config_path: Optional[str] = None) -> int:
    llm = load_llm_config(config_path)
    model = preferred_start_model(llm)
    url = str(llm["url"])
    port = int(llm["port"])
    host = f"{url.replace('http://', '').replace('https://', '')}:{port}"

    if not model:
        print(f"No model configured in {config_path}", file=sys.stderr)
        return 1

    try:
        version_proc = run_ollama_command("--version", host=host)
    except FileNotFoundError:
        print("ollama: command not found", file=sys.stderr)
        return 1

    if version_proc.returncode != 0 and not (version_proc.stdout or version_proc.stderr):
        print("ollama CLI failed to start", file=sys.stderr)
        return 1

    started = False
    if server_is_up(url, port):
        print(f"Ollama already serving at {host}")
    else:
        print(f"Starting ollama serve at {host} ...")
        start_detached_ollama_serve(host)
        try:
            wait_until_ready(url, port)
        except Exception as exc:
            print(f"Failed to start ollama serve: {exc}", file=sys.stderr)
            return 1
        started = True

    pull_proc = run_ollama_command("pull", model, host=host)
    if pull_proc.returncode != 0:
        sys.stderr.write((pull_proc.stdout or "") + (pull_proc.stderr or ""))
        return pull_proc.returncode

    try:
        preload_model(url, port, model, timeout=120.0)
    except Exception:
        # warming the model is best-effort; do not fail the whole start.
        pass

    save_last_served_model(model, config_path)

    if started:
        print(f"Completed: started ollama at {host}, pulled and warmed model '{model}'.")
    else:
        print(f"Completed: ollama already running at {host}; pulled and warmed model '{model}'.")
    return 0


def pull_model(model_name: str, timeout: float = 600.0) -> bool:
    """Pull/download a remote model into the local cache.

    This is a small convenience wrapper that delegates to :func:`download_model`.
    """
    return download_model(model_name, timeout=timeout)


def load_remote_timeout_catalog(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load a timeout catalog either from `path` or the bundled catalog.

    Returns a dictionary representing the catalog on success or an empty
    dictionary on error.
    """
    try:
        # prefer local file when provided
        if path:
            p = Path(path)
            if p.exists():
                try:
                    return json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    pass
        # fall back to the package-level timeout loader
        from . import timeout as _timeout

        return _timeout.load_catalog()
    except Exception:
        return {}


def common_model_timeout(model_name: str) -> Optional[float]:
    """Return a conservative timeout (seconds) for the named model.

    Returns ``None`` on error.
    """
    try:
        from .timeout import estimate_remote_timeout as _estimate

        return float(_estimate(model_name))
    except Exception:
        return None


def estimate_remote_model_timeout_details(model_name: str, input_tokens: int = 2048, concurrency: int = 1) -> tuple[int, Dict[str, Any]]:
    """Return a timeout estimate and diagnostic details from the catalog."""
    from .timeout import estimate_remote_timeout as _estimate

    t, src = _estimate(model_name, input_tokens=input_tokens,
                       concurrency=concurrency, with_source=True)
    return int(t), dict(src or {})


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="modelito-ollama",
                                description="Manage Ollama lifecycle and models")
    subs = p.add_subparsers(dest="cmd")

    sp = subs.add_parser("start")
    sp.add_argument("--config", "-c", dest="config", default=None)
    sp.add_argument("--wait", type=float, default=30.0)

    sp = subs.add_parser("stop")
    sp.add_argument("--config", "-c", dest="config", default=None)
    sp.add_argument("--host", default="http://127.0.0.1")
    sp.add_argument("--port", type=int, default=11434)
    sp.add_argument("--verbose", action="store_true")

    sp = subs.add_parser("install")
    sp.add_argument("--reinstall", action="store_true")

    sp = subs.add_parser("inspect")
    sp.add_argument("--config", "-c", dest="config", default=None)

    sp = subs.add_parser("pull")
    sp.add_argument("model")
    sp.add_argument("--timeout", type=float, default=600.0)

    subs.add_parser("list-local")
    subs.add_parser("list-remote")
    subs.add_parser("version")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    cmd = getattr(args, "cmd", None)

    if cmd == "start":
        cfg = getattr(args, "config", None)
        return start_service(cfg)

    if cmd == "stop":
        cfg = getattr(args, "config", None)
        host = getattr(args, "host", "http://127.0.0.1")
        port = getattr(args, "port", 11434)
        verbose = getattr(args, "verbose", False)
        return stop_service(host=host, port=port, verbose=verbose, config_path=cfg)

    if cmd == "install":
        return install_service(reinstall=getattr(args, "reinstall", False))[0]

    if cmd == "inspect":
        cfg = getattr(args, "config", None)
        import pprint

        pprint.pprint(inspect_service_state(cfg))
        return 0

    if cmd == "pull":
        ok = pull_model(args.model, timeout=getattr(args, "timeout", 600.0))
        return 0 if ok else 1

    if cmd == "list-local":
        print("\n".join(list_local_models()))
        return 0

    if cmd == "list-remote":
        print("\n".join(list_remote_models()))
        return 0

    if cmd == "version":
        print(ollama_version_text())
        return 0

    build_parser().print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())


def _listener_pids_from_connections(connections: Iterable[Any], port: int) -> List[int]:
    pids: set[int] = set()
    for conn in connections:
        try:
            if conn.status != getattr(conn, "status", None) and getattr(conn, "status", None) is None:
                continue
        except Exception:
            pass
        if not getattr(conn, "laddr", None):
            continue
        try:
            if conn.laddr.port != port or conn.pid is None:
                continue
        except Exception:
            continue
        pids.add(conn.pid)
    return sorted(pids)


def find_ollama_listener_pids(port: int) -> List[int]:
    """Return process IDs listening on the configured TCP port (best-effort)."""
    try:
        import importlib
        psutil = importlib.import_module("psutil")
    except Exception:
        psutil = None

    if psutil is None:
        return []

    try:
        return _listener_pids_from_connections(psutil.net_connections(kind="inet"), port)
    except psutil.AccessDenied:
        pass

    pids: set[int] = set()
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            name = str((proc.info or {}).get("name") or proc.name()).lower()
        except psutil.Error:
            continue
        if "ollama" not in name:
            continue
        try:
            connections = proc.net_connections(kind="inet")
        except psutil.Error:
            continue
        for conn in connections:
            if not getattr(conn, "laddr", None):
                continue
            try:
                if conn.laddr.port != port:
                    continue
            except Exception:
                continue
            pids.add(getattr(conn, "pid", None) or proc.pid)
    return sorted(pids)


def stop_service(host: str = "http://127.0.0.1", port: int = 11434, verbose: bool = False, config_path: Optional[str] = None) -> int:
    """Stop running models and terminate server processes (best-effort).

    If `config_path` is provided the function will load the configured URL/port
    from the LLM config and use that instead of the explicit `host`/`port`
    values.

    Returns 0 on success, non-zero on failure.
    """
    if config_path:
        try:
            cfg = load_llm_config(config_path)
            host = str(cfg.get("url") or host)
            port = int(cfg.get("port") or port)
        except Exception:
            # Fall back to explicit host/port on any load failure
            pass
    host_url = host
    host_env = f"{host_url.replace('http://', '').replace('https://', '')}:{port}"
    try:
        run_ollama_command("--version", host=host_env)
        models = running_model_names(host=host_env)
        if models and verbose:
            print(f"Stopping running models: {' '.join(models)}")
        for model in models:
            run_ollama_command("stop", model, host=host_env)
    except FileNotFoundError:
        if verbose:
            print("ollama CLI not found; skipping model stop.")

    pids = find_ollama_listener_pids(port)
    if not pids:
        if verbose:
            print(f"No process is listening on port {port} (already stopped?).")
        return 0

    killed = False
    try:
        import importlib
        psutil = importlib.import_module("psutil")
    except Exception:
        psutil = None

    if psutil:
        for pid in pids:
            try:
                proc = psutil.Process(pid)
            except psutil.Error:
                continue
            name = proc.name().lower()
            if "ollama" not in name:
                continue
            if verbose:
                print(f"Stopping ollama serve PID {pid} (port {port})")
            try:
                proc.terminate()
                killed = True
            except psutil.Error:
                continue

        # wait and kill survivors
        try:
            _gone, alive = psutil.wait_procs([psutil.Process(pid)
                                             for pid in pids if psutil.pid_exists(pid)], timeout=3.0)
            for proc in alive:
                try:
                    proc.kill()
                except psutil.Error:
                    continue
        except Exception:
            pass

    if verbose:
        if killed:
            print(f"Ollama server on {host_env} stopped.")
        else:
            print(f"No ollama serve process found on {host_env}.")
    return 0
