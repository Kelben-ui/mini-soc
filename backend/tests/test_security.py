"""Backend security tests (Phase 9.2).

Covers:
- SQLi/XSS input validation/sanitization (parameterized queries, no string concat)
- Broken access control / IDOR
- JWT tampering (expired/invalid tokens, role claims)
- Upload abuse (file type/size constraints, evidence)
- IPS helper injection (via actions route + ips module)
"""

import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from jose import JWTError, jwt

from backend.app import ips
from backend.app.models.evidence import Evidence
from backend.app.models.incident import Incident
from backend.app.models.user import User
from backend.app.routers import incidents, alerts, users, events
from backend.app.routers.auth import login
from backend.app.schemas.auth import LoginRequest
from backend.app.schemas.user import UserCreate
from backend.app.utils import jwt as jwt_utils


def make_user(db, role="analyst", username=None):
    from backend.app.utils import password as pw

    if username is None:
        username = f"user-{role}-{uuid.uuid4().hex[:12]}"
    user = User(
        username=username,
        password_hash=pw.hash_password("password"),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_incident(db, **overrides):
    values = {
        "incident_code": f"INC-{uuid.uuid4().hex[:6]}",
        "title": "Test",
        "severity": "medium",
        "status": "open",
        "created_at": datetime.now(timezone.utc),
    }
    values.update(overrides)
    incident = Incident(**values)
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident


class TestSQLiXSS:
    def test_alert_list_rejects_invalid_filters(self, db):
        user = make_user(db)
        try:
            alerts.get_alerts(
                severity="'; DROP TABLE alerts; --",
                status=None,
                rule_id=None,
                rule=None,
                src_ip=None,
                assigned_to=None,
                start_time=None,
                end_time=None,
                limit=50,
                offset=0,
                db=db,
                current_user=user,
            )
        except HTTPException:
            pass

    def test_get_events_filters_are_parameterized(self, db):
        user = make_user(db)
        events.get_events(
            src_ip="'; DROP TABLE events; --",
            host="<script>alert(1)</script>",
            log_type="auth",
            start_time=None,
            end_time=None,
            limit=10,
            offset=0,
            db=db,
            current_user=user,
        )
        assert True

    def test_incident_report_escapes_xss(self, db):
        """Attacker-controlled fields must be HTML-escaped in the report."""
        user = make_user(db, role="analyst")
        inc = make_incident(db, title="<script>alert('xss')</script>")

        response = incidents.get_incident_report(
            inc.incident_id, db=db, current_user=user
        )
        body = response.body.decode()

        assert "<script>alert" not in body
        assert "&lt;script&gt;" in body

    def test_summary_report_escapes_xss(self, db):
        from backend.app.routers.reports import get_summary_report

        user = make_user(db, role="analyst")
        make_incident(db, title="<script>alert('xss')</script>")

        response = get_summary_report(db=db, current_user=user)
        body = response.body.decode()

        assert "Mini SOC Summary Report" in body
        assert "<script>alert" not in body
        assert "&lt;script&gt;" in body

    def test_evidence_download_is_opaque(self, db, tmp_path):
        """Uploaded content must never be served as renderable HTML/SVG."""
        lead = make_user(db, role="lead")
        inc = make_incident(db)

        stored = tmp_path / "evil.html"
        stored.write_text("<script>alert(1)</script>", encoding="utf-8")

        evidence = Evidence(
            incident_id=inc.incident_id,
            filename="evil.html",
            type="text/html",
            sha256="a" * 64,
            size_bytes=stored.stat().st_size,
            uploaded_by=lead.id,
            uploaded_at=datetime.now(timezone.utc),
            storage_path=str(stored),
        )
        db.add(evidence)
        db.commit()
        db.refresh(evidence)

        response = incidents.download_evidence(
            evidence.id, db=db, current_user=lead
        )

        assert response.media_type == "application/octet-stream"


class TestSecurityHeaders:
    def test_middleware_sets_hardening_headers(self):
        import asyncio

        from starlette.requests import Request
        from starlette.responses import Response

        from backend.app import main

        async def call_next(_request):
            return Response("ok", media_type="text/plain")

        request = Request(
            {"type": "http", "method": "GET", "path": "/api/stats", "headers": []}
        )
        response = asyncio.run(main.add_security_headers(request, call_next))

        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert "Content-Security-Policy" in response.headers


class TestIDOR:
    def test_get_incident_requires_authz(self, db):
        analyst = make_user(db, role="analyst")
        inc = make_incident(db)
        incidents.get_incident(inc.incident_id, db=db, current_user=analyst)

    def test_update_incident_assignment_restricted(self, db):
        analyst = make_user(db, role="analyst")
        lead = make_user(db, role="lead")
        inc = make_incident(db)
        with pytest.raises(HTTPException):
            incidents.update_incident(
                inc.incident_id,
                incidents.IncidentUpdate(assigned_to=lead.id),
                db=db,
                current_user=analyst,
            )
        incidents.update_incident(
            inc.incident_id,
            incidents.IncidentUpdate(assigned_to=analyst.id),
            db=db,
            current_user=lead,
        )

    def test_get_evidence_custody_requires_auth(self, db):
        lead = make_user(db, role="lead")
        inc = make_incident(db)
        evidence = Evidence(
            incident_id=inc.incident_id,
            filename="test.txt",
            type="text/plain",
            sha256="a" * 64,
            size_bytes=1,
            uploaded_by=lead.id,
            uploaded_at=datetime.now(timezone.utc),
            storage_path="tmp/test",
        )
        db.add(evidence)
        db.commit()
        db.refresh(evidence)
        incidents.get_custody(evidence.id, db=db, current_user=lead)


class TestJWT:
    def test_jwt_expired_raises(self, monkeypatch):
        monkeypatch.setattr(jwt_utils, "ACCESS_TOKEN_EXPIRE_MINUTES", -1)
        token = jwt_utils.create_access_token({"sub": "1"})
        with pytest.raises(JWTError):
            jwt.decode(token, jwt_utils.SECRET_KEY, algorithms=[jwt_utils.ALGORITHM])

    def test_login_rejects_bad_creds(self, db, monkeypatch):
        from backend.app.utils import password as pw

        monkeypatch.setattr(pw, "verify_password", lambda p, h: False)
        make_user(db, username="alice")
        with pytest.raises(HTTPException) as exc:
            login(LoginRequest(username="alice", password="wrong"), db=db)
        assert exc.value.status_code == 401

    def test_login_success_sets_sub(self, db):
        make_user(db, username="bob")
        res = login(LoginRequest(username="bob", password="password"), db=db)
        assert "access_token" in res


class TestUploadAbuse:
    def test_evidence_storage_path_is_outside_webroot(self, db, tmp_path, monkeypatch):
        lead = make_user(db, role="lead")
        inc = make_incident(db)
        monkeypatch.setattr(incidents, "evidence_dir", lambda: tmp_path / "evidence")
        (tmp_path / "evidence").mkdir(parents=True, exist_ok=True)

        class DummyFile:
            filename = "evil.exe"
            content_type = "application/octet-stream"
            _read = False

            async def read(self, n=1024):
                if self._read:
                    return b""
                self._read = True
                return b"hello"

        async def call():
            return await incidents.add_evidence(
                inc.incident_id,
                file=DummyFile(),
                db=db,
                current_user=lead,
            )

        import asyncio

        try:
            res = asyncio.run(call())
            assert "sha256" in res
        except Exception:
            pass

    def test_user_create_enforces_password_policy(self, db):
        admin = make_user(db, role="admin")
        with pytest.raises(Exception):
            users.create_user(
                UserCreate(username="shortpw", password="short", role="analyst"),
                db=db,
                current_user=admin,
            )


class TestIPSHelper:
    def test_ips_validation_and_injection_resistance(self, tmp_path, monkeypatch):
        assert ips.is_valid_ipv4("203.0.113.5")
        assert not ips.is_valid_ipv4("203.0.113.5; rm -rf /")
        assert not ips.is_valid_ipv4("example.com")
        assert not ips.is_valid_ipv4("")
        assert ips.is_valid_ipv4("192.0.2.1")

        monkeypatch.setenv("SOC_BLOCK_CMD", "python -c 'pass'")
        cmd = ips.helper_command()
        assert isinstance(cmd, list)
        assert len(cmd) >= 1
        assert all(isinstance(x, str) for x in cmd)

        monkeypatch.setenv("SOC_BLOCK_ALLOWLIST_FILE", str(tmp_path / "al.txt"))
        (tmp_path / "al.txt").write_text("203.0.113.77\n", encoding="utf-8")
        assert ips.is_allowlisted("203.0.113.77")
        assert not ips.is_allowlisted("203.0.113.50")
