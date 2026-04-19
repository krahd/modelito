#!/usr/bin/env python3
"""Simple example showing `GeminiProvider` usage.

Falls back to a deterministic response if a Gemini-like SDK is not present.
"""
from __future__ import annotations

from modelito import GeminiProvider


def main() -> None:
    prov = GeminiProvider()
    print("GeminiProvider models:", prov.list_models())
    msgs = [{"role": "user", "content": "Summarize: Hello from Gemini example."}]
    resp = prov.summarize(msgs)
    print("Response:\n", resp)


if __name__ == "__main__":
    main()
