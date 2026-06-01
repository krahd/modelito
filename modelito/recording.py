"""
Recording and replay providers for modelito.

RecordingProvider wraps any modelito provider and persists request/response
pairs to a JSONL cassette file.  It is behaviour-preserving for normal
modelito message inputs, but normalises str/dict inputs into Message objects
before delegation — consistent with the package-level API, which already
treats strings and dicts as valid message inputs.

ReplayProvider reads a cassette and returns stored responses without
touching the network or any model runtime.

Both satisfy the core modelito Protocol surface for sync text calls:
    list_models() -> list[str]
    summarize(messages, settings=None) -> str
    chat(messages, settings=None) -> Response

stream() and embed() are not implemented in v1 and raise NotImplementedError.

Design constraints
------------------
- Zero dependencies: stdlib only (json, hashlib, datetime, pathlib, typing).
- Messages are materialised once before use to avoid consuming generators.
- Message normalisation uses modelito's flatten_message_inputs() so that
  strings, dicts, and Message objects all serialise consistently.
- Replay is model-agnostic by default (model=None): records are indexed
  by kind + messages + settings, ignoring the recorded provider's model.
  Pass model="..." explicitly to require an exact model match.
- Strict replay by default: ReplayMissError is raised if no record matches.
- Strict cassette parsing by default: CassetteFormatError on malformed JSON.
- RecordingProvider is behaviour-preserving for Message-style inputs and
    normalises supported str/dict inputs into Message objects before delegation.

Wrappers are composable::

    provider = RecordingProvider(
        wrapped=LatencyProvider(wrapped=ClaudeProvider(), delay=0.1),
        cassette="tests/cassettes/claude.jsonl",
    )
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .messages import Response as _Response  # type: ignore[attr-defined]

__all__ = [
    "CassetteFormatError",
    "ReplayMissError",
    "RecordingProvider",
    "ReplayProvider",
]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class CassetteFormatError(ValueError):
    """Raised when a cassette file contains malformed JSON.

    Attributes
    ----------
    path: Path to the cassette file.
    line_number: 1-based line number of the malformed entry.
    line: The raw string that failed to parse.
    """

    def __init__(self, path: Path, line_number: int, line: str) -> None:
        self.path = path
        self.line_number = line_number
        self.line = line
        super().__init__(
            f"Malformed JSON in cassette {path!s} at line {line_number}: "
            f"{line[:80]!r}"
        )


class ReplayMissError(KeyError):
    """Raised by ReplayProvider when no cassette record matches a request.

    Attributes
    ----------
    kind: The call kind looked up (e.g. ``"summarize"``).
    request_hash: Full SHA-256 hex digest of the unmatched request.
    """

    def __init__(self, kind: str, request_hash: str) -> None:
        self.kind = kind
        self.request_hash = request_hash
        super().__init__(
            f"No cassette record for kind={kind!r} "
            f"hash={request_hash[:16]}… — "
            f"run with RecordingProvider first to capture this request."
        )


# ---------------------------------------------------------------------------
# Message normalisation
# ---------------------------------------------------------------------------

def _message_to_dict(msg: Any) -> dict[str, str]:
    """Convert a single message value to a plain JSON-serialisable dict.

    Handles: str (→ user message), dict, and any object with .role/.content.
    Missing ``role`` defaults to ``"user"`` to match ``flatten_message_inputs``
    semantics.
    """
    if isinstance(msg, str):
        return {"role": "user", "content": msg}
    if isinstance(msg, dict):
        return {
            "role": str(msg.get("role", "user")),
            "content": str(msg.get("content", "")),
        }
    return {
        "role": str(getattr(msg, "role", "user")),
        "content": str(getattr(msg, "content", "")),
    }


def _to_message(item: Any) -> Any:
    """Convert a single message item to a ``Message`` object.

    Handles ``str`` (→ user message), ``dict``, and existing ``Message``
    objects.  Unknown objects with ``.role``/``.content`` are passed through
    unchanged so that custom provider types are not broken.
    """
    from .messages import Message as _Message  # type: ignore[attr-defined]

    if isinstance(item, _Message):
        return item
    if isinstance(item, str):
        return _Message(role="user", content=item)
    if isinstance(item, dict):
        return _Message(
            role=str(item.get("role", "user")),
            content=str(item.get("content", "")),
        )
    # Preserve unknown objects (custom provider types, duck-typed messages).
    return item


def _normalise_messages(messages: Any) -> tuple[list[Any], list[dict[str, str]]]:
    """Materialise and normalise messages to avoid generator exhaustion.

    Returns ``(provider_items, cassette_dicts)`` where:

    - ``provider_items`` is a ``list`` of ``Message`` objects safe to pass
      to any wrapped provider (including ``MockProvider``).  Each item is
      converted via :func:`_to_message`, so ``str``, ``dict``, and
      ``Message`` items all work whether supplied individually or inside an
      iterable.
    - ``cassette_dicts`` is a list of ``{"role": ..., "content": ...}`` dicts
      for JSON serialisation, produced by ``flatten_message_inputs``.

    The two outputs are kept separate because ``flatten_message_inputs()``
    returns dicts, which breaks providers that expect ``.content`` attributes.

    Note: ``RecordingProvider`` normalises supported modelito message inputs
    (``str``, ``dict``, ``Message``) into ``Message`` objects before
    delegation.  It is not a zero-transformation passthrough for raw strings
    or dicts, consistent with the package-level API which already treats those
    as valid message inputs.
    """
    # --- 1. Materialise to a flat list of raw items -------------------------
    if messages is None:
        raw_items: list[Any] = []
    elif isinstance(messages, (str, dict)):
        # Guard before iteration: a bare str would iterate as characters.
        raw_items = [messages]
    else:
        raw_items = list(messages)  # exhausts generators exactly once

    # --- 2. Convert each item to a Message object ---------------------------
    provider_items: list[Any] = [_to_message(item) for item in raw_items]

    # --- 3. Serialise for the cassette via flatten_message_inputs -----------
    try:
        from .messages import flatten_message_inputs as _flatten  # type: ignore[attr-defined]
        cassette_dicts: list[dict[str, str]] = _flatten(provider_items)
    except (ImportError, AttributeError):
        cassette_dicts = [_message_to_dict(m) for m in provider_items]

    return provider_items, cassette_dicts


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _json_safe(value: Any) -> Any:
    """Recursively convert a value to a JSON-serialisable primitive.

    Prevents unstable ``repr()`` strings or non-serialisable objects from
    producing different cassette hashes across runs.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return str(value)


def _settings_to_dict(settings: Any) -> dict[str, Any]:
    """Normalise settings to a stable, JSON-serialisable dict."""
    if settings is None:
        return {}
    if isinstance(settings, dict):
        return _json_safe(settings)
    try:
        return _json_safe(vars(settings))
    except TypeError:
        return {}


def _response_to_dict(response: Any) -> dict[str, Any]:
    """Extract normalised fields from a Response object.

    ``raw`` is intentionally excluded: it may contain SDK objects that are
    not JSON-serialisable.
    """
    return {
        "text": str(getattr(response, "text", "") or ""),
        "finish_reason": getattr(response, "finish_reason", None),
        "tokens_in": getattr(response, "tokens_in", None),
        "tokens_out": getattr(response, "tokens_out", None),
        "model": getattr(response, "model", None),
    }


def _response_from_dict(data: dict[str, Any]) -> Any:
    """Reconstruct a Response from a plain dict."""
    kwargs: dict[str, Any] = {"text": data.get("text", "")}
    for field in ("finish_reason", "tokens_in", "tokens_out", "model"):
        if field in data:
            kwargs[field] = data[field]
    try:
        return _Response(**kwargs)
    except TypeError:
        # Response dataclass has fewer fields than expected; fall back.
        return _Response(text=kwargs["text"])


# ---------------------------------------------------------------------------
# Stable hash
# ---------------------------------------------------------------------------

def _stable_request_hash(
    kind: str,
    messages: list[dict[str, str]],
    settings: dict[str, Any],
    model: str | None,
) -> str:
    """Produce a stable SHA-256 hex digest for cassette key lookup.

    Covers kind, normalised messages, normalised settings, and model.
    Excludes timestamps and provider object identity so the same logical
    request always maps to the same digest.

    When ``model`` is ``None``, the hash is model-agnostic: two records
    with different provider models but identical messages produce the
    same digest under this argument.
    """
    payload = json.dumps(
        {
            "kind": kind,
            "messages": messages,
            "settings": settings,
            "model": model,
        },
        sort_keys=True,
        ensure_ascii=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Cassette I/O
# ---------------------------------------------------------------------------

def _load_cassette(
    path: Path,
    *,
    strict_format: bool = True,
) -> list[dict[str, Any]]:
    """Read all records from a JSONL cassette file.

    Parameters
    ----------
    strict_format:
        If ``True`` (default), raise :exc:`CassetteFormatError` when a line
        fails to parse.  If ``False``, skip malformed lines silently (not
        recommended for CI).
    """
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line_number, line in enumerate(fh, 1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                records.append(json.loads(stripped))
            except json.JSONDecodeError:
                if strict_format:
                    raise CassetteFormatError(path, line_number, stripped)
                # else: skip silently (non-default behaviour)
    return records


def _append_record(path: Path, record: dict[str, Any]) -> None:
    """Append one record to a JSONL cassette, creating parent dirs if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=True, default=str) + "\n")


# ---------------------------------------------------------------------------
# RecordingProvider
# ---------------------------------------------------------------------------

class RecordingProvider:
    """Wraps any modelito provider and persists calls to a JSONL cassette.

    Behaviour-preserving for normal modelito message inputs (``Message``
    objects).  Normalises ``str`` and ``dict`` inputs into ``Message``
    objects before delegation, consistent with the package-level message API.

    Parameters
    ----------
    wrapped:
        Any object satisfying the modelito Provider protocol.
    cassette:
        Path to the JSONL cassette file.  Parent directories are created
        on first write if they do not exist.

    Examples
    --------
    ::

        from modelito import Message
        from modelito.recording import RecordingProvider

        provider = RecordingProvider(
            wrapped=ClaudeProvider(),
            cassette="tests/cassettes/claude.jsonl",
        )
        result = provider.summarize([Message(role="user", content="hello")])
    """

    def __init__(self, wrapped: Any, cassette: str | Path) -> None:
        self._wrapped = wrapped
        self._cassette = Path(cassette)

    # ------------------------------------------------------------------
    # Protocol surface
    # ------------------------------------------------------------------

    def list_models(self) -> list[str]:
        result = self._wrapped.list_models()
        self._write(
            kind="list_models",
            request={"messages": [], "settings": {}},
            response={"models": result},
            error=None,
        )
        return result

    def summarize(self, messages: Any, settings: Any = None) -> str:
        # Materialise once: avoids consuming a generator before delegation.
        message_items, message_dicts = _normalise_messages(messages)
        stgs = _settings_to_dict(settings)
        try:
            result: str = self._wrapped.summarize(message_items, settings)
            self._write(
                kind="summarize",
                request={"messages": message_dicts, "settings": stgs},
                response={"text": str(result)},
                error=None,
            )
            return result
        except Exception as exc:
            self._write(
                kind="summarize",
                request={"messages": message_dicts, "settings": stgs},
                response={},
                error={"type": type(exc).__name__, "message": str(exc)},
            )
            raise

    def chat(self, messages: Any, settings: Any = None) -> Any:
        if not hasattr(self._wrapped, "chat"):
            raise NotImplementedError(
                f"{type(self._wrapped).__name__} does not implement chat(). "
                "Use summarize() or wrap a provider that has chat()."
            )
        message_items, message_dicts = _normalise_messages(messages)
        stgs = _settings_to_dict(settings)
        try:
            result = self._wrapped.chat(message_items, settings)
            self._write(
                kind="chat",
                request={"messages": message_dicts, "settings": stgs},
                response=_response_to_dict(result),
                error=None,
            )
            return result
        except Exception as exc:
            self._write(
                kind="chat",
                request={"messages": message_dicts, "settings": stgs},
                response={},
                error={"type": type(exc).__name__, "message": str(exc)},
            )
            raise

    def stream(self, *args: Any, **kwargs: Any) -> Iterator[str]:
        raise NotImplementedError(
            "RecordingProvider does not support stream() in v1. "
            "Call stream() on the wrapped provider directly."
        )

    def embed(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError(
            "RecordingProvider does not support embed() in v1. "
            "Call embed() on the wrapped provider directly."
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _provider_name(self) -> str:
        return type(self._wrapped).__name__

    def _model_name(self) -> str | None:
        return getattr(self._wrapped, "model", None)

    def _write(
        self,
        kind: str,
        request: dict[str, Any],
        response: dict[str, Any],
        error: dict[str, str] | None,
    ) -> None:
        msgs: list[dict[str, str]] = request.get("messages", [])
        stgs: dict[str, Any] = request.get("settings", {})
        model = self._model_name()
        record: dict[str, Any] = {
            "version": 1,
            "kind": kind,
            "provider": self._provider_name(),
            "model": model,
            "request_hash": _stable_request_hash(kind, msgs, stgs, model),
            "request": request,
            "response": response,
            "error": error,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _append_record(self._cassette, record)


# ---------------------------------------------------------------------------
# ReplayProvider
# ---------------------------------------------------------------------------

class ReplayProvider:
    """Reads a JSONL cassette and returns stored responses offline.

    By default, ``model=None`` means model-agnostic replay: records are
    matched by kind + messages + settings, ignoring whatever model name
    the provider had at recording time.  This is the correct default
    because callers should not need to know the internal ``.model``
    attribute of the provider that was used during recording.

    Pass ``model="..."`` to require an exact model match when your cassette
    contains recordings from multiple models and you want to distinguish them.

    The cassette index is built lazily on the first call and cached for
    the lifetime of the instance.  Two indexes are maintained internally:
    a model-aware index (keyed by the original ``request_hash`` stored in
    the cassette) and a model-agnostic index (keyed by a hash recomputed
    without the model field).

    Parameters
    ----------
    cassette:
        Path to the JSONL cassette file written by RecordingProvider.
    strict:
        If ``True`` (default), raise :exc:`ReplayMissError` when no
        matching record exists.
    model:
        If given, perform model-aware lookup.  If ``None`` (default),
        perform model-agnostic lookup (recommended).
    strict_cassette:
        If ``True`` (default), raise :exc:`CassetteFormatError` on
        malformed JSONL lines rather than skipping them silently.

    Examples
    --------
    ::

        from modelito import Message
        from modelito.recording import ReplayProvider

        provider = ReplayProvider(cassette="tests/cassettes/claude.jsonl")
        result = provider.summarize([Message(role="user", content="hello")])
    """

    def __init__(
        self,
        cassette: str | Path,
        *,
        strict: bool = True,
        model: str | None = None,
        strict_cassette: bool = True,
    ) -> None:
        self._cassette = Path(cassette)
        self._strict = strict
        self._model = model
        self._strict_cassette = strict_cassette
        # Populated lazily on first call.
        self._model_aware_idx: dict[str, dict[str, Any]] | None = None
        self._model_agnostic_idx: dict[str, dict[str, Any]] | None = None

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    def _build_indexes(
        self,
    ) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
        records = _load_cassette(self._cassette, strict_format=self._strict_cassette)
        model_aware: dict[str, dict[str, Any]] = {}
        model_agnostic: dict[str, dict[str, Any]] = {}

        for record in records:
            # Model-aware: use the hash recorded by RecordingProvider (last write wins).
            h = record.get("request_hash")
            if h:
                model_aware[h] = record

            # Model-agnostic: recompute without the model field.
            req = record.get("request", {})
            kind = record.get("kind", "")
            agnostic_h = _stable_request_hash(
                kind,
                req.get("messages", []),
                req.get("settings", {}),
                None,  # model deliberately excluded
            )
            model_agnostic[agnostic_h] = record  # last write wins

        return model_aware, model_agnostic

    def _get_indexes(
        self,
    ) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
        if self._model_aware_idx is None:
            self._model_aware_idx, self._model_agnostic_idx = self._build_indexes()
        return self._model_aware_idx, self._model_agnostic_idx  # type: ignore[return-value]

    def _lookup(
        self,
        kind: str,
        messages: list[dict[str, str]],
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        model_aware, model_agnostic = self._get_indexes()

        if self._model is not None:
            # Strict model-aware lookup.
            request_hash = _stable_request_hash(kind, messages, settings, self._model)
            record = model_aware.get(request_hash)
        else:
            # Model-agnostic lookup (default).
            request_hash = _stable_request_hash(kind, messages, settings, None)
            record = model_agnostic.get(request_hash)

        if record is None:
            if self._strict:
                raise ReplayMissError(kind, request_hash)
            return {}

        if record.get("error"):
            err = record["error"]
            raise RuntimeError(
                f"Cassette recorded an error for this request: "
                f"{err.get('type')}: {err.get('message')}"
            )

        return record

    # ------------------------------------------------------------------
    # Protocol surface
    # ------------------------------------------------------------------

    def list_models(self) -> list[str]:
        record = self._lookup("list_models", [], {})
        return record.get("response", {}).get("models", [])

    def summarize(self, messages: Any, settings: Any = None) -> str:
        _, message_dicts = _normalise_messages(messages)
        stgs = _settings_to_dict(settings)
        record = self._lookup("summarize", message_dicts, stgs)
        return record.get("response", {}).get("text", "")

    def chat(self, messages: Any, settings: Any = None) -> Any:
        _, message_dicts = _normalise_messages(messages)
        stgs = _settings_to_dict(settings)
        record = self._lookup("chat", message_dicts, stgs)
        return _response_from_dict(record.get("response", {}))

    def stream(self, *args: Any, **kwargs: Any) -> Iterator[str]:
        raise NotImplementedError(
            "ReplayProvider does not support stream() in v1."
        )

    def embed(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError(
            "ReplayProvider does not support embed() in v1."
        )
