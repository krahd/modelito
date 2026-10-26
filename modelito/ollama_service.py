"""Lightweight Ollama HTTP, CLI and explicitly configured lifecycle helpers."""

from __future__ import annotations

import socket
import math
import hashlib
import queue
from urllib.parse import urlsplit
from urllib.request import urlopen
from urllib.request import Request
import time
import asyncio
import shutil
import re
import subprocess
import os
import sys
import shlex
import threading
from typing import Optional, List, Dict, Any, Iterable, Callable, NoReturn, Generator
from pathlib import Path
from functools import partial
from html.parser import HTMLParser
import json
import logging
import argparse
from dataclasses import dataclass, field

from .errors import ProviderError
from .plumbing import TransportPolicy, normalize_network_error, retry_with_backoff

ROOT = Path(__file__).resolve().parents[1]
UNIX_INSTALL_URL = "https://ollama.com/install.sh"
WINDOWS_INSTALL_URL = "https://ollama.com/install.ps1"
DEFAULT_URL = "http://127.0.0.1"
DEFAULT_PORT = 11434

# Module logger
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RemoteModelCatalogEntry:
    """Structured metadata for a remote Ollama model listing entry."""

    name: str
    family: str
    tag: Optional[str] = None
    installed: bool = False
    source: str = "remote"
    raw: str = ""


@dataclass(frozen=True)
class ModelLifecycleState:
    """Best-effort lifecycle state keyed by model name.

    The state is intentionally lightweight so callers can poll it without
    depending on any background worker or external persistence layer.
    """

    model: str
    phase: str
    message: str = ""
    progress: Optional[float] = None
    completed: Optional[int] = None
    total: Optional[int] = None
    error: Optional[str] = None
    source: str = "cli"
    updated_at: float = field(default_factory=time.time)


@dataclass(frozen=True)
class ReadinessResult:
    """Structured result from model readiness checks.

    Combines success status, lifecycle phase, message, source, and elapsed time
    into a single result object for cleaner UI integration and reduced polling.
    """

    success: bool
    phase: str  # e.g., "ready", "preparing", "error"
    message: str = ""
    source: str = "http"  # e.g., "ollama", "http", "cli"
    elapsed_seconds: float = 0.0
    error: Optional[str] = None


_MODEL_STATE_LOCK = threading.Lock()
_MODEL_LIFECYCLE_STATES: Dict[str, ModelLifecycleState] = {}
_PERCENT_RE = re.compile(r"(?P<pct>\d{1,3}(?:\.\d+)?)%")
_COUNT_RE = re.compile(r"(?P<completed>\d+)\s*/\s*(?P<total>\d+)")


def _record_model_state(
    model_name: str,
    phase: str,
    *,
    message: str = "",
    progress: Optional[float] = None,
    completed: Optional[int] = None,
    total: Optional[int] = None,
    error: Optional[str] = None,
    source: str = "cli",
) -> ModelLifecycleState:
    state = ModelLifecycleState(
        model=model_name,
        phase=phase,
        message=message,
        progress=progress,
        completed=completed,
        total=total,
        error=error,
        source=source,
    )
    with _MODEL_STATE_LOCK:
        _MODEL_LIFECYCLE_STATES[model_name] = state
    return state


def get_model_lifecycle_state(model_name: str) -> Optional[ModelLifecycleState]:
    """Return the latest tracked lifecycle state for `model_name`."""
    with _MODEL_STATE_LOCK:
        return _MODEL_LIFECYCLE_STATES.get(model_name)


def list_model_lifecycle_states() -> Dict[str, ModelLifecycleState]:
    """Return a snapshot of all tracked per-model lifecycle states."""
    with _MODEL_STATE_LOCK:
        return dict(_MODEL_LIFECYCLE_STATES)


def clear_model_lifecycle_state(model_name: str) -> bool:
    """Remove the cached lifecycle state for `model_name`."""
    with _MODEL_STATE_LOCK:
        return _MODEL_LIFECYCLE_STATES.pop(model_name, None) is not None


def _parse_progress_from_line(
    line: str,
) -> tuple[Optional[float], Optional[int], Optional[int]]:
    progress: Optional[float] = None
    completed: Optional[int] = None
    total: Optional[int] = None

    match = _PERCENT_RE.search(line)
    if match:
        try:
            progress = max(0.0, min(100.0, float(match.group("pct"))))
        except Exception:
            progress = None

    count_match = _COUNT_RE.search(line)
    if count_match:
        try:
            completed = int(count_match.group("completed"))
            total = int(count_match.group("total"))
            if progress is None and total > 0:
                progress = max(0.0, min(100.0, (completed / total) * 100.0))
        except Exception:
            completed = None
            total = None

    return progress, completed, total


def _phase_from_progress_line(line: str) -> str:
    low = line.strip().lower()
    if not low:
        return "downloading"
    if "verifying" in low:
        return "verifying"
    if "manifest" in low or "finaliz" in low:
        return "finalizing"
    if "error" in low or "failed" in low:
        return "error"
    if "done" in low or "success" in low or "complete" in low:
        return "downloaded"
    return "downloading"


def detect_install_method(platform_name: Optional[str] = None) -> str:
    """Return the preferred install backend for the current platform.

    The helper prefers package managers when they are present and falls back to
    the official Ollama install scripts otherwise.
    """
    platform_name = platform_name or sys.platform
    if platform_name.startswith("win"):
        return "choco" if shutil.which("choco") else "powershell"
    if platform_name == "darwin":
        return "brew" if shutil.which("brew") else "script"
    if shutil.which("apt-get"):
        return "apt"
    return "script"


def _install_command_for_method(method: str) -> tuple[List[str], str]:
    if method == "choco":
        return ["choco", "install", "ollama", "-y"], "choco install ollama -y"
    if method == "powershell":
        command = [
            "powershell.exe",
            "-NoExit",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            f"irm {WINDOWS_INSTALL_URL} | iex",
        ]
        return command, f"irm {WINDOWS_INSTALL_URL} | iex"
    if method == "brew":
        return ["brew", "install", "ollama"], "brew install ollama"
    if method == "apt":
        shell_command = "sudo apt-get update && sudo apt-get install -y ollama"
        return ["/bin/sh", "-lc", shell_command], shell_command
    install_command = (
        f"export OLLAMA_NO_START=1; curl -fsSL {shlex.quote(UNIX_INSTALL_URL)} | sh"
    )
    return ["/bin/sh", "-lc", install_command], install_command


def _extract_model_name(raw_item: str) -> str:
    token = (
        str(raw_item or "").strip().split()[0] if str(raw_item or "").strip() else ""
    )
    return token.strip()


def _catalog_entry(
    raw_item: str, installed_models: set[str]
) -> Optional[RemoteModelCatalogEntry]:
    name = _extract_model_name(raw_item)
    if not name:
        return None
    family, _, tag = name.partition(":")
    if "/" in family:
        family = family.split("/", 1)[0]
    return RemoteModelCatalogEntry(
        name=name,
        family=family or name,
        tag=tag or None,
        installed=(
            name in installed_models
            or (":" not in name and f"{name}:latest" in installed_models)
        ),
        raw=str(raw_item or ""),
    )


def _ensure_pythonpath_env(env: Dict[str, str]) -> None:
    """Ensure the repository root is present in `PYTHONPATH` inside `env`.

    This helps when the resolved `ollama` entrypoint is a Python module
    (for example `python -m llm.service`) so that consumers that invoke
    the CLI via the helpers get a PYTHONPATH that can import the local
    package tree.
    """
    try:
        cur = env.get("PYTHONPATH", "") or ""
        parts = [p for p in cur.split(os.pathsep) if p]
        root_str = str(ROOT)
        if root_str not in parts:
            parts.append(root_str)
            env["PYTHONPATH"] = os.pathsep.join(parts)
    except Exception:
        # Best-effort only; do not raise for environment adjustments.
        pass


def endpoint_url(host: str, port: int, path: str = "/api/generate") -> str:
    """Return a fully-qualified endpoint URL for the Ollama HTTP API.

    Args:
        host: Host string; may include scheme (e.g. "http://127.0.0.1").
        port: TCP port to use when the host does not already include one.
        path: API path to append (defaults to "/api/generate").

    Returns:
        A string containing the full URL to the requested API path.
    """
    if not isinstance(host, str) or not host.strip():
        raise ValueError("host must be a non-empty string")
    parsed = urlsplit(host if "://" in host else f"http://{host}")
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("host must be an HTTP endpoint")
    hostname = parsed.hostname
    if ":" in hostname:
        hostname = f"[{hostname}]"
    authority = f"{hostname}:{parsed.port or int(port)}"
    return f"{parsed.scheme}://{authority}{parsed.path.rstrip('/')}{path}"


def _timeout(value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError("timeout must be finite and positive")
    return value


def _remaining(deadline: float, command: List[str], timeout: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise subprocess.TimeoutExpired(command, timeout)
    return remaining


def _cli_env(host: Optional[str], port: int = DEFAULT_PORT) -> Dict[str, str]:
    env = os.environ.copy()
    if host is not None:
        env["OLLAMA_HOST"] = endpoint_url(host, port, "")
    return env


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


def ensure_ollama_running(
    host: str = DEFAULT_URL,
    port: int = DEFAULT_PORT,
    auto_start: bool = False,
    start_args: Optional[List[str]] = None,
    timeout: float = 10.0,
) -> bool:
    """Ensure an Ollama server is reachable at `host:port`.

    If `auto_start` is True and the `ollama` binary is available on PATH,
    attempt to start `ollama serve` in a detached process and wait up to
    `timeout` seconds for the server to become available.

    Returns True if the server is reachable, False otherwise.
    """
    # Delegate to the verbose variant and return only the boolean result.
    ok, _msg = ensure_ollama_running_verbose(
        host=host,
        port=port,
        auto_start=auto_start,
        start_args=start_args,
        timeout=timeout,
    )
    return bool(ok)


def ensure_ollama_running_verbose(
    host: str = DEFAULT_URL,
    port: int = DEFAULT_PORT,
    auto_start: bool = False,
    start_args: Optional[List[str]] = None,
    timeout: float = 10.0,
) -> tuple[bool, str]:
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
    host_env = endpoint_url(host, port, "")

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


def install_ollama(
    allow_install: bool = False, method: Optional[str] = None, timeout: float = 600.0
) -> bool:
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
        selected = method or detect_install_method()
        attempted_methods: List[str] = [selected]
        fallback_method = (
            "script"
            if selected in ("brew", "apt")
            else "powershell" if selected == "choco" else None
        )
        if fallback_method and fallback_method not in attempted_methods:
            attempted_methods.append(fallback_method)

        for candidate_method in attempted_methods:
            cmd, _ = _install_command_for_method(candidate_method)
            try:
                subprocess.run(
                    cmd,
                    cwd=str(ROOT),
                    text=True,
                    capture_output=True,
                    check=False,
                    timeout=timeout,
                )
            except Exception:
                continue
            if get_ollama_binary() is not None:
                return True
        return False
    except Exception:
        return False


def start_ollama(
    host: str = DEFAULT_URL,
    port: int = DEFAULT_PORT,
    start_args: Optional[List[str]] = None,
    timeout: float = 10.0,
) -> bool:
    """Start `ollama serve` and wait for it to become available."""
    return ensure_ollama_running(
        host=host, port=port, auto_start=True, start_args=start_args, timeout=timeout
    )


def stop_ollama(force: bool = False) -> bool:
    """Stop only the default server owned by Modelito; force never broadens scope."""
    return stop_service() == 0


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
        res = subprocess.run(
            [binp, "update"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
        if res.returncode == 0:
            return True
    except Exception:
        pass
    if allow_upgrade and shutil.which("brew"):
        try:
            subprocess.run(
                ["brew", "upgrade", "ollama"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout,
            )
            return True
        except Exception:
            return False
    return False


def list_local_models(
    *, host: Optional[str] = None, port: int = DEFAULT_PORT, timeout: float = 30.0
) -> List[str]:
    """Return a best-effort list of locally installed Ollama models.

    The helper attempts common CLI variants (``ollama list``, ``ollama ls``,
    etc.) and parses any output into a list of non-empty lines. If the
    ``ollama`` binary is not present or the calls fail, an empty list is
    returned.
    """

    timeout = _timeout(timeout)
    if host is not None:
        data = json_get(endpoint_url(host, port, "/api/tags"), timeout=timeout)
        return [
            str(m["name"])
            for m in data.get("models", [])
            if isinstance(m, dict) and isinstance(m.get("name"), str)
        ]

    def _looks_like_error_or_header(line: str) -> bool:
        if not line:
            return True
        low = line.strip().lower()
        error_indicators = (
            "error",
            "failed",
            "unable",
            "not found",
            "no such",
            "denied",
            "unauthorized",
            "forbidden",
            "exception",
        )
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

    deadline = time.monotonic() + _timeout(timeout)
    binp = get_ollama_binary()
    if not binp:
        return []

    # Try JSON-capable invocations first, falling back to plain text parsing.
    cmds = [
        [binp, "list", "--json"],
        [binp, "ls", "--json"],
        [binp, "models", "--json"],
        [binp, "list"],
        [binp, "ls"],
        [binp, "models"],
    ]
    for cmd in cmds:
        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=_remaining(deadline, cmd, timeout),
                env=_cli_env(host, port),
                check=False,
            )
            if res.returncode != 0:
                continue
            out = (res.stdout or "").strip()
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
                        "Failed to parse JSON output from %s; stdout/stderr: %s",
                        cmd,
                        out[:1000],
                    )
                    continue

            # Plain text fallback: filter out obvious error/header lines
            lines = [line.strip() for line in out.splitlines() if line.strip()]
            good = [line for line in lines if not _looks_like_error_or_header(line)]
            if good:
                return [_extract_model_name(line) for line in good]
        except (subprocess.TimeoutExpired, TimeoutError):
            raise
        except Exception as exc:
            logger.debug("Exception while listing local models with %s: %s", cmd, exc)
            continue
    return []


class _LibraryModelParser(HTMLParser):
    """Extract model links from Ollama's public library, not presentation text."""

    def __init__(self) -> None:
        super().__init__()
        self.names: set[str] = set()

    def handle_starttag(self, tag: str, attrs: List[tuple[str, Optional[str]]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if not href:
            return
        link = urlsplit(href)
        if link.scheme not in ("", "https") or link.netloc not in ("", "ollama.com"):
            return
        match = re.fullmatch(
            r"/library/([A-Za-z0-9][A-Za-z0-9_.-]*(?::[A-Za-z0-9][A-Za-z0-9_.-]*)?)/?",
            link.path,
        )
        if match:
            self.names.add(match.group(1))


def list_remote_models(
    *, host: Optional[str] = None, port: int = DEFAULT_PORT, timeout: float = 30.0
) -> List[str]:
    """Discover model families from https://ollama.com/library.

    No local CLI or daemon is required. Retained host/port arguments do not
    select a registry: the source is Ollama's public library. This is HTML
    discovery, not a documented catalogue API or an enumeration of all tags.
    Fetch/format errors propagate rather than masquerading as an empty list.
    """
    timeout = _timeout(timeout)
    request = Request(
        "https://ollama.com/library",
        headers={"User-Agent": "modelito", "Accept": "text/html"},
    )
    limit = 4 * 1024 * 1024
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(limit + 1)
        if len(body) > limit:
            raise ValueError("Ollama library response exceeds 4 MiB")
        parser = _LibraryModelParser()
        parser.feed(body.decode("utf-8"))
        if not parser.names:
            raise ValueError("Ollama library contains no recognised model links")
        return sorted(parser.names)
    except Exception as exc:
        _raise_normalized_network_error(exc, "list_remote_models")


def list_remote_model_catalog(
    query: Optional[str] = None,
    *,
    host: Optional[str] = None,
    port: int = DEFAULT_PORT,
    timeout: float = 30.0,
    include_installed: bool = True,
) -> List[RemoteModelCatalogEntry]:
    """Return a structured remote model catalog with light metadata.

    The helper builds on `list_remote_models()` and adds a stable object shape
    for higher-level tooling, including a simple query filter and whether the
    model appears to already be installed locally.
    """
    try:
        installed = (
            set(list_local_models(host=host, port=port, timeout=timeout))
            if include_installed
            else set()
        )
    except (subprocess.TimeoutExpired, TimeoutError):
        raise
    except Exception:
        if host is not None:
            raise
        installed = set()

    query_text = (query or "").strip().lower()
    entries: List[RemoteModelCatalogEntry] = []
    seen: set[str] = set()
    for raw_item in list_remote_models(host=host, port=port, timeout=timeout):
        entry = _catalog_entry(raw_item, installed)
        if entry is None or entry.name in seen:
            continue
        haystack = " ".join([entry.name, entry.family, entry.raw]).lower()
        if query_text and query_text not in haystack:
            continue
        entries.append(entry)
        seen.add(entry.name)
    return sorted(entries, key=lambda item: item.name)


def download_model_progress(
    model_name: str,
    timeout: float = 600.0,
    *,
    host: Optional[str] = None,
    port: int = DEFAULT_PORT,
) -> Generator[ModelLifecycleState, None, None]:
    """Yield structured lifecycle updates while downloading a model.

    The function tracks the latest state in the in-memory lifecycle registry so
    UI or automation can poll by model name while a download is in progress.
    """
    deadline = time.monotonic() + _timeout(timeout)
    binp = get_ollama_binary()
    if not binp:
        yield _record_model_state(
            model_name,
            "error",
            error="ollama binary not found",
            message="ollama binary not found",
        )
        return

    yield _record_model_state(
        model_name,
        "downloading",
        message=f"Starting download for {model_name}",
        progress=0.0,
    )

    commands = [[binp, "pull", model_name], [binp, "download", model_name]]
    for index, cmd in enumerate(commands):
        process: Optional[subprocess.Popen[str]] = None
        last_line = ""
        try:
            _remaining(deadline, cmd, timeout)
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                env=_cli_env(host, port),
            )
            assert process.stdout is not None
            output: queue.Queue[Any] = queue.Queue()

            def read_output(
                stream: Any = process.stdout, sink: queue.Queue[Any] = output
            ) -> None:
                try:
                    for line in stream:
                        sink.put(line)
                except Exception as exc:
                    sink.put(exc)
                finally:
                    sink.put(None)

            reader = threading.Thread(target=read_output, daemon=True)
            reader.start()
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(cmd, timeout)
                try:
                    raw_line = output.get(timeout=remaining)
                except queue.Empty:
                    raise subprocess.TimeoutExpired(cmd, timeout)
                if raw_line is None:
                    break
                if isinstance(raw_line, Exception):
                    raise raw_line
                line = raw_line.rstrip("\n")
                if not line:
                    continue
                last_line = line
                progress, completed, total = _parse_progress_from_line(line)
                phase = _phase_from_progress_line(line)
                yield _record_model_state(
                    model_name,
                    phase,
                    message=line,
                    progress=progress,
                    completed=completed,
                    total=total,
                )
            returncode = process.wait(timeout=max(0.001, deadline - time.monotonic()))
            if returncode == 0:
                yield _record_model_state(
                    model_name,
                    "downloaded",
                    message=last_line or f"Downloaded {model_name}",
                    progress=100.0,
                )
                return
            if index == len(commands) - 1:
                yield _record_model_state(
                    model_name,
                    "error",
                    message=last_line or f"Download failed for {model_name}",
                    error=f"download command exited with status {returncode}",
                )
                return
            yield _record_model_state(
                model_name,
                "retrying",
                message=f"Retrying download for {model_name} with fallback command",
            )
        except FileNotFoundError:
            yield _record_model_state(
                model_name,
                "error",
                error="ollama binary not found",
                message="ollama binary not found",
            )
            return
        except subprocess.TimeoutExpired:
            if process is not None:
                try:
                    process.kill()
                except Exception:
                    pass
            yield _record_model_state(
                model_name,
                "error",
                error=f"download timed out after {timeout} seconds",
                message=f"download timed out after {timeout} seconds",
            )
            return
        except Exception as exc:
            if index == len(commands) - 1:
                yield _record_model_state(
                    model_name, "error", error=str(exc), message=str(exc)
                )
                return
            yield _record_model_state(
                model_name,
                "retrying",
                message=f"Retrying download for {model_name}: {exc}",
            )
        finally:
            if process is not None:
                try:
                    if process.poll() is None:
                        process.kill()
                    process.wait(timeout=5)
                finally:
                    stream = process.stdout
                    if stream is not None and hasattr(stream, "close"):
                        stream.close()


def download_model(
    model_name: str,
    timeout: float = 600.0,
    *,
    host: Optional[str] = None,
    port: int = DEFAULT_PORT,
) -> bool:
    """Download a remote model into the local Ollama cache using the CLI.

    Tries common command names (``pull``, ``download``) and returns ``True``
    when the subprocess exit code indicates success.

    Args:
        model_name: Name of the model to download.
        timeout: Subprocess timeout in seconds.

    Returns:
        ``True`` on success, else ``False``.
    """
    final_state: Optional[ModelLifecycleState] = None
    for state in download_model_progress(
        model_name, timeout=timeout, host=host, port=port
    ):
        final_state = state
    if final_state is None:
        logger.debug("download_model produced no lifecycle updates for %s", model_name)
        return False
    ok = final_state.phase == "downloaded"
    if not ok:
        logger.warning(
            "download_model failed for %s: %s",
            model_name,
            final_state.error or final_state.message,
        )
    return ok


def delete_model(
    model_name: str,
    *,
    host: Optional[str] = None,
    port: int = DEFAULT_PORT,
    timeout: float = 60.0,
) -> bool:
    """Delete a locally cached model using the Ollama CLI.

    Tries multiple possible subcommands (``rm``, ``remove``, ``delete``) and
    returns ``True`` when any of them report success.
    """
    deadline = time.monotonic() + _timeout(timeout)
    binp = get_ollama_binary()
    if not binp:
        logger.debug("delete_model: ollama binary not found")
        return False
    cmds = [
        [binp, "rm", model_name],
        [binp, "remove", model_name],
        [binp, "delete", model_name],
    ]
    for cmd in cmds:
        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=_remaining(deadline, cmd, timeout),
                env=_cli_env(host, port),
                check=False,
            )
            if res.returncode == 0:
                logger.debug("delete_model succeeded for %s via %s", model_name, cmd)
                return True
            else:
                logger.debug(
                    "delete_model attempt for %s via %s returned %s; stdout=%s stderr=%s",
                    model_name,
                    cmd,
                    res.returncode,
                    (res.stdout or "")[:1000],
                    (res.stderr or "")[:1000],
                )
        except (subprocess.TimeoutExpired, TimeoutError):
            raise
        except Exception as exc:
            logger.debug(
                "Exception running delete command %s for %s: %s", cmd, model_name, exc
            )
            continue
    return False


def serve_model(
    model_name: Optional[str] = None,
    start_args: Optional[List[str]] = None,
    timeout: float = 10.0,
) -> bool:
    """Start ``ollama serve`` and wait until a server is reachable.

    Uses :func:`start_detached_ollama_serve` so environment and detachment
    semantics are consistent across helpers.
    """
    if not ollama_installed():
        return False

    host_env = (
        f"{DEFAULT_URL.replace('http://', '').replace('https://', '')}:{DEFAULT_PORT}"
    )
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


def ensure_model_available(
    model_name: str,
    allow_download: bool = False,
    timeout: float = 600.0,
    *,
    host: Optional[str] = None,
    port: int = DEFAULT_PORT,
) -> bool:
    """Ensure a model is available locally, optionally attempting to download it.

    Args:
        model_name: Name of the model to check.
        allow_download: If True, try to download the model when missing.
        timeout: Timeout for download operations in seconds.

    Returns:
        True if the model is available locally (or successfully downloaded), else False.
    """
    try:
        local = list_local_models(host=host, port=port, timeout=timeout)
    except Exception:
        local = []
    if model_name in local:
        return True
    if not allow_download:
        return False
    return download_model(model_name, timeout=timeout, host=host, port=port)


def ensure_model_ready(
    model_name: str,
    host: str = DEFAULT_URL,
    port: int = DEFAULT_PORT,
    auto_start: bool = False,
    allow_download: bool = False,
    timeout: float = 120.0,
) -> bool:
    """Ensure a specific model is downloaded, warmed, and ready to serve.

    This helper goes beyond server liveness by optionally starting Ollama,
    downloading the selected model, issuing a warm-up request, and confirming a
    follow-up model-scoped generate call succeeds.
    """
    result = ensure_model_ready_detailed(
        model_name,
        host=host,
        port=port,
        auto_start=auto_start,
        allow_download=allow_download,
        timeout=timeout,
    )
    return result.success


def ensure_model_ready_detailed(
    model_name: str,
    host: str = DEFAULT_URL,
    port: int = DEFAULT_PORT,
    auto_start: bool = False,
    allow_download: bool = False,
    timeout: float = 120.0,
) -> ReadinessResult:
    """Ensure a specific model is downloaded, warmed, and ready; return structured result.

    Similar to `ensure_model_ready()` but returns a structured `ReadinessResult`
    object with success, phase, message, source, elapsed time, and error details.
    This is useful for UI integration and detailed diagnostics without polling.
    """
    start_time = time.time()
    deadline = start_time + float(timeout)
    _record_model_state(
        model_name, "preparing", message=f"Preparing model {model_name}"
    )

    ok, message = ensure_ollama_running_verbose(
        host=host, port=port, auto_start=auto_start, timeout=min(timeout, 30.0)
    )
    if not ok:
        _record_model_state(model_name, "error", message=message, error=message)
        elapsed = time.time() - start_time
        return ReadinessResult(
            success=False,
            phase="error",
            message=message,
            source="ollama",
            elapsed_seconds=elapsed,
            error=message,
        )

    remaining = max(1.0, deadline - time.time())
    if not ensure_model_available(
        model_name,
        allow_download=allow_download,
        timeout=remaining,
        host=host,
        port=port,
    ):
        error = f"Model {model_name} is not available locally"
        _record_model_state(model_name, "error", message=error, error=error)
        elapsed = time.time() - start_time
        return ReadinessResult(
            success=False,
            phase="error",
            message=error,
            source="cli",
            elapsed_seconds=elapsed,
            error=error,
        )

    _record_model_state(model_name, "warming", message=f"Warming model {model_name}")
    try:
        preload_model(host, port, model_name, timeout=min(remaining, 60.0))
    except Exception as exc:
        _record_model_state(
            model_name, "error", message=str(exc), error=str(exc), source="http"
        )
        elapsed = time.time() - start_time
        return ReadinessResult(
            success=False,
            phase="error",
            message=str(exc),
            source="http",
            elapsed_seconds=elapsed,
            error=str(exc),
        )

    host_env = endpoint_url(host, port, "")
    running = running_model_names(host_env)
    if model_name in running:
        msg = f"Model {model_name} is warmed and running"
        _record_model_state(
            model_name, "ready", message=msg, progress=100.0, source="http"
        )
        elapsed = time.time() - start_time
        return ReadinessResult(
            success=True,
            phase="ready",
            message=msg,
            source="http",
            elapsed_seconds=elapsed,
        )

    try:
        json_post(
            endpoint_url(host, port, "/api/generate"),
            {
                "model": model_name,
                "prompt": "ping",
                "stream": False,
                "keep_alive": "30m",
            },
            timeout=min(max(1.0, deadline - time.time()), 30.0),
        )
    except Exception as exc:
        _record_model_state(
            model_name, "error", message=str(exc), error=str(exc), source="http"
        )
        elapsed = time.time() - start_time
        return ReadinessResult(
            success=False,
            phase="error",
            message=str(exc),
            source="http",
            elapsed_seconds=elapsed,
            error=str(exc),
        )

    msg = f"Model {model_name} responded to readiness probe"
    _record_model_state(model_name, "ready", message=msg, progress=100.0, source="http")
    elapsed = time.time() - start_time
    return ReadinessResult(
        success=True,
        phase="ready",
        message=msg,
        source="http",
        elapsed_seconds=elapsed,
    )


def ensure_model_loaded(
    model_name: str,
    host: str = DEFAULT_URL,
    port: int = DEFAULT_PORT,
    auto_start: bool = False,
    allow_download: bool = False,
    timeout: float = 120.0,
) -> bool:
    """Ensure a model is available locally and loaded/warmed for inference.

    This is an explicit alias for `ensure_model_ready()` to provide a clearer
    lifecycle primitive for callers that reason in "loaded" terminology.
    """
    return ensure_model_ready(
        model_name,
        host=host,
        port=port,
        auto_start=auto_start,
        allow_download=allow_download,
        timeout=timeout,
    )


async def async_ensure_model_available(
    model_name: str,
    allow_download: bool = False,
    timeout: float = 600.0,
    *,
    host: Optional[str] = None,
    port: int = DEFAULT_PORT,
) -> bool:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        partial(
            ensure_model_available,
            model_name,
            allow_download,
            timeout,
            host=host,
            port=port,
        ),
    )


async def async_ensure_model_ready(
    model_name: str,
    host: str = DEFAULT_URL,
    port: int = DEFAULT_PORT,
    auto_start: bool = False,
    allow_download: bool = False,
    timeout: float = 120.0,
) -> bool:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        ensure_model_ready,
        model_name,
        host,
        port,
        auto_start,
        allow_download,
        timeout,
    )


async def async_ensure_model_ready_detailed(
    model_name: str,
    host: str = DEFAULT_URL,
    port: int = DEFAULT_PORT,
    auto_start: bool = False,
    allow_download: bool = False,
    timeout: float = 120.0,
) -> ReadinessResult:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        ensure_model_ready_detailed,
        model_name,
        host,
        port,
        auto_start,
        allow_download,
        timeout,
    )


def change_ollama_config(
    config: Dict[str, Any], config_path: Optional[str] = None
) -> bool:
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
            candidates.append(
                Path(local_appdata) / "Programs" / "Ollama" / "ollama.exe"
            )
        candidates.append(
            Path.home() / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe"
        )
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
    """Find the best available `ollama` CLI path or raise FileNotFoundError.

    The resolver probes candidates returned by :func:`ollama_binary_candidates`,
    which includes a PATH lookup via :func:`shutil.which` and a small set of
    common platform-specific locations (macOS app bundles, Homebrew paths,
    common UNIX locations, and Windows Program Files candidates). The first
    candidate that exists on the filesystem is returned. If no candidate is
    present a :class:`FileNotFoundError` is raised.
    """
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


def run_ollama_command(
    *args: str,
    host: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    timeout: float = 30.0,
) -> subprocess.CompletedProcess[str]:
    """Run an Ollama CLI command and capture the Result.

    Args:
        *args: Arguments to pass to the resolved ``ollama`` binary.
        host: Optional host string to set as ``OLLAMA_HOST`` in the subprocess
            environment (e.g. ``"127.0.0.1:11434"``).
        env: Optional environment mapping to merge into the child process
            environment. When provided it overlays on top of the current
            environment. The helper also ensures the repository root is
            present in ``PYTHONPATH`` to support entrypoints that import
            local modules via ``python -m``.
        timeout: Finite positive subprocess deadline; expiry propagates as
            ``subprocess.TimeoutExpired``.

    Returns:
        A :class:`subprocess.CompletedProcess` instance containing stdout/stderr
        and return code.
    """
    timeout = _timeout(timeout)
    base_env = os.environ.copy()
    if env:
        base_env.update(env)
    if host:
        base_env["OLLAMA_HOST"] = host
    _ensure_pythonpath_env(base_env)
    command = resolve_ollama_command()
    return subprocess.run(
        [command, *args],
        cwd=str(ROOT),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        env=base_env,
        timeout=timeout,
    )


def start_detached_ollama_serve(
    host: str,
    start_args: Optional[List[str]] = None,
    env: Optional[Dict[str, str]] = None,
) -> subprocess.Popen[Any]:
    """Start `ollama serve` in the background for the current platform.

    `start_args` are appended to the serve command and can include options
    such as `--model <name>`.

    Args:
        host: Host:port string to set as ``OLLAMA_HOST`` in the child env.
        start_args: Optional list of extra args to append to ``serve``.
        env: Optional environment mapping to merge into the child process.
    """
    command = resolve_ollama_command()
    cmd = [command, "serve"]
    if start_args:
        cmd.extend(start_args)

    # Build common parameters explicitly to satisfy strict typing of subprocess.Popen
    common_env: Dict[str, str] = {**os.environ, **(env or {}), "OLLAMA_HOST": host}
    _ensure_pythonpath_env(common_env)
    if os.name == "nt":
        creationflags_val = (
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        process = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            env=common_env,
            text=True,
            creationflags=creationflags_val,
        )
    else:
        process = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            env=common_env,
            text=True,
            start_new_session=True,
        )
    _record_owned_server(host, process)
    return process


def _ownership_path(host: str) -> Path:
    key = hashlib.sha256(endpoint_url(host, DEFAULT_PORT, "").encode()).hexdigest()
    return Path.home() / ".modelito" / "servers" / f"{key}.json"


def _record_owned_server(host: str, process: subprocess.Popen[Any]) -> None:
    try:
        import psutil

        if process.poll() is not None:
            return
        proc = psutil.Process(process.pid)
        receipt = {
            "pid": proc.pid,
            "created": proc.create_time(),
            "exe": proc.exe(),
            "cmdline": proc.cmdline(),
        }
        if process.poll() is not None:
            return
        path = _ownership_path(host)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(f".{os.getpid()}.tmp")
        temporary.write_text(json.dumps(receipt), encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(path)
    except Exception:
        logger.warning(
            "Cannot record Ollama ownership; automatic stop is disabled", exc_info=True
        )


def _raise_normalized_network_error(exc: Exception, operation: str) -> NoReturn:
    err = normalize_network_error(exc, provider="ollama", operation=operation)
    raise ProviderError(
        err.message, provider="ollama", code=err.code, details=err.details
    ) from exc


def json_post(
    url: str,
    payload: Dict[str, Any],
    timeout: float = 60.0,
    policy: Optional[TransportPolicy] = None,
) -> Dict[str, Any]:
    """POST JSON payload with timeout + retry/backoff support."""

    merged_policy = policy or TransportPolicy(timeout=timeout)

    def _op() -> Dict[str, Any]:
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=merged_policy.timeout) as response:
            body = response.read().decode("utf-8")
        return json.loads(body) if body else {}

    try:
        return retry_with_backoff(
            _op,
            policy=merged_policy,
            is_retryable=lambda exc: normalize_network_error(exc).retryable,
        )
    except Exception as exc:
        _raise_normalized_network_error(exc, "json_post")


def json_get(
    url: str,
    timeout: float = 5.0,
    policy: Optional[TransportPolicy] = None,
) -> Dict[str, Any]:
    """Read JSON from an HTTP GET endpoint with timeout + retry/backoff."""

    merged_policy = policy or TransportPolicy(timeout=timeout)

    def _op() -> Dict[str, Any]:
        with urlopen(url, timeout=merged_policy.timeout) as response:
            body = response.read().decode("utf-8")
        return json.loads(body) if body else {}

    try:
        return retry_with_backoff(
            _op,
            policy=merged_policy,
            is_retryable=lambda exc: normalize_network_error(exc).retryable,
        )
    except Exception as exc:
        _raise_normalized_network_error(exc, "json_get")


def ollama_health_check(
    host: str = DEFAULT_URL,
    port: int = DEFAULT_PORT,
    timeout: float = 2.0,
    policy: Optional[TransportPolicy] = None,
) -> Dict[str, Any]:
    """Return a best-effort health snapshot for the local Ollama service."""
    started = time.time()
    host_env = endpoint_url(host, port, "")
    reachable = server_is_up(host, port)
    version = ""
    http_ok = False
    error: Optional[str] = None

    if reachable:
        try:
            version_payload = json_get(
                endpoint_url(host, port, "/api/version"),
                timeout=timeout,
                policy=policy,
            )
            http_ok = True
            if isinstance(version_payload, dict):
                version = str(
                    version_payload.get("version")
                    or version_payload.get("ollama_version")
                    or ""
                )
        except Exception as exc:
            error = str(exc)

    try:
        running = running_model_names(host_env)
    except Exception:
        running = []

    return {
        "host": host,
        "port": port,
        "reachable": bool(reachable),
        "http_ok": bool(http_ok),
        "version": version,
        "running_models": running,
        "ready": bool(reachable and (http_ok or len(running) > 0)),
        "duration_ms": int((time.time() - started) * 1000),
        "error": error,
    }


def ollama_readiness_probe(
    host: str = DEFAULT_URL,
    port: int = DEFAULT_PORT,
    timeout: float = 2.0,
    policy: Optional[TransportPolicy] = None,
) -> bool:
    """Probe whether the local Ollama service is ready for request handling."""
    merged_policy = policy or TransportPolicy(timeout=timeout)
    try:
        json_get(
            endpoint_url(host, port, "/api/tags"), timeout=timeout, policy=merged_policy
        )
        return True
    except Exception:
        return False


async def async_preload_model(
    url: str, port: int, model: str, timeout: float = 120.0
) -> None:
    """Async wrapper around :func:`preload_model` using an executor."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, preload_model, url, port, model, timeout)


async def async_list_local_models(
    *, host: Optional[str] = None, port: int = DEFAULT_PORT, timeout: float = 30.0
) -> List[str]:
    """Async wrapper for :func:`list_local_models`."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, partial(list_local_models, host=host, port=port, timeout=timeout)
    )


async def async_list_remote_models(
    *, host: Optional[str] = None, port: int = DEFAULT_PORT, timeout: float = 30.0
) -> List[str]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, partial(list_remote_models, host=host, port=port, timeout=timeout)
    )


async def async_download_model(
    model_name: str,
    timeout: float = 600.0,
    *,
    host: Optional[str] = None,
    port: int = DEFAULT_PORT,
) -> bool:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, partial(download_model, model_name, timeout, host=host, port=port)
    )


async def async_delete_model(
    model_name: str,
    *,
    host: Optional[str] = None,
    port: int = DEFAULT_PORT,
    timeout: float = 60.0,
) -> bool:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, partial(delete_model, model_name, host=host, port=port, timeout=timeout)
    )


async def async_serve_model(
    model_name: Optional[str] = None,
    start_args: Optional[List[str]] = None,
    timeout: float = 10.0,
) -> bool:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, serve_model, model_name, start_args, timeout
    )


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
    json_post(
        endpoint_url(url, port, "/api/generate"),
        {"model": model, "keep_alive": "30m", "stream": False},
        timeout=timeout,
    )


def running_model_names(host: str, timeout: float = 30.0) -> List[str]:
    """Return the names reported by `ollama ps` (best-effort)."""
    try:
        proc = run_ollama_command("ps", host=host, timeout=timeout)
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
    _load_config_data: Optional[Callable[..., Dict[str, Any]]] = None
    _load_config: Optional[Callable[..., Dict[str, Any]]] = None
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


def _effective_config(
    path: Optional[str], config: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    if config is None:
        return load_llm_config(path)
    if path is not None:
        raise ValueError("supply config or config_path, not both")
    return {
        "url": DEFAULT_URL,
        "port": DEFAULT_PORT,
        "model": "",
        "last_served_model": "",
        **config,
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


def ollama_version_text(host: Optional[str] = None, timeout: float = 30.0) -> str:
    try:
        proc = run_ollama_command("--version", host=host, timeout=timeout)
    except FileNotFoundError:
        return ""
    return (proc.stdout or proc.stderr or "").strip()


def install_command_for_current_platform(
    platform_name: Optional[str] = None,
) -> tuple[List[str], str]:
    selected_method = detect_install_method(platform_name=platform_name)
    return _install_command_for_method(selected_method)


def install_service(reinstall: bool = False, timeout: float = 600.0) -> tuple[int, str]:
    action = "reinstall" if reinstall else "install"
    command, display = install_command_for_current_platform()
    try:
        proc = subprocess.run(
            command,
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            check=False,
            timeout=_timeout(timeout),
        )
        combined = ((proc.stdout or "") + (proc.stderr or "")).strip()
        if proc.returncode == 0:
            return 0, combined or f"Completed the official Ollama {action} workflow."
        return proc.returncode, combined or f"Ollama {action} failed."
    except FileNotFoundError as exc:
        return 1, f"Unable to launch the Ollama installer command ({display}): {exc}"


def inspect_service_state(
    config_path: Optional[str] = None, *, config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    llm = _effective_config(config_path, config)
    url = str(llm["url"])
    port = int(llm["port"])
    host = endpoint_url(url, port, "")
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


def start_service(
    config_path: Optional[str] = None,
    warmup_timeout: float = 30.0,
    *,
    config: Optional[Dict[str, Any]] = None,
    timeout: float = 600.0,
) -> int:
    """Start Ollama service with optional model preload and configurable warmup timeout.

    Args:
        config_path: Optional path to LLM configuration file.
        warmup_timeout: Timeout in seconds for server warmup. Default is 30.0.

    Returns:
        0 on success, non-zero on failure.
    """
    llm = _effective_config(config_path, config)
    model = preferred_start_model(llm)
    url = str(llm["url"])
    port = int(llm["port"])
    host = endpoint_url(url, port, "")
    # Ensure the CLI is available and responding before attempting to start
    try:
        version_proc = run_ollama_command("--version", host=host, timeout=timeout)
    except FileNotFoundError:
        print("ollama: command not found", file=sys.stderr)
        return 1

    if version_proc.returncode != 0 and not (
        version_proc.stdout or version_proc.stderr
    ):
        print("ollama CLI failed to start", file=sys.stderr)
        return 1

    started = False
    if server_is_up(url, port):
        print(f"Ollama already serving at {host}")
    else:
        print(f"Starting ollama serve at {host} ...")
        start_detached_ollama_serve(host)
        try:
            deadline = time.time() + float(warmup_timeout)
            while time.time() < deadline:
                if server_is_up(url, port):
                    break
                time.sleep(0.5)
            if not server_is_up(url, port):
                print(f"Timeout waiting for ollama serve at {host}", file=sys.stderr)
                return 1
        except Exception as exc:
            print(f"Failed to start ollama serve: {exc}", file=sys.stderr)
            return 1
        started = True

    # If no model configured, starting the server successfully is a valid
    # outcome — return success rather than failing early.
    if not model:
        print(f"No model configured in {config_path}", file=sys.stderr)
        if started:
            print(f"Completed: started ollama at {host} (no model configured).")
        else:
            print(f"Completed: ollama already running at {host} (no model configured).")
        return 0

    pull_proc = run_ollama_command("pull", model, host=host, timeout=timeout)
    if pull_proc.returncode != 0:
        sys.stderr.write((pull_proc.stdout or "") + (pull_proc.stderr or ""))
        return pull_proc.returncode

    try:
        preload_model(url, port, model, timeout=120.0)
    except Exception as exc:
        print(f"Failed to warm model {model}: {exc}", file=sys.stderr)
        return 1

    if config is None:
        save_last_served_model(model, config_path)

    if started:
        print(
            f"Completed: started ollama at {host}, pulled and warmed model '{model}'."
        )
    else:
        print(
            f"Completed: ollama already running at {host}; pulled and warmed model '{model}'."
        )
    return 0


def pull_model(
    model_name: str,
    timeout: float = 600.0,
    *,
    host: Optional[str] = None,
    port: int = DEFAULT_PORT,
) -> bool:
    """Pull/download a remote model into the local cache.

    This is a small convenience wrapper that delegates to :func:`download_model`.
    """
    return download_model(model_name, timeout=timeout, host=host, port=port)


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

        res = _estimate(model_name)
        # _estimate may return either a numeric value or a (value, source) tuple
        if isinstance(res, tuple):
            t = res[0]
        else:
            t = res
        return float(t)
    except Exception:
        return None


def estimate_remote_model_timeout_details(
    model_name: str, input_tokens: int = 2048, concurrency: int = 1
) -> tuple[int, Dict[str, Any]]:
    """Return a timeout estimate and diagnostic details from the catalog."""
    from .timeout import estimate_remote_timeout as _estimate

    res = _estimate(
        model_name, input_tokens=input_tokens, concurrency=concurrency, with_source=True
    )
    if isinstance(res, tuple):
        t, src = res
    else:
        t = res
        src = {}
    return int(t), dict(src or {})


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="modelito-ollama", description="Manage Ollama lifecycle and models"
    )
    subs = p.add_subparsers(dest="cmd")

    sp = subs.add_parser("start")
    sp.add_argument("--config", "-c", dest="config", default=None)
    sp.add_argument(
        "--warmup-timeout",
        type=float,
        default=30.0,
        help="Server warmup timeout in seconds (default: 30.0)",
    )
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
        warmup_timeout = getattr(args, "warmup_timeout", 30.0)
        return start_service(cfg, warmup_timeout=warmup_timeout)

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


def _listener_pids_from_connections(connections: Iterable[Any], port: int) -> List[int]:
    pids: set[int] = set()
    for conn in connections:
        try:
            if (
                conn.status != getattr(conn, "status", None)
                and getattr(conn, "status", None) is None
            ):
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
        return _listener_pids_from_connections(
            psutil.net_connections(kind="inet"), port
        )
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


def stop_service(
    host: str = DEFAULT_URL,
    port: int = DEFAULT_PORT,
    verbose: bool = False,
    config_path: Optional[str] = None,
    *,
    config: Optional[Dict[str, Any]] = None,
    timeout: float = 3.0,
) -> int:
    """Terminate only a server started by Modelito with a matching ownership receipt.

    Never unload models or discover/kill arbitrary listeners. Missing receipts,
    unavailable psutil, remote endpoints and changed process identity fail closed.
    """
    timeout = _timeout(timeout)
    if config_path is not None or config is not None:
        cfg = _effective_config(config_path, config)
        host, port = str(cfg["url"]), int(cfg["port"])
    endpoint = endpoint_url(host, port, "")
    if urlsplit(endpoint).hostname not in ("localhost", "127.0.0.1", "::1"):
        return 1
    path = _ownership_path(endpoint)
    if not path.exists():
        if verbose:
            print(f"No Modelito ownership receipt for {endpoint}; server preserved.")
        return 1
    try:
        import psutil

        receipt = json.loads(path.read_text(encoding="utf-8"))
        proc = psutil.Process(receipt["pid"])
        command = proc.cmdline()
        if (
            proc.create_time() != receipt["created"]
            or proc.exe() != receipt["exe"]
            or command != receipt["cmdline"]
            or len(command) < 2
            or Path(command[0]).stem.lower() != "ollama"
            or command[1] != "serve"
        ):
            return 1
        proc.terminate()
        try:
            proc.wait(timeout=timeout)
        except psutil.TimeoutExpired:
            # psutil's process object checks PID reuse before signalling.
            proc.kill()
            proc.wait(timeout=timeout)
        path.unlink(missing_ok=True)
        return 0
    except Exception:
        logger.debug("Owned Ollama shutdown failed", exc_info=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
