from modelito.openai import OpenAIProvider


def test_acomplete_uses_threadpool():
    prov = OpenAIProvider(client=None)
    prov.summarize = lambda messages, settings=None: "joined"
    import asyncio

    out = asyncio.run(prov.acomplete(["a", "b"]))
    assert out == "joined"
