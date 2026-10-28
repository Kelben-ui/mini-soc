from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.user import User
from ..schemas.auth import LoginRequest
from ..utils.password import verify_password
from ..utils.jwt import create_access_token


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
)


@router.post("/login")
def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(
        User.username == login_data.username
    ).first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    if not verify_password(
        login_data.password,
        user.password_hash
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="This account has been deactivated"
        )

    token = create_access_token({
        "sub": str(user.id),
        "username": user.username,
        "role": user.role
    })

    return {
        "access_token": token,
        "token_type": "bearer"
    }


# Apply rate limiting if available
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    from fastapi import Request

    limiter = Limiter(key_func=get_remote_address)

    @router.post("/login/rate-limited")
    @limiter.limit("5/minute")
    async def login_rate_limited(request: Request, login_req: LoginRequest, db: Session = Depends(get_db)):
        return login(login_req, db)
except Exception:
    pass
