#!/usr/bin/env python3
"""CI helper: fail if legacy dict-shaped messages are present in docs/examples/tests.

This script scans the repository (docs, examples, and tests) for simple
patterns that indicate legacy dict-style messages like
`{'role': 'user', 'content': '...'}` or calls to `to_message(...)`.
If any matches are found the script exits non-zero so CI can fail and
prevent regressions.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Scan non-library files (docs, examples, tests) for literal dict-shaped
# message examples that look like: [{ 'role': 'user', 'content': '...' }]
TARGET_EXTS = {".py", ".md", ".rst"}
EXCLUDE_DIRS = {".venv", "docs/build", "dist", ".git"}

PATTERNS = [
    # Inline list containing a dict with a `role` key: [{ "role": ... }]
    re.compile(r"\[\s*\{\s*[\'\"]role[\'\"]\s*:")
]


def _is_excluded(path: Path) -> bool:
    for part in path.parts:
        if part in EXCLUDE_DIRS:
            return True
    return False


def scan() -> int:
    matches = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in TARGET_EXTS:
            continue
        if _is_excluded(p):
            continue

        # Only scan docs, examples, and tests (and top-level README files).
        rel = p.relative_to(ROOT)
        if not (rel.parts[0] in ("docs", "examples", "tests") or rel.name.lower() in ("readme.md", "readme.rst")):
            continue

        text = p.read_text(encoding="utf8")

        # line-by-line quick checks (common in docs/examples)
        for i, line in enumerate(text.splitlines(), start=1):
            for pat in PATTERNS:
                if pat.search(line):
                    matches.append((p.relative_to(ROOT), i, line.strip()))

        # multi-line pattern: assignments like `new_messages = [ { 'role': ... } ]`
        if re.search(r"new_messages\s*=\s*\[.*?[\'\"]role[\'\"]", text, flags=re.DOTALL):
            # report at the first matching line
            idx = re.search(r"new_messages\s*=\s*\[.*?[\'\"]role[\'\"]", text, flags=re.DOTALL)
            if idx:
                lineno = text[: idx.start()].count("\n") + 1
                snippet = text.splitlines()[lineno - 1].strip() if lineno - \
                    1 < len(text.splitlines()) else ""
                matches.append((p.relative_to(ROOT), lineno, snippet))

    if matches:
        print("Found literal dict-shaped message examples (use `Message(...)` instead):")
        for path, lineno, line in matches:
            print(f"  {path}:{lineno}: {line}")
        print("\nPlease update examples to use `modelito.messages.Message` dataclasses.")
        return 2

    print("No literal dict-shaped message examples found in docs/examples/tests.")
    return 0


if __name__ == '__main__':
    raise SystemExit(scan())
