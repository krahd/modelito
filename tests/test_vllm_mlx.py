from modelito.provider_registry import get_provider, list_providers
from modelito.vllm_mlx import VLLMMLXProvider


def test_vllm_mlx_defaults_to_local_openai_compatible_endpoint():
    provider = VLLMMLXProvider(model="mlx-community/Qwen3-4B-4bit", strict=True)

    assert provider.base_url == "http://localhost:8000/v1"
    assert provider.model == "mlx-community/Qwen3-4B-4bit"
    assert provider.strict is True


def test_vllm_mlx_is_registered_provider():
    provider = get_provider(
        "vllm-mlx",
        model="mlx-community/Qwen3-4B-4bit",
        base_url="http://127.0.0.1:9001/v1",
        api_key="test-key",
        strict=True,
    )

    assert "vllm-mlx" in list_providers()
    assert isinstance(provider, VLLMMLXProvider)
    assert provider.base_url == "http://127.0.0.1:9001/v1"
    assert provider.api_key == "test-key"


def test_vllm_mlx_underscore_alias_is_registered():
    provider = get_provider("vllm_mlx", model="test-model")

    assert isinstance(provider, VLLMMLXProvider)
