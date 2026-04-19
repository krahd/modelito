import sys
import pytest

pytestmark = pytest.mark.integration

from modelito import ollama_service as osvc


def test_load_and_inspect_config_smoke():
    conf = osvc.load_llm_config()
    assert isinstance(conf, dict)
    assert "url" in conf and "port" in conf
    assert isinstance(osvc.preferred_start_model(conf), str)

    state = osvc.inspect_service_state()
    assert isinstance(state, dict)
    assert "installed" in state and isinstance(state["installed"], bool)


def test_start_service_safe():
    # start_service should return non-zero when ollama CLI missing
    if not osvc.ollama_installed():
        res = osvc.start_service()
        assert isinstance(res, int) and res != 0
    else:
        # if installed, we at least get an int result
        res = osvc.start_service()
        assert isinstance(res, int)
