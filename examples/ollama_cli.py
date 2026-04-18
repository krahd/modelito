#!/usr/bin/env python3
"""Small example showing `ollama_service` helpers.

This script is safe to run offline; functions will return empty lists or False
when the `ollama` CLI is not present.
"""
from __future__ import annotations

from modelito.ollama_service import get_ollama_binary, list_local_models, list_remote_models, server_is_up, endpoint_url


def main() -> None:
    host = "http://127.0.0.1"
    port = 11434

    print("ollama binary:", get_ollama_binary())
    print("local models:", list_local_models())
    print("remote models:", list_remote_models())
    print("server up:", server_is_up(host, port))
    print("endpoint:", endpoint_url(host, port))


if __name__ == "__main__":
    main()
