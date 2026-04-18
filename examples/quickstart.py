#!/usr/bin/env python3
"""Quickstart example for modelito.

Run this script to exercise the shipped provider shims and connector.
"""
from __future__ import annotations

from modelito import (
    __version__,
    count_tokens,
    estimate_remote_timeout,
    OllamaConnector,
    OllamaProvider,
)


def main() -> None:
    print("modelito", __version__)

    text = "Hello from modelito example. This is a short message."
    print("text:", text)
    print("tokens:", count_tokens(text))
    print("timeout estimate:", estimate_remote_timeout(
        "gpt-3.5-turbo", input_tokens=50, concurrency=1))

    provider = OllamaProvider()
    conn = OllamaConnector(provider=provider)
    user_msg = {"role": "user", "content": "Please summarize: Hello world"}
    resp = conn.send_sync(conv_id="example", new_messages=[user_msg])
    print("provider response:", resp)


if __name__ == "__main__":
    main()
