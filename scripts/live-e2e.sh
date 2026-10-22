#!/usr/bin/env bash
# Mini SOC live end-to-end test launcher.
#
# Brings up the whole demo path on this host:
#
#   DVWA (nginx + PHP-FPM + MariaDB)
#     -> nginx access log (the `soc` log format)
#     -> soc-agent (tails the logs, batches them to the collector)
#     -> soc-collector (normalises the lines into events)
#     -> PostgreSQL (soc-detection evaluates the events against rules/)
#     -> soc-backend (API) -> nginx -> the dashboard in the browser
#
# It starts every component, verifies each one, and (with --attack) fires the
# lab attack payloads so the alerts and events appear in the dashboard while
# you watch them.
#
# Usage:
#   sudo bash scripts/live-e2e.sh [--attack] [--skip-build] [--status]
#                                   [--wait SECONDS]
#
#   --attack         After the stack is up, fire the attack payloads
#                    (SQLi, XSS, command injection, LFI, web brute force,
#                    scanner User-Agent, a bounded port scan, an SSH brute
#                    force, a DNS-tunnel lookup and an outbound connection),
#                    wait for detection and print the new alerts.
#   --skip-build     Do not rebuild the frontend (dist/) before the test.
#   --status         Report component status only; change nothing.
#   --wait SECONDS   How long to wait for the alerts to appear (default 45).
#
# Overridable environment variables:
#   SOC_USER / SOC_PASS    dashboard credentials (default user: admin)
#   SOC_HOST / SOC_PORT    dashboard host and port (default 127.0.0.1 / 443)
#   DVWA_HOST / DVWA_PORT  DVWA host and port (default 127.0.0.1 / 80)
#   SSH_USER / SSH_PASS    throwaway SSH account for the SSH rules
#                           (default svcuser / Sunshine123)
#
# The dashboard password is *not* baked into this script: put it in
# scripts/live-e2e.env (git-ignored, see .gitignore) or export SOC_PASS.
#
# Idempotent: safe to re-run.  Starts what is stopped, leaves healthy
# services alone, and never restarts or deletes data.
set -uo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"
export APP_DIR

# Every run gets its own log directory: a shared path in /tmp cannot be
# reused safely, because the shell that truncates an existing file may not be
# allowed to (the sandbox drops the capabilities that would let root write to
# a file owned by another user).
LOG_DIR="$(mktemp -d "${TMPDIR:-/tmp}/mini-soc-live-e2e.XXXXXX")"

# Keep the logs when something failed or warned - they are the only way to
# see what the failing step printed.  A clean run leaves nothing behind.
cleanup() {
    if [ "${FAIL:-0}" -gt 0 ] || [ "${WARN:-0}" -gt 0 ]; then
        echo "Logs kept in $LOG_DIR"
    else
        rm -rf "$LOG_DIR"
    fi
}

trap cleanup EXIT

# --- configuration ----------------------------------------------------------
# Optional local credentials file (git-ignored): SOC_PASS, SOC_USER, SSH_PASS.
if [ -f "$APP_DIR/scripts/live-e2e.env" ]; then
    set -a
    # shellcheck disable=SC1091
    . "$APP_DIR/scripts/live-e2e.env"
    set +a
fi

PY="$APP_DIR/.venv/bin/python"
SOC_USER="${SOC_USER:-admin}"
SOC_PASS="${SOC_PASS:-}"
SOC_HOST="${SOC_HOST:-127.0.0.1}"
SOC_PORT="${SOC_PORT:-443}"
DVWA_HOST="${DVWA_HOST:-127.0.0.1}"
DVWA_PORT="${DVWA_PORT:-80}"
SSH_USER="${SSH_USER:-svcuser}"
SSH_PASS="${SSH_PASS:-Sunshine123}"

# The attacker namespace created by docs/testing/wsl-local/setup-attacker.sh.
ATK_NS="${ATK_NS:-atk}"
ATK_HOST_IP="${ATK_HOST_IP:-10.99.0.1}"
ATK_IP="${ATK_IP:-10.99.0.2}"

# The web attack scripts refuse to run unless the target matches
# ALLOWED_TARGET in attack-sim/target.conf, so read it from there.
ATTACK_TARGET="$(sed -n 's/^ALLOWED_TARGET="\(.*\)"/\1/p' "$APP_DIR/attack-sim/target.conf" 2>/dev/null | head -1)"
[ -z "$ATTACK_TARGET" ] && ATTACK_TARGET="$DVWA_HOST"

API_BASE="https://$SOC_HOST:$SOC_PORT"
TOKEN=""

# How often the detection loop polls (from .env) - used in the closing notes.
DETECTION_INTERVAL_SECONDS="$(sed -n 's/^DETECTION_INTERVAL_SECONDS=//p' "$APP_DIR/.env" 2>/dev/null | head -1)"
DETECTION_INTERVAL_SECONDS="${DETECTION_INTERVAL_SECONDS:-5}"

# --- flags ------------------------------------------------------------------
ATTACK=0
SKIP_BUILD=0
STATUS_ONLY=0
WAIT_SECS=45

while [ $# -gt 0 ]; do
    case "$1" in
        --attack)     ATTACK=1; shift ;;
        --skip-build) SKIP_BUILD=1; shift ;;
        --status)     STATUS_ONLY=1; shift ;;
        --wait)       WAIT_SECS="${2:-45}"; shift; [ $# -gt 0 ] && shift ;;
        --wait=*)     WAIT_SECS="${1#*=}"; shift ;;
        -h|--help)    sed -n '2,36p' "$0"; exit 0 ;;
        *) echo "Unknown flag: $1 (try --help)" >&2; exit 2 ;;
    esac
done

# --- output helpers ---------------------------------------------------------
if [ -t 1 ]; then
    RED=$'\033[31m'; GRN=$'\033[32m'; YLW=$'\033[33m'; BLD=$'\033[1m'; RST=$'\033[0m'
else
    RED=""; GRN=""; YLW=""; BLD=""; RST=""
fi
PASS=0; FAIL=0; WARN=0
ok()   { echo "  ${GRN}[OK]${RST}   $1"; PASS=$((PASS + 1)); }
bad()  { echo "  ${RED}[FAIL]${RST} $1"; FAIL=$((FAIL + 1)); }
warn() { echo "  ${YLW}[WARN]${RST} $1"; WARN=$((WARN + 1)); }
head_(){ echo; echo "${BLD}=== $1 ===${RST}"; }
note() { echo "         $1"; }

# --- small utilities --------------------------------------------------------
service_active() { systemctl is-active --quiet "$1" 2>/dev/null; }

# wait_http <url> <timeout-seconds> [extra curl args...]
wait_http() {
    local url="$1" timeout="$2"; shift 2
    local deadline=$((SECONDS + timeout))
    while [ "$SECONDS" -lt "$deadline" ]; do
        if curl -sf -m 2 "$@" "$url" >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done
    return 1
}

port_open() { (exec 3<>"/dev/tcp/$1/$2") 2>/dev/null; }

# ensure_service <unit> [label] - start a unit only when it is not running.
ensure_service() {
    local unit="$1" label="${2:-$1}"
    if service_active "$unit"; then
        ok "$label already active"
        return 0
    fi
    if [ "$STATUS_ONLY" -eq 1 ]; then
        bad "$label not active"
        return 1
    fi
    if systemctl start "$unit" >/dev/null 2>&1 && service_active "$unit"; then
        ok "$label started"
        return 0
    fi
    bad "$label failed to start - journalctl -u $unit -n 20"
    return 1
}

# api_get <path> - authenticated API call (dashboard is self-signed).
api_get() {
    curl -sk -m 10 "$API_BASE$1" -H "Authorization: Bearer $TOKEN"
}

api_login() {
    local resp
    resp=$(curl -sk -m 10 -X POST "$API_BASE/api/auth/login" \
        -H 'Content-Type: application/json' \
        -d "{\"username\":\"$SOC_USER\",\"password\":\"$SOC_PASS\"}" 2>/dev/null)
    TOKEN=$(printf '%s' "$resp" | "$PY" -c '
import sys, json
try:
    print(json.load(sys.stdin).get("access_token", ""))
except Exception:
    print("")' 2>/dev/null)
    [ -n "$TOKEN" ]
}

# ============================================================================
# 1. Preflight
# ============================================================================
head_ "Preflight"

if [ "$(id -u)" -ne 0 ]; then
    echo "This script must run as root:" >&2
    echo "  sudo bash $0" >&2
    exit 1
fi
ok "running as root"

if [ ! -f "$APP_DIR/.env" ]; then
    bad ".env missing - copy .env.example to .env and fill in the secrets"
    exit 1
fi
ok ".env present"

if [ ! -x "$PY" ]; then
    bad ".venv missing or broken - the installer (deploy/install.sh) creates it"
    exit 1
fi
ok ".venv present"

for cmd in curl; do
    if command -v "$cmd" >/dev/null 2>&1; then
        ok "$cmd available"
    else
        bad "$cmd missing - install it and re-run"
    fi
done

if [ "$STATUS_ONLY" -eq 0 ] && ! nginx -t 2>/dev/null; then
    bad "nginx config test failed - fix it before starting nginx"
    nginx -t 2>&1 | sed 's/^/    /' >&2
    exit 1
fi
[ "$STATUS_ONLY" -eq 0 ] && ok "nginx -t"

# ============================================================================
# 2. Core OS services
# ============================================================================
head_ "Core services"

# PHP-FPM: the unit name follows the PHP version (php8.4-fpm here), so take
# it from the socket the DVWA site points at, then fall back to systemd.
PHP_FPM_UNIT=""
for sock in /run/php/php*-fpm.sock; do
    [ -e "$sock" ] || continue
    PHP_FPM_UNIT="$(basename "$sock" .sock)"
    break
done
if [ -z "$PHP_FPM_UNIT" ]; then
    PHP_FPM_UNIT=$(systemctl list-units --type=service --all 'php*-fpm.service' \
        --no-legend --no-pager 2>/dev/null | awk '{print $1}' | head -1)
fi

ensure_service postgresql "postgresql (SOC database)"
ensure_service mariadb "mariadb (DVWA database)"
if [ -n "$PHP_FPM_UNIT" ]; then
    ensure_service "$PHP_FPM_UNIT" "$PHP_FPM_UNIT (DVWA)"
else
    warn "no php*-fpm unit found - DVWA will not answer"
fi
ensure_service ssh "ssh (SSH-BF-001 / SSH-SUCCESS-001)"
ensure_service rsyslog "rsyslog (auth.log for the SSH rules)"

# nginx is handled below together with its site configuration.
ensure_service nginx "nginx"

# nftables: the IDS reads the SOC_DROP / SOC_OUT lines the firewall logs.
if nft list ruleset 2>/dev/null | grep -q 'SOC_DROP'; then
    ok "firewall ruleset loaded with SOC_DROP logging"
elif [ "$STATUS_ONLY" -eq 1 ]; then
    bad "no SOC_DROP in the ruleset - the NET-* rules will not fire"
elif [ -f /etc/nftables.conf ]; then
    if nft -f /etc/nftables.conf 2>/dev/null && nft list ruleset 2>/dev/null | grep -q 'SOC_DROP'; then
        ok "firewall ruleset applied from /etc/nftables.conf"
    else
        bad "could not apply /etc/nftables.conf - NET-PORTSCAN-001 and NET-OUTBOUND-001 will not fire"
    fi
else
    bad "/etc/nftables.conf missing - the NET-* rules will not fire"
fi

# ============================================================================
# 3. nginx sites (DVWA on :80, dashboard on :443)
# ============================================================================
head_ "nginx sites"

NGINX_CHANGED=0
for site in dvwa mini-soc; do
    avail="/etc/nginx/sites-available/$site.conf"
    enabled="/etc/nginx/sites-enabled/$site.conf"

    if [ ! -f "$avail" ]; then
        if [ "$site" = "dvwa" ]; then
            warn "$avail missing - DVWA will not be served"
        else
            bad "$avail missing - the dashboard will not be served"
        fi
        continue
    fi

    if [ ! -e "$enabled" ]; then
        if [ "$STATUS_ONLY" -eq 1 ]; then
            bad "$site.conf not enabled"
        else
            ln -s "$avail" "$enabled" 2>/dev/null && {
                ok "$site.conf enabled"
                NGINX_CHANGED=1
            } || bad "could not enable $site.conf"
        fi
    else
        ok "$site.conf enabled"
    fi
done

if [ -d /var/www/dvwa ]; then
    ok "DVWA files present (/var/www/dvwa)"
else
    warn "/var/www/dvwa missing - install DVWA there or the web rules cannot fire"
fi

if [ "$STATUS_ONLY" -eq 0 ] && [ "$NGINX_CHANGED" -eq 1 ]; then
    if nginx -t >/dev/null 2>&1; then
        systemctl reload nginx >/dev/null 2>&1 && ok "nginx reloaded" || bad "nginx reload failed"
    else
        bad "nginx config test failed after enabling a site"
    fi
fi

# ============================================================================
# 4. SOC services
# ============================================================================
head_ "SOC services"

SOC_SERVICES=(soc-collector soc-backend soc-detection soc-agent mini-soc-ids)
for svc in "${SOC_SERVICES[@]}"; do
    ensure_service "$svc" "$svc"
done

head_ "Service health"

if wait_http "http://127.0.0.1:8000/health" 20; then
    ok "backend :8000 /health"
else
    bad "backend :8000 never became healthy - journalctl -u soc-backend -n 40"
fi

if port_open 127.0.0.1 9000; then
    ok "collector :9000 accepting connections"
else
    bad "collector :9000 not reachable - journalctl -u soc-collector -n 40"
fi

# DVWA: the login page proves PHP is alive; the user_token field proves the
# session/CSRF code ran, and the absence of a database error proves MariaDB
# is reachable.
DVWA_PAGE="$(curl -s -m 5 "http://$DVWA_HOST:$DVWA_PORT/dvwa/login.php" 2>/dev/null)"
if printf '%s' "$DVWA_PAGE" | grep -q "user_token"; then
    ok "DVWA login page served (PHP + session working)"
else
    bad "DVWA login page did not render - check php-fpm and /var/www/dvwa"
fi
if printf '%s' "$DVWA_PAGE" | grep -qiE 'unable to connect|database error|SQLSTATE'; then
    bad "DVWA cannot reach its database - check the mariadb service and config/config.inc.php"
fi

DASH_CODE="$(curl -sk -o /dev/null -m 5 -w '%{http_code}' "https://$SOC_HOST:$SOC_PORT/" 2>/dev/null)"
if [ "$DASH_CODE" = "200" ]; then
    ok "dashboard served on https://$SOC_HOST:$SOC_PORT/ (TLS self-signed)"
else
    bad "dashboard returned HTTP $DASH_CODE - check nginx and frontend/dist"
fi

# The agent must be shipping lines: a heartbeat in the last two minutes
# proves the agent loop is alive and the collector is reachable.
HB_INFO="$("$PY" - <<'PY' 2>/dev/null
import os, sys
sys.path.insert(0, os.path.join(os.environ.get("APP_DIR", "."), "backend"))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.environ.get("APP_DIR", "."), ".env"))
    from app.database import SessionLocal
    from app.models.agent import Agent
    from sqlalchemy import select
    db = SessionLocal()
    agent = db.execute(select(Agent)).scalars().first()
    if agent is None:
        print("no-agent")
    else:
        hb = agent.last_heartbeat
        print(f"{agent.status}|{hb.isoformat() if hb else 'never'}")
except Exception as exc:
    print(f"error|{exc}")
PY
)"
HB_STATUS="${HB_INFO%%|*}"
HB_TIME="${HB_INFO#*|}"
if [ "$HB_STATUS" = "online" ]; then
    ok "log agent online (last heartbeat $HB_TIME)"
else
    warn "log agent not reporting (status='$HB_STATUS', last heartbeat $HB_TIME)"
fi

# ============================================================================
# 5. Frontend build
# ============================================================================
if [ "$SKIP_BUILD" -eq 0 ] && [ "$STATUS_ONLY" -eq 0 ]; then
    head_ "Frontend build"
    if command -v npm >/dev/null 2>&1; then
        if [ ! -d "$APP_DIR/frontend/node_modules" ]; then
            warn "frontend/node_modules missing - run 'npm ci' in frontend/ (serving the existing dist/)"
        elif (cd "$APP_DIR/frontend" && npm run build >"$LOG_DIR/build.log" 2>&1); then
            ok "frontend built (playbooks synced into dist/)"
        else
            bad "npm run build failed - see $LOG_DIR/build.log"
        fi
    else
        warn "npm not found - skipping the frontend rebuild (serving the existing dist/)"
    fi
fi

# ============================================================================
# 6. Attacker namespace (network rules need a non-loopback source)
# ============================================================================
head_ "Attacker namespace"

ATK_READY=0
if [ "$STATUS_ONLY" -eq 1 ]; then
    if ip netns list 2>/dev/null | grep -qw "$ATK_NS"; then
        ok "netns '$ATK_NS' exists"
        ATK_READY=1
    else
        warn "netns '$ATK_NS' missing - the NET-* rules need it"
    fi
elif [ -f "$APP_DIR/docs/testing/wsl-local/setup-attacker.sh" ]; then
    if bash "$APP_DIR/docs/testing/wsl-local/setup-attacker.sh" >"$LOG_DIR/atk.log" 2>&1; then
        ok "netns '$ATK_NS' ready (source IP $ATK_IP, host $ATK_HOST_IP)"
        ATK_READY=1
    else
        warn "setup-attacker.sh failed - see $LOG_DIR/atk.log (NET-* rules will not fire)"
    fi
else
    warn "docs/testing/wsl-local/setup-attacker.sh missing - the NET-* rules will not fire"
fi

# ============================================================================
# 7. Dashboard credentials
# ============================================================================
head_ "Dashboard login"

if [ -z "$SOC_PASS" ]; then
    bad "no dashboard password configured - create $APP_DIR/scripts/live-e2e.env (SOC_PASS=...) or export SOC_PASS"
elif api_login; then
    ok "logged in to the API as '$SOC_USER'"
else
    bad "login failed for '$SOC_USER' - set SOC_USER / SOC_PASS and re-run"
    note "the browser needs the same credentials: https://$SOC_HOST:$SOC_PORT/login"
fi

# ============================================================================
# 8. Attack phase
# ============================================================================
if [ "$ATTACK" -eq 1 ] && [ "$STATUS_ONLY" -eq 0 ]; then
    head_ "Attack payloads"

    BEFORE_FILE="$LOG_DIR/alerts-before.json"
    AFTER_FILE="$LOG_DIR/alerts-after.json"
    api_get "/api/alerts?limit=200" > "$BEFORE_FILE"

    # -- web rules: SQLi, XSS, command injection, LFI, web login brute force
    if [ -f "$APP_DIR/attack-sim/sqli-xss.sh" ]; then
        if bash "$APP_DIR/attack-sim/sqli-xss.sh" "$ATTACK_TARGET" all >"$LOG_DIR/sqli.log" 2>&1; then
            ok "web payloads sent (SQLi, XSS, command injection, LFI, web brute force)"
        else
            bad "sqli-xss.sh failed - see $LOG_DIR/sqli.log"
        fi
    else
        bad "attack-sim/sqli-xss.sh missing"
    fi

    # -- scanner User-Agent -> WEB-SCAN-001
    if [ -f "$APP_DIR/attack-sim/scanner-ua.sh" ]; then
        if bash "$APP_DIR/attack-sim/scanner-ua.sh" "$ATTACK_TARGET" >"$LOG_DIR/ua.log" 2>&1; then
            ok "scanner User-Agent requests sent (WEB-SCAN-001)"
        else
            bad "scanner-ua.sh failed - see $LOG_DIR/ua.log"
        fi
    fi

    # -- bounded port scan from the namespace -> NET-PORTSCAN-001 + SOC_DROP
    if [ "$ATK_READY" -eq 1 ] && command -v nmap >/dev/null 2>&1; then
        if ip netns exec "$ATK_NS" nmap -Pn -sS -p 1000-1023 -T4 --max-retries 1 \
            "$ATK_HOST_IP" -oG "$LOG_DIR/nmap.gnmap" >/dev/null 2>&1; then
            ok "port scan from $ATK_IP (24 ports - above the 20-port threshold)"
        else
            warn "nmap from the namespace failed - the NET-PORTSCAN-001 rule will not fire"
        fi
    else
        warn "port scan skipped (namespace or nmap unavailable)"
    fi

    # -- SSH brute force -> SSH-BF-001
    HYDRA_LOG="$LOG_DIR/hydra.log"
    if [ "$ATK_READY" -eq 1 ] && command -v hydra >/dev/null 2>&1 \
        && [ -f "$APP_DIR/attack-sim/passlist.txt" ]; then
        # hydra exits 0 even when it finds no valid pair; the rejected logins
        # are what raises SSH-BF-001, so the summary line is what counts.
        ip netns exec "$ATK_NS" hydra -l "$SSH_USER" -P "$APP_DIR/attack-sim/passlist.txt" \
            -t 4 -f "$ATK_HOST_IP" ssh >"$HYDRA_LOG" 2>&1
        TRIES="$(grep -oE '[0-9]+ login tries' "$HYDRA_LOG" 2>/dev/null | grep -oE '[0-9]+' | head -1)"
        if grep -qE '0 valid password' "$HYDRA_LOG" 2>/dev/null; then
            ok "SSH brute force from $ATK_IP (SSH-BF-001) - ${TRIES:-?} passwords tried, all rejected"
        elif grep -qE '[0-9]+ valid password' "$HYDRA_LOG" 2>/dev/null; then
            warn "hydra found a valid password for '$SSH_USER' - check the throwaway account"
        else
            warn "hydra did not run - see $HYDRA_LOG"
        fi
    else
        warn "SSH brute force skipped (namespace, hydra or passlist unavailable)"
    fi

    # -- one successful SSH login -> SSH-SUCCESS-001
    if [ "$ATK_READY" -eq 1 ] && command -v sshpass >/dev/null 2>&1; then
        # sshd penalises the source address after failed logins
        # (PerSourcePenalties, authfail:+5s each), so the connection right
        # after the brute force is dropped.  Retry until the penalty decays.
        SSH_OK=0
        for _ in $(seq 1 12); do
            if ip netns exec "$ATK_NS" sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no \
                -o UserKnownHostsFile=/dev/null -o ConnectTimeout=5 -o NumberOfPasswordPrompts=1 \
                "$SSH_USER@$ATK_HOST_IP" 'echo ssh-ok' >"$LOG_DIR/ssh.log" 2>&1; then
                SSH_OK=1
                break
            fi
            sleep 10
        done
        if [ "$SSH_OK" -eq 1 ]; then
            ok "successful SSH login from $ATK_IP (SSH-SUCCESS-001)"
        else
            warn "SSH success step failed - wrong password for '$SSH_USER'? (see $LOG_DIR/ssh.log)"
        fi
    fi

    # -- host-side rules: DNS tunnel and unusual outbound.  Both are read by
    #    the IDS: the DNS one needs the raw-socket sniffer, the outbound one
    #    needs the firewall's SOC_OUT log line (and can be swallowed by the
    #    IDS cooldown when another outbound event fired just before).
    if [ -f "$APP_DIR/attack-sim/dns-tunnel-sim.sh" ]; then
        if bash "$APP_DIR/attack-sim/dns-tunnel-sim.sh" 6 >"$LOG_DIR/dns.log" 2>&1; then
            ok "DNS-tunnel lookups sent (expects DNS-ANOMALY-001)"
        else
            bad "dns-tunnel-sim.sh failed - see $LOG_DIR/dns.log"
        fi
    fi
    if [ -f "$APP_DIR/attack-sim/outbound-conn.sh" ]; then
        if bash "$APP_DIR/attack-sim/outbound-conn.sh" 8.8.8.8 4444 >"$LOG_DIR/outbound.log" 2>&1; then
            ok "outbound connection to 8.8.8.8:4444 sent (expects NET-OUTBOUND-001)"
        else
            bad "outbound-conn.sh failed - see $LOG_DIR/outbound.log"
        fi
    fi

    head_ "Waiting for detection (${WAIT_SECS}s)"

    DEADLINE=$((SECONDS + WAIT_SECS))
    LAST_SIG=""
    while [ "$SECONDS" -lt "$DEADLINE" ]; do
        SIG="$(api_get "/api/alerts?limit=200" | "$PY" -c '
import sys, json
try:
    items = json.load(sys.stdin).get("items", [])
except Exception:
    items = []
print("|".join("{}:{}".format(a["alert_id"], a.get("count")) for a in items))' 2>/dev/null)"
        if [ -n "$SIG" ] && [ "$SIG" != "$LAST_SIG" ]; then
            LAST_SIG="$SIG"
            echo "  ... alerts changing"
        fi
        sleep 3
    done

    api_get "/api/alerts?limit=200" > "$AFTER_FILE"

    head_ "New alerts"
    "$PY" - "$BEFORE_FILE" "$AFTER_FILE" <<'PY'
import json
import sys

def rows(path):
    with open(path) as handle:
        data = json.load(handle)
    items = data.get("items", data) if isinstance(data, dict) else data
    return {a["alert_id"]: a for a in items}

before = rows(sys.argv[1])
after = rows(sys.argv[2])

new = [a for aid, a in after.items() if aid not in before]
grown = [a for aid, a in after.items()
         if aid in before and a.get("count") != before[aid].get("count")]

if not new and not grown:
    print("  no new or updated alerts - check that the payloads really hit")
    print("  (journalctl -u soc-detection -f, journalctl -u soc-collector -f)")
    raise SystemExit

for alert in sorted(new, key=lambda a: a["alert_id"]):
    print(f"  #{alert['alert_id']:<4} {alert['rule_id']:<22} "
          f"sev={alert.get('severity'):<8} src={str(alert.get('src_ip')):<16} "
          f"count={alert.get('count')}  {alert.get('title')}")

if grown:
    print("  updated:")
    for alert in sorted(grown, key=lambda a: a["alert_id"]):
        print(f"  #{alert['alert_id']:<4} {alert['rule_id']:<22} "
              f"count {before[alert['alert_id']].get('count')} -> {alert.get('count')}")
PY

    head_ "Newest events"
    api_get "/api/events?limit=200" | "$PY" -c '
import sys, json
try:
    items = json.load(sys.stdin).get("items", [])
except Exception:
    items = []


def describe(event):
    details = event.get("details") or {}
    what = (details.get("uri") or details.get("query") or details.get("message")
            or details.get("signature") or "")
    if not what and details.get("dst"):
        what = "{}:{} -> {}:{}".format(details.get("src"), details.get("spt"),
                                       details.get("dst"), details.get("dpt"))
    return str(what)[:60]


# The dashboard polls the API every few seconds; that traffic is not
# interesting for the demo, so skip it.
interesting = [e for e in items
               if not str((e.get("details") or {}).get("uri", "")).startswith("/api/")]

for log_type in ("nginx_access", "auth", "firewall", "mini_soc_ids"):
    rows = [e for e in interesting if e.get("log_type") == log_type][:3]
    if not rows:
        continue
    print("  -- " + log_type)
    for event in rows:
        print("     {:<20} {:<16} {}".format(
            str(event.get("timestamp"))[:19], str(event.get("src_ip")),
            describe(event)))

if not interesting:
    print("  (no events yet - run the attacks again)")' 2>/dev/null
fi

# ============================================================================
# 9. Summary
# ============================================================================
head_ "Summary"
echo "  ${GRN}passed${RST}: $PASS   ${RED}failed${RST}: $FAIL   ${YLW}warnings${RST}: $WARN"
echo

if [ "$FAIL" -gt 0 ]; then
    echo "${RED}Some components failed. Fix them before running the live test.${RST}"
    echo
fi

echo "${BLD}Open these in your browser:${RST}"
echo "  DVWA       :  http://$DVWA_HOST:$DVWA_PORT/dvwa/login.php   (admin / password)"
if [ -n "$SOC_PASS" ]; then
    echo "  Dashboard  :  https://$SOC_HOST:$SOC_PORT/                    ($SOC_USER / $SOC_PASS)"
else
    echo "  Dashboard  :  https://$SOC_HOST:$SOC_PORT/                    ($SOC_USER / see scripts/live-e2e.env)"
fi
echo "  Alerts     :  https://$SOC_HOST:$SOC_PORT/alerts"
echo "  Events     :  https://$SOC_HOST:$SOC_PORT/events"
echo "  Rule book  :  https://$SOC_HOST:$SOC_PORT/rules"
echo
echo "${BLD}Rules the --attack phase targets:${RST}"
echo "  WEB-SQLI-001  WEB-XSS-001  WEB-CMD-001  WEB-LFI-001  WEB-BF-001  WEB-SCAN-001"
echo "  NET-PORTSCAN-001 + SSH-BF-001   (from the $ATK_IP namespace)"
echo "  NET-OUTBOUND-001 + DNS-ANOMALY-001   (host-side, best effort)"
echo
echo "${BLD}Fire more alerts by hand:${RST}"
echo "  cd $APP_DIR && bash attack-sim/sqli-xss.sh $ATTACK_TARGET all   # SQLi XSS CMDi LFI web-BF"
echo "  cd $APP_DIR && bash attack-sim/scanner-ua.sh $ATTACK_TARGET      # WEB-SCAN-001"
echo "  ip netns exec $ATK_NS nmap -Pn -sS -p 1000-1023 -T4 $ATK_HOST_IP # NET-PORTSCAN-001"
echo "  cd $APP_DIR && bash attack-sim/dns-tunnel-sim.sh 6               # DNS-ANOMALY-001"
echo "  cd $APP_DIR && bash attack-sim/outbound-conn.sh 8.8.8.8 4444     # NET-OUTBOUND-001"
echo
echo "${BLD}Watch the pipeline live:${RST}"
echo "  journalctl -u soc-detection -f"
echo "  journalctl -u soc-collector -f"
echo "  tail -f /var/log/nginx/access.log"
echo
echo "Alerts appear within ~10s of the events landing (agent batches every 2s,"
echo "detection polls every ${DETECTION_INTERVAL_SECONDS:-5}s).  Refresh the"
echo "dashboard page to see them."

[ "$FAIL" -gt 0 ] && exit 1
exit 0
