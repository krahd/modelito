from modelito.cache import ResponseCache

def test_cache_set_get():
    cache = ResponseCache(max_size=2)
    key1 = ("prompt1",)
    key2 = ("prompt2",)
    cache.set(key1, "result1")
    assert cache.get(key1) == "result1"
    cache.set(key2, "result2")
    assert cache.get(key2) == "result2"

def test_cache_eviction():
    cache = ResponseCache(max_size=2)
    cache.set(("a",), 1)
    cache.set(("b",), 2)
    cache.set(("c",), 3)
    # Oldest should be evicted
    assert cache.get(("a",)) is None
    assert cache.get(("b",)) == 2 or cache.get(("c",)) == 3

def test_cache_clear():
    cache = ResponseCache()
    cache.set(("x",), 42)
    cache.clear()
    assert cache.get(("x",)) is None
