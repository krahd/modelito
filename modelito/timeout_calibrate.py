"""Calibration harness for timeout estimator.

This lightweight harness writes sample prompts and (optionally) exercises a
local Ollama HTTP endpoint to measure request durations for simple prompts.

The harness is intentionally conservative and will not error when Ollama is
absent; use `--execute` to attempt actual network runs.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen

from .timeout import load_catalog


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="modelito-calibrate",
                                description="Calibration harness for timeout estimator")
    p.add_argument("--model", required=True, help="Model name to calibrate")
    p.add_argument("--outdir", default="./calibration",
                   help="Directory to write prompts and results")
    p.add_argument("--iterations", type=int, default=None,
                   help="Number of iterations (overrides catalog)")
    p.add_argument("--execute", action="store_true",
                   help="Attempt to call local Ollama HTTP API to measure timings")
    p.add_argument("--url", default="http://127.0.0.1", help="Ollama base URL when executing")
    p.add_argument("--port", type=int, default=11434, help="Ollama port when executing")
    return p


def _post_json(url: str, payload: dict, timeout: int = 60) -> tuple[int, str]:
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.getcode(), (resp.read() or b"").decode("utf-8", errors="ignore")
    except Exception as exc:
        return 0, str(exc)


def main(argv: Optional[list[str]] = None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    catalog = load_catalog()
    calib = catalog.get("calibration_defaults", {}) or {}

    iterations = args.iterations or int(calib.get("iterations", 3))
    prompts = list(calib.get("prompt_samples", [])) or ["{text}"]
    max_tokens = int(calib.get("max_tokens", 64))

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "prompts.json").write_text(json.dumps(prompts, indent=2))

    results = {"model": args.model, "iterations": iterations, "runs": []}

    if args.execute:
        base = f"{args.url.rstrip('/')}:{args.port}"
        endpoint = f"{base}/api/generate"
        for i in range(iterations):
            for prompt in prompts:
                sample_text = "This is a short calibration sample text used for timing."
                payload = {"model": args.model, "prompt": prompt.replace(
                    "{text}", sample_text), "max_tokens": max_tokens}
                start = time.time()
                code, body = _post_json(endpoint, payload, timeout=int(
                    calib.get("timeout_seconds_per_request", 60)))
                elapsed = time.time() - start
                results["runs"].append(
                    {"prompt": prompt, "status": code, "elapsed_seconds": elapsed})
    else:
        results["note"] = "Execution not requested; prompts written to prompts.json"

    (outdir / "calibration_results.json").write_text(json.dumps(results, indent=2))
    print(f"Wrote calibration artifacts to {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
