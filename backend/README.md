# Backend API and Database

## 1. Purpose

The backend provides the REST API and persistent database functionality for the Mini SOC Platform.

It is responsible for:

* database access
* API endpoints
* authentication
* authorization
* user roles
* audit logging
* evidence storage and hashing
* response-action recording
* incident reports

---

## 2. Technology

The backend uses:

* Python 3.11+
* FastAPI
* PostgreSQL 16
* Alembic
* JWT authentication

---

## 3. Directory Structure

```text
backend/
├── README.md
├── app/
├── migrations/
└── tests/
```

---

## 4. API

The backend implements the API endpoints defined in:

`docs/contracts.md`

The main API areas are:

* Authentication
* Event ingestion and search
* Alert management
* Incident management
* Evidence
* Response actions
* Reports
* Statistics

---

## 5. Authentication

The API uses JWT authentication for users.

Passwords are hashed using bcrypt or Argon2.

Supported roles:

* analyst
* lead
* admin

---

## 6. Database

PostgreSQL is the central database.

Database schema changes are managed using Alembic migrations.

---

## 7. Audit Logging

Every write operation must produce an append-only audit record.

---

## 8. Evidence

Evidence files are stored outside the web root.

SHA-256 hashes are calculated when evidence is uploaded.

Evidence cannot be edited or overwritten.

---

## 9. Testing

Backend tests are located in:

```text
backend/tests/
```

Tests must verify:

* authentication
* authorization
* input validation
* API behavior
* database operations
* audit logging
* evidence hashing
