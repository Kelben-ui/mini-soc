"""Backend agent heartbeat + stats health (task 3.7).

Calls the route functions directly (the venv's starlette wants ``httpx2`` and
TestClient is unavailable); the 401 authentication behaviour is covered by
exercising ``verify_ingest_api_key`` directly.
"""

import pytest
from fastapi import HTTPException, Response

from backend.app.dependencies import verify_ingest_api_key
from backend.app.models.agent import Agent
from backend.app.routers.agents import heartbeat
from backend.app.routers.stats import get_stats
from backend.app.schemas.agent import AgentHeartbeat


def test_heartbeat_requires_api_key():
    with pytest.raises(HTTPException) as exc:
        verify_ingest_api_key(None)

    assert exc.value.status_code == 401


def test_heartbeat_upserts_agent(db):
    result = heartbeat(
        AgentHeartbeat(
            name="log-agent",
            host="host-a",
            status="online",
            ids={"service": "mini-soc-ids", "status": "active"},
        ),
        db=db,
        _=True,
    )

    assert result["agent"] == "log-agent"

    db.expire_all()

    agent = db.query(Agent).filter(Agent.name == "log-agent").first()

    assert agent is not None
    assert agent.host == "host-a"
    assert agent.status == "online"
    assert agent.last_heartbeat is not None
    assert '"ids"' in agent.details


def test_stats_reports_agent_and_ids_health(db):
    heartbeat(
        AgentHeartbeat(
            name="log-agent",
            host="host-a",
            status="online",
            ids={"service": "mini-soc-ids", "status": "active"},
        ),
        db=db,
        _=True,
    )

    db.expire_all()

    stats = get_stats(db=db, current_user=None, response=Response())

    assert stats["ids_status"] == "active"
    assert stats["agents_online"] == 1

    rows = [agent for agent in stats["agents"] if agent["name"] == "log-agent"]

    assert len(rows) == 1
    assert rows[0]["status"] == "online"
    assert rows[0]["ids_status"] == "active"