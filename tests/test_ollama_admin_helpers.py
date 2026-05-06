from modelito.ollama_service import (
    clear_model_lifecycle_state,
    detect_install_method,
    download_model_progress,
    ensure_model_ready,
    get_model_lifecycle_state,
    install_command_for_current_platform,
    list_remote_model_catalog,
)


def test_detect_install_method_prefers_package_managers(monkeypatch):
    def fake_which(name):
        mapping = {
            "brew": "/opt/homebrew/bin/brew",
            "apt-get": "/usr/bin/apt-get",
            "choco": "C:/ProgramData/choco.exe",
        }
        return mapping.get(name)

    monkeypatch.setattr("modelito.ollama_service.shutil.which", fake_which)

    assert detect_install_method("darwin") == "brew"
    assert detect_install_method("linux") == "apt"
    assert detect_install_method("win32") == "choco"


def test_install_command_for_current_platform_uses_detected_backend(monkeypatch):
    monkeypatch.setattr("modelito.ollama_service.shutil.which",
                        lambda name: "/usr/bin/apt-get" if name == "apt-get" else None)
    cmd, display = install_command_for_current_platform(platform_name="linux")
    assert cmd[:2] == ["/bin/sh", "-lc"]
    assert "apt-get install -y ollama" in display

    monkeypatch.setattr("modelito.ollama_service.shutil.which",
                        lambda name: "C:/ProgramData/choco.exe" if name == "choco" else None)
    cmd, display = install_command_for_current_platform(platform_name="win32")
    assert cmd[:3] == ["choco", "install", "ollama"]
    assert display == "choco install ollama -y"


def test_list_remote_model_catalog_returns_structured_entries(monkeypatch):
    monkeypatch.setattr(
        "modelito.ollama_service.list_remote_models",
        lambda: ["llama3.1:8b latest", "mistral:7b instruct"],
    )
    monkeypatch.setattr(
        "modelito.ollama_service.list_local_models",
        lambda: ["mistral:7b"],
    )

    entries = list_remote_model_catalog(query="mistral")
    assert len(entries) == 1
    assert entries[0].name == "mistral:7b"
    assert entries[0].family == "mistral"
    assert entries[0].tag == "7b"
    assert entries[0].installed is True


def test_download_model_progress_tracks_state(monkeypatch):
    class FakePopen:
        def __init__(self, *args, **kwargs):
            self.stdout = iter(
                [
                    "pulling manifest\n",
                    "downloading 50%\n",
                    "verifying sha256 digest\n",
                    "success\n",
                ]
            )

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr("modelito.ollama_service.get_ollama_binary",
                        lambda: "/usr/local/bin/ollama")
    monkeypatch.setattr("modelito.ollama_service.subprocess.Popen", FakePopen)

    states = list(download_model_progress("llama3.1:8b"))
    assert states[0].phase == "downloading"
    assert states[-1].phase == "downloaded"
    assert states[-1].progress == 100.0

    latest = get_model_lifecycle_state("llama3.1:8b")
    assert latest is not None
    assert latest.phase == "downloaded"
    assert clear_model_lifecycle_state("llama3.1:8b") is True


def test_ensure_model_ready_marks_model_ready(monkeypatch):
    monkeypatch.setattr(
        "modelito.ollama_service.ensure_ollama_running_verbose",
        lambda **kwargs: (True, "Ollama is ready"),
    )
    monkeypatch.setattr(
        "modelito.ollama_service.ensure_model_available",
        lambda model_name, allow_download=False, timeout=600.0: True,
    )
    monkeypatch.setattr("modelito.ollama_service.preload_model",
                        lambda host, port, model, timeout=120.0: None)
    monkeypatch.setattr("modelito.ollama_service.running_model_names", lambda host: ["llama3.1:8b"])

    assert ensure_model_ready("llama3.1:8b") is True
    latest = get_model_lifecycle_state("llama3.1:8b")
    assert latest is not None
    assert latest.phase == "ready"
    assert clear_model_lifecycle_state("llama3.1:8b") is True
