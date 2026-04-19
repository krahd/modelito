import types

from modelito.openai import OpenAIProvider


def test_embed_uses_client_embeddings_create():
    class FakeEmbeddings:
        def create(self, input, **kwargs):
            return {"data": [{"embedding": [1.0, 2.0]}, {"embedding": [3.0, 4.0]}]}

    fake_client = types.SimpleNamespace(embeddings=FakeEmbeddings())
    prov = OpenAIProvider(client=fake_client)
    out = prov.embed(["one", "two"])
    assert out == [[1.0, 2.0], [3.0, 4.0]]
