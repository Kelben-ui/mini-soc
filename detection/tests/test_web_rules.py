"""Rule-contract tests for the web rules.

These exist because two rules silently stopped matching the traffic the lab
actually produces:

- ``WEB-CMD-001`` required the shell metacharacter *and* a space
  (``"; id"``), while ``attack-sim/sqli-xss.sh`` sends ``;whoami``.
- ``WEB-BF-001`` pinned ``details.uri: /login``, but that is the dashboard's
  client-side SPA route (it never reaches nginx).  DVWA's login is
  ``/dvwa/login.php`` and its brute-force exercise posts to
  ``/dvwa/vulnerabilities/brute/``.

The events below mirror what ``collector/parsers/nginx_access_parser.py``
stores for those requests (decoded ``uri``/``query``/``body`` fields).
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from detection.engine.evaluator import get_threshold_events, matches_rule
from detection.engine.rule_loader import load_rules

REPO_RULES_DIR = Path(__file__).resolve().parents[2] / "rules"


@pytest.fixture(scope="module")
def rules():
    return {rule["id"]: rule for rule in load_rules(rules_dir=str(REPO_RULES_DIR))}


def make_event(
    *,
    log_type="nginx_access",
    category="web",
    action="http_request",
    method="GET",
    uri="/",
    query=None,
    body=None,
    user_agent="curl/8.5.0",
    src_ip="198.51.100.7",
    timestamp=None,
):
    details = {"method": method, "uri": uri, "user_agent": user_agent}
    if query is not None:
        details["query"] = query
    if body is not None:
        details["body"] = body

    return {
        "log_type": log_type,
        "category": category,
        "action": action,
        "src_ip": src_ip,
        "details": details,
        "raw": f"{method} {uri} HTTP/1.1",
        "timestamp": timestamp or datetime.now(timezone.utc),
    }


# --- WEB-CMD-001 -----------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        "ip=127.0.0.1;whoami",       # attack-sim/sqli-xss.sh form (no space)
        "ip=127.0.0.1; whoami",      # spaced form (original rule contract)
        "ip=127.0.0.1|id",           # pipe, no space
        "ip=127.0.0.1&&cat /etc/passwd",
    ],
)
def test_command_injection_matches_common_payloads(rules, payload):
    event = make_event(uri="/dvwa/vulnerabilities/exec/", query=payload)

    assert matches_rule(event, rules["WEB-CMD-001"]), payload


def test_command_injection_ignores_benign_request(rules):
    event = make_event(uri="/dvwa/login.php", method="POST", body="username=a&password=b")

    assert not matches_rule(event, rules["WEB-CMD-001"])


# --- WEB-BF-001 ------------------------------------------------------------


def _brute_force_events(n, uri="/dvwa/login.php"):
    now = datetime.now(timezone.utc)
    return [
        make_event(
            method="POST",
            uri=uri,
            body=f"username=admin&password=wrong{i}&Login=Login",
            timestamp=now - timedelta(seconds=i),
        )
        for i in range(n)
    ]


@pytest.mark.parametrize(
    "uri",
    [
        "/dvwa/login.php",
        "/dvwa/vulnerabilities/brute/",
    ],
)
def test_web_bruteforce_fires_on_dvwa_paths(rules, uri):
    events = _brute_force_events(20, uri=uri)

    matched = get_threshold_events(events, rules["WEB-BF-001"])

    assert len(matched) >= 20


def test_web_bruteforce_requires_the_threshold(rules):
    events = _brute_force_events(19)

    assert get_threshold_events(events, rules["WEB-BF-001"]) == []


# --- sanity: the other web rules still match attack-sim traffic -------------


@pytest.mark.parametrize(
    ("rule_id", "event"),
    [
        ("WEB-SQLI-001", make_event(uri="/dvwa/vulnerabilities/sqli/", query="id=1' OR 1=1-- -&Submit=Submit")),
        ("WEB-XSS-001", make_event(uri="/dvwa/vulnerabilities/xss_r/", query="name=<script>alert(1)</script>")),
        ("WEB-LFI-001", make_event(uri="/dvwa/vulnerabilities/fi/", query="page=../../../../etc/passwd")),
        ("WEB-SCAN-001", make_event(uri="/dvwa/", user_agent="sqlmap/1.8#stable (http://sqlmap.org)")),
    ],
)
def test_other_web_rules_match_attack_sim_traffic(rules, rule_id, event):
    assert matches_rule(event, rules[rule_id])


def test_every_enabled_rule_has_id_name_and_mitre(rules):
    assert rules, "expected rules to load"

    for rule_id, rule in rules.items():
        assert rule.get("name"), rule_id
        assert rule.get("mitre"), rule_id
