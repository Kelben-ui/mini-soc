from collector.parsers.auth_parser import parse
from collector.parsers.common import get_private_ip

FAILED = (
    "Oct 13 09:11:02 ip-172-31-13-199 sshd[2203]: Failed password for "
    "root from 203.0.113.9 port 52820 ssh2"
)

FAILED_INVALID = (
    "Oct 13 09:12:02 ip-172-31-13-199 sshd[2203]: Failed password for "
    "invalid user admin from 198.51.100.77 port 50488 ssh2"
)

INVALID = (
    "Oct 13 09:16:03 ip-172-31-13-199 sshd[2289]: Invalid user guest "
    "from 203.0.113.9 port 53777"
)

ACCEPTED = (
    "Oct 13 09:14:01 ip-172-31-13-199 sshd[2261]: Accepted publickey for "
    "ubuntu from 143.105.152.60 port 52313 ssh2: RSA SHA256:abc.."
)

SUDO = (
    "Oct 13 09:15:00 ip-172-31-13-199 sudo: pam_unix(sudo:session): "
    "session opened for user root by (uid=0)"
)

# rsyslog RSYSLOG_FileFormat (default on recent Ubuntu): ISO timestamp.
ISO_FAILED = (
    "2026-10-14T14:24:06.152339+00:00 ip-172-31-13-199 sshd[2203]: "
    "Failed password for root from 203.0.113.9 port 52820 ssh2"
)

ISO_SUDO = (
    "2026-10-14T14:24:06.152339+00:00 ip-172-31-13-199 sudo: ubuntu : "
    "TTY=/dev/pts/4 ; PWD=/home/ubuntu/mini-soc ; USER=root ; "
    "COMMAND=/usr/bin/true"
)


def test_failed_ssh_login():
    result = parse(FAILED)

    assert result is not None
    assert result["log_type"] == "auth"
    assert result["category"] == "authentication"
    assert result["action"] == "ssh_login"
    assert result["outcome"] == "failure"
    assert result["src_ip"] == "203.0.113.9"
    assert result["src_port"] == 52820
    assert result["user"] == "root"
    assert result["dst_ip"] == get_private_ip()
    assert result["dst_port"] == 22


def test_accepted_ssh_login():
    result = parse(ACCEPTED)

    assert result["action"] == "ssh_login"
    assert result["outcome"] == "success"
    assert result["user"] == "ubuntu"
    assert result["src_ip"] == "143.105.152.60"


def test_invalid_and_invalid_user_failed_variants():
    invalid_result = parse(INVALID)
    failed_invalid = parse(FAILED_INVALID)

    assert invalid_result["outcome"] == "failure"
    assert invalid_result["user"] == "guest"
    assert failed_invalid["user"] == "admin"


def test_sudo_line_is_activity():
    result = parse(SUDO)

    assert result["action"] == "sudo"
    assert result["outcome"] == "activity"


def test_malformed_lines_return_none():
    assert parse("Failed password") is None
    assert parse("") is None
    assert parse("random garbage without a timestamp") is None


def test_iso_failed_ssh_login():
    result = parse(ISO_FAILED)

    assert result is not None
    assert result["action"] == "ssh_login"
    assert result["outcome"] == "failure"
    assert result["user"] == "root"
    assert result["src_ip"] == "203.0.113.9"
    assert result["src_port"] == 52820
    assert result["dst_port"] == 22
    assert result["timestamp"] == "2026-10-14T14:24:06Z"


def test_iso_sudo_line_is_activity():
    result = parse(ISO_SUDO)

    assert result is not None
    assert result["action"] == "sudo"
    assert result["outcome"] == "activity"
    assert result["timestamp"] == "2026-10-14T14:24:06Z"


def test_repeated_message_summary_is_skipped():
    repeated = (
        "Oct 13 09:12:44 ip-172-31-13-199 sshd[2203]: message repeated "
        "2 times: [ Failed password for root from 203.0.113.9 port 52820 "
        "ssh2 ]"
    )

    assert parse(repeated) is None