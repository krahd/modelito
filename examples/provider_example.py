#!/usr/bin/env python3
"""Provider example: switching providers and using `OllamaConnector`.

Demonstrates typing with the `Provider` Protocol and how to swap providers
without changing client code.
"""
from __future__ import annotations

from typing import List

from modelito import (
    Provider,
    OpenAIProvider,
    ClaudeProvider,
    GeminiProvider,
    GrokProvider,
    OllamaProvider,
    OllamaConnector,
    Message,
    Response,
)


def run_with_provider(provider: Provider, msgs: List[Message]) -> None:
    print("---")
    print("Provider:", provider.__class__.__name__)
    print("Models:", provider.list_models())
    print("Is Provider:", isinstance(provider, Provider))
    # provider.summarize accepts an iterable of messages
    print("Summary:", provider.summarize(msgs))


def main() -> None:
    msgs = [Message(role="user", content="Summarize: Hello from provider example.")]

    # Try OpenAI shim
    p1: Provider = OpenAIProvider()
    run_with_provider(p1, msgs)

    # Switch to Claude shim
    p2: Provider = ClaudeProvider()
    run_with_provider(p2, msgs)

    # Switch to Gemini shim
    p3: Provider = GeminiProvider()
    run_with_provider(p3, msgs)

    # Grok shim
    p4: Provider = GrokProvider()
    run_with_provider(p4, msgs)

    # Connector usage with an OllamaProvider
    oll = OllamaProvider()
    conn = OllamaConnector(provider=oll)
    resp: Response = conn.complete(conv_id="provider-example", new_messages=msgs)
    print("OllamaConnector response:", resp.text)


if __name__ == "__main__":
    main()
