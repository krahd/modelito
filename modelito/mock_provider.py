"""
Mock Provider for Modelito
- Simulates completions, streaming, and embeddings for testing/CI/offline
"""
from typing import Iterable, List, Optional, Dict, Any
from .messages import Message

class MockProvider:
    def __init__(self, model: Optional[str] = None):
        self.model = model or "mock-model"

    def list_models(self) -> List[str]:
        return ["mock-model"]

    def summarize(self, messages: Iterable[Message], settings: Optional[Dict[str, Any]] = None) -> str:
        return "[MOCK] " + " ".join(m.content for m in messages)

    def stream(self, messages: Iterable[Message], settings: Optional[Dict[str, Any]] = None) -> Iterable[str]:
        text = self.summarize(messages, settings)
        for i in range(0, len(text), 8):
            yield text[i:i + 8]

    def embed(self, texts: Iterable[str], **kwargs: Any) -> List[List[float]]:
        return [[float(len(t)) for _ in range(8)] for t in texts]
