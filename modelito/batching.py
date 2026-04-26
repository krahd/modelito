"""
Batching utilities for Modelito
- Supports batching requests (e.g., for embeddings)
"""
from typing import Iterable, List, Callable, Any

def batch_iterable(iterable: Iterable[Any], batch_size: int) -> Iterable[List[Any]]:
    """Yield successive batches from an iterable."""
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) == batch_size:
            yield batch
            batch = []
    if batch:
        yield batch
