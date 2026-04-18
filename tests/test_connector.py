from modelito.connector import OllamaConnector


class DummyProvider:
    def summarize(self, messages, settings=None):
        # return a simple joined message as a fake summary
        return "|".join(m.get("content", "") for m in messages if m.get("role") != "system")


def test_connector_history_and_trim():
    prov = DummyProvider()
    conn = OllamaConnector(prov, max_history_messages=10, max_history_tokens=20)
    conv = "c1"
    conn.set_system_message("You are a helpful assistant.")
    conn.add_to_history(conv, "user", "hello")
    conn.add_to_history(conv, "assistant", "hi")
    conn.add_to_history(conv, "user", "this is a longer message that should be trimmed")
    hist = conn.get_history(conv)
    assert len(hist) >= 2
    # build prompt with small token budget to force trimming
    prompt = conn.build_prompt(conv, include_history=True, max_prompt_tokens=8)
    # ensure tokens within budget (approx)
    # rely on internal _total_tokens via behavior: trimmed list length <= original
    assert len(prompt) <= len(hist)

    # test send_sync uses provider and returns string
    resp = conn.send_sync(conv, [{"role": "user", "content": "please summarize"}], settings={})
    assert isinstance(resp, str)
