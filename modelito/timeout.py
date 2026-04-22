"""Timeout estimator using a small bundled catalog.

This module provides a conservative estimation of network/RPC timeouts for
remote LLM calls. It ships a small JSON catalog under `data/` and exposes a
diagnostic helper that returns both the estimated timeout and a details
dictionary useful for debugging and calibration.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def _catalog_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "ollama_remote_timeout_catalog.json"


def load_catalog() -> Dict[str, Any]:
    p = _catalog_path()
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {
        "size_bands": [
            {"max_input_tokens": 2048, "timeout_seconds": 15},
            {"max_input_tokens": 8192, "timeout_seconds": 60},
            {"max_input_tokens": 32768, "timeout_seconds": 300},
        ],
        "family_overrides": {},
        "model_overrides": {},
        "pattern_overrides": [],
        "keyword_adjustments": {},
        "concurrency_factor": {"per_extra_request": 1.15},
    }


def estimate_remote_timeout(model_name: Optional[str], input_tokens: int = 2048, concurrency: int = 1, with_source: bool = False) -> "int | Tuple[int, Dict[str, Any]]":
    t, details = estimate_remote_timeout_details(
        model_name, input_tokens=input_tokens, concurrency=concurrency)
    if with_source:
        return t, details
    return t


def estimate_remote_timeout_details(model_name: Optional[str], input_tokens: int = 2048, concurrency: int = 1) -> Tuple[int, Dict[str, Any]]:
    catalog = load_catalog()
    size_bands = catalog.get("size_bands", []) or []

    model = (model_name or "").lower()

    base_timeout = None
    used_band = None
    for band in size_bands:
        try:
            if input_tokens <= int(band.get("max_input_tokens", 0)):
                base_timeout = int(band.get("timeout_seconds", 60))
                used_band = band
                break
        except Exception:
            continue
    if base_timeout is None:
        base_timeout = int(size_bands[-1].get("timeout_seconds", 300)) if size_bands else 60

    details: Dict[str, Any] = {
        "model": model_name,
        "input_tokens": int(input_tokens),
        "concurrency": int(concurrency),
        "base_timeout": base_timeout,
        "used_size_band": used_band,
    }

    # family overrides
    family_mult = 1.0
    fam_over = catalog.get("family_overrides", {}) or {}
    for fam, mult in fam_over.items():
        if fam in model:
            try:
                family_mult = float(mult)
                details["family_matched"] = fam
            except Exception:
                pass

    # exact model overrides
    model_overrides = catalog.get("model_overrides", {}) or {}
    model_mult = None
    if model_name and model_name in model_overrides:
        try:
            model_mult = float(model_overrides[model_name])
            details["model_override_matched"] = model_name
        except Exception:
            model_mult = None
    if model_mult is not None:
        details["matched_model_override"] = model_mult

    # pattern overrides (regex list of {pattern, multiplier})
    pattern_mult = None
    for patt in (catalog.get("pattern_overrides") or []):
        try:
            if re.match(patt.get("pattern", ""), model or ""):
                pattern_mult = float(patt.get("multiplier", 1.0))
                details.setdefault("pattern_overrides_matched", []).append(patt.get("pattern"))
        except Exception:
            continue

    # keyword adjustments (pick highest)
    kw_adj = catalog.get("keyword_adjustments", {}) or {}
    kw_mult = 1.0
    kw_matches = []
    for kw, mult in kw_adj.items():
        if kw in model:
            try:
                kw_mult = max(kw_mult, float(mult))
                kw_matches.append(kw)
            except Exception:
                pass
    if kw_matches:
        details["keyword_matches"] = kw_matches

    # choose the most conservative multiplier among family/model/pattern/keyword
    multipliers = [1.0, family_mult, kw_mult]
    if model_mult is not None:
        multipliers.append(model_mult)
    if pattern_mult is not None:
        multipliers.append(pattern_mult)
    final_multiplier = max(float(m) for m in multipliers)

    # concurrency adjustment (linear fallback)
    per_extra = float((catalog.get("concurrency_factor") or {}).get("per_extra_request", 1.15))
    concurrency_multiplier = 1.0 + max(0, int(concurrency) - 1) * per_extra

    timeout = int(max(5, base_timeout * final_multiplier * concurrency_multiplier))

    details.update(
        {
            "family_multiplier": family_mult,
            "keyword_multiplier": kw_mult,
            "model_multiplier": model_mult,
            "pattern_multiplier": pattern_mult,
            "chosen_multiplier": final_multiplier,
            "concurrency_multiplier": concurrency_multiplier,
            "estimated_timeout": timeout,
        }
    )

    details["catalog_source"] = "bundled" if _catalog_path().exists() else "fallback"

    return timeout, details
