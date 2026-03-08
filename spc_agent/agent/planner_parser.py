
from __future__ import annotations
import json

def parse_planner_output(raw_text: str) -> dict:
    try:
        obj = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Planner output is not valid JSON: {e}") from e

    if not isinstance(obj, dict):
        raise ValueError("Planner output must be a JSON object")

    return obj
