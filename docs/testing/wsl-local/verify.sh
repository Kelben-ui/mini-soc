#!/bin/bash
# Quick API-level view of the local lab: event/alert counts and recent rows.
#
# Requires the stack to be running and an admin account to exist.
# Override the app dir or credentials with environment variables:
#
#   APP_DIR=/root/mini-soc SOC_USER=admin SOC_PASS=... bash verify.sh delta
#
# Sub-commands:
#   baseline   record the current event/alert counts
#   delta      show counts now vs the last baseline, plus the newest alerts
#   query [lt] show the newest events, optionally filtered by log_type
set -uo pipefail

APP_DIR="${APP_DIR:-/root/mini-soc}"
SOC_USER="${SOC_USER:-admin}"
SOC_PASS="${SOC_PASS:-password}"
TOKEN_FILE="${TOKEN_FILE:-$HOME/.api-token}"
STATE="${STATE:-$HOME/.verify-baseline}"

get_token() {
    if [ ! -s "$TOKEN_FILE" ]; then
        local resp token
        resp=$(curl -sk -X POST https://127.0.0.1/api/auth/login \
            -H 'Content-Type: application/json' \
            -d "{\"username\":\"$SOC_USER\",\"password\":\"$SOC_PASS\"}")
        token=$(printf '%s' "$resp" \
            | "$APP_DIR/.venv/bin/python" -c 'import sys,json
try:
    print(json.load(sys.stdin)["access_token"])
except Exception:
    print("")')
        if [ -z "$token" ]; then
            echo "ERROR: login failed for user '$SOC_USER' (set SOC_USER/SOC_PASS)" >&2
            echo "       response: $resp" >&2
            exit 1
        fi
        printf '%s' "$token" > "$TOKEN_FILE"
    fi
    cat "$TOKEN_FILE"
}

# Refresh the token once on any auth failure (expired or rejected token).
api() {
    local token out code

    token=$(get_token)
    out=$(curl -sk -w $'\n%{http_code}' "$1" -H "Authorization: Bearer $token")
    code="${out##*$'\n'}"
    out="${out%$'\n'*}"

    if [[ "$code" == "401" || "$code" == "403" ]]; then
        rm -f "$TOKEN_FILE"
        token=$(get_token)
        out=$(curl -sk "$1" -H "Authorization: Bearer $token")
    fi

    printf '%s' "$out"
}

py() { "$APP_DIR/.venv/bin/python" "$@"; }

counts() {
    api "https://127.0.0.1/api/stats" \
        | py -c 'import sys,json; d=json.load(sys.stdin); print(d["total_events"], d["total_alerts"])'
}

case "${1:-delta}" in
    baseline) counts > "$STATE"; echo "baseline (events alerts): $(cat "$STATE")" ;;
    delta)
        echo "before (events alerts): $(cat "$STATE" 2>/dev/null || echo '0 0')"
        echo "after  (events alerts): $(counts)"
        echo "--- latest alerts ---"
        SOC_JSON="$(api "https://127.0.0.1/api/alerts?limit=8")" py <<'PY'
import json, os
d = json.loads(os.environ["SOC_JSON"])
rows = d.get("items", d) if isinstance(d, dict) else d
for a in rows[:8]:
    print(f"  #{a.get('alert_id')} {a.get('rule_id'):<22} sev={a.get('severity'):<7} src={str(a.get('src_ip')):<16} {a.get('title')}")
PY
        ;;
    query)
        lt="${2:-}"; url="https://127.0.0.1/api/events?limit=12"
        [ -n "$lt" ] && url="$url&log_type=$lt"
        SOC_JSON="$(api "$url")" py <<'PY'
import json, os
d = json.loads(os.environ["SOC_JSON"])
rows = d.get("items", d) if isinstance(d, dict) else d
print(f"{'timestamp':<26} {'log_type':<13} {'src_ip':<15} detail")
for e in rows[:12]:
    det = e.get("details") or {}
    detail = det.get("uri") or det.get("query") or det.get("message") or det.get("raw") or ""
    print(f"{str(e.get('timestamp'))[:25]:<26} {str(e.get('log_type')):<13} {str(e.get('src_ip')):<15} {str(detail)[:60]}")
print(f"(returned {len(rows)})")
PY
        ;;
    *) echo "Usage: bash verify.sh [baseline|delta|query [log_type]]"; exit 1 ;;
esac
