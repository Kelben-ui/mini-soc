"""Attack-chain correlation endpoints (task 7.7, spec §4).

The detection engine stamps related alerts with a shared ``chain_id`` (spec
§4.2).  This router exposes those chains to the dashboard so an analyst can
review the correlated activity as a kill-chain timeline and promote the whole
chain to a single incident with one click (spec §4.3 / §19).
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import require_role
from ..models.alert import Alert
from ..models.audit_log import AuditLog
from ..models.incident import Incident


router = APIRouter(
    prefix="/api",
    tags=["Attack Chains"],
)

# Highest first; used to derive a chain's overall severity.
SEVERITY_ORDER = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}


def _as_utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _max_severity(alerts):
    best = None

    for alert in alerts:
        severity = (alert.severity or "").upper()
        if not severity:
            continue
        if best is None or SEVERITY_ORDER.get(severity, 0) > SEVERITY_ORDER.get(
            best, 0
        ):
            best = severity

    return best


def _serialize_alert(alert):
    return {
        "alert_id": alert.alert_id,
        "rule_id": alert.rule_id,
        "title": alert.title,
        "severity": alert.severity,
        "status": alert.status,
        "category": alert.category,
        "mitre": alert.mitre,
        "src_ip": alert.src_ip,
        "dst_ip": alert.dst_ip,
        "dst_host": alert.dst_host,
        "count": alert.count,
        "first_seen": alert.first_seen,
        "last_seen": alert.last_seen,
        "incident_id": alert.incident_id,
    }


def _group_chains(db):
    """Group every chained alert by ``chain_id`` (oldest first)."""
    alerts = (
        db.query(Alert)
        .filter(Alert.chain_id.isnot(None))
        .order_by(Alert.first_seen.asc(), Alert.alert_id.asc())
        .all()
    )

    groups = {}

    for alert in alerts:
        groups.setdefault(alert.chain_id, []).append(alert)

    return groups


def _summarize(chain_id, alerts):
    first_seen = min(
        (_as_utc(a.first_seen) for a in alerts if a.first_seen),
        default=None,
    )
    last_seen = max(
        (_as_utc(a.last_seen) for a in alerts if a.last_seen),
        default=None,
    )

    incident_ids = {a.incident_id for a in alerts if a.incident_id}
    incident_id = next(iter(incident_ids)) if incident_ids else None

    categories = sorted({a.category for a in alerts if a.category})
    src_ips = sorted({a.src_ip for a in alerts if a.src_ip})
    hosts = sorted({a.dst_host for a in alerts if a.dst_host})

    return {
        "chain_id": chain_id,
        "alert_count": len(alerts),
        "categories": categories,
        "src_ips": src_ips,
        "affected_hosts": hosts,
        "max_severity": _max_severity(alerts),
        "first_seen": first_seen,
        "last_seen": last_seen,
        "incident_id": incident_id,
        "promoted": incident_id is not None,
        "alert_ids": [a.alert_id for a in alerts],
    }


@router.get("/chains")
def get_chains(
    only_unpromoted: bool = Query(default=False),
    since: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(require_role("analyst", "lead", "admin")),
):
    """List correlated attack chains, most recent first."""
    if since is not None:
        since = _as_utc(since)

    summaries = []

    for chain_id, alerts in _group_chains(db).items():
        summary = _summarize(chain_id, alerts)

        if only_unpromoted and summary["promoted"]:
            continue

        if since is not None and (
            summary["last_seen"] is None or summary["last_seen"] < since
        ):
            continue

        summaries.append(summary)

    summaries.sort(
        key=lambda item: item["last_seen"] or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    return {"items": summaries, "total": len(summaries)}


@router.get("/chains/{chain_id}")
def get_chain(
    chain_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("analyst", "lead", "admin")),
):
    """Return a single chain plus its alerts in kill-chain order."""
    alerts = _group_chains(db).get(chain_id)

    if not alerts:
        raise HTTPException(status_code=404, detail="Attack chain not found")

    summary = _summarize(chain_id, alerts)
    summary["alerts"] = [_serialize_alert(alert) for alert in alerts]

    return summary


def _next_incident_code(db):
    last_incident = (
        db.query(Incident).order_by(Incident.incident_id.desc()).first()
    )
    next_number = last_incident.incident_id + 1 if last_incident else 1
    return f"INC-{next_number:04d}"


@router.post("/chains/{chain_id}/promote")
def promote_chain(
    chain_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("analyst", "lead", "admin")),
):
    """Create one incident from every alert in the chain (spec §4.3).

    The incident creation and the alert links happen in a single transaction so
    promoting is atomic.
    """
    alerts = _group_chains(db).get(chain_id)

    if not alerts:
        raise HTTPException(status_code=404, detail="Attack chain not found")

    if any(alert.incident_id for alert in alerts):
        raise HTTPException(
            status_code=409,
            detail="Attack chain has already been promoted to an incident",
        )

    categories = sorted({a.category for a in alerts if a.category})
    src_ips = sorted({a.src_ip for a in alerts if a.src_ip})
    hosts = sorted({a.dst_host for a in alerts if a.dst_host})

    label = ", ".join(categories) if categories else "correlated activity"
    title = f"Attack chain {chain_id}: {label}"

    incident = Incident(
        incident_code=_next_incident_code(db),
        title=title[:255],
        description=(
            f"Promoted from attack chain {chain_id} "
            f"({len(alerts)} correlated alerts)."
        ),
        severity=_max_severity(alerts) or "MEDIUM",
        status="open",
        category=categories[0] if categories else None,
        affected_hosts=hosts or None,
        source_ips=src_ips or None,
        created_at=datetime.now(timezone.utc),
    )

    db.add(incident)
    db.flush()

    for alert in alerts:
        alert.incident_id = incident.incident_id

    audit = AuditLog(
        user_id=current_user.id,
        action="attack_chain_promoted",
        resource_type="attack_chain",
        resource_id=str(chain_id),
        details=(
            f"Chain {chain_id} with {len(alerts)} alerts promoted to "
            f"{incident.incident_code}"
        ),
        created_at=datetime.now(timezone.utc),
    )

    db.add(audit)
    db.commit()
    db.refresh(incident)

    return {
        "chain_id": chain_id,
        "incident_id": incident.incident_id,
        "incident_code": incident.incident_code,
        "title": incident.title,
        "severity": incident.severity,
        "status": incident.status,
        "alert_count": len(alerts),
    }
