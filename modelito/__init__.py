"""`modelito` package exports.

This package is intentionally small and focused on provider/connectors
utilities used by downstream projects.
"""

try:
    from importlib.metadata import PackageNotFoundError, version
except Exception:
    __version__ = "1.4.6"
else:
    try:
        __version__ = version("modelito")
    except PackageNotFoundError:
        __version__ = "1.4.6"

from .basert import BaseRTProvider
from .claude import ClaudeProvider
from .client import Client
from .config import load_config, parse_host_port
from .connector import OllamaConnector
from .doctor import ProviderStatus, check_provider_ready, format_provider_status
from .embeddings import Embedder, StubEmbeddingProvider, embed_texts
from .exceptions import (
    LLMProviderError,
    ModelitoBadResponseError,
    ModelitoConnectionError,
    ModelitoModelNotFoundError,
    ModelitoProviderError,
    ModelitoTimeoutError,
)
from .gemini import GeminiProvider
from .grok import GrokProvider
from .local_runtime import (
    LOCAL_PROFILE_AUTO,
    LOCAL_PROFILE_MAC_PERFORMANCE,
    LOCAL_PROFILE_PORTABLE,
    LOCAL_PROFILES,
    LocalRuntimeCapabilities,
    LocalRuntimeSelection,
    is_macos_apple_silicon,
    local_client,
    local_provider_candidates,
    local_runtime_capabilities,
    normalize_local_profile,
    select_local_runtime,
)
from .messages import Message, Messages, Response, flatten_message_inputs
from .model_metadata import (
    ModelMetadata,
    get_model_info,
    get_model_metadata,
    infer_model_metadata,
)
from .normalization import normalize_metadata, normalize_models
from .ollama import OllamaProvider
from .ollama_service import (
    ModelLifecycleState,
    ReadinessResult,
    RemoteModelCatalogEntry,
    async_ensure_model_ready,
    async_ensure_model_ready_detailed,
    change_ollama_config,
    clear_model_lifecycle_state,
    delete_model,
    detect_install_method,
    download_model,
    download_model_progress,
    endpoint_url,
    ensure_model_loaded,
    ensure_model_ready,
    ensure_model_ready_detailed,
    ensure_ollama_running,
    ensure_ollama_running_verbose,
    find_ollama_listener_pids,
    get_model_lifecycle_state,
    get_ollama_binary,
    install_ollama,
    install_service,
    list_local_models,
    list_model_lifecycle_states,
    list_remote_model_catalog,
    list_remote_models,
    ollama_binary_candidates,
    ollama_health_check,
    ollama_installed,
    ollama_readiness_probe,
    preload_model,
    resolve_ollama_command,
    run_ollama_command,
    running_model_names,
    serve_model,
    server_is_up,
    start_detached_ollama_serve,
    start_ollama,
    stop_ollama,
    stop_service,
    update_ollama,
    wait_until_ready,
)
from .omlx import OMLXProvider
from .openai import OpenAIProvider
from .openai_compat import OpenAICompatibleHTTPProvider
from .plumbing import (
    ErrorEnvelope,
    ResponseEnvelope,
    TransportPolicy,
    envelope_error,
    envelope_ok,
    normalize_network_error,
    retry_with_backoff,
)
from .provider import (
    ChatProvider,
    EmbeddingProvider,
    MessageInput,
    OpenAIMessageDict,
    Provider,
    RawChatProvider,
)
from .timeout import estimate_remote_timeout, estimate_remote_timeout_details
from .tokenizer import count_tokens
from .vllm_mlx import VLLMMLXProvider

__all__ = [
    "__version__",
    "count_tokens",
    "estimate_remote_timeout",
    "estimate_remote_timeout_details",
    "TransportPolicy",
    "ErrorEnvelope",
    "ResponseEnvelope",
    "retry_with_backoff",
    "normalize_network_error",
    "envelope_ok",
    "envelope_error",
    "OllamaConnector",
    "OllamaProvider",
    "GeminiProvider",
    "GrokProvider",
    "OpenAIProvider",
    "ClaudeProvider",
    "OMLXProvider",
    "BaseRTProvider",
    "VLLMMLXProvider",
    "Provider",
    "EmbeddingProvider",
    "ChatProvider",
    "RawChatProvider",
    "MessageInput",
    "OpenAIMessageDict",
    "RemoteModelCatalogEntry",
    "ModelLifecycleState",
    "ReadinessResult",
    "Client",
    "LOCAL_PROFILE_AUTO",
    "LOCAL_PROFILE_PORTABLE",
    "LOCAL_PROFILE_MAC_PERFORMANCE",
    "LOCAL_PROFILES",
    "LocalRuntimeSelection",
    "LocalRuntimeCapabilities",
    "is_macos_apple_silicon",
    "normalize_local_profile",
    "local_provider_candidates",
    "local_runtime_capabilities",
    "select_local_runtime",
    "local_client",
    "ProviderStatus",
    "check_provider_ready",
    "format_provider_status",
    "Embedder",
    "StubEmbeddingProvider",
    "embed_texts",
    "Message",
    "Messages",
    "Response",
    "flatten_message_inputs",
    "ModelMetadata",
    "get_model_info",
    "get_model_metadata",
    "infer_model_metadata",
    "normalize_models",
    "normalize_metadata",
    "load_config",
    "parse_host_port",
    "LLMProviderError",
    "ModelitoConnectionError",
    "ModelitoTimeoutError",
    "ModelitoBadResponseError",
    "ModelitoProviderError",
    "ModelitoModelNotFoundError",
    "OpenAICompatibleHTTPProvider",
    "server_is_up",
    "endpoint_url",
    "ensure_ollama_running",
    "detect_install_method",
    "get_ollama_binary",
    "install_ollama",
    "start_ollama",
    "stop_ollama",
    "update_ollama",
    "list_local_models",
    "list_remote_models",
    "list_remote_model_catalog",
    "download_model",
    "download_model_progress",
    "delete_model",
    "serve_model",
    "change_ollama_config",
    "ollama_binary_candidates",
    "resolve_ollama_command",
    "ollama_installed",
    "run_ollama_command",
    "start_detached_ollama_serve",
    "wait_until_ready",
    "preload_model",
    "ensure_model_ready",
    "ensure_model_ready_detailed",
    "ensure_model_loaded",
    "ollama_health_check",
    "ollama_readiness_probe",
    "running_model_names",
    "get_model_lifecycle_state",
    "list_model_lifecycle_states",
    "clear_model_lifecycle_state",
    "find_ollama_listener_pids",
    "stop_service",
    "install_service",
    "ensure_ollama_running_verbose",
    "async_ensure_model_ready",
    "async_ensure_model_ready_detailed",
]
