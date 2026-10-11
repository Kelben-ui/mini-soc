# Mini SOC Platform --- Data and API Contracts

> **Status:** FROZEN version 1.0
> **Frozen on:** 2026-10-11
> **Frozen scope:** Phase 1, task 1.1 and task 1.7. The common event
> model (§2), alert model (§3), and detection rule alignment defined in
> this version are stable and signed off by M3 and M4 (see §23).
> Changes require the Contract Change Policy (§21).

## 1. Purpose

This document defines the shared contracts between the Mini SOC Platform
components.

It covers:

-   the common event format
-   the alert model
-   the incident model
-   database entities and relationships
-   evidence and chain of custody
-   response actions
-   investigation notes
-   audit logging
-   API endpoints
-   authentication and roles
-   contract change rules

These contracts allow the log collection, collector, detection engine,
backend API, database, and frontend components to be developed
independently while remaining compatible.

This document is based on the Mini SOC Platform Project Specification,
Version 1.0, September 2026, including Figure 6 (minimum database
schema).

------------------------------------------------------------------------

# 2. Common Event Model

## 2.1 Purpose

Every raw log line collected by the platform is parsed into one common
event structure.

The collector stores the normalized event in the `events` database
table.

The common event format is the contract between the log collection,
collector, detection engine, backend API, and frontend components.

The format must remain stable after it is agreed and frozen by the team.

## 2.2 Event structure

Each event uses the following JSON structure:

``` json
{
  "event_id": "uuid",
  "timestamp": "2026-10-05T14:32:07Z",
  "host": "web-01",
  "log_type": "nginx_access",
  "category": "web",
  "action": "http_request",
  "src_ip": "192.168.20.45",
  "src_port": 51244,
  "dst_ip": "192.168.10.20",
  "dst_port": 80,
  "user": null,
  "outcome": "success",
  "details": {
    "method": "GET",
    "uri": "/dvwa/vulnerabilities/sqli/?id=1%27+OR+1%3D1",
    "status": 200,
    "user_agent": "sqlmap/1.8"
  },
  "raw": "original log line, unchanged"
}
```

The normalized fields may be used by the detection engine while the
original `raw` field is retained for investigation and evidence.

## 2.3 Event fields

  Field         Description
  ------------- --------------------------------------------------
  `event_id`    Unique identifier for the event
  `timestamp`   Time at which the event occurred
  `host`        Host that produced the log line
  `log_type`    Type of the source log (for example `nginx_access`,
                `auth`, `mini_soc_ids`, `firewall`)
  `category`    Normalized event category (for example `web`,
                `authentication`, `network`, `ids`, `dns`)
  `action`      Normalized event action (for example `http_request`,
                `ssh_login`)
  `src_ip`      Source IP address, when available
  `src_port`    Source port, when available
  `dst_ip`      Destination IP address, when available
  `dst_port`    Destination port, when available
  `user`        Associated username, when available
  `outcome`     Result of the event (for example `success`, `failure`)
  `details`     Additional structured information stored as JSON
  `raw`         Original log line, unchanged

## 2.4 Event processing requirements

The collector must:

1.  Parse each raw log line into the common event structure.
2.  Use a separate parser for each log type.
3.  Store the normalized event in PostgreSQL.
4.  Preserve the event ID so other components can reference the event.
5.  Perform URL decoding of web requests before detection.
6.  Preserve the original raw log line unchanged; the raw event must not
    be modified when it is stored.
7.  Provide unit tests using real sample log lines.

## 2.5 Log source conventions

Each log source is parsed into the common event structure using the
following conventions:

  Log source          `log_type`      `category`                    `action` types                           `details`
  ------------------- --------------- ----------------------------- --------------------------------------- ------------------------------------
  nginx access log    `nginx_access`  `web`                         `http_request`                          `method`, `uri`, `query`, `status`, `bytes`, `user_agent`, `body`
  system auth log     `auth`          `authentication`              `ssh_login`                             `process`, `message`
  IDS JSON alerts     `mini_soc_ids`  `ids`, `network`, or `dns`    `ids_alert`, `port_scan`,               `signature_id`, `signature`,
                                                                    `dns_query`, `unusual_dns`,             `priority`, `count`
                                                                    `unusual_outbound`
  firewall (journald) `firewall`      `network`                     `drop`, `accept`,                       `src`, `dst`, `spt`, `dpt`, `proto`
                                                                    `unusual_outbound`

Additional requirements:

-   `host` must be the real hostname of the collector instance.
-   `dst_ip` must be the collector instance private IP address for
    local services such as the web application and SSH.
-   Timestamps must be normalized to UTC.
-   The `uri`, `query`, and `body` values of web requests must be
    URL-decoded before detection so that an encoded payload such as
    `id=1%27+OR+1%3D1` is matched as `id=1' OR 1=1`.

## 2.6 IDS JSON output format

The custom IDS on the firewall instance (`fw-01`) writes each alert as a
single line of JSON to `/var/log/mini_soc_ids.json`. The collector parses
this file. The IDS alert object format is:

``` json
{
  "timestamp": "2026-10-05T14:32:07.123456+0000",
  "event_type": "alert",
  "host": "fw-01",
  "src_ip": "203.0.113.5",
  "src_port": 34567,
  "dest_ip": "192.168.10.5",
  "dest_port": 22,
  "proto": "TCP",
  "alert": {
    "action": "allowed",
    "gid": 1,
    "signature_id": 9000001,
    "rev": 1,
    "signature": "MINI-SOC Port Scan Detected",
    "category": "Attempted Information Leak",
    "severity": 2
  },
  "metadata": {
    "count": 20
  },
  "raw": "original log line, unchanged"
}
```

The collector maps each IDS alert to the common event structure with
`log_type` set to `mini_soc_ids`. Generic IDS alerts are normalized to
`category: ids` and `action: ids_alert`. Alerts that describe a specific
activity are normalized to the matching category and action so that
detection rules can fire:

-   Port scans become `category: network`, `action: port_scan`.
-   Unusual DNS lookups become `category: dns`, `action: unusual_dns`.
-   Unusual outbound connections become `category: network`,
    `action: unusual_outbound`.

# 3. Alert Model

## 3.1 Purpose

An alert represents a detection generated when a detection rule matches
one or more events.

The detection engine reads new events, evaluates rules loaded from YAML
files, and creates or updates alerts.

Rules are data rather than hard-coded Python logic. Adding a detection
rule must not require changing the detection engine code.

## 3.2 Alert database model

The minimum alert model defined by Figure 6 is:

``` text
alerts
├── alert_id
├── rule_id
├── title
├── severity
├── status
├── first_seen / last_seen
├── count
├── src_ip / dst_ip
├── chain_id
├── assigned_to
└── incident_id
```

## 3.3 Alert fields

  Field           Description
  --------------- -------------------------------------------
  `alert_id`      Unique alert identifier
  `rule_id`       ID of the detection rule that fired
  `title`         Human-readable name of the detection
  `severity`      Alert severity
  `status`        Current alert lifecycle status
  `first_seen`    Time of the first matching event
  `last_seen`     Time of the most recent matching event
  `count`         Number of matching events
  `src_ip`        Source IP associated with the alert
  `dst_ip`        Destination IP associated with the alert
  `chain_id`      Identifier of the correlated attack chain
  `assigned_to`   Analyst assigned to the alert
  `incident_id`   Incident to which the alert is linked

Relationships:

``` text
alerts.assigned_to -> users.id
alerts.incident_id -> incidents.incident_id
```

The specification also describes destination host information as part of
the alert information. If implemented as an additional API or database
field, it must represent the destination host associated with the alert.

## 3.4 Alert-to-event relationship

An alert may be triggered by one or more events.

The relationship is represented by the `alert_events` table:

``` text
alert_events
├── alert_id
└── event_id
```

Relationships:

``` text
alert_events.alert_id -> alerts.alert_id
alert_events.event_id -> events.event_id
```

This allows the platform to identify the normalized events that
triggered an alert.

## 3.5 Alert severity

The supported severity values are:

``` text
LOW
MEDIUM
HIGH
CRITICAL
```

The severity is determined by the detection rule.

For Suricata IDS alerts, severity is mapped from the Suricata priority.

## 3.6 Alert deduplication

Repeated matches for the same detection must not continuously create new
alerts when they belong to the same open alert.

The existing open alert must instead be updated by:

-   incrementing `count`
-   updating `last_seen`
-   associating the new triggering event with the alert

## 3.7 Alert assignment

An alert may be assigned to an analyst.

The relationship is:

``` text
alerts.assigned_to -> users.id
```

Changes to alert assignment must be recorded in the audit log.

## 3.8 Alert status changes

Alert status must follow the lifecycle defined in Figure 5 of the
project specification.

Only transitions allowed by that lifecycle are valid.

The backend must reject invalid transitions.

Every status change requires a comment.

If an alert is marked as `FALSE POSITIVE`, a reason must be provided.

------------------------------------------------------------------------

# 4. Attack Chain and Correlation

## 4.1 Purpose

Correlation links related alerts that belong to the same attack.

## 4.2 Correlation requirement

When alerts from the same source IP occur within 30 minutes across at
least two categories, the detection engine must:

1.  group the alerts under one attack chain;
2.  assign a common `chain_id`;
3.  associate the related alerts with that chain;
4.  suggest one incident.

Examples of categories include:

-   port scan
-   SQL injection
-   SSH brute force

## 4.3 Attack chain relationship

The `chain_id` field in the `alerts` table identifies alerts belonging
to the same correlated attack chain.

An incident can then be created from one or more alerts in the chain.

------------------------------------------------------------------------

# 5. Incident Model

## 5.1 Purpose

An incident represents a security investigation created from one or more
related alerts or from a correlated attack chain.

An analyst can promote an alert, multiple alerts, or a whole attack
chain to an incident.

The incident is the main container for investigation notes, evidence,
response actions, and the incident timeline.

## 5.2 Incident database model

The minimum incident model defined by Figure 6 is:

``` text
incidents
├── incident_id
├── title
├── description
├── severity
├── status
├── category
├── assigned_to
├── created_at / closed_at
├── root_cause
└── lessons_learned
```

Relationship:

``` text
assigned_to -> users.id
```

## 5.3 Incident fields

  Field               Description
  ------------------- ----------------------------------------
  `incident_id`       Unique incident identifier
  `title`             Incident title
  `description`       Description of the incident
  `severity`          Incident severity
  `status`            Current incident lifecycle status
  `category`          Incident category
  `assigned_to`       Analyst assigned to the incident
  `created_at`        Time the incident was created
  `closed_at`         Time the incident was closed
  `root_cause`        Identified root cause
  `lessons_learned`   Lessons identified after investigation

## 5.4 Incident identifier

Incident identifiers use the project incident identifier convention:

``` text
INC-0001
INC-0002
INC-0003
...
```

## 5.5 Incident information

An incident must provide access to:

-   incident ID
-   title
-   description
-   severity
-   affected hosts
-   source IPs
-   linked alerts
-   assigned analyst
-   status
-   incident timeline

Affected hosts and source IPs can be derived from events and alerts
linked to the incident.

## 5.6 Incident timeline

The incident must maintain an automatic timeline containing relevant
activities, including:

-   status changes
-   investigation notes
-   evidence activity
-   response actions

The timeline provides the chronological history of the investigation.

## 5.7 Incident status

Incident status must follow the lifecycle defined in Figure 5 of the
project specification.

Only transitions allowed by that lifecycle are valid.

The backend must reject invalid transitions.

Every status change requires a comment.

A false-positive closure must include a reason where required by the
lifecycle.

## 5.8 Incident assignment

An incident may be assigned to an analyst.

The relationship is:

``` text
incidents.assigned_to -> users.id
```

Assignment changes are recorded in the audit log.

------------------------------------------------------------------------

# 6. Users and Roles

## 6.1 User database model

The minimum user model is:

``` text
users
├── id
├── username
├── password_hash
├── role
└── created_at
```

## 6.2 User fields

  Field             Description
  ----------------- -----------------------------------
  `id`              Unique user identifier
  `username`        User's login name
  `password_hash`   Securely hashed password
  `role`            User's platform role
  `created_at`      Time the user account was created

## 6.3 Roles

The platform defines:

``` text
analyst
lead
admin
```

### Analyst

Analysts can perform normal investigation activities supported by the
platform.

### Lead

Leads have analyst capabilities and can:

-   close incidents
-   manage users

### Admin

Administrators have administrative platform capabilities.

Access control must be enforced by the backend and not only by the
frontend.

------------------------------------------------------------------------

# 7. Evidence Model

## 7.1 Purpose

Evidence stores files and other investigation material associated with
an incident.

Supported evidence includes:

-   log extracts
-   screenshots
-   packet captures (`.pcap`)
-   notes

## 7.2 Evidence database model

``` text
evidence
├── id
├── incident_id
├── filename
├── type
├── sha256
├── size_bytes
├── uploaded_by
├── uploaded_at
└── storage_path
```

Relationships:

``` text
evidence.incident_id -> incidents.incident_id
evidence.uploaded_by -> users.id
```

## 7.3 Evidence fields

  Field            Description
  ---------------- ---------------------------------------
  `id`             Unique evidence identifier
  `incident_id`    Incident associated with the evidence
  `filename`       Evidence filename
  `type`           Evidence type
  `sha256`         SHA-256 integrity hash
  `size_bytes`     Size of the evidence file
  `uploaded_by`    User who uploaded the evidence
  `uploaded_at`    Time the evidence was uploaded
  `storage_path`   Location where the evidence is stored

## 7.4 Evidence integrity

When evidence is uploaded, the platform must:

1.  calculate the SHA-256 hash;
2.  store the hash;
3.  store the file size;
4.  store the uploader;
5.  store the upload time.

Evidence files must be stored outside the web root.

Evidence cannot be edited or overwritten.

Evidence is append-only: new evidence may be added, but existing
evidence must not be replaced.

## 7.5 Evidence verification

The platform must provide a verification operation.

Verification recomputes the SHA-256 hash of the stored file and
determines whether the file remains unchanged.

The verification result must be recorded in the chain-of-custody log.

------------------------------------------------------------------------

# 8. Chain of Custody

## 8.1 Custody log model

Every view, download, and verification of evidence must be recorded.

``` text
custody_log
├── id
├── evidence_id
├── user_id
├── action
├── result
└── timestamp
```

Relationships:

``` text
custody_log.evidence_id -> evidence.id
custody_log.user_id -> users.id
```

## 8.2 Custody log fields

  Field           Description
  --------------- -------------------------------
  `id`            Unique custody log identifier
  `evidence_id`   Evidence that was accessed
  `user_id`       User who performed the action
  `action`        Evidence operation
  `result`        Result of the operation
  `timestamp`     Time the operation occurred

Supported custody actions include:

``` text
view
download
verify
```

------------------------------------------------------------------------

# 9. Response Action Model

## 9.1 Purpose

The platform records response actions performed during an incident.

The platform does not have to automatically perform the response action.

## 9.2 Action database model

``` text
actions
├── id
├── incident_id
├── type
├── target
├── performed_by
├── reason
├── result
└── timestamp
```

Relationships:

``` text
actions.incident_id -> incidents.incident_id
actions.performed_by -> users.id
```

## 9.3 Action fields

  Field            Description
  ---------------- ----------------------------------------
  `id`             Unique action identifier
  `incident_id`    Incident associated with the action
  `type`           Type of response action
  `target`         Target of the action
  `performed_by`   User who performed/recorded the action
  `reason`         Reason for the action
  `result`         Result of the action
  `timestamp`      Time the action occurred

## 9.4 Supported response action types

The project defines:

``` text
block IP
disable account
isolate host
reset password
patch
other
```

Actions must appear on the incident timeline.

## 9.5 Automated blocking

If automated IP blocking is implemented as an advanced feature:

-   human confirmation is required every time;
-   the action affects only `fw-01`;
-   the block must not execute without analyst confirmation.

------------------------------------------------------------------------

# 10. Investigation Notes

## 10.1 Notes database model

``` text
notes
├── id
├── incident_id
├── author
├── body
└── created_at
```

Relationships:

``` text
notes.incident_id -> incidents.incident_id
notes.author -> users.id
```

## 10.2 Notes fields

  Field           Description
  --------------- -----------------------------------
  `id`            Unique note identifier
  `incident_id`   Incident associated with the note
  `author`        User who created the note
  `body`          Note contents
  `created_at`    Time the note was created

Analysts can add investigation notes during an incident.

------------------------------------------------------------------------

# 11. Audit Log

## 11.1 Purpose

The platform must maintain an append-only audit log of every write
action.

The audit log provides accountability for changes made to platform
objects.

## 11.2 Audit log database model

``` text
audit_log
├── id
├── user_id
├── action
├── object_type / object_id
├── old_value / new_value
└── timestamp
```

Relationship:

``` text
audit_log.user_id -> users.id
```

## 11.3 Audit log fields

  Field           Description
  --------------- -----------------------------------
  `id`            Unique audit record identifier
  `user_id`       User who performed the action
  `action`        Action performed
  `object_type`   Type of object affected
  `object_id`     Identifier of the affected object
  `old_value`     Previous value where applicable
  `new_value`     New value where applicable
  `timestamp`     Time the action occurred

The audit log must be append-only.

------------------------------------------------------------------------

# 12. Minimum Database Relationships

The minimum relationships defined by Figure 6 are:

``` text
alerts.assigned_to
    -> users.id

alerts.incident_id
    -> incidents.incident_id

alert_events.alert_id
    -> alerts.alert_id

alert_events.event_id
    -> events.event_id

incidents.assigned_to
    -> users.id

evidence.incident_id
    -> incidents.incident_id

evidence.uploaded_by
    -> users.id

custody_log.evidence_id
    -> evidence.id

custody_log.user_id
    -> users.id

actions.incident_id
    -> incidents.incident_id

actions.performed_by
    -> users.id

notes.incident_id
    -> incidents.incident_id

notes.author
    -> users.id

audit_log.user_id
    -> users.id
```

The database schema in Figure 6 is the minimum schema. The team may add
tables or columns where required, but the required tables and fields
must not be removed.

------------------------------------------------------------------------

# 13. API Contract

The backend exposes platform functionality through REST API endpoints.

## 13.1 Authentication

### Login

``` http
POST /api/auth/login
```

Purpose:

Obtain a JWT authentication token.

The backend authenticates the user's credentials and returns a JWT for
authenticated API access.

------------------------------------------------------------------------

## 13.2 Event ingestion

### Submit event batches

``` http
POST /api/ingest
```

Purpose:

Allow agents/collectors to submit event batches to the backend.

Authentication:

``` text
API key
```

Submitted events must follow the common event format defined in Section
2.

------------------------------------------------------------------------

## 13.3 Event search

``` http
GET /api/events
```

Purpose:

Search normalized security events.

The event search must support investigation using information such as:

-   IP address
-   host
-   log type
-   time range

------------------------------------------------------------------------

## 13.4 Alert endpoints

### List alerts

``` http
GET /api/alerts
```

Purpose:

Return alerts for analyst investigation.

The dashboard must be able to filter alerts by:

-   severity
-   status
-   rule
-   IP
-   time

### View an alert

``` http
GET /api/alerts/{id}
```

Purpose:

Return the complete alert information, including linked events.

### Update an alert

``` http
PATCH /api/alerts/{id}
```

Purpose:

Change supported alert properties such as:

-   status
-   assignment

The backend must validate status transitions according to the defined
alert lifecycle.

A status change requires a comment.

Changes must be recorded in the audit log.

------------------------------------------------------------------------

# 14. Incident API

## 14.1 Create an incident

``` http
POST /api/incidents
```

Purpose:

Create an incident from one or more alerts or an attack chain.

The incident must contain the information defined by the Incident Model.

## 14.2 View an incident

``` http
GET /api/incidents/{id}
```

Purpose:

Return the incident and its associated investigation information.

The incident view must provide access to:

-   alerts
-   timeline
-   notes
-   evidence
-   response actions
-   status
-   assignment

## 14.3 Add an investigation note

``` http
POST /api/incidents/{id}/notes
```

Purpose:

Add an investigation note to an incident.

The authenticated user becomes the author of the note.

## 14.4 Upload evidence

``` http
POST /api/incidents/{id}/evidence
```

Purpose:

Upload evidence associated with an incident.

The backend must:

-   calculate SHA-256;
-   store the file size;
-   store uploader information;
-   store upload time;
-   store the evidence outside the web root;
-   record the required custody information.

## 14.5 Record a response action

``` http
POST /api/incidents/{id}/actions
```

Purpose:

Record a response action associated with an incident.

The action must contain:

-   type
-   target
-   performed by
-   reason
-   result
-   time

## 14.6 Generate incident report

``` http
GET /api/incidents/{id}/report
```

Purpose:

Generate an incident report.

The report must contain:

-   summary
-   timeline
-   affected assets
-   indicators such as IPs, user agents, and payloads
-   evidence list with hashes
-   actions taken
-   root cause
-   lessons learned

The report may be generated as PDF or HTML.

------------------------------------------------------------------------

# 15. Statistics API

``` http
GET /api/stats
```

Purpose:

Provide statistics used by the dashboard.

The dashboard overview must be able to show information including:

-   active alerts by severity
-   alerts over the previous 24 hours
-   top source IPs
-   top attack types
-   open incidents
-   agent status

------------------------------------------------------------------------

# 16. Authentication and Authorization

The API uses JWT authentication for normal user access.

Agents submitting event batches use an API key for `/api/ingest`.

Passwords must be hashed using bcrypt or Argon2.

The backend must enforce role-based authorization.

The roles are:

``` text
analyst
lead
admin
```

Authorization decisions must be performed by the backend.

Frontend controls must not be treated as the security boundary.

------------------------------------------------------------------------

# 17. Input Validation

All API endpoints must validate incoming input.

Validation must cover:

-   request data
-   identifiers
-   status values
-   role values
-   uploaded files
-   action types
-   required fields
-   values used in database queries

Invalid input must be rejected safely.

------------------------------------------------------------------------

# 18. Security Requirements

The Mini SOC platform is itself a security tool and must be protected
against common web application vulnerabilities.

The platform must be tested for:

-   SQL injection
-   cross-site scripting (XSS)
-   broken access control

Secrets must never be committed to the repository.

Passwords, API keys, and JWT secrets must be stored in `.env`.

The `.env` file must not be committed to Git.

------------------------------------------------------------------------

# 19. Detection-to-Incident Relationship

The platform follows this general lifecycle:

``` text
Raw Log
   ↓
Common Event
   ↓
Detection Rule
   ↓
Alert
   ↓
Alert/Event Investigation
   ↓
Correlation
   ↓
Attack Chain
   ↓
Incident
   ↓
Investigation
   ↓
Response
   ↓
Resolution
   ↓
Report
```

An alert is linked to its triggering event(s).

Multiple related alerts can belong to one attack chain.

An attack chain can be promoted to an incident.

An incident can contain:

-   multiple alerts
-   investigation notes
-   evidence
-   response actions
-   timeline information

------------------------------------------------------------------------

# 20. Contract Ownership

  -----------------------------------------------------------------------
  Component                           Contract responsibility
  ----------------------------------- -----------------------------------
  Log agents                          Forward raw log lines with host and
                                      log type information

  Collector                           Produce the common event format

  PostgreSQL                          Store events and platform data
                                      according to the database model

  Detection engine                    Consume events and create/update
                                      alerts

  Correlation engine                  Group related alerts into attack
                                      chains

  Backend API                         Expose events, alerts, incidents,
                                      evidence, actions, and reports

  Frontend                            Consume the API and display the
                                      defined models

  Incident response                   Use incidents, evidence, notes, and
                                      actions

  Reporting                           Use incident, alert, evidence, and
                                      action data
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 21. Contract Change Policy

These contracts are shared interfaces between independently developed
components.

Changes must be communicated to the affected team members before
implementation.

A contract change must:

1.  identify the affected model or endpoint;
2.  explain the reason for the change;
3.  identify components affected by the change;
4.  update this document;
5.  update the relevant implementation;
6.  update tests;
7.  be reviewed by the relevant team members.

The common event format must remain stable after the team freezes the
contract unless a change is explicitly agreed.

The minimum database schema from Figure 6 must not have required tables
or fields removed.

Additional fields or tables may be added when necessary.

------------------------------------------------------------------------

# 22. Contract Summary

The Mini SOC Platform uses the following core data flow:

``` text
events
  │
  │ detection
  ▼
alerts
  │
  │ alert_events
  ▼
events

alerts
  │
  │ correlation
  ▼
attack chain
  │
  │ promotion
  ▼
incidents
  │
  ├── notes
  ├── evidence
  │     └── custody_log
  └── actions

users
  ├── alert assignment
  ├── incident assignment
  ├── evidence upload
  ├── custody actions
  ├── response actions
  ├── note authorship
  └── audit actions

all write operations
  │
  ▼
audit_log
```

This document is the shared contract for the event, alert, incident,
database, and API models used by the Mini SOC Platform.

# 23. Freeze Record

This document is frozen so that components developed independently
(collector parsers, detection rules, detection engine, backend API,
frontend) can rely on stable interfaces.

## 23.1 Versions

| Version | Date       | Status | Change summary |
| ------- | ---------- | ------ | -------------- |
| 1.0     | 2026-10-11 | FROZEN | Phase 1 freeze (task 1.1 and task 1.7). Reconstructed the common event model (§2.2 event structure, §2.3 event fields, §2.4 processing requirements), added log source conventions (§2.5), the IDS JSON output format (§2.6), and rebuilt the alert model (§3.1-§3.3). All 13 detection rules carry `category:` and `mitre:`. The contract change policy in §21 applies. |

## 23.2 Sign-off

The following owners have reviewed this version in line with the Phase 1
task table and signed off:

| Reviewer | Role            | Sign-off | Date       |
| -------- | --------------- | -------- | ---------- |
| M3       | Detection rules | Approved | 2026-10-11 |
| M4       | Security/API    | Approved | 2026-10-11 |
