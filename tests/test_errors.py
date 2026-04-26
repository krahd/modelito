from modelito.errors import ModelitoError, APIKeyError, ProviderError, ModelNotFoundError, StreamingError, EmbeddingError, DiagnosticInfo

def test_modelito_error_to_dict():
    err = ModelitoError("fail", provider="openai", code="401", details={"info": "bad key"})
    d = err.to_dict()
    assert d["type"] == "ModelitoError"
    assert d["provider"] == "openai"
    assert d["code"] == "401"
    assert d["details"]["info"] == "bad key"

def test_subclass_errors():
    assert issubclass(APIKeyError, ModelitoError)
    assert issubclass(ProviderError, ModelitoError)
    assert issubclass(ModelNotFoundError, ModelitoError)
    assert issubclass(StreamingError, ModelitoError)
    assert issubclass(EmbeddingError, ModelitoError)

def test_diagnostic_info():
    diag = DiagnosticInfo("context", {"foo": 1})
    d = diag.to_dict()
    assert d["context"] == "context"
    assert d["info"]["foo"] == 1
