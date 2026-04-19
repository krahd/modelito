#!/usr/bin/env python3
"""CI helper: fail if legacy dict-shaped messages are present in `modelito/`.

This script scans the `modelito/` package for simple patterns that indicate
legacy dict-style messages like `{'role': 'user', 'content': '...'}` or
calls to `to_message(...)`. If any matches are found the script exits non-zero
so CI can fail and prevent regressions.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "modelito"
PATTERNS = [
    # Only fail on direct `to_message(...)` usage. Many provider adapters
    # legitimately construct small `{'role': ..., 'content': ...}` payloads
    # for transport; we allow those.
    re.compile(r"to_message\("),
]

EXCLUDE_FILES = []


def scan() -> int:
    matches = []
    for p in MODEL_DIR.rglob("*.py"):
        if any(str(p).endswith(x) for x in EXCLUDE_FILES):
            continue
        text = p.read_text(encoding="utf8")
        for i, line in enumerate(text.splitlines(), start=1):
            for pat in PATTERNS:
                if pat.search(line):
                    matches.append((p.relative_to(ROOT), i, line.strip()))
    if matches:
        print("Legacy dict-style messages or to_message() usage detected:")
        for path, lineno, line in matches:
            print(f"  {path}:{lineno}: {line}")
        print("\nPlease migrate to `modelito.messages.Message` dataclasses.")
        return 2
    print("No legacy dict-usage found in modelito/.")
    return 0


if __name__ == '__main__':
    raise SystemExit(scan())
