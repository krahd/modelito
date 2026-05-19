from dataclasses import dataclass
from typing import TypedDict

import pytest

from modelito.client import Client
from modelito.messages import Response


class FakeSummarizeProvider:
    model = "fake"

    def __init__(self, payload: str):
        self.payload = payload
        self.last_settings = None

    def list_models(self):
        return [self.model]

    def summarize(self, messages, settings=None):
        self.last_settings = settings
        return self.payload


class FakeChatProvider(FakeSummarizeProvider):
    def __init__(self, payload: str):
        super().__init__(payload)
        self.chat_called = False
        self.summarize_called = False

    def summarize(self, messages, settings=None):
        self.summarize_called = True
        return super().summarize(messages, settings=settings)

    def chat(self, messages, settings=None):
        self.chat_called = True
        self.last_settings = settings
        return Response(text=self.payload)


class PersonSchema(TypedDict):
    name: str
    age: int


@dataclass
class Person:
    name: str
    age: int


def test_chat_json_injects_json_response_format():
    provider = FakeSummarizeProvider('{"name": "Ada", "age": 36}')
    client = Client(provider=provider)

    result = client.chat_json(["hello"])

    assert result == {"name": "Ada", "age": 36}
    assert provider.last_settings["response_format"] == {"type": "json_object"}


def test_chat_json_preserves_existing_settings():
    provider = FakeSummarizeProvider('{"name": "Ada", "age": 36}')
    client = Client(provider=provider)

    client.chat_json(["hello"], settings={"temperature": 0})

    assert provider.last_settings["temperature"] == 0
    assert provider.last_settings["response_format"] == {"type": "json_object"}


def test_chat_json_raises_for_invalid_json():
    provider = FakeSummarizeProvider("not json")
    client = Client(provider=provider)

    with pytest.raises(ValueError):
        client.chat_json(["hello"])


def test_chat_json_key_presence_schema_validation():
    provider = FakeSummarizeProvider('{"name": "Ada"}')
    client = Client(provider=provider)

    with pytest.raises(ValueError, match="missing required keys"):
        client.chat_json(["hello"], schema=PersonSchema)


def test_chat_json_strict_schema_dataclass_success_and_failure():
    ok_provider = FakeSummarizeProvider('{"name": "Ada", "age": 36}')
    ok_client = Client(provider=ok_provider)

    ok = ok_client.chat_json(["hello"], schema=Person, strict_schema=True)
    assert ok == {"name": "Ada", "age": 36}

    bad_provider = FakeSummarizeProvider('{"name": "Ada", "age": 36, "extra": true}')
    bad_client = Client(provider=bad_provider)

    with pytest.raises(ValueError, match="dataclass validation"):
        bad_client.chat_json(["hello"], schema=Person, strict_schema=True)


def test_chat_parsed_returns_dataclass_instance():
    provider = FakeSummarizeProvider('{"name": "Ada", "age": 36}')
    client = Client(provider=provider)

    obj = client.chat_parsed(["hello"], Person)

    assert isinstance(obj, Person)
    assert obj.name == "Ada"
    assert obj.age == 36


def test_chat_json_uses_provider_chat_when_available():
    provider = FakeChatProvider('{"ok": true}')
    client = Client(provider=provider)

    result = client.chat_json(["hello"])

    assert result == {"ok": True}
    assert provider.chat_called is True
    assert provider.summarize_called is False
