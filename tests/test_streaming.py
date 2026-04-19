from modelito.streaming import collect_stream


class DummyStreamingProvider:
    def stream(self, messages, settings=None):
        # simulate chunked output
        yield "Hello"
        yield " "
        yield "world"


def test_collect_stream_from_provider():
    prov = DummyStreamingProvider()
    chunks = prov.stream([])
    text = collect_stream(chunks)
    assert text == "Hello world"
