from modelito.connector import OllamaConnector
import os
import sys
import pytest

pytestmark = pytest.mark.smoke

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)




class DummyProvider:
    def summarize(self, messages, settings=None):
        return "dummy-response"


def test_connector_send_sync_and_history():
    prov = DummyProvider()
    conn = OllamaConnector(provider=prov)
    conn.clear_history()
    conn.add_to_history(None, "user", "first")
    from modelito.messages import Message
    resp = conn.send_sync(None, [Message(role="user", content="ask")])
    assert isinstance(resp, str)
    hist = conn.get_history(None)
    # should contain at least one assistant response
    assert any(m.role == "assistant" for m in hist)
