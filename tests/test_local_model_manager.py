from modelito.local_model_manager import LocalModelManager

def test_discover_models(monkeypatch):
    monkeypatch.setattr("modelito.local_model_manager.list_local_models", lambda: ["foo", "bar"])
    mgr = LocalModelManager()
    models = mgr.discover_models()
    assert models == ["foo", "bar"]

def test_health_check(monkeypatch):
    monkeypatch.setattr("modelito.local_model_manager.server_is_up", lambda host, port: True)
    mgr = LocalModelManager()
    mgr.models = ["foo"]
    status = mgr.health_check()
    assert status["server_up"] is True
    assert status["models"] == ["foo"]

def test_select_model():
    mgr = LocalModelManager()
    mgr.models = ["foo", "bar"]
    assert mgr.select_model("foo") == "foo"
    assert mgr.select_model("baz") is None

def test_status_report(monkeypatch):
    monkeypatch.setattr("modelito.local_model_manager.server_is_up", lambda host, port: False)
    mgr = LocalModelManager()
    mgr.models = []
    report = mgr.get_status_report()
    assert "error" in report
