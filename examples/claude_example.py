#!/usr/bin/env python3
"""Simple example showing `ClaudeProvider` usage.

Falls back to an offline deterministic response if the `anthropic` SDK
is not available.
"""
from __future__ import annotations

from modelito import ClaudeProvider, Provider, Message


def main() -> None:
    prov: Provider = ClaudeProvider()
    print("ClaudeProvider models:", prov.list_models())
    print("Is Provider:", isinstance(prov, Provider))
    msgs = [Message(role="user", content="Summarize: Hello from Claude example.")]
    resp = prov.summarize(msgs)
    print("Response:\n", resp)


if __name__ == "__main__":
    main()
