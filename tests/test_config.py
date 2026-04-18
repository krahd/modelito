from modelito import config


def test_parse_host_port():
    h, p = config.parse_host_port("http://127.0.0.1:11434")
    assert h == "127.0.0.1"
    assert p == 11434

    h2, p2 = config.parse_host_port("127.0.0.1:9000")
    assert h2 == "127.0.0.1"
    assert p2 == 9000

    h3, p3 = config.parse_host_port("localhost")
    assert h3 == "localhost"
    assert isinstance(p3, int)
