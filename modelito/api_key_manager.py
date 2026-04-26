"""
API Key Manager for Modelito
- Secure, user-friendly API key management for all providers
- Supports environment variable overrides and config files
- Provides validation utilities
"""
import os
from typing import Optional, Dict

# Map provider names to their environment variable names
PROVIDER_API_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
    "gemini": "GOOGLE_API_KEY",
}

class APIKeyManager:
    def __init__(self, config: Optional[Dict[str, str]] = None):
        self.config = config or {}

    def get_api_key(self, provider: str) -> Optional[str]:
        """Get API key for a provider, checking env var then config."""
        env_var = PROVIDER_API_KEY_ENV.get(provider.lower())
        if env_var and env_var in os.environ:
            return os.environ[env_var]
        return self.config.get(provider.lower())

    def set_api_key(self, provider: str, key: str):
        """Set API key in config (not persisted)."""
        self.config[provider.lower()] = key

    def validate_api_key(self, provider: str, key: Optional[str] = None) -> bool:
        """Basic validation: checks presence and plausible length."""
        key = key or self.get_api_key(provider)
        if not key or len(key) < 10:
            return False
        # Optionally, add provider-specific validation here
        return True

    def require_api_key(self, provider: str) -> str:
        """Raise if API key is missing or invalid."""
        key = self.get_api_key(provider)
        if not self.validate_api_key(provider, key):
            raise ValueError(f"Missing or invalid API key for provider: {provider}")
        assert key is not None
        return key
