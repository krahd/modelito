import json
from pathlib import Path

from modelito.config import load_config_data


def test_load_config_data_merge(tmp_path: Path):
    base = tmp_path / "base.json"
    user = tmp_path / "user.json"
    project = tmp_path / "project.json"

    base.write_text(
        json.dumps({
            "llm": {
                "model": "base-model",
                "model_timeouts": {"a": 1, "b": 2},
                "timeout": 10,
            }
        })
    )

    user.write_text(
        json.dumps({
            "llm": {
                "model": "user-model",
                "model_timeouts": {"b": 20, "c": 30},
            }
        })
    )

    project.write_text(
        json.dumps({
            "llm": {
                "last_served_model": "project-last",
                "model_timeouts": {"c": 300},
            }
        })
    )

    merged = load_config_data(str(base), str(user), str(project))
    assert isinstance(merged, dict)
    llm = merged.get("llm") or {}
    assert llm.get("model") == "user-model"
    assert llm.get("last_served_model") == "project-last"
    assert llm.get("timeout") == 10
    assert llm.get("model_timeouts") == {"a": 1, "b": 20, "c": 300}
def test_load_config_data_merge(tmp_path: Path):
    base = tmp_path / "base.json"
    user = tmp_path / "user.json"
    project = tmp_path / "project.json"

    base.write_text(
        json.dumps({
            "llm": {
                "model": "base-model",
                "model_timeouts": {"a": 1, "b": 2},
                "timeout": 10,
            }
        })
    )

    user.write_text(
        json.dumps({
            "llm": {
                "model": "user-model",
                "model_timeouts": {"b": 20, "c": 30},
            }
        })
    )

    project.write_text(
        json.dumps({
            "llm": {
                "last_served_model": "project-last",
                "model_timeouts": {"c": 300},
            }
        })
    )

    merged = load_config_data(str(base), str(user), str(project))
    assert isinstance(merged, dict)
    llm = merged.get("llm") or {}
    assert llm.get("model") == "user-model"
    assert llm.get("last_served_model") == "project-last"
    assert llm.get("timeout") == 10
    assert llm.get("model_timeouts") == {"a": 1, "b": 20, "c": 300}
>>>>>> > f1078c8(Phase B / C: config merge, timeout diagnostics & calibration, async Ollama wrappers, docs, release helper)
