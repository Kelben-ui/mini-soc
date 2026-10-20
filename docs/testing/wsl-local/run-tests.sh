#!/bin/bash
# Local (WSL2) lab smoke tests: firewall, nginx, DVWA detection.
#
# Run after deploy/install.sh has provisioned the stack and
# setup-attacker.sh has created the attacker namespace.
#
# This is deliberately bounded and non-destructive: the port scan uses a small
# range (not -p-) so it does not flood the pipeline or trip the SYN-flood
# signature, and nothing here deletes data.
#
# Usage: sudo bash run-tests.sh [firewall|nginx|web|all]
set -uo pipefail

APP_DIR="${APP_DIR:-/root/mini-soc}"
NS="${NS:-atk}"
HOST_IP="${HOST_IP:-10.99.0.1}"
ATTACKER_IP="${ATTACKER_IP:-10.99.0.2}"
DOMAIN="${DOMAIN:-localhost}"

PASS=0
FAIL=0

ok()   { echo "  [PASS] $1"; PASS=$((PASS + 1)); }
bad()  { echo "  [FAIL] $1"; FAIL=$((FAIL + 1)); }
check(){ if eval "$2" >/dev/null 2>&1; then ok "$1"; else bad "$1"; fi; }
head_(){ echo; echo "=== $1 ==="; }

# ---------------------------------------------------------------------------
# Firewall: external view must expose only 80/443, and drops must be logged.
# ---------------------------------------------------------------------------
test_firewall() {
    head_ "Firewall"

    if ! ip netns list | grep -qw "$NS"; then
        bad "attacker namespace '$NS' missing — run setup-attacker.sh first"
        return
    fi

    # Bounded scan: 24 ports, well over the 20-distinct-port threshold, without
    # the flood of a full -p- sweep.
    ip netns exec "$NS" nmap -Pn -sS -p 1000-1023 -T4 --max-retries 1 "$HOST_IP" \
        -oG /tmp/wsl-local-nmap.gnmap >/dev/null 2>&1 || true

    local open_ports
    open_ports=$(grep -oE "Ports: .*" /tmp/wsl-local-nmap.gnmap 2>/dev/null || echo "")

    # Expect every probed port filtered/closed — none of 1000-1023 is intended
    # to be open, so any "open" here is a firewall failure.
    if grep -q "open" /tmp/wsl-local-nmap.gnmap 2>/dev/null; then
        bad "unexpected open port in 1000-1023 (firewall leak)"
    else
        ok "ports 1000-1023 filtered/closed (no leak)"
    fi

    # Confirm the drop path is logging to the journal.
    local drops
    drops=$(journalctl -k --since "2 minutes ago" --no-pager 2>/dev/null | grep -c "SOC_DROP:" || true)
    if [[ "${drops:-0}" -gt 0 ]]; then
        ok "SOC_DROP log lines present (${drops} in last 2 min)"
    else
        bad "no SOC_DROP log lines — nftables logging not active?"
    fi
}

# ---------------------------------------------------------------------------
# nginx: config, listeners, TLS, headers, log format, DVWA vhost.
# ---------------------------------------------------------------------------
test_nginx() {
    head_ "nginx"

    check "nginx -t succeeds"          "nginx -t"
    check "nginx service active"       "systemctl is-active --quiet nginx"
    check "listening on :80"           "ss -tlnp | grep -q ':80 '"
    check "listening on :443"          "ss -tlnp | grep -q ':443 '"
    check "dashboard 200"              "curl -sk https://127.0.0.1/ | grep -qi '<div id=\"root\">'"
    check "backend /health ok"         "curl -s http://127.0.0.1:8000/health | grep -q '\"status\": *\"ok\"'"
    check "API rejects anonymous"      "test \"\$(curl -sk -o /dev/null -w '%{http_code}' https://127.0.0.1/api/stats)\" = 403"

    local hdr
    hdr=$(curl -skI https://127.0.0.1/ 2>/dev/null)
    for h in X-Content-Type-Options X-Frame-Options Referrer-Policy Permissions-Policy Content-Security-Policy; do
        if grep -qi "^$h:" <<<"$hdr"; then ok "security header $h present"; else bad "security header $h missing"; fi
    done

    # The `soc` log format must be exactly what the collector's parser expects.
    if grep -qE '\[iso=[0-9T:+-]+\] "[A-Z]+ ' /var/log/nginx/access.log 2>/dev/null; then
        ok "access.log uses the 'soc' iso format"
    else
        bad "access.log does not match the 'soc' format"
    fi

    check "DVWA login 200"             "test \"\$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1/dvwa/login.php)\" = 200"
    check "DVWA setup 200"             "test \"\$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1/dvwa/setup.php)\" = 200"
}

# ---------------------------------------------------------------------------
# Web detection: run attack-sim's authenticated DVWA payloads and confirm the
# detection engine raises each web rule.
# ---------------------------------------------------------------------------
test_web() {
    head_ "Web detection (DVWA -> collector -> detection)"

    local sim="$APP_DIR/attack-sim/sqli-xss.sh"
    if [[ ! -f "$sim" ]]; then
        bad "attack-sim/sqli-xss.sh not found under $APP_DIR"
        return
    fi

    # A throwaway target.conf so the script's ALLOWED_TARGET guard is satisfied.
    local tmp; tmp=$(mktemp -d)
    cat > "$tmp/target.conf" <<EOF
ALLOWED_TARGET="127.0.0.1"
DVWA_USER="admin"
DVWA_PASS="password"
DVWA_SCHEME="http"
EOF
    cp "$sim" "$tmp/sqli-xss.sh"

    echo "  running authenticated DVWA attacks (all types)..."
    if bash "$tmp/sqli-xss.sh" 127.0.0.1 all; then
        ok "attack-sim ran against DVWA (authenticated)"
    else
        bad "attack-sim failed — is DVWA initialised and reachable?"
    fi
    rm -rf "$tmp"

    # Give the agent -> collector -> detection loop time to catch up.
    echo "  waiting 15s for detection..."
    sleep 15

    local expect=(WEB-SQLI-001 WEB-XSS-001 WEB-LFI-001 WEB-CMD-001 WEB-SCAN-001 WEB-BF-001)
    local rules
    rules=$(mktemp)
    APP_DIR="$APP_DIR" ENV_FILE=/etc/mini-soc/.env "$APP_DIR/.venv/bin/python" - <<PY > "$rules" 2>/dev/null
import os, sys
sys.path.insert(0, "$APP_DIR")
os.environ.setdefault("ENV_FILE", "/etc/mini-soc/.env")
from backend.app.database import SessionLocal
from backend.app.models.alert import Alert
db = SessionLocal()
for rule_id, in db.query(Alert.rule_id).distinct():
    print(rule_id)
db.close()
PY
    for r in "${expect[@]}"; do
        if grep -qx "$r" "$rules"; then ok "alert raised: $r"; else bad "no alert for $r"; fi
    done
    rm -f "$rules"
}

case "${1:-all}" in
    firewall) test_firewall ;;
    nginx)    test_nginx ;;
    web)      test_web ;;
    all)      test_firewall; test_nginx; test_web ;;
    *) echo "Usage: bash run-tests.sh [firewall|nginx|web|all]"; exit 1 ;;
esac

echo
echo "=== summary: ${PASS} passed, ${FAIL} failed ==="
[[ "$FAIL" -eq 0 ]]
