"""Small Ollama HTTP helpers (lightweight) used by the calibration tool.

This module intentionally provides only thin helpers (endpoint builder and
server liveness check) so the package can be used without requiring the
full Ollama lifecycle helpers from BatLLM.
"""

from __future__ import annotations

import socket
from urllib.request import urlopen
from urllib.error import URLError
from urllib.request import Request
from urllib.error import HTTPError
import time
import shutil
import subprocess
import os
import sys
import shlex
from typing import Optional, List, Dict, Any
from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[1]


def endpoint_url(host: str, port: int, path: str = "/api/generate") -> str:
    h = host.rstrip("/")
    # if host already contains a port, don't append
    if ":" in h.split("/")[2] if "/" in h else ":" in h:
        return f"{h}{path}"
    return f"{h}:{port}{path}"


def server_is_up(host: str, port: int) -> bool:
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


def ensure_ollama_running(host: str = "http://127.0.0.1", port: int = 11434, auto_start: bool = False, start_args: Optional[list] = None, timeout: float = 10.0) -> bool:
    """Ensure an Ollama server is reachable at `host:port`.

    If `auto_start` is True and the `ollama` binary is available on PATH,
    attempt to start `ollama serve` in a detached process and wait up to
    `timeout` seconds for the server to become available.

    Returns True if the server is reachable, False otherwise.
    """
    if server_is_up(host, port):
        return True

    if not auto_start:
        return False

    ollama_bin = shutil.which("ollama")
    if not ollama_bin:
        return False

    cmd = [ollama_bin, "serve"]
    if start_args:
        cmd.extend(start_args)

    # Start detached process, redirect output to devnull
    try:
        devnull = subprocess.DEVNULL
        subprocess.Popen(cmd, stdout=devnull, stderr=devnull)
    except Exception:
        return False

    # wait for the server
    deadline = time.time() + float(timeout)
    while time.time() < deadline:
        if server_is_up(host, port):
            return True
        time.sleep(0.5)
    return False


def get_ollama_binary() -> Optional[str]:
    """Return the path to the `ollama` binary if available on PATH."""
    return shutil.which("ollama")


def install_ollama(allow_install: bool = False, method: Optional[str] = None, timeout: float = 600.0) -> bool:
    """Attempt to install `ollama` using a supported installer.

    This is intentionally conservative: the function will only perform an
    installation if `allow_install` is True. On macOS the default method is
    Homebrew when available.
    """
    if get_ollama_binary():
        return True
    if not allow_install:
        return False
    try:
        import sys

        if (method == "brew") or (method is None and sys.platform == "darwin"):
            if shutil.which("brew"):
                try:
                    subprocess.run(["brew", "install", "ollama"], check=True,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout)
                    return get_ollama_binary() is not None
                except Exception:
                    return False
    except Exception:
        return False
    return False


def start_ollama(host: str = "http://127.0.0.1", port: int = 11434, start_args: Optional[list] = None, timeout: float = 10.0) -> bool:
    """Start `ollama serve` and wait for it to become available."""
    return ensure_ollama_running(host=host, port=port, auto_start=True, start_args=start_args, timeout=timeout)


def stop_ollama(force: bool = False) -> bool:
    """Attempt to stop running `ollama` processes.

    Uses `psutil` when available for a graceful shutdown; falls back to
    `pkill -f ollama` if `force` is True and `pkill` exists.
    """
    try:
        import psutil
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
    """Try to update the `ollama` installation.

    Prefer `ollama update` if supported; fall back to Homebrew upgrade when
    `allow_upgrade` is True and `brew` is available.
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
    """Return a best-effort list of locally installed models (if any)."""
    binp = get_ollama_binary()
    if not binp:
        return []
    cmds = [[binp, "list"], [binp, "ls"], [binp, "models"]]
    for cmd in cmds:
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True, timeout=15, check=False)
            out = res.stdout or res.stderr
            if out:
                lines = [l.strip() for l in out.splitlines() if l.strip()]
                if lines:
                    return lines
        except Exception:
            continue
    return []


def list_remote_models() -> List[str]:
    """Return a best-effort list of remote models available for download."""
    binp = get_ollama_binary()
    if not binp:
        return []
    cmds = [[binp, "list", "--remote"], [binp, "ls", "--remote"],
            [binp, "models", "--remote"], [binp, "llms", "--remote"]]
    for cmd in cmds:
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True, timeout=20, check=False)
            out = res.stdout or res.stderr
            if out:
                lines = [l.strip() for l in out.splitlines() if l.strip()]
                if lines:
                    return lines
        except Exception:
            continue
    return []


def download_model(model_name: str, timeout: float = 600.0) -> bool:
    """Download a remote model into the local Ollama cache.

    Tries common command names (`pull`, `download`) and returns True on
    success.
    """
    binp = get_ollama_binary()
    if not binp:
        return False
    cmds = [[binp, "pull", model_name], [binp, "download", model_name]]
    for cmd in cmds:
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True, timeout=timeout, check=False)
            if res.returncode == 0:
                return True
        except Exception:
            continue
    return False


def delete_model(model_name: str) -> bool:
    """Delete a locally cached model."""
    binp = get_ollama_binary()
    if not binp:
        return False
    cmds = [[binp, "rm", model_name], [binp, "remove", model_name], [binp, "delete", model_name]]
    for cmd in cmds:
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True, timeout=60, check=False)
            if res.returncode == 0:
                return True
        except Exception:
            continue
    return False


def serve_model(model_name: Optional[str] = None, start_args: Optional[list] = None, timeout: float = 10.0) -> bool:
    """Serve Ollama (optionally specifying a particular model) and wait until up."""
    binp = get_ollama_binary()
    if not binp:
        return False
    cmd = [binp, "serve"]
    if model_name:
        cmd.extend(["--model", model_name])
    if start_args:
        cmd.extend(start_args)
    try:
        devnull = subprocess.DEVNULL
        subprocess.Popen(cmd, stdout=devnull, stderr=devnull)
    except Exception:
        return False
    deadline = time.time() + timeout
    while time.time() < deadline:
        if server_is_up("http://127.0.0.1", 11434):
            return True
        time.sleep(0.5)
    return False


def change_ollama_config(config: Dict[str, Any], config_path: Optional[str] = None) -> bool:
    """Write `config` as JSON to the Ollama configuration file.

    Default path is `~/.ollama/config.json`.
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


def run_ollama_command(*args: str, host: Optional[str] = None) -> subprocess.CompletedProcess:
    """Run an Ollama CLI command and capture the result.

    `host` when provided should be the host:port string used by the Ollama
    CLI via the `OLLAMA_HOST` env var (e.g. "127.0.0.1:11434").
    """
    env = os.environ.copy()
    if host:
        env["OLLAMA_HOST"] = host
    command = resolve_ollama_command()
    return subprocess.run([command, *args], cwd=str(ROOT), text=True, capture_output=True, check=False, env=env)


def start_detached_ollama_serve(host: str) -> subprocess.Popen:
    """Start `ollama serve` in the background for the current platform."""
    command = resolve_ollama_command()
    kwargs: Dict[str, object] = {
        "cwd": str(ROOT),
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
        "env": {**os.environ, "OLLAMA_HOST": host},
        "text": True,
    }

    if os.name == "nt":
        kwargs["creationflags"] = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        )
    else:
        kwargs["start_new_session"] = True

    return subprocess.Popen([command, "serve"], **kwargs)


def json_post(url: str, payload: dict, timeout: float = 60.0) -> dict:
    request = Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    return json.loads(body) if body else {}


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
    json_post(endpoint_url(url, port, "/api/generate"), {"model": model, "keep_alive": "30m"}, timeout=timeout)


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


def _listener_pids_from_connections(connections, port: int) -> List[int]:
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
        import psutil
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


def stop_service(host: str = "http://127.0.0.1", port: int = 11434, verbose: bool = False) -> int:
    """Stop running models and terminate server processes (best-effort).

    Returns 0 on success, non-zero on failure.
    """
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
        import psutil
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
            _gone, alive = psutil.wait_procs([psutil.Process(pid) for pid in pids if psutil.pid_exists(pid)], timeout=3.0)
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
