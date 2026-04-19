import pytest

from modelito.openai import OpenAIProvider


@pytest.mark.asyncio
async def test_acomplete_uses_threadpool():
    prov = OpenAIProvider(client=None)
    prov.summarize = lambda messages, settings=None: "joined"
    out = await prov.acomplete(["a", "b"])
    assert out == "joined"
