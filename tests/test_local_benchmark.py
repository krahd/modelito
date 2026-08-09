import pytest

from modelito.local_benchmark import (
    StreamMetrics,
    _extract_stream_text,
    _is_useful_phrase,
    _normalise_provider,
    _parse_context_turns,
    _summarise_samples,
)


def test_extract_stream_text_reads_openai_delta():
    event = {"choices": [{"delta": {"content": "hello"}}]}

    assert _extract_stream_text(event) == "hello"


def test_extract_stream_text_ignores_non_text_events():
    assert _extract_stream_text({"choices": [{"delta": {"role": "assistant"}}]}) == ""
    assert _extract_stream_text({}) == ""


def test_useful_phrase_heuristic():
    assert _is_useful_phrase("Hello.") is True
    assert _is_useful_phrase("this is a sufficiently long fragment") is True
    assert _is_useful_phrase("short fragment") is False


def test_provider_aliases_are_normalised():
    assert _normalise_provider("vllm_mlx") == "vllm-mlx"
    assert _normalise_provider("mlx_lm") == "mlx-lm"
    assert _normalise_provider("generic") == "openai-compatible"


def test_context_turn_parser_deduplicates_and_validates():
    assert _parse_context_turns("1,2,2,4") == [1, 2, 4]
    with pytest.raises(ValueError, match="positive"):
        _parse_context_turns("0,2")


def test_sample_summary_uses_medians():
    samples = [
        StreamMetrics(100.0, 150.0, 500.0, 20, 5, 10.0),
        StreamMetrics(200.0, 250.0, 600.0, 20, 5, 20.0),
        StreamMetrics(300.0, None, 700.0, 20, 5, 30.0),
    ]

    summary = _summarise_samples(samples)

    assert summary["median_ttft_ms"] == 200.0
    assert summary["median_first_useful_ms"] == 200.0
    assert summary["median_estimated_decode_tokens_per_s"] == 20.0
    assert len(summary["samples"]) == 3
