"""Small example CLI demonstrating the Phase A Ollama helpers.

Usage examples:
  python examples/ollama_manage.py --action version
  python examples/ollama_manage.py --action ps
  python examples/ollama_manage.py --action pull --model your-model
  python examples/ollama_manage.py --action gen --prompt "hello world"
"""
from __future__ import annotations

import argparse

from modelito.ollama_api import api_generate, api_ps, api_pull, api_version


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--host", default=None)
    p.add_argument("--port", default=11434, type=int)
    p.add_argument("--action", choices=("version", "ps", "pull", "gen"), required=True)
    p.add_argument("--model", default=None)
    p.add_argument("--prompt", default=None)
    p.add_argument("--stream", action="store_true")
    args = p.parse_args()

    if args.action == "version":
        print(api_version(host=args.host, port=args.port))
        return

    if args.action == "ps":
        print("\n".join(api_ps(host=args.host, port=args.port)))
        return

    if args.action == "pull":
        if not args.model:
            print("--model required for pull")
            return
        ok = api_pull(args.model, host=args.host, port=args.port)
        print("pulled" if ok else "failed")
        return

    if args.action == "gen":
        prompt = args.prompt or "hello"
        if args.stream:
            for chunk in api_generate(prompt, host=args.host, port=args.port, model=args.model, stream=True):
                print(chunk, end="", flush=True)
            print()
        else:
            text = api_generate(prompt, host=args.host, port=args.port,
                                model=args.model, stream=False)
            print(text)


if __name__ == "__main__":
    main()
