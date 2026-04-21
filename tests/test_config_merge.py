import json

from modelito.config import load_config_data


def test_load_config_data_merge(tmp_path):
    base = {"llm": {"model": "base", "model_timeouts": {"base": 5}, "timeout": 10}}
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps(base))

    overlay = {"llm": {"model": "overlay", "model_timeouts": {"overlay": 7}}}

    merged = load_config_data(str(p), overlays=[overlay])
    assert merged["llm"]["model"] == "overlay"
    assert "base" in merged["llm"]["model_timeouts"]
    assert "overlay" in merged["llm"]["model_timeouts"]
    assert merged["llm"]["timeout"] == 10
