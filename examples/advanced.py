#!/usr/bin/env python3
"""Advanced example for `modelito`.

Demonstrates conversation history, trimming, system messages, and estimators.
"""
from __future__ import annotations

from modelito import (
    count_tokens,
    estimate_remote_timeout,
    OllamaConnector,
    OllamaProvider,
    Provider,
    load_config,
)


def main() -> None:
    # config helpers (safe fallback)
    cfg = load_config("nonexistent.json")
    print("Loaded config (sample):", cfg)

    # provider + connector
    provider = OllamaProvider()
    provider: Provider = OllamaProvider()
    conn = OllamaConnector(provider=provider, shared_history=False,
                           max_history_messages=5, max_history_tokens=200)
    conn.set_system_message("You are a concise assistant.")

    conv = "adv-example"
    conn.add_to_history(conv, "user", "Hello!")
    conn.add_to_history(conv, "assistant", "Hi, how can I help?")

    from modelito import Message, Response

    new_message = Message(role="user", content="Summarize the conversation in one sentence.")
    prompt = conn.build_prompt(conv, new_messages=[new_message])
    print("Built prompt:", prompt)
    resp: Response = conn.complete(conv, [new_message])
    print("Response:", resp.text)
    print("Token estimate:", count_tokens(resp))
    print("Timeout suggestion:", estimate_remote_timeout(
        "gpt-3.5-turbo", input_tokens=count_tokens(resp), concurrency=1))


if __name__ == "__main__":
    main()
