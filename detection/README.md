# Detection Engine

## 1. Purpose

The detection engine reads normalized events from PostgreSQL and evaluates them against detection rules stored as YAML files.

When a rule condition is satisfied, the engine creates or updates an alert.

---

## 2. Directory Structure

```text
detection/
├── README.md
├── engine/
└── tests/
```

Detection rules are stored separately in:

```text
rules/
```

There is one YAML file per rule.

---

## 3. Detection Process

```text
PostgreSQL
    ↓
New Events
    ↓
Rule Loader
    ↓
Rule Evaluator
    ↓
Threshold / Time Window
    ↓
Alert Creation or Update
```

---

## 4. Rule Loader

The rule loader reads YAML files from the `rules/` directory.

Rules with:

```yaml
enabled: false
```

are not evaluated.

Adding a new rule should require adding a YAML file rather than changing the detection engine Python code.

---

## 5. Rule Evaluator

The evaluator compares normalized event fields against the conditions defined in each rule.

Where required, the evaluator applies:

* event matching
* thresholds
* time windows
* grouping
* correlation

---

## 6. Alert Creation

When a detection rule is satisfied, the detection engine creates an alert.

Repeated matches of the same activity update an existing open alert rather than creating duplicate alerts.

The alert count and last-seen time are updated.

Triggering event IDs are linked to the alert.

---

## 7. Correlation

The detection engine correlates related activity from the same source IP.

Activity occurring within the defined 30-minute window across at least two categories can be grouped into one attack chain.

---

## 8. Testing

Detection tests are stored in:

```text
detection/tests/
```

Tests use sample events and replay data.

Each required detection rule must have tests demonstrating detection and expected behavior.

---

## 9. Required Rules

The required detection rules are documented in:

```text
docs/rules.md
```

The actual rule definitions are stored in:

```text
rules/
```
