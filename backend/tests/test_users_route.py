"""User management endpoints and guardrails (phase 7, task 7.9)."""

import uuid

import pytest
from fastapi import HTTPException

from backend.app.models.audit_log import AuditLog
from backend.app.models.user import User
from backend.app.routers.users import (
    create_user,
    list_users,
    reset_password,
    update_user,
)
from backend.app.schemas.user import PasswordReset, UserCreate, UserUpdate


def make_user(db, role="analyst"):
    user = User(
        username=f"user-{role}-{uuid.uuid4().hex[:12]}",
        password_hash="x",
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_create_and_list_user(db):
    admin = make_user(db, role="admin")
    username = f"new-{uuid.uuid4().hex[:10]}"

    created = create_user(
        UserCreate(username=username, password="a-very-long-password", role="analyst"),
        db=db,
        current_user=admin,
    )

    assert created["username"] == username
    assert created["role"] == "analyst"

    users = list_users(db=db, current_user=admin)
    assert any(user["id"] == created["id"] for user in users)

    assert (
        db.query(AuditLog).filter(AuditLog.action == "user_created").first()
        is not None
    )


def test_create_user_rejects_duplicate(db):
    admin = make_user(db, role="admin")
    username = f"dupe-{uuid.uuid4().hex[:10]}"

    create_user(
        UserCreate(username=username, password="a-very-long-password"),
        db=db,
        current_user=admin,
    )

    with pytest.raises(HTTPException) as exc:
        create_user(
            UserCreate(username=username, password="a-very-long-password"),
            db=db,
            current_user=admin,
        )

    assert exc.value.status_code == 409


def test_create_user_rejects_invalid_role(db):
    admin = make_user(db, role="admin")

    with pytest.raises(HTTPException) as exc:
        create_user(
            UserCreate(
                username=f"x-{uuid.uuid4().hex[:8]}",
                password="a-very-long-password",
                role="superuser",
            ),
            db=db,
            current_user=admin,
        )

    assert exc.value.status_code == 400


def test_cannot_change_own_role(db):
    admin = make_user(db, role="admin")

    with pytest.raises(HTTPException) as exc:
        update_user(
            admin.id,
            UserUpdate(role="analyst"),
            db=db,
            current_user=admin,
        )

    assert exc.value.status_code == 400


def test_cannot_demote_last_admin(db):
    # Make the target the only admin in the shared test database.
    for existing in db.query(User).filter(User.role == "admin").all():
        existing.role = "analyst"
    db.commit()

    target = make_user(db, role="admin")
    actor = make_user(db, role="analyst")

    with pytest.raises(HTTPException) as exc:
        update_user(
            target.id,
            UserUpdate(role="analyst"),
            db=db,
            current_user=actor,
        )

    assert exc.value.status_code == 400


def test_reset_password_updates_hash(db):
    admin = make_user(db, role="admin")
    target = make_user(db, role="analyst")

    reset_password(
        target.id,
        PasswordReset(password="another-long-password"),
        db=db,
        current_user=admin,
    )

    db.refresh(target)
    assert target.password_hash != "x"
