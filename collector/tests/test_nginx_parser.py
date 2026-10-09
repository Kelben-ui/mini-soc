from collector.parsers.nginx_access_parser import parse

def test_parser():
    result = parse("127.0.0.1 GET /")

    assert result["log_type"] == "nginx_access"
