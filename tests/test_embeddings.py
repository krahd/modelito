from modelito.embeddings import embed_texts, StubEmbeddingProvider


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
