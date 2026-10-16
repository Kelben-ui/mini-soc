"""Detection-rule inventory for the dashboard (task 7.9).

Rules are still authored as YAML under ``rules/``; this endpoint reads them
and enriches each one with live alert statistics (how many alerts it has fired
and when it last fired), so the Rules page can show fire count and MITRE
technique without exposing raw rule internals.

Loading goes through ``detection.engine.rule_loader.load_rules`` so the page and
the detection engine agree on where the rules live (including the fallback to
``<repo>/rules`` when ``RULES_DIR`` points somewhere that does not exist).
``include_disabled=True`` keeps ``enabled: false`` rules in the list so the page
can grey them out instead of hiding them.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from detection.engine.rule_loader import load_rules

from ..database import get_db
from ..dependencies import get_current_user
from ..models.alert import Alert


router = APIRouter(
    prefix="/api",
    tags=["Rules"]
)


def _load_rules():
    """Return every rule YAML file that defines a rule (``id``), disabled too."""
    return load_rules(include_disabled=True)


def _alert_stats(db):
    counts = dict(
        db.query(Alert.rule_id, func.count(Alert.alert_id))
        .group_by(Alert.rule_id)
        .all()
    )

    last_fired = dict(
        db.query(Alert.rule_id, func.max(Alert.last_seen))
        .group_by(Alert.rule_id)
        .all()
    )

    return counts, last_fired


@router.get("/rules")
def get_rules(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    counts, last_fired = _alert_stats(db)

    enriched = []

    for rule in _load_rules():
        rule_id = rule.get("id")

        enriched.append(
            {
                "id": rule_id,
                "name": rule.get("name"),
                "severity": rule.get("severity"),
                "category": rule.get("category"),
                "enabled": rule.get("enabled", True),
                "mitre": rule.get("mitre"),
                "alerts_count": counts.get(rule_id, 0),
                "last_fired": last_fired.get(rule_id),
            }
        )

    return enriched
