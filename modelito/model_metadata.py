"""
Model Capabilities Discovery for Modelito
- Exposes model metadata (context window, tool/function support, etc.)
"""
from typing import Dict, Any

# Example metadata registry (could be expanded or loaded dynamically)
MODEL_METADATA = {
    "gpt-3.5-turbo": {"context_window": 4096, "functions": True, "tools": True},
    "gpt-4": {"context_window": 8192, "functions": True, "tools": True},
    "claude-2.1": {"context_window": 200000, "functions": False, "tools": False},
    "gemini-1.0": {"context_window": 32768, "functions": True, "tools": True},
    # Add more as needed
}

def get_model_metadata(model_name: str) -> Dict[str, Any]:
    """Return metadata for a given model name."""
    return MODEL_METADATA.get(model_name, {})
