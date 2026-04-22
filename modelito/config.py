"""Small config helpers for modelito.

Provides JSON/YAML loading and a multi-path deep-merge helper.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union


def load_config(path: str) -> Dict[str, Any]:
    """Load configuration from a JSON or YAML file.

    Tries JSON first and falls back to YAML (if available).
    Returns an empty dict on error or when the file is missing.
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

    Defaults to port 11434 when a port cannot be parsed.
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


def _deep_merge(a: dict, b: dict) -> dict:
    """Recursively merge dict `b` into dict `a` and return the result.

    Values from `b` take precedence. Nested dicts are merged recursively.
    """
    result = dict(a)
    for key, val in b.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def load_config_data(*paths: Union[str, Path], default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Load and merge configuration files from multiple paths.

    Later paths override earlier ones. Non-existing paths are skipped. An
    optional `default` dict can be provided as the base configuration.
    """
    base: Dict[str, Any] = dict(default or {})
    for p in paths:
        if not p:
            continue
        pth = Path(p)
        if not pth.exists():
            continue
        try:
            data = load_config(str(pth))
        except Exception:
            try:
                text = pth.read_text(encoding="utf-8")
                data = json.loads(text) if text else {}
            except Exception:
                data = {}
        if not isinstance(data, dict):
            continue
        base = _deep_merge(base, data)
    return base
