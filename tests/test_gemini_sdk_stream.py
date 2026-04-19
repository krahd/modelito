import types

from modelito.gemini import GeminiProvider
from modelito.messages import Message


def test_gemini_generate_text_iterable():
    class FakeGen:
        def generate_text(self, model, prompt, **kwargs):
            yield {"text": "X"}
            yield {"text": "Y"}

    fake = FakeGen()
    prov = GeminiProvider(client=fake)
    out = "".join(list(prov.stream([Message(role="user", content="hi")])))
    assert out == "XY"


def test_gemini_client_generate_text():
    class FakeClient:
        def generate_text(self, model, prompt, **kwargs):
            yield {"text": "1"}
            yield {"text": "2"}

    fake = types.SimpleNamespace(client=FakeClient())
    prov = GeminiProvider(client=fake)
    out = "".join(list(prov.stream([Message(role="user", content="hi")])))
    assert out == "12"
