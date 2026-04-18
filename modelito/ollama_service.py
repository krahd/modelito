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
from typing import Optional


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
