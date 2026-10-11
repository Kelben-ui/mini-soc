from fastapi import APIRouter, Depends, HTTPException
import os
import yaml

from ..dependencies import get_current_user

router = APIRouter(
    prefix="/api",
    tags=["Rules"]
)

# Adjust this path to point to wherever your YAML rules files are stored on disk
RULES_DIR = os.getenv("RULES_DIR", "../../rules") 

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
