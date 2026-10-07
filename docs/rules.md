# Mini SOC Platform — Detection Rules

## 1. Purpose

This document defines the detection rules implemented by the Mini SOC detection engine.

Rules are stored as YAML files in the `rules/` directory.

The detection engine loads the enabled rules and evaluates new normalized events against them.

Adding or disabling a detection rule must not require changes to the detection engine Python code.

---

# 2. Rule Structure

The project specification uses the following structure for a detection rule:

```yaml
id: SSH-BF-001
name: SSH brute force
severity: HIGH
enabled: true
match:
  log_type: auth
  action: ssh_login
  outcome: failure
threshold:
  count: 10
  window_seconds: 300
  group_by: [src_ip, dst_ip]
mitre: T1110
```

Each rule contains:

* `id`
* `name`
* `severity`
* `enabled`
* `match`
* `threshold`, where required
* `mitre`, where specified

---

# 3. Required Detection Rules

## 3.1 SSH Brute Force

**Rule ID:** SSH-BF-001

**Source:** auth.log

**Logic:** Detect at least 10 failed SSH login attempts from the same source within 5 minutes.

**Severity:** HIGH

**Grouping:** Source IP and destination IP

**MITRE:** T1110

---

## 3.2 Login Success After Brute Force

**Logic:** Detect a successful login from an IP that has an open brute-force alert.

**Severity:** CRITICAL

---

## 3.3 Web Login Brute Force

**Source:** Nginx

**Logic:** Detect at least 20 POST requests to the DVWA login from the same source within 2 minutes.

**Severity:** HIGH

---

**Source:** Nginx


## 3.5 Cross-Site Scripting
**Logic:** Detect:
* event handlers

in the URI or request body.
**Severity:** MEDIUM


## 3.6 Command Injection
**Source:** Nginx

**Logic:** Detect `;`, `|` or `&&` followed by shell commands on the DVWA execution page.

**Severity:** HIGH

---

## 3.7 Directory Traversal / LFI

**Source:** Nginx

**Logic:** Detect:

* `../`
* `/etc/passwd`
* `php://`

in parameters.

**Severity:** HIGH

---

## 3.8 Scanner User-Agent

**Source:** Nginx

**Logic:** Detect the following scanner names in the User-Agent:

* sqlmap
* nikto
* nmap
* gobuster

**Severity:** MEDIUM

---

## 3.9 HTTP Flood

**Source:** Nginx

**Logic:** Detect more than 300 requests from the same source within 1 minute.

**Severity:** MEDIUM

---

## 3.10 Port Scan

**Source:** nftables / Suricata

**Logic:** Detect at least 20 distinct destination ports from the same source within 1 minute.

**Severity:** MEDIUM

---

## 3.11 IDS Signature

**Source:** Suricata

**Logic:** Detect any Suricata alert.

**Severity:** Mapped from Suricata priority.

---

## 3.12 Unusual Outbound Connection

**Source:** nftables

**Logic:** Detect a server opening a connection to a port that is not on the allow-list.

**Severity:** MEDIUM

---

## 3.13 Unusual DNS Activity

**Source:** Suricata

**Logic:** Detect very long subdomains or a high DNS query rate from one host.

**Severity:** LOW

---

# 4. Deduplication

Repeated matches must not create a new alert every time.

When a rule continues to match the same activity:

* update the existing open alert
* increase its count
* update its last-seen time
* link the new triggering event ID to the alert

---

# 5. Alert-to-Event Relationship

Every alert must be linked to the event IDs that triggered it.

This allows an analyst to investigate the original normalized events and their preserved raw log lines.

---

# 6. Correlation

The detection engine must correlate activity from the same source IP within a 30-minute window.

When the same source IP generates activity across at least two categories, the platform groups the activity into one attack chain and suggests one incident.

---

# 7. Rule Configuration

Rules can be disabled through the YAML configuration using:

```yaml
enabled: false
```

Disabled rules must not generate alerts.

---

# 8. Testing

Each rule must have replay tests using sample events/logs.

Testing must verify that:

1. The rule detects matching activity.
2. The rule does not trigger on unrelated activity.
3. The correct severity is assigned.
4. Thresholds and time windows are respected.
5. Repeated matches are deduplicated.
6. Triggering event IDs are linked to the alert.

---

* `javascript:`
* `<script`


**Source:** Nginx

---

**Severity:** HIGH
* quotes with OR
* SQL comments
* SLEEP
* UNION

**Logic:** Detect decoded URI or request body containing SQL injection patterns, including:


## Port Scan Detection

The Mini SOC uses the project's custom IDS as the source of normalized
port-scan events.

The IDS identifies port-scan activity based on multiple destination
ports observed from the same source within the configured detection
window.

Once detected, the IDS produces a standardized event:

- category: network
- action: port_scan
- src_ip: source IP
- dst_ip: destination IP
- details: IDS-specific information
- raw: original IDS event

The Detection Engine consumes this standardized event and creates the
NET-PORTSCAN-001 alert.

This keeps the Detection Engine source-independent and allows the IDS
to perform network-specific detection.
