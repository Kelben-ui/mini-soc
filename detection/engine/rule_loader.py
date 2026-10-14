from pathlib import Path
import yaml

from mini_soc_config import rules_dir as default_rules_dir


def load_rules(rules_dir=None):
    # Default to the absolute rules directory (RULES_DIR env -> <repo>/rules) so
    # loading never depends on the current working directory (task 2.8).  If the
    # configured directory is missing (e.g. a dev .env that points RULES_DIR at a
    # production path), fall back to the rules bundled with the repo.
    if rules_dir is None:
        rules_dir = default_rules_dir()

    rules_path = Path(rules_dir)
    if not rules_path.is_dir():
        rules_path = Path(__file__).resolve().parents[2] / "rules"

    rules = []

    for rule_file in rules_path.glob("*.yaml"):
        with open(rule_file, "r", encoding="utf-8") as file:
            rule = yaml.safe_load(file)

        if not rule:
            continue

        if not isinstance(rule, dict):
            continue

        if rule.get("enabled", True) is False:
            continue

        if "id" not in rule:
            continue

        rules.append(rule)

    return rules
