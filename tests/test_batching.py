from modelito.batching import batch_iterable

def test_batch_iterable():
    items = list(range(10))
    batches = list(batch_iterable(items, 3))
    assert batches == [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]
    assert all(isinstance(b, list) for b in batches)
    assert sum(len(b) for b in batches) == 10
