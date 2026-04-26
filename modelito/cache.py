"""
Simple in-memory response cache for Modelito
- Optionally caches responses for repeated prompts
"""
from typing import Any, Dict, Tuple
import threading

class ResponseCache:
    def __init__(self, max_size: int = 128):
        self.cache: Dict[Tuple, Any] = {}
        self.max_size = max_size
        self.lock = threading.Lock()

    def get(self, key: Tuple) -> Any:
        with self.lock:
            return self.cache.get(key)

    def set(self, key: Tuple, value: Any):
        with self.lock:
            if len(self.cache) >= self.max_size:
                self.cache.pop(next(iter(self.cache)))
            self.cache[key] = value

    def clear(self):
        with self.lock:
            self.cache.clear()
