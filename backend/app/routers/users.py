"""User management for the dashboard (task 7.9).

The project originally created users only from the command line
(``backend/create_user.py``).  The Users page needs full management, so this
router adds create / role-change / password-reset endpoints, all ``admin``
only and audited.

Guardrails:
  * usernames are unique;
  * roles are restricted to analyst/lead/admin;
  * the last remaining admin cannot be demoted;
  * you cannot change your own role (prevents locking yourself out);
  * passwords keep the 12-character minimum used by the CLI.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import require_role
from ..models.audit_log import AuditLog
from ..models.user import User
from ..schemas.user import PasswordReset, UserCreate, UserUpdate
from ..utils.password import hash_password


router = APIRouter(
    prefix="/api",
    tags=["Users"]
)

VALID_ROLES = {"analyst", "lead", "admin"}
ADMIN_ROLE = "admin"


def _serialize(user):
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "created_at": user.created_at,
    }


def _audit(db, current_user, action, resource_id, details):
    db.add(
        AuditLog(
            user_id=current_user.id,
            action=action,
            resource_type="user",
            resource_id=str(resource_id),
            details=details,
            created_at=datetime.now(timezone.utc),
        )
    )


def _admin_count(db):
    return db.query(User).filter(User.role == ADMIN_ROLE).count()


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    current_user=Depends(require_role("lead", "admin")),
):
    users = db.query(User).order_by(User.id.asc()).all()
    return [_serialize(user) for user in users]


@router.post("/users", status_code=201)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    role = payload.role.lower()

    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")

    existing = db.query(User).filter(User.username == payload.username).first()

    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=role,
    )

    db.add(user)
    db.flush()

    _audit(
        db,
        current_user,
        "user_created",
        user.id,
        f"Created user '{user.username}' with role '{role}'",
    )

    db.commit()
    db.refresh(user)

    return _serialize(user)


@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    role = payload.role.lower()

    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id and role != user.role:
        raise HTTPException(
            status_code=400,
            detail="You cannot change your own role",
        )

    if (
        user.role == ADMIN_ROLE
        and role != ADMIN_ROLE
        and _admin_count(db) <= 1
    ):
        raise HTTPException(
            status_code=400,
            detail="Cannot demote the last remaining admin",
        )

    old_role = user.role
    user.role = role

    _audit(
        db,
        current_user,
        "user_role_changed",
        user.id,
        f"Role for '{user.username}' changed from '{old_role}' to '{role}'",
    )

    db.commit()
    db.refresh(user)

    return _serialize(user)


@router.post("/users/{user_id}/password")
def reset_password(
    user_id: int,
    payload: PasswordReset,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin")),
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password_hash = hash_password(payload.password)

    _audit(
        db,
        current_user,
        "user_password_reset",
        user.id,
        f"Password reset for '{user.username}'",
    )

    db.commit()

    return {"id": user.id, "username": user.username, "message": "Password updated"}
