"""Conversational benchmark for running local OpenAI-compatible runtimes.

The benchmark is deliberately runtime-neutral. It measures observable client
latency for a representative conversation rather than declaring a universal
provider winner. Results should be compared on the same machine, model family,
quantisation, context, and server configuration.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import statistics
import subprocess
import threading
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence
from urllib.request import Request, urlopen

from .tokenizer import count_tokens

_PROVIDER_BASE_URLS = {
    "basert": "http://127.0.0.1:8080/v1",
    "vllm-mlx": "http://127.0.0.1:8000/v1",
    "omlx": "http://127.0.0.1:8000/v1",
    "ollama": "http://127.0.0.1:11434/v1",
    "mlx-lm": "http://127.0.0.1:8080/v1",
}
_PROVIDER_ALIASES = {
    "vllm_mlx": "vllm-mlx",
    "vllmmlx": "vllm-mlx",
    "mlx_lm": "mlx-lm",
    "generic": "openai-compatible",
}
_SUPPORTED_PROVIDERS = tuple(_PROVIDER_BASE_URLS) + ("openai-compatible",)


@dataclass(frozen=True)
class StreamMetrics:
    """Observable metrics for one streamed chat request."""

    ttft_ms: Optional[float]
    first_useful_ms: Optional[float]
    elapsed_ms: float
    output_chars: int
    estimated_output_tokens: int
    estimated_decode_tokens_per_s: Optional[float]
    cancel_close_ms: Optional[float] = None


def _normalise_provider(provider: str) -> str:
    value = str(provider or "").strip().lower()
    return _PROVIDER_ALIASES.get(value, value)


def _headers(api_key: Optional[str]) -> Dict[str, str]:
    headers = {
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _extract_stream_text(event: Any) -> str:
    if not isinstance(event, dict):
        return ""
    choices = event.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    delta = first.get("delta")
    if isinstance(delta, dict):
        content = delta.get("content")
        if isinstance(content, str):
            return content
    text = first.get("text")
    return text if isinstance(text, str) else ""


def _is_useful_phrase(text: str) -> bool:
    """Return whether streamed text has become visibly phrase-like.

    This is a UI-oriented heuristic rather than a linguistic metric: terminal
    punctuation/newline qualifies immediately; otherwise a multi-word fragment
    of at least 24 characters is considered useful enough to display.
    """

    stripped = text.strip()
    if not stripped:
        return False
    if any(mark in stripped for mark in (".", "!", "?", "\n")):
        return True
    return len(stripped) >= 24 and " " in stripped


def _discover_model(
    base_url: str, api_key: Optional[str], timeout: float
) -> str:
    request = Request(
        f"{base_url.rstrip('/')}/models",
        headers=_headers(api_key),
        method="GET",
    )
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    models = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(models, list):
        for item in models:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                return item["id"]
    raise RuntimeError("The server returned no model IDs from /models")


def _stream_chat(
    base_url: str,
    model: str,
    messages: Iterable[Dict[str, str]],
    *,
    api_key: Optional[str],
    timeout: float,
    max_tokens: int,
    stop_after_first: bool = False,
) -> StreamMetrics:
    payload = {
        "model": model,
        "messages": list(messages),
        "stream": True,
        "max_tokens": int(max_tokens),
        "temperature": 0,
    }
    request = Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers=_headers(api_key),
        method="POST",
    )

    start = time.perf_counter()
    first_token_at: Optional[float] = None
    first_useful_at: Optional[float] = None
    cancel_close_ms: Optional[float] = None
    parts: List[str] = []

    response = urlopen(request, timeout=timeout)
    try:
        while True:
            raw_line = response.readline()
            if not raw_line:
                break
            line = raw_line.decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            if line.startswith("data:"):
                line = line[5:].lstrip()
            if line == "[DONE]":
                break
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = _extract_stream_text(event)
            if not text:
                continue
            now = time.perf_counter()
            if first_token_at is None:
                first_token_at = now
            parts.append(text)
            accumulated = "".join(parts)
            if first_useful_at is None and _is_useful_phrase(accumulated):
                first_useful_at = now
            if stop_after_first:
                close_start = time.perf_counter()
                response.close()
                cancel_close_ms = (time.perf_counter() - close_start) * 1000.0
                break
    finally:
        response.close()

    end = time.perf_counter()
    output = "".join(parts)
    token_count = count_tokens(output) if output else 0
    ttft_ms = (
        (first_token_at - start) * 1000.0 if first_token_at is not None else None
    )
    useful_ms = (
        (first_useful_at - start) * 1000.0 if first_useful_at is not None else None
    )
    decode_tps: Optional[float] = None
    if first_token_at is not None and token_count > 1 and end > first_token_at:
        decode_tps = (token_count - 1) / (end - first_token_at)

    return StreamMetrics(
        ttft_ms=ttft_ms,
        first_useful_ms=useful_ms,
        elapsed_ms=(end - start) * 1000.0,
        output_chars=len(output),
        estimated_output_tokens=token_count,
        estimated_decode_tokens_per_s=decode_tps,
        cancel_close_ms=cancel_close_ms,
    )


def _median(values: Iterable[Optional[float]]) -> Optional[float]:
    present = [float(value) for value in values if value is not None]
    return statistics.median(present) if present else None


def _summarise_samples(samples: Sequence[StreamMetrics]) -> Dict[str, Any]:
    return {
        "samples": [asdict(sample) for sample in samples],
        "median_ttft_ms": _median(sample.ttft_ms for sample in samples),
        "median_first_useful_ms": _median(
            sample.first_useful_ms for sample in samples
        ),
        "median_estimated_decode_tokens_per_s": _median(
            sample.estimated_decode_tokens_per_s for sample in samples
        ),
    }


def _conversation(turns: int) -> List[Dict[str, str]]:
    messages: List[Dict[str, str]] = [
        {
            "role": "system",
            "content": (
                "Answer concisely. Preserve the markers supplied by the user so "
                "the final question can refer to the latest one."
            ),
        }
    ]
    for index in range(1, turns + 1):
        marker = f"MARKER-{index:02d}-ALPHA"
        messages.extend(
            [
                {
                    "role": "user",
                    "content": (
                        f"Conversation turn {index}. Remember marker {marker}. "
                        "Reply only that you have recorded it."
                    ),
                },
                {"role": "assistant", "content": f"Recorded {marker}."},
            ]
        )
    messages.append(
        {
            "role": "user",
            "content": "In one short sentence, state the latest marker you recorded.",
        }
    )
    return messages


def _read_rss_kb(pid: int) -> Optional[int]:
    try:
        result = subprocess.run(
            ["ps", "-o", "rss=", "-p", str(pid)],
            check=False,
            capture_output=True,
            text=True,
            timeout=1.0,
        )
        text = result.stdout.strip()
        return int(text.splitlines()[0]) if text else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


class _PeakRSSSampler:
    def __init__(self, pid: Optional[int], interval: float = 0.05) -> None:
        self.pid = pid
        self.interval = interval
        self.peak_kb: Optional[int] = None
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self.pid is None:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        assert self.pid is not None
        while not self._stop.is_set():
            rss = _read_rss_kb(self.pid)
            if rss is not None and (self.peak_kb is None or rss > self.peak_kb):
                self.peak_kb = rss
            self._stop.wait(self.interval)

    def stop(self) -> Optional[float]:
        if self._thread is None:
            return None
        self._stop.set()
        self._thread.join(timeout=2.0)
        return self.peak_kb / 1024.0 if self.peak_kb is not None else None


def run_benchmark(
    *,
    provider: str,
    base_url: str,
    model: str,
    api_key: Optional[str],
    timeout: float,
    max_tokens: int,
    repetitions: int,
    context_turns: Sequence[int],
    pid: Optional[int],
) -> Dict[str, Any]:
    """Run the conversational benchmark against one already-running server."""

    sampler = _PeakRSSSampler(pid)
    sampler.start()
    try:
        first_request = _stream_chat(
            base_url,
            model,
            _conversation(1),
            api_key=api_key,
            timeout=timeout,
            max_tokens=max_tokens,
        )

        warm_messages = _conversation(max(4, max(context_turns, default=4)))
        warm_baseline = _stream_chat(
            base_url,
            model,
            warm_messages,
            api_key=api_key,
            timeout=timeout,
            max_tokens=max_tokens,
        )
        warm_reuse = [
            _stream_chat(
                base_url,
                model,
                warm_messages,
                api_key=api_key,
                timeout=timeout,
                max_tokens=max_tokens,
            )
            for _ in range(repetitions)
        ]

        scaling: List[Dict[str, Any]] = []
        for turns in context_turns:
            samples = [
                _stream_chat(
                    base_url,
                    model,
                    _conversation(turns),
                    api_key=api_key,
                    timeout=timeout,
                    max_tokens=max_tokens,
                )
                for _ in range(repetitions)
            ]
            scaling.append({"turns": turns, **_summarise_samples(samples)})

        cancellation_stream = _stream_chat(
            base_url,
            model,
            [
                {
                    "role": "user",
                    "content": (
                        "Write a long numbered explanation of local language-model "
                        "inference, with at least twenty items."
                    ),
                }
            ],
            api_key=api_key,
            timeout=timeout,
            max_tokens=max(256, max_tokens),
            stop_after_first=True,
        )
        post_cancel_probe = _stream_chat(
            base_url,
            model,
            [{"role": "user", "content": "Reply with the single word ready."}],
            api_key=api_key,
            timeout=timeout,
            max_tokens=min(max_tokens, 32),
        )
    finally:
        peak_rss_mb = sampler.stop()

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "base_url": base_url,
        "model": model,
        "repetitions": repetitions,
        "first_request": asdict(first_request),
        "warm_prefix": {
            "baseline": asdict(warm_baseline),
            "reuse": _summarise_samples(warm_reuse),
        },
        "context_scaling": scaling,
        "cancellation": {
            "client_stream_close": asdict(cancellation_stream),
            "post_cancel_probe": asdict(post_cancel_probe),
        },
        "peak_process_rss_mb": peak_rss_mb,
        "measurement_notes": {
            "first_request": (
                "This is the first request made by this benchmark process. It is a "
                "cold-model metric only if the runtime/model was actually cold."
            ),
            "tokens_per_second": (
                "Output tokens are estimated with Modelito's tokenizer helper; this "
                "is not the runtime's native tokenizer accounting."
            ),
            "first_useful": (
                "A UI heuristic: terminal punctuation/newline, or a multi-word "
                "fragment of at least 24 characters."
            ),
            "cancellation": (
                "cancel_close_ms measures how quickly the client closes the HTTP "
                "stream. It does not prove server-side cancellation acknowledgement."
            ),
            "rss": (
                "If --pid is supplied, peak_process_rss_mb samples process RSS via "
                "ps. On macOS this can under-report native Metal/unified-memory use."
            ),
        },
    }


def _parse_context_turns(value: str) -> List[int]:
    out: List[int] = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        turns = int(item)
        if turns < 1:
            raise ValueError("context turns must be positive integers")
        if turns not in out:
            out.append(turns)
    if not out:
        raise ValueError("at least one context-turn value is required")
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="modelito-benchmark-local",
        description=(
            "Benchmark conversational latency for a running local "
            "OpenAI-compatible LLM server."
        ),
    )
    parser.add_argument(
        "--provider",
        required=True,
        help=(
            "Runtime label: basert, vllm-mlx, omlx, ollama, mlx-lm, or "
            "openai-compatible"
        ),
    )
    parser.add_argument("--base-url", default=None, help="Override API base URL")
    parser.add_argument("--model", default=None, help="Model ID; auto-detect if omitted")
    parser.add_argument("--api-key", default=None, help="Optional bearer token")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--max-tokens", type=int, default=96)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--context-turns", default="1,2,4,8")
    parser.add_argument(
        "--pid",
        type=int,
        default=None,
        help="Optional server PID for approximate process-RSS sampling",
    )
    parser.add_argument("--output", default=None, help="Write JSON result to this path")
    parser.add_argument(
        "--json", action="store_true", help="Print the complete JSON result"
    )
    return parser


def _format_number(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value:.1f}"


def _print_summary(result: Dict[str, Any]) -> None:
    first = result["first_request"]
    warm = result["warm_prefix"]["reuse"]
    print(f"provider: {result['provider']}")
    print(f"model: {result['model']}")
    print(f"first request TTFT: {_format_number(first['ttft_ms'])} ms")
    print(
        "warm-prefix median TTFT: "
        f"{_format_number(warm['median_ttft_ms'])} ms"
    )
    print(
        "warm-prefix median estimated decode: "
        f"{_format_number(warm['median_estimated_decode_tokens_per_s'])} tok/s"
    )
    peak = result.get("peak_process_rss_mb")
    print(f"peak sampled process RSS: {_format_number(peak)} MB")
    print("See JSON output for context-scaling, first-useful, and cancellation metrics.")


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    provider = _normalise_provider(args.provider)
    if provider not in _SUPPORTED_PROVIDERS:
        parser.error(
            "--provider must be one of: " + ", ".join(_SUPPORTED_PROVIDERS)
        )
    if args.repetitions < 1:
        parser.error("--repetitions must be at least 1")
    if args.max_tokens < 2:
        parser.error("--max-tokens must be at least 2")
    try:
        context_turns = _parse_context_turns(args.context_turns)
    except ValueError as exc:
        parser.error(str(exc))

    base_url = args.base_url or _PROVIDER_BASE_URLS.get(provider)
    if not base_url:
        parser.error("--base-url is required for openai-compatible providers")
    base_url = base_url.rstrip("/")
    model = args.model or _discover_model(base_url, args.api_key, args.timeout)

    result = run_benchmark(
        provider=provider,
        base_url=base_url,
        model=model,
        api_key=args.api_key,
        timeout=args.timeout,
        max_tokens=args.max_tokens,
        repetitions=args.repetitions,
        context_turns=context_turns,
        pid=args.pid,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(rendered + "\n")
    if args.json:
        print(rendered)
    else:
        _print_summary(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
