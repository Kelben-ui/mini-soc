from backend.app.database import SessionLocal

from detection.engine.engine import run_detection
from detection.engine.rule_loader import load_rules


def main():
    rules = load_rules()

    print(f"Loaded {len(rules)} detection rule(s).")

    db = SessionLocal()

    try:
        alert_ids = run_detection(db, rules)

        print(
            f"Detection complete. "
            f"Alerts created/updated: {alert_ids}"
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()
