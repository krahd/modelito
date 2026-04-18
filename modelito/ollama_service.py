"""Small Ollama HTTP helpers (lightweight) used by the calibration tool.

This module intentionally provides only thin helpers (endpoint builder and
server liveness check) so the package can be used without requiring the
full Ollama lifecycle helpers from BatLLM.
"""

from __future__ import annotations

import socket
from urllib.request import urlopen
from urllib.error import URLError


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
