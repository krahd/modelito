"""`modelito` package exports.

This package is intentionally small and focused on provider/connectors
utilities used by downstream projects.
"""
try:
    from importlib.metadata import version, PackageNotFoundError
except Exception:
    __version__ = "1.0.0"
else:
    try:
        __version__ = version("modelito")
    except PackageNotFoundError:
        __version__ = "1.0.0"

from .tokenizer import count_tokens
from .timeout import estimate_remote_timeout
from .connector import OllamaConnector
from .config import load_config, parse_host_port
from .exceptions import LLMProviderError
from .ollama_service import server_is_up, endpoint_url
from .ollama_service import ensure_ollama_running
from .ollama_service import (
    get_ollama_binary,
    install_ollama,
    start_ollama,
    stop_ollama,
    update_ollama,
    list_local_models,
    list_remote_models,
    download_model,
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
    running_model_names,
    find_ollama_listener_pids,
    stop_service,
    install_service,
    ensure_ollama_running_verbose,
)
from .ollama import OllamaProvider
from .gemini import GeminiProvider
from .grok import GrokProvider
from .openai import OpenAIProvider
from .claude import ClaudeProvider
from .provider import Provider
from .client import Client
from .messages import Message, Messages, Response

__all__ = [
    "__version__",
    "count_tokens",
    "estimate_remote_timeout",
    "OllamaConnector",
    "OllamaProvider",
    "GeminiProvider",
    "GrokProvider",
    "OpenAIProvider",
    "ClaudeProvider",
    "Provider",
    "Client",
    "Message",
    "Messages",
    "Response",
    "load_config",
    "parse_host_port",
    "LLMProviderError",
    "server_is_up",
    "endpoint_url",
    "ensure_ollama_running",
    "get_ollama_binary",
    "install_ollama",
    "start_ollama",
    "stop_ollama",
    "update_ollama",
    "list_local_models",
    "list_remote_models",
    "download_model",
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
    "running_model_names",
    "find_ollama_listener_pids",
    "stop_service",
    "install_service",
    "ensure_ollama_running_verbose",
]
