"""Small Ollama HTTP helpers (lightweight) used by the calibration tool.

This module intentionally provides only thin helpers (endpoint builder and
server liveness check) so the package can be used without requiring the
full Ollama lifecycle helpers from BatLLM.
"""

from __future__ import annotations

import socket
from urllib.request import urlopen
from urllib.error import URLError
import time
import shutil
import subprocess
from typing import Optional, List, Dict, Any
from pathlib import Path
import json


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
