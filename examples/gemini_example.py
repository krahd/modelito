#!/usr/bin/env python3
"""Simple example showing `GeminiProvider` usage.

Falls back to a deterministic response if a Gemini-like SDK is not present.
"""
from __future__ import annotations

from modelito import GeminiProvider, Provider, Message


def main() -> None:
    prov: Provider = GeminiProvider()
    print("GeminiProvider models:", prov.list_models())
    print("Is Provider:", isinstance(prov, Provider))
    msgs = [Message(role="user", content="Summarize: Hello from Gemini example.")]
    resp = prov.summarize(msgs)
    print("Response:\n", resp)


if __name__ == "__main__":
    main()
