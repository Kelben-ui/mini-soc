"""Agent registration + heartbeat (task 3.7).

The log agent POSTs ``/api/agents/heartbeat`` periodically; the endpoint
upserts a row in the ``agents`` table with the agent's identity, last-seen
time and the current IDS service status.  ``/api/stats`` then exposes that
health to the dashboard Overview.

Authentication reuses the shared ingest API key (``X-API-Key``) because the
caller is a service, not a browser session.
"""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import verify_ingest_api_key
from ..models.agent import Agent
from ..schemas.agent import AgentHeartbeat


router = APIRouter(
    prefix="/api",
    tags=["Agents"],
)


@router.post("/agents/heartbeat")
def heartbeat(
    payload: AgentHeartbeat,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_ingest_api_key),
):
    now = datetime.now(timezone.utc)

    agent = db.query(Agent).filter(Agent.name == payload.name).first()

    if agent is None:
        agent = Agent(name=payload.name)
        db.add(agent)

    details = {}

    if payload.ids is not None:
        details["ids"] = payload.ids.model_dump()

    agent.host = payload.host
    agent.status = payload.status
    agent.last_heartbeat = now
    agent.details = json.dumps(details)

    db.commit()

    return {
        "status": "ok",
        "agent": agent.name,
        "last_heartbeat": now.isoformat(),
    }
