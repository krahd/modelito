#!/usr/bin/env python3
"""Small helper to bump the project version in `pyproject.toml` and add a
placeholder changelog entry.

Usage: ./scripts/bump_version.py 1.0.5
"""
import sys
from pathlib import Path
from datetime import date


def read_pyproject(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_pyproject(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def bump_version(pyproject_path: Path, new_version: str) -> bool:
    txt = read_pyproject(pyproject_path)
    if "version" not in txt:
        return False
    # naive replace for the version field
    import re

    new_txt = re.sub(r"version\s*=\s*\"[0-9a-zA-Z.\-]+\"",
                     f"version = \"{new_version}\"", txt, count=1)
    if new_txt == txt:
        return False
    write_pyproject(pyproject_path, new_txt)
    return True


def add_changelog_entry(changelog_path: Path, new_version: str) -> None:
    header = f"## {new_version} - {date.today().isoformat()}\n"
    body = "- Bump version and release notes placeholder.\n\n"
    if changelog_path.exists():
        existing = changelog_path.read_text(encoding="utf-8")
    else:
        existing = ""
    changelog_path.write_text(header + body + existing, encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: bump_version.py NEW_VERSION")
        return 2
    new_version = argv[1]
    root = Path(__file__).resolve().parents[1]
    pyproject = root / "pyproject.toml"
    changelog = root / "CHANGELOG.md"
    ok = bump_version(pyproject, new_version)
    if not ok:
        print("Failed to update pyproject.toml")
        return 1
    add_changelog_entry(changelog, new_version)
    print(f"Updated version to {new_version} and prepended changelog entry.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
