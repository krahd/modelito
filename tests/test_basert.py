from modelito.basert import BaseRTProvider
from modelito.provider_registry import get_provider, list_providers


def test_basert_defaults_to_local_openai_compatible_endpoint():
    provider = BaseRTProvider(model="Qwen/Qwen3-4B", strict=True)

    assert provider.base_url == "http://127.0.0.1:8080/v1"
    assert provider.model == "Qwen/Qwen3-4B"
    assert provider.strict is True


def test_basert_is_registered_provider():
    provider = get_provider(
        "basert",
        model="Qwen/Qwen3-4B",
        base_url="http://127.0.0.1:9000/v1",
        api_key="test-key",
        strict=True,
    )

    assert "basert" in list_providers()
    assert isinstance(provider, BaseRTProvider)
    assert provider.base_url == "http://127.0.0.1:9000/v1"
    assert provider.api_key == "test-key"
