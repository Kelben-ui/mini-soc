from fastapi import APIRouter, Depends, HTTPException
import os
import yaml

from mini_soc_config import rules_dir

from ..dependencies import get_current_user

router = APIRouter(
    prefix="/api",
    tags=["Rules"]
)

# Absolute by default (RULES_DIR env -> <repo>/rules); never CWD-relative.
RULES_DIR = str(rules_dir())

@router.get("/rules")
def get_rules(
    current_user=Depends(get_current_user),
):
    rules = []
    if not os.path.exists(RULES_DIR):
        return []
    
    for filename in os.listdir(RULES_DIR):
        if filename.endswith(".yml") or filename.endswith(".yaml"):
            file_path = os.path.join(RULES_DIR, filename)
            try:
                with open(file_path, "r") as f:
                    rule_data = yaml.safe_load(f)
                    if rule_data:
                        rules.append(rule_data)
            except Exception as e:
                print(f"Error parsing {filename}: {e}")
                
    return rules
