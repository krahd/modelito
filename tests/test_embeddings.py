import pytest

from modelito.embeddings import Embedder, StubEmbeddingProvider, embed_texts
from modelito.provider_registry import get_embedder, list_embedders


def test_embed_texts_shape():
    texts = ["a", "bb", "ccc"]
    embs = embed_texts(texts, dim=4)
    assert len(embs) == 3
    assert all(len(v) == 4 for v in embs)


def test_stub_provider_embed():
    prov = StubEmbeddingProvider()
    out = prov.embed(["one", "two"], dim=3)
    assert len(out) == 2
    assert all(len(v) == 3 for v in out)


def test_embedder_registry_exposes_known_embedders():
    embedders = list_embedders()

    assert "openai" in embedders
    assert "ollama" in embedders
    assert get_embedder("mock") is not None


def test_embedder_runtime_selection_uses_provider_embed_surface():
    embedder = Embedder(provider="mock")

    out = embedder.embed(["one", "three"])

    assert out == [[3.0] * 8, [5.0] * 8]


def test_embedder_available_embedders_matches_registry():
    assert Embedder.available_embedders() == list_embedders()


def test_embedder_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unknown embedder"):
        Embedder(provider="does-not-exist")
