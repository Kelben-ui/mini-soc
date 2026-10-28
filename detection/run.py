"""Mini SOC detection loop.

Runs the detection engine continuously and records a checkpoint after each
run so operators can see when detection last advanced and alerts can appear
within a few seconds of a new event (task 2.8).

Run as a module so the repo root is importable::

    python -m detection.run

The engine itself only evaluates events that have not yet been linked to an
alert, so the checkpoint is an observability/resume marker rather than a
correctness requirement.  When no new events have arrived the loop skips the
engine entirely to avoid pointless scans.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from mini_soc_config import get_env, get_float, rules_dir, state_dir  # noqa: E402
from backend.app.database import SessionLocal  # noqa: E402
from backend.app.models.event import Event  # noqa: E402
from detection.engine.engine import run_detection  # noqa: E402
from detection.engine.rule_loader import load_rules  # noqa: E402


def _checkpoint_path() -> str:
    return os.path.join(str(state_dir()), "detection_checkpoint.json")


def _read_checkpoint() -> dict:
    try:
        with open(_checkpoint_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_checkpoint(data: dict) -> None:
    path = _checkpoint_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError:
        logging.exception("could not write detection checkpoint")


def _latest_event_timestamp(db):
    latest = db.query(Event).order_by(Event.timestamp.desc()).first()
    return latest.timestamp if latest else None


def _iso(value) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    rules_path = str(rules_dir())
    poll_seconds = max(
        get_float(
            "DETECTION_POLL_SECONDS",
            get_float("DETECTION_INTERVAL_SECONDS", 2.0),
        ),
        0.5,
    )

    logging.info("Mini SOC detection loop starting")
    logging.info("Rules directory: %s", rules_path)
    logging.info("Polling interval: %ss", poll_seconds)
    logging.info("Checkpoint file: %s", _checkpoint_path())

    checkpoint = _read_checkpoint()
    logging.info("Loaded checkpoint: %s", checkpoint or "(none)")

    while True:
        db = SessionLocal()
        try:
            rules = load_rules(rules_path)
            alert_ids = run_detection(db, rules)
            latest_ts = _latest_event_timestamp(db)
            latest_iso = _iso(latest_ts)
            checkpoint = {
                "last_event_timestamp": latest_iso,
                "last_run": datetime.now(timezone.utc).isoformat(),
                "alerts": alert_ids,
            }
            _write_checkpoint(checkpoint)

            if alert_ids:
                logging.info(
                    "Detection run complete: alert IDs %s",
                    alert_ids,
                )

        except Exception:
            db.rollback()
            logging.exception("Detection run failed")
        finally:
            db.close()

        time.sleep(poll_seconds)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Detection loop stopped")
