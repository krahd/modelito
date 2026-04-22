"""Small config helpers for modelito.

Provides JSON/YAML loading and simple host:port parsing.
"""

from __future__ import annotations
from typing import Any, Dict, Tuple, Optional, Union
from typing import Any, Dict, Tuple, List, Optional, Union

import json
from pathlib import Path
<< << << < HEAD
== == == =
>>>>>> > f1078c8(Phase B / C: config merge, timeout diagnostics & calibration, async Ollama wrappers, docs, release helper)


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


<< << << < HEAD
def _deep_merge(a: dict, b: dict) -> dict:
    """Recursively merge dict `b` into dict `a` and return the result.

    Values from `b` take precedence. Nested dicts are merged recursively.
    Non-dict values in `b` replace values from `a`.
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

    Paths are applied in the order given; later paths override earlier ones.
    Each path may be a JSON or YAML file (when PyYAML is installed). If a
    path does not exist it is skipped. An optional ``default`` dict may be
    provided as the base configuration.

    Returns the merged configuration as a dict.
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
                # fallback to direct JSON read if load_config is unavailable
                text = pth.read_text(encoding="utf-8")
                data = json.loads(text) if text else {}
            except Exception:
                data = {}
        if not isinstance(data, dict):
            continue
        base = _deep_merge(base, data)
    return base
== == == =
def _deep_merge(a: dict, b: dict) -> dict:
    """Recursively merge dict `b` into dict `a` and return the result.

    Values from `b` take precedence. Nested dicts are merged recursively.
    Non-dict values in `b` replace values from `a`.
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

    Paths are applied in the order given; later paths override earlier ones.
    Each path may be a JSON or YAML file (when PyYAML is installed). If a
    path does not exist it is skipped. An optional ``default`` dict may be
    provided as the base configuration.

    Returns the merged configuration as a dict.
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
                # fallback to direct JSON read if load_config is unavailable
                text = pth.read_text(encoding="utf-8")
                data = json.loads(text) if text else {}
            except Exception:
                data = {}
        if not isinstance(data, dict):
            continue
        base = _deep_merge(base, data)
    return base
>>>>>> > f1078c8(Phase B / C: config merge, timeout diagnostics & calibration, async Ollama wrappers, docs, release helper)
