from modelito.client import Client
from modelito.messages import Message


class StreamingProvider:
    model = "gpt-3.5-turbo"

    def list_models(self):
        return [self.model]

    def summarize(self, messages, settings=None):
        return "fallback"

    def stream(self, messages, settings=None):
        yield "one"
        yield "two"


class MetadataProvider:
    model = "provider-model"

    def list_models(self):
        return [self.model]

    def summarize(self, messages, settings=None):
        return "summary"

    def model_metadata(self, model=None):
        return {"ctx": 1234, "model": model}


def test_client_stream_yields_provider_chunks():
    client = Client(provider=StreamingProvider())

    assert list(client.stream([Message(role="user", content="hello")])) == ["one", "two"]


def test_client_model_metadata_uses_provider_when_available():
    client = Client(provider=MetadataProvider())

    assert client.model_metadata() == {
        "ctx": 1234,
        "context_window": 1234,
        "model": "provider-model",
    }


def test_client_model_metadata_falls_back_to_registry():
    client = Client(provider=StreamingProvider())

    metadata = client.model_metadata()

    assert metadata["context_window"] == 4096
    assert metadata["functions"] is True
    assert metadata["tools"] is True
