#!/bin/bash
# LAB USE ONLY - targets fixed to 192.168.10.0/24
# Usage: ./port-scan.sh <target_ip>
TARGET="$1"
nmap -sS -p 1-1000 "$TARGET"
