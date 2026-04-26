from modelito.api_key_manager import APIKeyManager

def test_env_var_override(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "envkey1234567890")
    mgr = APIKeyManager()
    assert mgr.get_api_key("openai") == "envkey1234567890"
    assert mgr.validate_api_key("openai")

def test_config_fallback(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    mgr = APIKeyManager(config={"openai": "configkey0987654321"})
    assert mgr.get_api_key("openai") == "configkey0987654321"
    assert mgr.validate_api_key("openai")

def test_require_api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "envkey1234567890")
    mgr = APIKeyManager()
    assert mgr.require_api_key("openai") == "envkey1234567890"

def test_invalid_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    mgr = APIKeyManager()
    assert not mgr.validate_api_key("openai")
