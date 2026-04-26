"""
Local Model Manager for Modelito
- Auto-discovers local models (Ollama, LM Studio, etc.)
- Performs health checks
- Reports errors and status
- Supports dynamic model selection
"""
from typing import List, Dict, Any, Optional
from .ollama_service import list_local_models, server_is_up, ensure_ollama_running

class LocalModelManager:
    def __init__(self, host: str = "http://127.0.0.1", port: int = 11434):
        self.host = host
        self.port = port
        self.models: List[str] = []
        self.status: Dict[str, Any] = {}

    def discover_models(self) -> List[str]:
        """Auto-discover local models (Ollama)."""
        self.models = list_local_models()
        return self.models

    def health_check(self) -> Dict[str, Any]:
        """Check health of local model server."""
        up = server_is_up(self.host, self.port)
        self.status = {"server_up": up, "models": self.models}
        return self.status

    def ensure_running(self, auto_start: bool = False) -> bool:
        """Ensure Ollama server is running."""
        return ensure_ollama_running(self.host, self.port, auto_start=auto_start)

    def select_model(self, model_name: str) -> Optional[str]:
        """Select a model dynamically if available."""
        if model_name in self.models:
            return model_name
        return None

    def get_status_report(self) -> Dict[str, Any]:
        """Return a status report with errors if any."""
        report = self.health_check()
        if not report["server_up"]:
            report["error"] = "Local model server is not running."
        elif not report["models"]:
            report["warning"] = "No local models found."
        return report
