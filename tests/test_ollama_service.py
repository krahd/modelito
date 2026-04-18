from modelito import ollama_service as osvc


def test_ollama_service_smoke():
    # Ensure calls are safe when `ollama` isn't installed; return types verified.
    binp = osvc.get_ollama_binary()
    assert binp is None or isinstance(binp, str)
    assert isinstance(osvc.list_local_models(), list)
    assert isinstance(osvc.list_remote_models(), list)
    # Download/delete/update attempts should be safe booleans
    assert isinstance(osvc.download_model("nonexistent-model"), bool)
    assert isinstance(osvc.delete_model("nonexistent-model"), bool)
    assert isinstance(osvc.install_ollama(allow_install=False), bool)
    assert isinstance(osvc.update_ollama(allow_upgrade=False), bool)