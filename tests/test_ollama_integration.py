import os
import pytest

from modelito import ollama_service as osvc

# mark as integration so CI can easily select/deselect these
pytestmark = pytest.mark.integration


def _env_true(name: str) -> bool:
    return os.environ.get(name, "").lower() in ("1", "true", "yes", "on")


if not _env_true("RUN_OLLAMA_INTEGRATION"):
    pytest.skip("Ollama integration tests disabled (set RUN_OLLAMA_INTEGRATION=1)",
                allow_module_level=True)


def test_install_and_update_if_needed():
    binp = osvc.get_ollama_binary()
    if not binp:
        if _env_true("ALLOW_OLLAMA_INSTALL"):
            assert osvc.install_ollama(allow_install=True)
            binp = osvc.get_ollama_binary()
            if not binp:
                pytest.skip("ollama install attempted but not found")
        else:
            pytest.skip("ollama not installed and installation not allowed")

    if os.environ.get("ALLOW_OLLAMA_UPDATE") == "1":
        assert isinstance(osvc.update_ollama(allow_upgrade=True), bool)


def test_list_models_and_config():
    binp = osvc.get_ollama_binary()
    if not binp:
        if _env_true("ALLOW_OLLAMA_INSTALL"):
            # Try installation if allowed but continue gracefully if it fails
            osvc.install_ollama(allow_install=True)
            binp = osvc.get_ollama_binary()
        if not binp:
            pytest.skip("ollama not available; skipping list/config test")
    local = osvc.list_local_models()
    assert isinstance(local, list)
    remote = osvc.list_remote_models()
    assert isinstance(remote, list)
    cfg = {"test_integration": True}
    assert osvc.change_ollama_config(cfg)


def test_serve_and_stop():
    binp = osvc.get_ollama_binary()
    assert binp is not None
    started = osvc.serve_model(timeout=30)
    assert started is True
    assert osvc.server_is_up("http://127.0.0.1", 11434)
    stopped = osvc.stop_ollama(force=True)
    assert isinstance(stopped, bool)


def test_download_delete_model_optional():
    binp = osvc.get_ollama_binary()
    if not binp:
        pytest.skip("ollama not available; skipping download test")
    if not _env_true("ALLOW_OLLAMA_DOWNLOAD"):
        pytest.skip("Model download disabled")
    remote = osvc.list_remote_models()
    if not remote:
        pytest.skip("No remote models reported")
    # remote lines may include additional columns; first token usually is the model name
    model = remote[0].split()[0] if remote else None
    if not model or model.lower().startswith("error"):
        pytest.skip("Could not parse remote model name")
    success = osvc.download_model(model)
    if not success:
        pytest.skip("Model download failed; skipping delete")
    assert osvc.delete_model(model)
