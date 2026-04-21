"""Timeout estimator using a small catalog of conservative defaults.

This is a compact, readable approximation intended for downstream projects
to compute conservative timeouts for remote LLM calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple, Optional
import re


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


def estimate_remote_timeout(model_name: str | None, input_tokens: int = 2048, concurrency: int = 1, with_source: bool = False) -> "int | Tuple[int, Dict[str, Any]]":
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
        if with_source:
            return 60, {"reason": "no model_name", "catalog_source": load_catalog().get("source")}
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

    # Compute multiplier using a prioritized set of overrides. We record
    # matching choices in the `source` structure so callers can understand
    # why a particular timeout was chosen.
    multiplier = 1.0
    source: Dict[str, Any] = {
        "catalog_source": catalog.get("source"),
        "matched_band": None,
        "matched_model_override": None,
        "pattern_matches": [],
        "family_match": None,
        "keyword_matches": [],
        "concurrency": int(concurrency),
    }

    # matched size band for diagnostics
    matched_band: Optional[Dict[str, Any]] = None
    for band in size_bands:
        if input_tokens <= int(band.get("max_input_tokens", 0)):
            matched_band = band
            break
    if matched_band is None and size_bands:
        matched_band = size_bands[-1]
    source["matched_band"] = matched_band

    # Exact model overrides (highest priority)
    model_overrides = catalog.get("model_overrides", {}) or {}
    if model_overrides:
        mv = model_overrides.get(model)
        if mv is None:
            # try case-insensitive exact matches
            for k, v in model_overrides.items():
                if k.lower() == model:
                    mv = v
                    break
        if mv is not None:
            try:
                multiplier = float(mv)
                source["matched_model_override"] = float(mv)
            except Exception:
                pass

    # If an exact model override is present we treat it as authoritative
    # and skip additional pattern/family/keyword adjustments so the model
    # override remains the primary driver for the multiplier.
    if source.get("matched_model_override") is None:
        # Pattern-based overrides
        pattern_overrides = catalog.get("pattern_overrides", []) or []
        for entry in pattern_overrides:
            try:
                pat = entry.get("pattern")
                mult = float(entry.get("multiplier", 1.0))
                if pat and re.search(pat, model):
                    multiplier *= mult
                    source["pattern_matches"].append({"pattern": pat, "multiplier": mult})
            except Exception:
                continue

        # Family substring overrides
        fam_over = catalog.get("family_overrides", {}) or {}
        for fam, mult in fam_over.items():
            try:
                if fam in model:
                    multiplier *= float(mult)
                    source["family_match"] = fam
                    break
            except Exception:
                continue

        # Keyword adjustments (multiply for each keyword found)
        kw_adj = catalog.get("keyword_adjustments", {}) or {}
        for kw, mult in kw_adj.items():
            try:
                if kw in model:
                    multiplier *= float(mult)
                    source["keyword_matches"].append({"keyword": kw, "multiplier": float(mult)})
            except Exception:
                continue

    # Concurrency factor from catalog (per extra request multiplier)
    try:
        per_extra = float(catalog.get("concurrency_factor", {}).get("per_extra_request", 1.0))
    except Exception:
        per_extra = 1.0
    if int(concurrency) > 1 and per_extra and per_extra != 1.0:
        multiplier *= per_extra ** (int(concurrency) - 1)

    # As a compatibility measure, also account for concurrency linearly
    timeout = int(max(5, base_timeout * multiplier * max(1, int(concurrency))))

    if with_source:
        source["multiplier"] = multiplier
        source["base_timeout"] = base_timeout
        source["input_tokens"] = int(input_tokens)
        return timeout, source
    return timeout
