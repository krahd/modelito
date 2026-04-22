import asyncio

from modelito.ollama_service import async_list_local_models


def test_async_list_local_models():
    async def _run():
        res = await async_list_local_models()
        assert isinstance(res, list)

    asyncio.run(_run())
