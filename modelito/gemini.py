"""Gemini provider that attempts to use Google generative SDKs when present.

The provider performs runtime detection for common Gemini/Generative AI
Python packages (for example `google.generativeai` or similar client
shapes). When an SDK is available it will attempt a text generation call;
otherwise it falls back to joining message contents deterministically.
"""
from __future__ import annotations

import importlib
from typing import Any, List, Optional


class GeminiProvider:
    """Provider for Google Gemini-like APIs with best-effort SDK usage.

    The provider supports multiple client shapes via runtime introspection
    and falls back to a local deterministic summarizer when calls fail.
    """

    def __init__(self, host: Optional[str] = None, client: Any = None, model: Optional[str] = None):
        # host is informational; default is a placeholder URL
        self.host = host or "https://gemini.local"
        self.model = model
        self._client = client
        # try common module names used by Google/third-party SDKs
        mod = None
        for name in ("google.generativeai", "google.ai.generativelanguage", "generativeai"):
            try:
                mod = importlib.import_module(name)
                break
            except Exception:
                mod = None
        self._gemini_mod = mod

        if self._client is None and self._gemini_mod is not None:
            try:
                if hasattr(self._gemini_mod, "Client"):
                    try:
                        self._client = self._gemini_mod.Client()
                    except Exception:
                        self._client = None
                elif hasattr(self._gemini_mod, "client"):
                    self._client = getattr(self._gemini_mod, "client")
            except Exception:
                self._client = None

    def list_models(self) -> List[str]:
        try:
            if self._gemini_mod is not None:
                if hasattr(self._gemini_mod, "list_models"):
                    try:
                        return list(self._gemini_mod.list_models())
                    except Exception:
                        pass
                if hasattr(self._gemini_mod, "models") and hasattr(self._gemini_mod.models, "list"):
                    try:
                        return list(self._gemini_mod.models.list())
                    except Exception:
                        pass
        except Exception:
            pass
        return []

    def summarize(self, messages: Any, settings: Optional[dict] = None) -> str:
        def _flatten(msgs: Any) -> str:
            if not msgs:
                return ""
            out = []
            for m in (msgs or []):
                if isinstance(m, dict):
                    out.append(m.get("content", ""))
                else:
                    out.append(str(m))
            return "\n".join(p for p in out if p)

        prompt = _flatten(messages)

        if self._gemini_mod is not None:
            try:
                gen = self._client or self._gemini_mod
                # preferred shape: generate_text(model=..., prompt=...)
                if hasattr(gen, "generate_text"):
                    try:
                        res = gen.generate_text(model=self.model or "gemini-1.0",
                                                prompt=prompt, **(settings or {}))
                        # dict-like responses
                        if isinstance(res, dict):
                            if "candidates" in res and isinstance(res["candidates"], list) and res["candidates"]:
                                first = res["candidates"][0]
                                if isinstance(first, dict):
                                    return str(first.get("content") or first.get("output") or "")
                                return str(first)
                            if "text" in res:
                                return str(res.get("text") or "")
                        else:
                            text = getattr(res, "text", None) or getattr(res, "content", None)
                            if text:
                                return str(text)
                    except Exception:
                        pass

                if hasattr(gen, "client") and hasattr(gen.client, "generate_text"):
                    try:
                        res = gen.client.generate_text(
                            model=self.model or "gemini-1.0", prompt=prompt, **(settings or {}))
                        if isinstance(res, dict):
                            if "candidates" in res and res["candidates"]:
                                first = res["candidates"][0]
                                if isinstance(first, dict):
                                    return str(first.get("content") or first.get("output") or "")
                                return str(first)
                            if "text" in res:
                                return str(res.get("text") or "")
                        else:
                            text = getattr(res, "text", None) or getattr(res, "content", None)
                            if text:
                                return str(text)
                    except Exception:
                        pass
            except Exception:
                pass

        # deterministic fallback
        return prompt

    def stream(self, messages: Any, settings: Optional[dict] = None):
        """Streaming fallback for Gemini provider.

        Returns the summarize() result sliced into sequential chunks.
        """
        text = self.summarize(messages, settings=settings)
        if not text:
            return
        chunk_size = 64
        try:
            if isinstance(settings, dict) and "chunk_size" in settings:
                chunk_size = int(settings.get("chunk_size", chunk_size) or chunk_size)
        except Exception:
            pass
        for i in range(0, len(text), chunk_size):
            yield text[i : i + chunk_size]

    def embed(self, texts: Any, **kwargs) -> List[List[float]]:
        """Embedding surface for tests: delegate to the embeddings helper."""
        try:
            from .embeddings import embed_texts
        except Exception:
            from modelito.embeddings import embed_texts

        texts_list = [str(t) for t in (texts or [])]
        dim = int(kwargs.get("dim", 8))
        return embed_texts(texts_list, dim=dim)
