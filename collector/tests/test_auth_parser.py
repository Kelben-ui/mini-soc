from collector.parsers.auth_parser import parse

def test_auth_parser():
    result = parse("Failed password")

    assert result["log_type"] == "auth"
