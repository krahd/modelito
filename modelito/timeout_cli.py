"""Small CLI for timeout diagnostics using the bundled catalog.

Usage: python -m modelito.timeout_cli --model llama-2-13b --input-tokens 2048
"""
from __future__ import annotations

import argparse
import json
from typing import Optional

from .timeout import estimate_remote_timeout_details


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="modelito-timeout",
                                description="Estimate remote model timeout with diagnostics")
    p.add_argument("--model", required=True, help="Model name to estimate for")
    p.add_argument("--input-tokens", type=int, default=2048, help="Approximate input tokens")
    p.add_argument("--concurrency", type=int, default=1, help="Concurrent requests")
    p.add_argument("--json", action="store_true", help="Print full diagnostic JSON")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    timeout, details = estimate_remote_timeout_details(
        args.model, input_tokens=args.input_tokens, concurrency=args.concurrency)
    if args.json:
        print(json.dumps(details, indent=2))
    else:
        print(f"Estimated timeout: {timeout} seconds")
        print("Breakdown:")
        for k in ("base_timeout", "chosen_multiplier", "concurrency_multiplier", "estimated_timeout", "catalog_source"):
            if k in details:
                print(f" - {k}: {details[k]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
