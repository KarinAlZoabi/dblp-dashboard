"""Small deterministic query router for the first chatbot milestone."""

import re


def route(question: str) -> dict:
    q = question.lower().strip()

    if re.search(r"\bhow many\b|\bcount\b|\bnumber of\b|\bmost\b|\btop \d+\b|\btrend\b", q):
        return {"intent": "analytical"}

    if re.search(r"\bby\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\b", question):
        return {"intent": "exact_lookup"}

    if re.search(r"\bfind\b|\bshow\b|\blist\b|\bsearch\b", q):
        return {"intent": "hybrid_search"}

    return {"intent": "semantic_search"}
