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
