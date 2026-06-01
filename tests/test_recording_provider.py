"""
Tests for RecordingProvider and ReplayProvider.

All tests use MockProvider as the wrapped provider so they run
offline with no SDK, network, or API key dependencies.

Run:
    pytest tests/test_recording_provider.py -q
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from modelito import Message
from modelito.mock_provider import MockProvider
from modelito.recording import (
    CassetteFormatError,
    RecordingProvider,
    ReplayMissError,
    ReplayProvider,
    _message_to_dict,
    _normalise_messages,
    _stable_request_hash,
    _to_message,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def msgs(*contents: str) -> list[Message]:
    return [Message(role="user", content=c) for c in contents]


def read_cassette(path: Path) -> list[dict]:
    records = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                records.append(json.loads(stripped))
    return records


# ---------------------------------------------------------------------------
# _message_to_dict
# ---------------------------------------------------------------------------

class TestMessageToDict:
    def test_from_message_object(self):
        d = _message_to_dict(Message(role="user", content="hello"))
        assert d == {"role": "user", "content": "hello"}

    def test_from_plain_dict(self):
        d = _message_to_dict({"role": "assistant", "content": "hi"})
        assert d == {"role": "assistant", "content": "hi"}

    def test_from_string_becomes_user_message(self):
        d = _message_to_dict("hello")
        assert d == {"role": "user", "content": "hello"}

    def test_missing_dict_keys_default_role_to_user(self):
        d = _message_to_dict({})
        assert d["role"] == "user"
        assert d["content"] == ""


# ---------------------------------------------------------------------------
# _normalise_messages
# ---------------------------------------------------------------------------

class TestNormaliseMessages:
    def test_list_of_messages(self):
        items, dicts = _normalise_messages(msgs("hello", "world"))
        assert len(items) == 2
        assert len(dicts) == 2
        assert dicts[0]["content"] == "hello"

    def test_generator_is_materialised(self):
        gen = (Message(role="user", content=c) for c in ["a", "b", "c"])
        items, dicts = _normalise_messages(gen)
        assert len(items) == 3
        assert len(dicts) == 3

    def test_list_of_strings_becomes_message_objects(self):
        items, dicts = _normalise_messages(["hello", "world"])
        assert all(hasattr(m, "content") for m in items)
        assert [d["content"] for d in dicts] == ["hello", "world"]

    def test_list_of_dicts_becomes_message_objects(self):
        items, dicts = _normalise_messages([
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "world"},
        ])
        assert all(hasattr(m, "content") for m in items)
        assert dicts[0]["content"] == "hello"
        assert dicts[1]["content"] == "world"
        assert dicts[1]["role"] == "assistant"

    def test_generator_of_strings_becomes_message_objects(self):
        gen = (s for s in ["a", "b"])
        items, dicts = _normalise_messages(gen)
        assert all(hasattr(m, "content") for m in items)
        assert [d["content"] for d in dicts] == ["a", "b"]

    def test_list_of_strings(self, tmp_path):
        """RecordingProvider + MockProvider must work with a list of strings."""
        p = RecordingProvider(wrapped=MockProvider(), cassette=tmp_path / "t.jsonl")
        result = p.summarize(["hello", "world"])
        assert "hello" in result
        assert "world" in result

    def test_list_of_dicts(self, tmp_path):
        """RecordingProvider + MockProvider must work with a list of dicts."""
        p = RecordingProvider(wrapped=MockProvider(), cassette=tmp_path / "t.jsonl")
        result = p.summarize([{"role": "user", "content": "hello"}])
        assert "hello" in result

    def test_string_becomes_user_message(self):
        items, dicts = _normalise_messages("hello")
        assert len(dicts) == 1
        assert dicts[0]["content"] == "hello"
        assert dicts[0]["role"] == "user"

    def test_none_becomes_empty(self):
        items, dicts = _normalise_messages(None)
        assert items == []
        assert dicts == []

    def test_generator_not_exhausted_before_items_returned(self):
        """Materialising once means items is a real list, not an exhausted generator."""
        gen = (Message(role="user", content=c) for c in ["x", "y"])
        items, _ = _normalise_messages(gen)
        # items must be iterable more than once (i.e. a list, not a generator)
        assert list(items) == list(items)


# ---------------------------------------------------------------------------
# _to_message
# ---------------------------------------------------------------------------

class TestToMessage:
    def test_message_object_passes_through(self):
        m = Message(role="user", content="hello")
        assert _to_message(m) is m

    def test_string_becomes_user_message(self):
        result = _to_message("hello")
        assert result.role == "user"
        assert result.content == "hello"

    def test_dict_becomes_message(self):
        result = _to_message({"role": "assistant", "content": "hi"})
        assert result.role == "assistant"
        assert result.content == "hi"

    def test_dict_missing_role_defaults_to_user(self):
        result = _to_message({"content": "hi"})
        assert result.role == "user"

    def test_unknown_object_passes_through(self):
        class Custom:
            role = "user"
            content = "hi"
        obj = Custom()
        assert _to_message(obj) is obj


# ---------------------------------------------------------------------------
# _normalise_messages — iterable str/dict (previously broken cases)
# ---------------------------------------------------------------------------

class TestStableRequestHash:
    def test_identical_inputs_same_hash(self):
        h1 = _stable_request_hash("summarize", [{"role": "user", "content": "hi"}], {}, None)
        h2 = _stable_request_hash("summarize", [{"role": "user", "content": "hi"}], {}, None)
        assert h1 == h2

    def test_different_content_different_hash(self):
        h1 = _stable_request_hash("summarize", [{"role": "user", "content": "hi"}], {}, None)
        h2 = _stable_request_hash("summarize", [{"role": "user", "content": "bye"}], {}, None)
        assert h1 != h2

    def test_different_kind_different_hash(self):
        h1 = _stable_request_hash("summarize", [], {}, None)
        h2 = _stable_request_hash("chat", [], {}, None)
        assert h1 != h2

    def test_none_model_differs_from_named_model(self):
        h1 = _stable_request_hash("summarize", [], {}, None)
        h2 = _stable_request_hash("summarize", [], {}, "gpt-4")
        assert h1 != h2

    def test_settings_key_order_irrelevant(self):
        h1 = _stable_request_hash("summarize", [], {"a": 1, "b": 2}, None)
        h2 = _stable_request_hash("summarize", [], {"b": 2, "a": 1}, None)
        assert h1 == h2

    def test_hash_is_64_hex_chars(self):
        h = _stable_request_hash("summarize", [], {}, None)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


# ---------------------------------------------------------------------------
# RecordingProvider — summarize
# ---------------------------------------------------------------------------

class TestRecordingProviderSummarize:
    def test_returns_wrapped_result(self, tmp_path):
        p = RecordingProvider(wrapped=MockProvider(), cassette=tmp_path / "t.jsonl")
        assert isinstance(p.summarize(msgs("hello")), str)

    def test_result_matches_wrapped_provider(self, tmp_path):
        mock = MockProvider()
        p = RecordingProvider(wrapped=mock, cassette=tmp_path / "t.jsonl")
        assert p.summarize(msgs("hello")) == mock.summarize(msgs("hello"))

    def test_writes_one_record(self, tmp_path):
        cassette = tmp_path / "t.jsonl"
        RecordingProvider(wrapped=MockProvider(), cassette=cassette).summarize(msgs("hello"))
        assert len(read_cassette(cassette)) == 1

    def test_record_schema(self, tmp_path):
        cassette = tmp_path / "t.jsonl"
        RecordingProvider(wrapped=MockProvider(), cassette=cassette).summarize(msgs("hello"))
        record = read_cassette(cassette)[0]
        for key in ("version", "kind", "provider", "model", "request_hash",
                    "request", "response", "error", "created_at"):
            assert key in record, f"missing key: {key}"

    def test_record_kind(self, tmp_path):
        cassette = tmp_path / "t.jsonl"
        RecordingProvider(wrapped=MockProvider(), cassette=cassette).summarize(msgs("hello"))
        assert read_cassette(cassette)[0]["kind"] == "summarize"

    def test_record_provider_name(self, tmp_path):
        cassette = tmp_path / "t.jsonl"
        RecordingProvider(wrapped=MockProvider(), cassette=cassette).summarize(msgs("hello"))
        assert read_cassette(cassette)[0]["provider"] == "MockProvider"

    def test_record_stores_message_content(self, tmp_path):
        cassette = tmp_path / "t.jsonl"
        RecordingProvider(wrapped=MockProvider(), cassette=cassette).summarize(msgs("distinct-content"))
        record = read_cassette(cassette)[0]
        assert record["request"]["messages"][0]["content"] == "distinct-content"

    def test_multiple_calls_append(self, tmp_path):
        cassette = tmp_path / "t.jsonl"
        p = RecordingProvider(wrapped=MockProvider(), cassette=cassette)
        p.summarize(msgs("first"))
        p.summarize(msgs("second"))
        assert len(read_cassette(cassette)) == 2

    def test_different_messages_different_hashes(self, tmp_path):
        cassette = tmp_path / "t.jsonl"
        p = RecordingProvider(wrapped=MockProvider(), cassette=cassette)
        p.summarize(msgs("first"))
        p.summarize(msgs("second"))
        records = read_cassette(cassette)
        assert records[0]["request_hash"] != records[1]["request_hash"]

    def test_creates_parent_dirs(self, tmp_path):
        cassette = tmp_path / "nested" / "deep" / "t.jsonl"
        RecordingProvider(wrapped=MockProvider(), cassette=cassette).summarize(msgs("hello"))
        assert cassette.exists()

    def test_generator_messages_are_not_exhausted_before_delegation(self, tmp_path):
        """The wrapped provider receives all messages as Message-like objects."""
        received: list[list] = []

        class SpyProvider:
            model = "spy"
            def list_models(self): return ["spy"]
            def summarize(self, messages, settings=None):
                received.append(list(messages))
                return "spy-result"
            def chat(self, messages, settings=None):
                received.append(list(messages))
                from modelito import Response
                return Response(text="spy")

        gen = (Message(role="user", content=c) for c in ["a", "b", "c"])
        p = RecordingProvider(wrapped=SpyProvider(), cassette=tmp_path / "t.jsonl")
        p.summarize(gen)
        assert len(received) == 1
        assert len(received[0]) == 3
        # Provider receives Message objects (with .content), not plain dicts.
        assert all(hasattr(m, "content") for m in received[0])

    def test_bare_string_recorded_as_one_message_not_characters(self, tmp_path):
        """A bare string must become one user message, not one per character."""
        cassette = tmp_path / "t.jsonl"
        p = RecordingProvider(wrapped=MockProvider(), cassette=cassette)
        p.summarize("hello")
        records = read_cassette(cassette)
        assert len(records[0]["request"]["messages"]) == 1
        assert records[0]["request"]["messages"][0]["content"] == "hello"

    def test_bare_string_provider_receives_one_message(self, tmp_path):
        """The wrapped provider must receive exactly one Message for a bare string."""
        received: list[list] = []

        class SpyProvider:
            model = "spy"
            def list_models(self): return ["spy"]
            def summarize(self, messages, settings=None):
                received.append(list(messages))
                return "ok"

        RecordingProvider(
            wrapped=SpyProvider(), cassette=tmp_path / "t.jsonl"
        ).summarize("hello")
        assert len(received[0]) == 1
        assert received[0][0].content == "hello"

    def test_string_message_is_recorded_and_retrievable(self, tmp_path):
        cassette = tmp_path / "t.jsonl"
        p = RecordingProvider(wrapped=MockProvider(), cassette=cassette)
        p.summarize("hello as string")
        records = read_cassette(cassette)
        assert len(records) == 1
        assert records[0]["request"]["messages"][0]["role"] == "user"
        assert records[0]["request"]["messages"][0]["content"] == "hello as string"

    def test_error_is_recorded_and_reraised(self, tmp_path):
        class BrokenProvider:
            model = None
            def list_models(self): return []
            def summarize(self, messages, settings=None):
                raise RuntimeError("provider failed")

        cassette = tmp_path / "t.jsonl"
        p = RecordingProvider(wrapped=BrokenProvider(), cassette=cassette)
        with pytest.raises(RuntimeError, match="provider failed"):
            p.summarize(msgs("hello"))
        record = read_cassette(cassette)[0]
        assert record["error"]["type"] == "RuntimeError"
        assert record["error"]["message"] == "provider failed"


# ---------------------------------------------------------------------------
# RecordingProvider — chat
# ---------------------------------------------------------------------------

class TestRecordingProviderChat:
    def test_returns_response_with_text(self, tmp_path):
        p = RecordingProvider(wrapped=MockProvider(), cassette=tmp_path / "t.jsonl")
        result = p.chat(msgs("hello"))
        assert hasattr(result, "text")
        assert isinstance(result.text, str)

    def test_writes_chat_record(self, tmp_path):
        cassette = tmp_path / "t.jsonl"
        RecordingProvider(wrapped=MockProvider(), cassette=cassette).chat(msgs("hello"))
        records = read_cassette(cassette)
        assert len(records) == 1
        assert records[0]["kind"] == "chat"
        assert "text" in records[0]["response"]

    def test_chat_on_provider_without_chat_raises(self, tmp_path):
        class NoChat:
            model = None
            def list_models(self): return []
            def summarize(self, messages, settings=None): return "ok"

        with pytest.raises(NotImplementedError, match="chat"):
            RecordingProvider(
                wrapped=NoChat(), cassette=tmp_path / "t.jsonl"
            ).chat(msgs("hello"))


# ---------------------------------------------------------------------------
# RecordingProvider — list_models
# ---------------------------------------------------------------------------

class TestRecordingProviderListModels:
    def test_returns_list(self, tmp_path):
        p = RecordingProvider(wrapped=MockProvider(), cassette=tmp_path / "t.jsonl")
        assert isinstance(p.list_models(), list)

    def test_writes_record(self, tmp_path):
        cassette = tmp_path / "t.jsonl"
        RecordingProvider(wrapped=MockProvider(), cassette=cassette).list_models()
        records = read_cassette(cassette)
        assert records[0]["kind"] == "list_models"
        assert "models" in records[0]["response"]


# ---------------------------------------------------------------------------
# RecordingProvider — unsupported methods
# ---------------------------------------------------------------------------

class TestRecordingProviderUnsupported:
    def test_stream_raises(self, tmp_path):
        p = RecordingProvider(wrapped=MockProvider(), cassette=tmp_path / "t.jsonl")
        with pytest.raises(NotImplementedError, match="stream"):
            p.stream()

    def test_embed_raises(self, tmp_path):
        p = RecordingProvider(wrapped=MockProvider(), cassette=tmp_path / "t.jsonl")
        with pytest.raises(NotImplementedError, match="embed"):
            p.embed([0.1])


# ---------------------------------------------------------------------------
# ReplayProvider — model-agnostic behaviour (the critical correctness test)
# ---------------------------------------------------------------------------

class TestReplayModelAgnostic:
    def test_replays_without_passing_model(self, tmp_path):
        """
        Core correctness test.

        RecordingProvider records with the wrapped provider's .model attribute
        (e.g. "mock-model" for MockProvider).  ReplayProvider(model=None)
        must still match by ignoring the recorded model, so users do not need
        to know the internal model name to replay a cassette.
        """
        cassette = tmp_path / "t.jsonl"
        mock = MockProvider()
        expected = RecordingProvider(
            wrapped=mock, cassette=cassette
        ).summarize(msgs("hello"))

        # Replay without supplying model — the default should work.
        result = ReplayProvider(cassette=cassette).summarize(msgs("hello"))
        assert result == expected

    def test_wrong_model_misses(self, tmp_path):
        """
        Passing an incorrect explicit model causes a miss even if messages match.
        """
        cassette = tmp_path / "t.jsonl"
        RecordingProvider(
            wrapped=MockProvider(), cassette=cassette
        ).summarize(msgs("hello"))

        replay = ReplayProvider(cassette=cassette, strict=True, model="wrong-model-xyz")
        with pytest.raises(ReplayMissError):
            replay.summarize(msgs("hello"))

    def test_correct_model_hits(self, tmp_path):
        """
        Passing the exact model name used during recording succeeds.
        """
        cassette = tmp_path / "t.jsonl"
        mock = MockProvider()
        recorded_model = mock.model  # e.g. "mock-model"
        expected = RecordingProvider(
            wrapped=mock, cassette=cassette
        ).summarize(msgs("hello"))

        result = ReplayProvider(
            cassette=cassette, model=recorded_model
        ).summarize(msgs("hello"))
        assert result == expected


# ---------------------------------------------------------------------------
# ReplayProvider — summarize
# ---------------------------------------------------------------------------

class TestReplayProviderSummarize:
    def test_replays_recorded_result(self, tmp_path):
        cassette = tmp_path / "t.jsonl"
        expected = RecordingProvider(
            wrapped=MockProvider(), cassette=cassette
        ).summarize(msgs("hello"))
        assert ReplayProvider(cassette=cassette).summarize(msgs("hello")) == expected

    def test_deterministic_across_calls(self, tmp_path):
        cassette = tmp_path / "t.jsonl"
        RecordingProvider(wrapped=MockProvider(), cassette=cassette).summarize(msgs("hello"))
        replay = ReplayProvider(cassette=cassette)
        assert replay.summarize(msgs("hello")) == replay.summarize(msgs("hello"))

    def test_different_messages_replay_differently(self, tmp_path):
        cassette = tmp_path / "t.jsonl"
        p = RecordingProvider(wrapped=MockProvider(), cassette=cassette)
        p.summarize(msgs("hello"))
        p.summarize(msgs("goodbye"))
        replay = ReplayProvider(cassette=cassette)
        assert replay.summarize(msgs("hello")) != replay.summarize(msgs("goodbye"))

    def test_strict_miss_raises_replay_miss_error(self, tmp_path):
        with pytest.raises(ReplayMissError):
            ReplayProvider(cassette=tmp_path / "t.jsonl", strict=True).summarize(
                msgs("not recorded")
            )

    def test_non_strict_miss_returns_empty_string(self, tmp_path):
        result = ReplayProvider(
            cassette=tmp_path / "t.jsonl", strict=False
        ).summarize(msgs("not recorded"))
        assert result == ""

    def test_replay_miss_error_attributes(self, tmp_path):
        with pytest.raises(ReplayMissError) as exc_info:
            ReplayProvider(cassette=tmp_path / "t.jsonl").summarize(msgs("x"))
        assert exc_info.value.kind == "summarize"
        assert len(exc_info.value.request_hash) == 64

    def test_string_message_replays(self, tmp_path):
        """A string passed to summarize() must normalise consistently for record and replay."""
        cassette = tmp_path / "t.jsonl"
        expected = RecordingProvider(
            wrapped=MockProvider(), cassette=cassette
        ).summarize("hello as string")
        result = ReplayProvider(cassette=cassette).summarize("hello as string")
        assert result == expected

    def test_last_write_wins_on_duplicate_hash(self, tmp_path):
        cassette = tmp_path / "t.jsonl"
        RecordingProvider(wrapped=MockProvider(), cassette=cassette).summarize(msgs("hello"))
        # Append an override record with the same hash but different response.
        first = read_cassette(cassette)[0]
        override = dict(first)
        override["response"] = {"text": "overridden"}
        with cassette.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(override) + "\n")
        assert ReplayProvider(cassette=cassette).summarize(msgs("hello")) == "overridden"

    def test_nonexistent_cassette_non_strict_returns_empty(self, tmp_path):
        result = ReplayProvider(
            cassette=tmp_path / "does_not_exist.jsonl", strict=False
        ).summarize(msgs("hello"))
        assert result == ""


# ---------------------------------------------------------------------------
# ReplayProvider — chat
# ---------------------------------------------------------------------------

class TestReplayProviderChat:
    def test_replays_chat_text(self, tmp_path):
        cassette = tmp_path / "t.jsonl"
        expected = RecordingProvider(
            wrapped=MockProvider(), cassette=cassette
        ).chat(msgs("hello"))
        result = ReplayProvider(cassette=cassette).chat(msgs("hello"))
        assert result.text == expected.text

    def test_replayed_response_has_text_attribute(self, tmp_path):
        cassette = tmp_path / "t.jsonl"
        RecordingProvider(wrapped=MockProvider(), cassette=cassette).chat(msgs("hello"))
        result = ReplayProvider(cassette=cassette).chat(msgs("hello"))
        assert isinstance(result.text, str)
        assert len(result.text) > 0


# ---------------------------------------------------------------------------
# ReplayProvider — list_models
# ---------------------------------------------------------------------------

class TestReplayProviderListModels:
    def test_replays_models(self, tmp_path):
        cassette = tmp_path / "t.jsonl"
        expected = RecordingProvider(
            wrapped=MockProvider(), cassette=cassette
        ).list_models()
        assert ReplayProvider(cassette=cassette).list_models() == expected


# ---------------------------------------------------------------------------
# ReplayProvider — unsupported methods
# ---------------------------------------------------------------------------

class TestReplayProviderUnsupported:
    def test_stream_raises(self, tmp_path):
        with pytest.raises(NotImplementedError, match="stream"):
            ReplayProvider(cassette=tmp_path / "t.jsonl").stream()

    def test_embed_raises(self, tmp_path):
        with pytest.raises(NotImplementedError, match="embed"):
            ReplayProvider(cassette=tmp_path / "t.jsonl").embed([0.1])


# ---------------------------------------------------------------------------
# ReplayProvider — recorded errors re-raised
# ---------------------------------------------------------------------------

class TestReplayProviderRecordedErrors:
    def test_recorded_error_is_raised_on_replay(self, tmp_path):
        cassette = tmp_path / "t.jsonl"
        m = msgs("hello")
        from modelito.recording import _message_to_dict, _stable_request_hash

        message_dicts = [_message_to_dict(msg) for msg in m]
        request_hash = _stable_request_hash("summarize", message_dicts, {}, None)
        error_record = {
            "version": 1,
            "kind": "summarize",
            "provider": "BrokenProvider",
            "model": None,
            "request_hash": request_hash,
            "request": {"messages": message_dicts, "settings": {}},
            "response": {},
            "error": {"type": "TimeoutError", "message": "timed out"},
            "created_at": "2026-01-01T00:00:00+00:00",
        }
        with cassette.open("w", encoding="utf-8") as fh:
            fh.write(json.dumps(error_record) + "\n")

        with pytest.raises(RuntimeError, match="TimeoutError"):
            ReplayProvider(cassette=cassette).summarize(m)


# ---------------------------------------------------------------------------
# Cassette format errors
# ---------------------------------------------------------------------------

class TestCassetteFormatErrors:
    def test_malformed_json_raises_cassette_format_error_by_default(self, tmp_path):
        cassette = tmp_path / "bad.jsonl"
        cassette.write_text('{"valid": true}\nnot valid json\n{"also_valid": true}\n')
        with pytest.raises(CassetteFormatError) as exc_info:
            ReplayProvider(cassette=cassette).summarize(msgs("x"))
        assert exc_info.value.line_number == 2
        assert "not valid json" in exc_info.value.line

    def test_malformed_json_skipped_when_strict_cassette_false(self, tmp_path):
        cassette = tmp_path / "bad.jsonl"
        # Record a valid entry first, then write a corrupt line.
        RecordingProvider(
            wrapped=MockProvider(), cassette=cassette
        ).summarize(msgs("hello"))
        with cassette.open("a") as fh:
            fh.write("not valid json\n")
        # Should still find the valid record, skipping the bad line.
        result = ReplayProvider(
            cassette=cassette, strict_cassette=False
        ).summarize(msgs("hello"))
        assert isinstance(result, str)

    def test_cassette_format_error_attributes(self, tmp_path):
        cassette = tmp_path / "bad.jsonl"
        cassette.write_text("bad line content\n")
        with pytest.raises(CassetteFormatError) as exc_info:
            ReplayProvider(cassette=cassette).summarize(msgs("x"))
        err = exc_info.value
        assert err.path == cassette
        assert err.line_number == 1
        assert "bad line content" in err.line


# ---------------------------------------------------------------------------
# Composability
# ---------------------------------------------------------------------------

class TestComposability:
    def test_recording_wraps_recording(self, tmp_path):
        inner = tmp_path / "inner.jsonl"
        outer = tmp_path / "outer.jsonl"
        RecordingProvider(
            wrapped=RecordingProvider(wrapped=MockProvider(), cassette=inner),
            cassette=outer,
        ).summarize(msgs("compose"))
        assert len(read_cassette(inner)) == 1
        assert len(read_cassette(outer)) == 1

    def test_replay_wrapped_by_recording(self, tmp_path):
        base = tmp_path / "base.jsonl"
        outer = tmp_path / "outer.jsonl"
        RecordingProvider(wrapped=MockProvider(), cassette=base).summarize(msgs("hello"))
        result = RecordingProvider(
            wrapped=ReplayProvider(cassette=base), cassette=outer
        ).summarize(msgs("hello"))
        assert isinstance(result, str)
        assert len(read_cassette(outer)) == 1

    def test_full_chain(self, tmp_path):
        base = tmp_path / "base.jsonl"
        outer = tmp_path / "outer.jsonl"
        RecordingProvider(wrapped=MockProvider(), cassette=base).summarize(msgs("chain"))
        result = RecordingProvider(
            wrapped=ReplayProvider(cassette=base), cassette=outer
        ).summarize(msgs("chain"))
        expected = ReplayProvider(cassette=base).summarize(msgs("chain"))
        assert result == expected
