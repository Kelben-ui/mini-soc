# Mini SOC Platform — Architecture

## 1. Overview

The Mini SOC Platform processes security information through the following lifecycle:

Detection → Alert → Investigation → Incident → Response → Resolution → Report

The platform consists of:

1. Log sources
2. Log agents
3. Collector
4. Detection engine
5. PostgreSQL database
6. Backend API
7. Dashboard

---

# 2. Data Flow

```text
Log Sources
    │
    ▼
Log Agents
    │
    ▼
Central Collector
    │
    │ normalized events
    ▼
PostgreSQL
    │
    │ new events
    ▼
Detection Engine
    │
    │ alerts
    ▼
PostgreSQL
    │
    ▼
Backend API
    │
    ▼
Dashboard
```

---

# 3. Log Sources

The platform collects logs from:

* Linux authentication/SSH
* Nginx
* DVWA
* nftables firewall
* Suricata IDS

---

# 4. Normalization

The collector parses raw log lines and converts them into the common event format.

The normalized event is stored in PostgreSQL.

The original raw log line is preserved for investigation and evidence.

---

# 5. Detection Engine

The detection engine:

1. Reads new events.
2. Loads detection rules from YAML files.
3. Evaluates events against the rules.
4. Applies thresholds and time windows where required.
5. Creates or updates alerts.
6. Deduplicates repeated matches.
7. Performs correlation.
8. Links alerts to triggering event IDs.

The engine reads new events periodically.

---

# 6. Database

PostgreSQL provides the central persistent data store.

It stores the data required for:

* events
* alerts
* incidents
* evidence
* response actions
* users
* audit records

The database schema is managed using migrations.

---

# 7. Backend API

The FastAPI backend provides authenticated REST access to:

* events
* alerts
* incidents
* evidence
* response actions
* statistics
* reports

JWT authentication is used for users.

Agents use API-key authentication for event ingestion.

---

# 8. Incident Workflow

```text
Event
  ↓
Detection
  ↓
Alert
  ↓
Investigation
  ↓
Incident
  ↓
Response
  ↓
Resolution
  ↓
Report
```

---

# 9. Evidence

Evidence is associated with incidents.

Evidence may include:

* log extracts
* screenshots
* packet captures
* notes


* secret management using `.env`
* security testing
* audit logging
* input validation
* role-based access
* JWT authentication
* password hashing
Required protections include:

Uploaded files are hashed using SHA-256 and protected by a chain-of-custody record.
The platform must protect its own API and data.

