from modelito.client import Client
from modelito.doctor import check_provider_ready
from modelito.messages import Message
from modelito.omlx import OMLXProvider
import pytest


class StreamingProvider:
    model = "gpt-4o-mini"

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

    assert metadata["provider"] == "openai"
    assert metadata["supports_streaming"] is True
    assert metadata["functions"] is True
    assert metadata["tools"] is True


def test_client_available_embedders_exposes_embedder_registry():
    embedders = Client.available_embedders()

    assert "openai" in embedders
    assert "mock" in embedders


class DummyResolvedProvider:
    model = "dummy"

    def list_models(self):
        return [self.model]

    def summarize(self, messages, settings=None):
        return "ok"


def test_client_auto_prefers_project_profile_provider(monkeypatch, tmp_path):
    profile = tmp_path / "profile.json"
    profile.write_text('{"provider": "omlx"}', encoding="utf-8")

    called = {"name": None}

    def fake_get_provider(name, **kwargs):
        called["name"] = name
        return DummyResolvedProvider()

    monkeypatch.setattr("modelito.client.get_provider", fake_get_provider)
    monkeypatch.setenv("MODELITO_PROVIDER", "ollama")
    monkeypatch.setattr(
        "modelito.client.Client._auto_select_provider",
        classmethod(
            lambda cls, model, provider_kwargs, remote_provider_env_var, prefer, auto_probe_timeout: "openai"
        ),
    )

    Client(provider="auto", profile_path=str(profile))
    assert called["name"] == "omlx"


def test_client_auto_prefers_env_provider_when_no_profile(monkeypatch):
    called = {"name": None}

    def fake_get_provider(name, **kwargs):
        called["name"] = name
        return DummyResolvedProvider()

    monkeypatch.setattr("modelito.client.get_provider", fake_get_provider)
    monkeypatch.setenv("MODELITO_PROVIDER", "ollama")
    monkeypatch.setattr(
        "modelito.client.Client._provider_from_project_profile",
        classmethod(lambda cls, profile_path=None: None),
    )
    monkeypatch.setattr(
        "modelito.client.Client._auto_select_provider",
        classmethod(
            lambda cls, model, provider_kwargs, remote_provider_env_var, prefer, auto_probe_timeout: "openai"
        ),
    )

    Client(provider="auto")
    assert called["name"] == "ollama"


def test_client_auto_uses_omlx_on_macos_apple_silicon(monkeypatch):
    called = {"name": None}

    def fake_get_provider(name, **kwargs):
        called["name"] = name
        return DummyResolvedProvider()

    monkeypatch.setattr("modelito.client.get_provider", fake_get_provider)
    monkeypatch.delenv("MODELITO_PROVIDER", raising=False)
    monkeypatch.setattr(
        "modelito.client.Client._provider_from_project_profile",
        classmethod(lambda cls, profile_path=None: None),
    )
    monkeypatch.setattr(
        "modelito.client.Client._is_macos_apple_silicon",
        staticmethod(lambda: True),
    )
    monkeypatch.setattr(
        "modelito.client.Client._omlx_probe",
        staticmethod(
            lambda model, provider_kwargs, timeout: {
                "provider": "omlx",
                "available": True,
                "models": ["omlx"],
                "endpoint": "http://localhost:8000/v1",
                "reason": None,
            }
        ),
    )
    monkeypatch.setattr(
        "modelito.client.Client._ollama_probe",
        staticmethod(
            lambda model, provider_kwargs, timeout: {
                "provider": "ollama",
                "available": False,
                "models": [],
                "endpoint": "http://127.0.0.1:11434",
                "reason": "not reachable",
            }
        ),
    )

    Client(provider="auto", model="omlx")
    assert called["name"] == "omlx"


def test_client_auto_raises_helpful_error_when_no_local_backend_on_macos_arm(monkeypatch):
    monkeypatch.delenv("MODELITO_PROVIDER", raising=False)
    monkeypatch.setattr(
        "modelito.client.Client._provider_from_project_profile",
        classmethod(lambda cls, profile_path=None: None),
    )
    monkeypatch.setattr(
        "modelito.client.Client._is_macos_apple_silicon",
        staticmethod(lambda: True),
    )
    monkeypatch.setattr(
        "modelito.client.Client._omlx_probe",
        staticmethod(
            lambda model, provider_kwargs, timeout: {
                "provider": "omlx",
                "available": False,
                "models": [],
                "endpoint": "http://localhost:8000/v1",
                "reason": "not reachable",
            }
        ),
    )
    monkeypatch.setattr(
        "modelito.client.Client._ollama_probe",
        staticmethod(
            lambda model, provider_kwargs, timeout: {
                "provider": "ollama",
                "available": False,
                "models": [],
                "endpoint": "http://127.0.0.1:11434",
                "reason": "not reachable",
            }
        ),
    )

    with pytest.raises(ValueError, match="Install/start one backend"):
        Client(provider="auto", model="missing-model")


def test_client_auto_prefers_ollama_on_non_macos(monkeypatch):
    called = {"name": None}

    def fake_get_provider(name, **kwargs):
        called["name"] = name
        return DummyResolvedProvider()

    monkeypatch.setattr("modelito.client.get_provider", fake_get_provider)
    monkeypatch.delenv("MODELITO_PROVIDER", raising=False)
    monkeypatch.setattr(
        "modelito.client.Client._provider_from_project_profile",
        classmethod(lambda cls, profile_path=None: None),
    )
    monkeypatch.setattr(
        "modelito.client.Client._is_macos_apple_silicon",
        staticmethod(lambda: False),
    )
    monkeypatch.setattr(
        "modelito.client.Client._ollama_probe",
        staticmethod(
            lambda model, provider_kwargs, timeout: {
                "provider": "ollama",
                "available": True,
                "models": ["llama3"],
                "endpoint": "http://127.0.0.1:11434",
                "reason": None,
            }
        ),
    )

    Client(provider="auto")
    assert called["name"] == "ollama"


def test_client_and_doctor_share_omlx_probe_results(monkeypatch):
    from modelito.probes import ProviderStatus

    status = ProviderStatus(
        provider="omlx",
        ready=False,
        endpoint="http://localhost:8000/v1",
        models=[],
        reason="oMLX server not reachable",
        setup_hint="Start oMLX",
    )
    monkeypatch.setattr("modelito.probes.probe_omlx_status", lambda *args, **kwargs: status)

    client_probe = Client._omlx_probe("omlx", {}, 1.5)
    doctor_status = check_provider_ready("omlx", model="omlx")

    assert client_probe["available"] is False
    assert doctor_status.ready is False
    assert client_probe["endpoint"] == doctor_status.endpoint


def test_client_auto_uses_remote_provider_env_on_non_macos_when_no_ollama(monkeypatch):
    called = {"name": None}

    def fake_get_provider(name, **kwargs):
        called["name"] = name
        return DummyResolvedProvider()

    monkeypatch.setattr("modelito.client.get_provider", fake_get_provider)
    monkeypatch.delenv("MODELITO_PROVIDER", raising=False)
    monkeypatch.setenv("MODELITO_REMOTE_PROVIDER", "openai")
    monkeypatch.setattr(
        "modelito.client.Client._provider_from_project_profile",
        classmethod(lambda cls, profile_path=None: None),
    )
    monkeypatch.setattr(
        "modelito.client.Client._is_macos_apple_silicon",
        staticmethod(lambda: False),
    )
    monkeypatch.setattr(
        "modelito.client.Client._ollama_probe",
        staticmethod(
            lambda model, provider_kwargs, timeout: {
                "provider": "ollama",
                "available": False,
                "models": [],
                "endpoint": "http://127.0.0.1:11434",
                "reason": "not reachable",
            }
        ),
    )

    Client(provider="auto")
    assert called["name"] == "openai"


def test_client_auto_falls_back_to_default_provider(monkeypatch):
    called = {"name": None}

    def fake_get_provider(name, **kwargs):
        called["name"] = name
        return DummyResolvedProvider()

    monkeypatch.setattr("modelito.client.get_provider", fake_get_provider)
    monkeypatch.delenv("MODELITO_PROVIDER", raising=False)
    monkeypatch.delenv("MODELITO_REMOTE_PROVIDER", raising=False)
    monkeypatch.setattr(
        "modelito.client.Client._provider_from_project_profile",
        classmethod(lambda cls, profile_path=None: None),
    )
    monkeypatch.setattr(
        "modelito.client.Client._is_macos_apple_silicon",
        staticmethod(lambda: False),
    )
    monkeypatch.setattr(
        "modelito.client.Client._ollama_probe",
        staticmethod(
            lambda model, provider_kwargs, timeout: {
                "provider": "ollama",
                "available": False,
                "models": [],
                "endpoint": "http://127.0.0.1:11434",
                "reason": "not reachable",
            }
        ),
    )

    Client(provider="auto")
    assert called["name"] == "openai"


def test_client_auto_honours_prefer_list(monkeypatch):
    called = {"name": None}

    def fake_get_provider(name, **kwargs):
        called["name"] = name
        return DummyResolvedProvider()

    monkeypatch.setattr("modelito.client.get_provider", fake_get_provider)
    monkeypatch.delenv("MODELITO_PROVIDER", raising=False)
    monkeypatch.delenv("MODELITO_REMOTE_PROVIDER", raising=False)
    monkeypatch.setattr(
        "modelito.client.Client._provider_from_project_profile",
        classmethod(lambda cls, profile_path=None: None),
    )
    monkeypatch.setattr(
        "modelito.client.Client._is_macos_apple_silicon",
        staticmethod(lambda: True),
    )
    monkeypatch.setattr(
        "modelito.client.Client._omlx_probe",
        staticmethod(
            lambda model, provider_kwargs, timeout: {
                "provider": "omlx",
                "available": True,
                "models": ["omlx"],
                "endpoint": "http://localhost:8000/v1",
                "reason": None,
            }
        ),
    )
    monkeypatch.setattr(
        "modelito.client.Client._ollama_probe",
        staticmethod(
            lambda model, provider_kwargs, timeout: {
                "provider": "ollama",
                "available": True,
                "models": ["llama3"],
                "endpoint": "http://127.0.0.1:11434",
                "reason": None,
            }
        ),
    )

    Client(provider="auto", prefer=["ollama", "omlx"])
    assert called["name"] == "ollama"


def test_omlx_provider_default_base_url_matches_current_docs():
    provider = OMLXProvider()
    assert provider.base_url == "http://localhost:8000/v1"
