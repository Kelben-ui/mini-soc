import os
import time
from datetime import datetime

from backend.app.database import SessionLocal
from detection.engine.engine import run_detection
from detection.engine.rule_loader import load_rules


def main():
    rules_dir = os.getenv("RULES_DIR", "rules")
    interval = int(os.getenv("DETECTION_INTERVAL_SECONDS", "5"))
    checkpoint_file = os.path.join(os.getenv("VAR_DIR", "/var/lib/mini-soc"), "detection_checkpoint.txt")

    print(f"[detection] Starting loop: rules_dir={rules_dir} interval={interval}s")
    rules = load_rules(rules_dir)

    while True:
        try:
            db = SessionLocal()
            try:
                run_detection(db, rules)
            finally:
                db.close()
            # write checkpoint
            try:
                os.makedirs(os.path.dirname(checkpoint_file), exist_ok=True)
                with open(checkpoint_file, "w") as f:
                    f.write(datetime.utcnow().isoformat() + "Z\n")
            except Exception:
                pass
            time.sleep(interval)
        except Exception as e:
            print(f"[detection] error: {e}")
            time.sleep(interval)


if __name__ == "__main__":
    main()
