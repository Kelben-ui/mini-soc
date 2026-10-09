from collector.parsers.nginx_error_parser import parse

def test_nginx_error_parser():
    result = parse("404 error")

    assert result["log_type"] == "nginx_error"
