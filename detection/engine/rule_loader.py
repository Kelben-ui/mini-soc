from pathlib import Path
import yaml


def load_rules(rules_dir="rules"):
    rules = []

    for rule_file in Path(rules_dir).glob("*.yaml"):
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
