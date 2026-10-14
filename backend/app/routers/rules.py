"""Detection-rule inventory for the dashboard (task 7.9).

Rules are still authored as YAML under ``rules/``; this endpoint reads them
and enriches each one with live alert statistics (how many alerts it has fired
and when it last fired), so the Rules page can show fire count and MITRE
technique without exposing raw rule internals.
"""

import os

import yaml
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from mini_soc_config import rules_dir

from ..database import get_db
from ..dependencies import get_current_user
from ..models.alert import Alert


router = APIRouter(
    prefix="/api",
    tags=["Rules"]
)

# Absolute by default (RULES_DIR env -> <repo>/rules); never CWD-relative.
RULES_DIR = str(rules_dir())


def _load_rules():
    """Return the rule YAML files that actually define a rule (``id``)."""
    rules = []

    if not os.path.exists(RULES_DIR):
        return rules

    for filename in sorted(os.listdir(RULES_DIR)):
        if not (filename.endswith(".yml") or filename.endswith(".yaml")):
            continue

        file_path = os.path.join(RULES_DIR, filename)

        try:
            with open(file_path, "r") as handle:
                rule_data = yaml.safe_load(handle)
        except Exception as exc:  # pragma: no cover - defensive
            print(f"Error parsing {filename}: {exc}")
            continue

        # Skip helper files such as allowlist.yaml that carry no rule id.
        if isinstance(rule_data, dict) and rule_data.get("id"):
            rules.append(rule_data)

    return rules


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
