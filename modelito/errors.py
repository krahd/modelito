"""
Standardized error types and diagnostics for Modelito
"""
from typing import Optional, Any

class ModelitoError(Exception):
    def __init__(self, message: str, provider: Optional[str] = None, code: Optional[str] = None, details: Optional[Any] = None):
        super().__init__(message)
        self.provider = provider
        self.code = code
        self.details = details

    def to_dict(self):
        return {
            "type": self.__class__.__name__,
            "message": str(self),
            "provider": self.provider,
            "code": self.code,
            "details": self.details,
        }

class APIKeyError(ModelitoError):
    pass

class ProviderError(ModelitoError):
    pass

class ModelNotFoundError(ModelitoError):
    pass

class StreamingError(ModelitoError):
    pass

class EmbeddingError(ModelitoError):
    pass

class DiagnosticInfo:
    def __init__(self, context: str, info: Any):
        self.context = context
        self.info = info

    def to_dict(self):
        return {"context": self.context, "info": self.info}
