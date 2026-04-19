"""Small config helpers for modelito.

Provides JSON/YAML loading and simple host:port parsing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple


def load_config(path: str) -> Dict[str, Any]:
    """Load configuration from a JSON or YAML file.

    The function first attempts to read the path as JSON. If JSON parsing
    fails and PyYAML is available, it will attempt to parse YAML. If the
    file does not exist or cannot be parsed, an empty dictionary is
    returned.

    Args:
        path: Path to the configuration file.

    Returns:
        Parsed configuration as a dictionary, or an empty dict on error.
    """
    p = Path(path)
    if not p.exists():
        return {}
    text = p.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    # try YAML if available (dynamic import to avoid static lint errors)
    try:
        import importlib

        yaml = importlib.import_module("yaml")
    except Exception:
        yaml = None

    if yaml is not None:
        try:
            return yaml.safe_load(text) or {}
        except Exception:
            return {}

    return {}


def parse_host_port(host_url: str) -> Tuple[str, int]:
    """Parse a host:port string or HTTP URL into a (host, port) tuple.

    Examples:
        >>> parse_host_port('http://127.0.0.1:11434')
        ('127.0.0.1', 11434)
        >>> parse_host_port('localhost:11434')
        ('localhost', 11434)

    Args:
        host_url: A host:port string or full URL.

    Returns:
        A tuple of ``(host, port)``. Defaults to port ``11434`` when a port
        cannot be parsed.
    """
    if host_url.startswith("http://") or host_url.startswith("https://"):
        from urllib.parse import urlparse

        u = urlparse(host_url)
        host = u.hostname or "localhost"
        port = int(u.port or 11434)
        return host, port
    if ":" in host_url:
        host, port_s = host_url.split(":", 1)
        try:
            return host, int(port_s)
        except Exception:
            return host, 11434
    return host_url, 11434
