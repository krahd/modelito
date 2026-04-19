#!/usr/bin/env python3
"""Simple example showing `OpenAIProvider` usage.

This example uses the provider shim and will fall back to a deterministic
response if the official `openai` SDK is not installed.
"""
from __future__ import annotations

from modelito import OpenAIProvider, Provider, Message


def main() -> None:
    prov: Provider = OpenAIProvider()
    print("OpenAIProvider models:", prov.list_models())
    print("Is Provider:", isinstance(prov, Provider))
    msgs = [Message(role="user", content="Summarize: Hello from OpenAI example.")]
    resp = prov.summarize(msgs)
    print("Response:\n", resp)


if __name__ == "__main__":
    main()
