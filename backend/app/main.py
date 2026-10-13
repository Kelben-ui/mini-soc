from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session
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


@app.on_event("startup")
def ensure_dirs():
    path = evidence_dir()
    path.mkdir(parents=True, exist_ok=True)


@app.get("/")
def root():
    return {
        "message": "Mini SOC Platform API is running"
    }


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
