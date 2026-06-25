import re
from typing import Any, Dict


def extract_entities(question: str) -> Dict[str, Any]:
    entities: Dict[str, Any] = {}
    employee_match = re.search(r"\bEMP\d{3}\b", question, flags=re.IGNORECASE)
    if employee_match:
        entities["employee_id"] = employee_match.group(0).upper()

    priority_words = {
        "urgent": "HIGH",
        "critical": "HIGH",
        "production": "HIGH",
        "down": "HIGH",
        "blocked": "HIGH",
        "minor": "LOW",
        "low": "LOW",
    }
    lowered = question.lower()
    for word, priority in priority_words.items():
        if word in lowered:
            entities["priority"] = priority
            break

    return entities
