"""Small config helpers for modelito.

Provides JSON/YAML loading and simple host:port parsing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple, List, Optional


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


def _merge_dicts(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Deep-merge two dictionaries.

    Values from ``b`` take precedence. Nested mappings are merged
    recursively; non-mapping values are overwritten by the value from
    ``b``.
    """
    out: Dict[str, Any] = dict(a or {})
    for k, v in (b or {}).items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _merge_dicts(out[k], v)
        else:
            out[k] = v
    return out


def load_config_data(path: Optional[str] = None, overlays: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Load configuration and apply overlay dictionaries.

    This helper extends :func:`load_config` by allowing callers to supply
    one or more overlay dictionaries that will be merged on top of the
    loaded file. Overlays are applied in-order so later entries override
    earlier ones.

    Args:
        path: Optional path to a JSON/YAML config file.
        overlays: Optional list of dictionaries to merge on top of the file.

    Returns:
        A merged configuration dictionary (possibly empty).
    """
    data: Dict[str, Any] = {}
    if path:
        try:
            data = load_config(path) or {}
        except Exception:
            data = {}
    # apply overlays in order
    if overlays:
        for ov in overlays:
            if isinstance(ov, dict):
                data = _merge_dicts(data, ov)
    return data
