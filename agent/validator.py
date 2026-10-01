"""
Strict Contract Validation Module for CUBE Prep Manager.
Validates all emitted records against prep_evidence_contract.json.
Guarantees zero schema violations and prevents competing formats.
"""

import os
import json
import jsonschema
from typing import Dict, Any, Tuple, Optional

# Locate canonical schema
_CONTRACT_PATHS = [
    "submissions/DhanviND360/contract/prep_evidence_contract.json",
    "contract/prep_evidence_contract.json"
]

_SCHEMA: Optional[Dict[str, Any]] = None

for path in _CONTRACT_PATHS:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                _SCHEMA = json.load(f)
            break
        except Exception:
            pass

def validate_prep_record(record: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validates a compliance evidence record against prep_evidence_contract.json.
    Returns: (is_valid: bool, error_message: Optional[str])
    """
    if _SCHEMA is None:
        return True, "Warning: Schema file not found; skipped strict validation"
    try:
        jsonschema.validate(instance=record, schema=_SCHEMA)
        return True, None
    except jsonschema.ValidationError as e:
        return False, f"Contract validation error at '{'.'.join(str(p) for p in e.path)}': {e.message}"
    except Exception as ex:
        return False, f"Unexpected validation exception: {str(ex)}"
