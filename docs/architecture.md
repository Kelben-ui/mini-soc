# Architecture

This document describes the Mini SOC platform architecture and operational model.

## Overview

The Mini SOC is a self-contained security operations platform deployed on a single EC2 instance (one-VM model). It replaces Docker-based orchestration with native systemd services for operational simplicity and compatibility.

## Design Principles

- One EC2 instance deployment (systemd-managed services)
- Local PostgreSQL 16 with Alembic migrations
- Nginx reverse proxy serving built frontend + API proxy
- IDS/IPS replaces Suricata with custom lightweight detection
- Evidence stored on filesystem with chain of custody
- Detection runs as a continuous loop

## Components

| Component | Service | Purpose |
|---|---|---|
| Backend API | soc-backend.service | FastAPI REST API, auth, RBAC, incidents, alerts, evidence |
| Collector | soc-collector.service | Ingests raw logs, normalizes events |
| Detection Engine | soc-detection.service | Evaluates rules, correlates, creates alerts |
| Log Agent | soc-agent.service | Watches log files, forwards to collector |
| IDS/IPS | mini-soc-ids.service | Custom IDS/IPS monitoring network activity |

## Network

- Backend: 127.0.0.1:8000 (uvicorn)
- Collector: 127.0.0.1:9000
- Nginx: 443/8443 (or 80) serving frontend dist/, proxying /api → 127.0.0.1:8000
- PostgreSQL: localhost:5432
- Evidence: /var/lib/mini-soc/evidence (mode 0444 after upload; custody logged)

## Security

- systemd hardening: NoNewPrivileges, ProtectSystem=strict, ReadWritePaths scoped
- Config in /etc/mini-soc/.env (0640)
- IPS: nftables blocklist with timeout, soc-block helper (root-owned), sudoers restricted to backend user
- Audit trail immutable (UPDATE/DELETE blocked on audit_logs)
- Input validation, parameterized queries, Jinja2 autoescape

## Deployment

- Layout: /opt/mini-soc (code), /opt/mini-soc/.venv (venv), /etc/mini-soc/.env (config), /var/lib/mini-soc/{evidence,agent} (state)
- Bootstrap: deploy/install.sh (idempotent)
- Updates: deploy/update.sh (git pull, deps, migrations, build, restart)
