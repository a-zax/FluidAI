RESTRICTED_PATTERNS = [
    "salary",
    "password",
    "api key",
    "secret",
    "ignore previous instructions",
    "drop database",
    "delete all",
]


def contains_forbidden_request(question: str) -> bool:
    lowered = question.lower()
    return any(pattern in lowered for pattern in RESTRICTED_PATTERNS)
