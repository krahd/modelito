"""Common exception types used across the package.

This module provides lightweight exception classes that callers can catch
when interacting with provider shims and connectors.
"""


class LLMProviderError(Exception):
    """Raised when an LLM provider call fails.

    This exception is used as a simple wrapper around lower-level errors
    raised by provider implementations to provide a stable type for
    connector code to catch and handle.
    """

    pass


class ModelitoConnectionError(LLMProviderError):
    """Raised when the provider endpoint is unreachable."""

    pass


class ModelitoTimeoutError(LLMProviderError):
    """Raised when a provider request times out."""

    pass


class ModelitoBadResponseError(LLMProviderError):
    """Raised when the provider returns an unparseable or unexpected response."""

    pass


class ModelitoProviderError(LLMProviderError):
    """Raised for provider-side errors (e.g. HTTP 5xx, internal failure)."""

    pass


class ModelitoModelNotFoundError(LLMProviderError):
    """Raised when the requested model is not found on the provider."""

    pass
