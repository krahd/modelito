"""Timeout estimator using a small catalog of conservative defaults.

This is a compact, readable approximation intended for downstream projects
to compute conservative timeouts for remote LLM calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def _catalog_path() -> Path:
    """Return the path to the bundled timeout catalog JSON file.

    The catalog file is located under the package ``data/`` directory and is
    used by ``load_catalog()`` as a source of conservative timeout defaults.

    Returns:
        A :class:`pathlib.Path` pointing to the JSON catalog file.
    """
    return Path(__file__).resolve().parent / "data" / "ollama_remote_timeout_catalog.json"


def load_catalog() -> Dict[str, Any]:
    """Load the timeout catalog from the bundled JSON file.

    Attempts to read and parse ``data/ollama_remote_timeout_catalog.json``.
    If the file is missing or cannot be parsed, returns a conservative
    fallback catalog suitable for estimating remote timeouts.

    Returns:
        A dictionary with keys ``size_bands``, ``family_overrides`` and
        ``keyword_adjustments`` used by :func:`estimate_remote_timeout`.
    """
    p = _catalog_path()
    if p.exists():
        try:
            data = json.loads(p.read_text())
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    # fallback minimal catalog
    return {
        "size_bands": [
            {"max_input_tokens": 2048, "timeout_seconds": 15},
            {"max_input_tokens": 8192, "timeout_seconds": 60},
            {"max_input_tokens": 32768, "timeout_seconds": 300},
        ],
        "family_overrides": {},
        "keyword_adjustments": {},
    }


def estimate_remote_timeout(model_name: str | None, input_tokens: int = 2048, concurrency: int = 1) -> int:
    """Estimate a conservative timeout (in seconds) for calling a remote model.

    The estimator uses a small catalog of size bands and optional family or
    keyword multipliers to return a conservative timeout suitable for use as
    an RPC/network timeout.

    Args:
        model_name: Optional model name used to match family or keyword
            overrides (case-insensitive). If ``None`` a sensible default is
            returned.
        input_tokens: Approximate number of input tokens for the request.
        concurrency: Number of concurrent requests to account for.

    Returns:
        Conservative timeout in seconds as an integer.
    """
    if not model_name:
        return 60
    model = model_name.lower()
    catalog = load_catalog()
    size_bands = catalog.get("size_bands", []) or []

    base_timeout = None
    for band in size_bands:
        if input_tokens <= int(band.get("max_input_tokens", 0)):
            base_timeout = int(band.get("timeout_seconds", 60))
            break
    if base_timeout is None:
        if size_bands:
            base_timeout = int(size_bands[-1].get("timeout_seconds", 300))
        else:
            base_timeout = 60

    multiplier = 1.0
    fam_over = catalog.get("family_overrides", {}) or {}
    for fam, mult in fam_over.items():
        if fam in model:
            try:
                multiplier = float(mult)
            except Exception:
                pass
            break

    kw_adj = catalog.get("keyword_adjustments", {}) or {}
    for kw, mult in kw_adj.items():
        if kw in model:
            try:
                multiplier = max(multiplier, float(mult))
            except Exception:
                pass

    timeout = int(max(5, base_timeout * multiplier * max(1, int(concurrency))))
    return timeout
