from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session
import sys
from pathlib import Path

# Add project root to sys.path to import mini_soc_config
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from mini_soc_config import evidence_dir, get_list
from .dependencies import require_role 
from .database import get_db
from .models.user import User
from .routers.auth import router as auth_router
from .routers.ingest import router as ingest_router
from .routers.events import router as events_router
from .routers.alerts import router as alerts_router
from .routers.incidents import router as incidents_router
from .routers.rules import router as rules_router
from .routers.stats import router as stats_router
from .routers.agents import router as agents_router
from .routers.actions import router as actions_router
from .routers.chains import router as chains_router
from .routers.users import router as users_router
from .routers.reports import router as reports_router
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI(
    title="Mini SOC Platform API",
    description="Backend API for the Mini SOC cybersecurity incident response platform",
    version="1.0.0",
)

allowed_origins = get_list(
    "CORS_ORIGINS",
    [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

app.include_router(auth_router)
app.include_router(ingest_router)
app.include_router(events_router)
app.include_router(alerts_router)
app.include_router(incidents_router)
app.include_router(rules_router)
app.include_router(stats_router)
app.include_router(agents_router)
app.include_router(actions_router)
app.include_router(chains_router)
app.include_router(users_router)
app.include_router(reports_router)


# --- Security headers (task 9.2) -------------------------------------------
# Defence in depth on top of the ORM (SQLi) and React/`esc` escaping (XSS):
# clickjacking, MIME sniffing and referrer leakage are all disabled, and every
# non-docs response carries a locked-down Content-Security-Policy.  `style-src
# 'unsafe-inline'` is required by the generated reports (embedded <style>) and
# by chart inline styles; scripts are still `default-src 'none'`.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "0",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=(), usb=(), payment=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}

API_CSP = (
    "default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
    "base-uri 'none'; frame-ancestors 'none'; form-action 'none'; "
    "object-src 'none'; script-src 'none'"
)

_DOCS_PREFIXES = ("/docs", "/redoc", "/openapi.json")


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)

    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)

    path = request.url.path

    if not path.startswith(_DOCS_PREFIXES):
        response.headers.setdefault("Content-Security-Policy", API_CSP)

    return response


@app.on_event("startup")
def ensure_dirs():
    path = evidence_dir()
    path.mkdir(parents=True, exist_ok=True)


@app.get("/")
def root():
    return {
        "message": "Mini SOC Platform API is running"
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/users")
def get_users(
    db: Session = Depends(get_db),
    current_user = Depends(require_role("lead", "admin")) 
):
    users = db.query(User).all()

    return [
        {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "created_at": user.created_at,
        }
        for user in users
    ]


# --- Rate limiting (security hardening) -------------------------------------
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded

    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
except Exception:
    limiter = None


# Request size limit middleware (basic protection)
@app.middleware("http")
async def limit_request_size(request, call_next):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > 25 * 1024 * 1024:  # 25MB limit
                from fastapi.responses import JSONResponse
                return JSONResponse(status_code=413, content={"detail": "Request too large"})
        except ValueError:
            pass
    response = await call_next(request)
    return response
