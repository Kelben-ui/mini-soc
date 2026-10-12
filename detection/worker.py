import logging
import os
import time

from backend.app.database import SessionLocal
from detection.engine.engine import run_detection
from detection.engine.rule_loader import load_rules


POLL_SECONDS = max(
    float(os.getenv("DETECTION_POLL_SECONDS", "2")),
    0.5,
)
RULES_DIR = os.getenv("DETECTION_RULES_DIR", "rules")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    logging.info("Mini SOC detection worker starting")
    logging.info("Rules directory: %s", RULES_DIR)
    logging.info("Polling interval: %s seconds", POLL_SECONDS)

    while True:
        db = SessionLocal()

        try:
            rules = load_rules(RULES_DIR)
            alert_ids = run_detection(db, rules)

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

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Detection worker stopped")
