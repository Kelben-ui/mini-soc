#!/bin/bash
# SentinelX live end-to-end test launcher.
#
# Starts every component the DVWA -> logs -> detection -> dashboard path
# needs, verifies each one, and prints the browser URLs and attack commands
# for a live test.
#
# Idempotent: safe to re-run. Starts what is stopped, leaves running
# services alone, and never restarts or deletes data.
#
# Usage:
#   sudo bash scripts/live-test.sh [--status] [--with-attacker] [--skip-build]
#
#   --status          Report component status only; change nothing.
#   --with-attacker   Also create the netns attacker (docs/testing/wsl-local/
#                     setup-attacker.sh) so the network rules can fire from a
#                     non-loopback source. Re-run after every WSL restart.
#   --skip-build      Do not rebuild the frontend (dist/) before the test.
set -uo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

STATUS_ONLY=0
WITH_ATTACKER=0
SKIP_BUILD=0
for arg in "$@"; do
    case "$arg" in
        --status)        STATUS_ONLY=1 ;;
        --with-attacker) WITH_ATTACKER=1 ;;
        --skip-build)    SKIP_BUILD=1 ;;
        -h|--help)       sed -n '2,16p' "$0"; exit 0 ;;
        *) echo "Unknown flag: $arg (try --help)" >&2; exit 2 ;;
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

# --- preflight --------------------------------------------------------------
head_ "Preflight"

if [ "$(id -u)" -ne 0 ]; then
    echo "This script must run as root:" >&2
    echo "  sudo bash $0" >&2
    exit 1
fi

if [ ! -f "$APP_DIR/.env" ]; then
    bad ".env missing — copy .env.example to .env and fill in the secrets"
    echo "    cp $APP_DIR/.env.example $APP_DIR/.env && \$EDITOR $APP_DIR/.env" >&2
    exit 1
fi
ok ".env present"

if [ ! -d "$APP_DIR/.venv" ]; then
    bad ".venv missing — the installer (deploy/install.sh) creates it"
    exit 1
fi
ok ".venv present"

if [ "$STATUS_ONLY" -eq 0 ] && ! nginx -t 2>/dev/null; then
    bad "nginx config test failed — fix it before starting nginx"
    nginx -t 2>&1 | sed 's/^/    /' >&2
    exit 1
fi
[ "$STATUS_ONLY" -eq 0 ] && ok "nginx -t"

# --- core OS services -------------------------------------------------------
CORE_SERVICES=(postgresql mariadb nftables nginx ssh)

if [ "$STATUS_ONLY" -eq 1 ]; then
    head_ "Core OS services (status only)"
    for svc in "${CORE_SERVICES[@]}"; do
        if systemctl is-active --quiet "$svc"; then
            ok "$svc"
        else
            bad "$svc not active"
        fi
    done
else
    head_ "Core OS services"
    for svc in "${CORE_SERVICES[@]}"; do
        if systemctl is-active --quiet "$svc"; then
            ok "$svc already active"
        elif systemctl enable --now "$svc" 2>/dev/null; then
            ok "$svc started"
        else
            bad "$svc failed to start"
        fi
    done
fi

# --- dependencies before SOC services ---------------------------------------
head_ "Dependency health"

backend_up=0
for _ in $(seq 1 15); do
    if curl -sf -m 2 http://127.0.0.1:8000/health >/dev/null 2>&1; then
        backend_up=1; break
    fi
    [ "$STATUS_ONLY" -eq 0 ] && systemctl is-active --quiet soc-backend 2>/dev/null || true
    sleep 1
done
if [ "$backend_up" -eq 1 ]; then
    ok "backend :8000 /health"
else
    if [ "$STATUS_ONLY" -eq 1 ]; then
        warn "backend :8000 not answering (will start with SOC services)"
    else
        bad "backend :8000 never became healthy"
    fi
fi

collector_up=0
for _ in $(seq 1 10); do
    if (exec 3<>/dev/tcp/127.0.0.1/9000) 2>/dev/null; then
        collector_up=1; break
    fi
    sleep 1
done
if [ "$collector_up" -eq 1 ]; then
    ok "collector :9000 accepting connections"
else
    if [ "$STATUS_ONLY" -eq 1 ]; then
        warn "collector :9000 not answering (will start with SOC services)"
    else
        bad "collector :9000 never became reachable"
    fi
fi

# --- SOC services -----------------------------------------------------------
SOC_SERVICES=(soc-collector soc-backend soc-detection soc-agent mini-soc-ids)

if [ "$STATUS_ONLY" -eq 1 ]; then
    head_ "SOC services (status only)"
    for svc in "${SOC_SERVICES[@]}"; do
        if systemctl is-active --quiet "$svc"; then
            ok "$svc"
        else
            bad "$svc not active"
        fi
    done
else
    head_ "SOC services"
    for svc in "${SOC_SERVICES[@]}"; do
        if systemctl is-active --quiet "$svc"; then
            ok "$svc already active"
        elif systemctl enable --now "$svc" 2>/dev/null; then
            ok "$svc started"
        else
            bad "$svc failed to start"
        fi
    done
fi

# --- nftables telemetry -----------------------------------------------------
head_ "nftables telemetry"
if nft list ruleset 2>/dev/null | grep -q "SOC_DROP"; then
    ok "ruleset loaded with SOC_DROP logging"
else
    if [ "$STATUS_ONLY" -eq 1 ]; then
        warn "no SOC_DROP in ruleset — network rules will not fire"
    else
        warn "SOC_DROP not found; attempting to apply /etc/nftables.conf"
        if nft -f /etc/nftables.conf 2>/dev/null && nft list ruleset 2>/dev/null | grep -q "SOC_DROP"; then
            ok "nftables ruleset applied"
        else
            warn "could not apply nftables — NET-PORTSCAN-001, IDS-SIG-001 and NET-OUTBOUND-001 will be dead"
        fi
    fi
fi

# --- frontend build ---------------------------------------------------------
if [ "$SKIP_BUILD" -eq 0 ] && [ "$STATUS_ONLY" -eq 0 ]; then
    head_ "Frontend build"
    if command -v npm >/dev/null 2>&1; then
        if (cd "$APP_DIR/frontend" && npm run build >/tmp/sentinelx-build.log 2>&1); then
            ok "frontend built (playbooks synced into dist/)"
        else
            bad "npm run build failed — see /tmp/sentinelx-build.log"
        fi
    else
        warn "npm not found — skipping frontend rebuild (serving existing dist/)"
    fi
fi

# --- attacker namespace (optional) ------------------------------------------
if [ "$WITH_ATTACKER" -eq 1 ]; then
    head_ "Attacker namespace"
    if [ "$STATUS_ONLY" -eq 1 ]; then
        if ip netns list 2>/dev/null | grep -qw atk; then
            ok "netns 'atk' exists"
        else
            warn "netns 'atk' missing — run with --with-attacker to create it"
        fi
    elif bash "$APP_DIR/docs/testing/wsl-local/setup-attacker.sh"; then
        ok "netns 'atk' ready (10.99.0.2)"
    else
        bad "setup-attacker.sh failed"
    fi
fi

# --- admin user -------------------------------------------------------------
head_ "Dashboard admin user"
USERS_COUNT="$("$APP_DIR/.venv/bin/python" - <<'PY' 2>/dev/null
import sys, os
sys.path.insert(0, os.path.join(os.environ.get("APP_DIR", "."), "backend"))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.environ.get("APP_DIR", "."), ".env"))
    from app.database import SessionLocal
    from app.models.user import User
    db = SessionLocal()
    print(db.query(User).count())
except Exception:
    print("unknown")
PY
)"
if [ "$USERS_COUNT" = "0" ]; then
    warn "no users in the database — create one before logging in:"
    echo "       cd $APP_DIR/backend && $APP_DIR/.venv/bin/python create_user.py --username admin --role admin"
elif [ "$USERS_COUNT" = "unknown" ]; then
    warn "could not query users table — check DATABASE_URL in .env"
else
    ok "$USERS_COUNT user(s) exist"
fi

# --- summary ----------------------------------------------------------------
head_ "Summary"
echo "  ${GRN}passed${RST}: $PASS   ${RED}failed${RST}: $FAIL   ${YLW}warnings${RST}: $WARN"
echo

if [ "$FAIL" -gt 0 ]; then
    echo "${RED}Some components failed. Fix them before running the live test.${RST}"
    exit 1
fi

echo "${BLD}Live test — open these in your browser:${RST}"
echo "  Dashboard :  https://127.0.0.1/            (SentinelX, TLS self-signed)"
echo "  DVWA      :  http://127.0.0.1/dvwa/login.php   (admin / password)"
echo
echo "${BLD}Trigger alerts, then refresh the dashboard (Alerts / Event Search):${RST}"
echo "  Web rules (SQLi, XSS, LFI, CMD, scanner UA, web brute force):"
echo "    cd $APP_DIR && bash attack-sim/sqli-xss.sh 127.0.0.1 all"
echo "  SSH rules (SSH-BF-001, SSH-SUCCESS-001):"
echo "    bash attack-sim/ssh-brute-force.sh 127.0.0.1   # if present"
echo "    # or: 20+ failed ssh logins to svcuser@127.0.0.1 within 120 s"
echo
echo "  Network rules (NET-PORTSCAN-001, IDS-SIG-001, NET-OUTBOUND-001) need a"
echo "  non-loopback source — re-run with --with-attacker, then:"
echo "    ip netns exec atk nmap -Pn -sS -p 1000-1023 -T4 --max-retries 1 10.99.0.1"
echo
echo "  Alerts appear within ~${DETECTION_POLL:-2}s of the events landing."
