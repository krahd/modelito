"""`modelito` package exports.

This package is intentionally small and focused on provider/connectors
utilities used by downstream projects.
"""
try:
    from importlib.metadata import version, PackageNotFoundError
except Exception:
    __version__ = "1.2.2"
else:
    try:
        __version__ = version("modelito")
    except PackageNotFoundError:
        __version__ = "1.2.2"

from .tokenizer import count_tokens
from .timeout import estimate_remote_timeout, estimate_remote_timeout_details
from .plumbing import (
    ErrorEnvelope,
    ResponseEnvelope,
    TransportPolicy,
    envelope_error,
    envelope_ok,
    normalize_network_error,
    retry_with_backoff,
)
from .connector import OllamaConnector
from .config import load_config, parse_host_port
from .exceptions import LLMProviderError
from .ollama_service import server_is_up, endpoint_url
from .ollama_service import ensure_ollama_running
from .ollama_service import (
    RemoteModelCatalogEntry,
    ModelLifecycleState,
    detect_install_method,
    get_ollama_binary,
    install_ollama,
    start_ollama,
    stop_ollama,
    update_ollama,
    list_local_models,
    list_remote_models,
    list_remote_model_catalog,
    download_model,
    download_model_progress,
    delete_model,
    serve_model,
    change_ollama_config,
    ollama_binary_candidates,
    resolve_ollama_command,
    ollama_installed,
    run_ollama_command,
    start_detached_ollama_serve,
    wait_until_ready,
    preload_model,
    ensure_model_ready,
    ensure_model_loaded,
    ollama_health_check,
    ollama_readiness_probe,
    running_model_names,
    get_model_lifecycle_state,
    list_model_lifecycle_states,
    clear_model_lifecycle_state,
    find_ollama_listener_pids,
    stop_service,
    install_service,
    ensure_ollama_running_verbose,
    async_ensure_model_ready,
)
from .ollama import OllamaProvider
from .gemini import GeminiProvider
from .grok import GrokProvider
from .openai import OpenAIProvider
from .claude import ClaudeProvider
from .provider import Provider, EmbeddingProvider
from .client import Client
from .embeddings import Embedder, StubEmbeddingProvider, embed_texts
from .messages import Message, Messages, Response
from .normalization import normalize_models, normalize_metadata

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
    "Provider",
    "EmbeddingProvider",
    "Client",
    "Embedder",
    "StubEmbeddingProvider",
    "embed_texts",
    "Message",
    "Messages",
    "Response",
    "normalize_models",
    "normalize_metadata",
    "load_config",
    "parse_host_port",
    "LLMProviderError",
    "server_is_up",
    "endpoint_url",
    "ensure_ollama_running",
    "RemoteModelCatalogEntry",
    "ModelLifecycleState",
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
]
