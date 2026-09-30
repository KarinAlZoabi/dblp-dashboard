from __future__ import annotations

import json
from functools import lru_cache

from google.genai import types

from .client import get_gemini_client
from .config import FALLBACK_GENERATION_MODEL, PRIMARY_GENERATION_MODEL
from .parsing import fast_plan


ALLOWED_INTENTS = {
    "dataset_count",
    "author_publications",
    "author_publication_count",
    "publication_authors",
    "publication_venue",
    "publication_pages",
    "publication_page_count",
    "publication_year",
    "publication_volume",
    "publication_number",
    "publication_publisher",
    "publication_ee",
    "publication_details",
    "top_coauthors",
    "topic_search",
}


def _sanitize(plan: dict, question: str) -> dict:
    if not isinstance(plan, dict) or plan.get("intent") not in ALLOWED_INTENTS:
        return {
            "intent": "topic_search",
            "search_text": question.strip(),
            "limit": None,
        }

    result = {
        "intent": plan.get("intent"),
        "title": plan.get("title"),
        "author": plan.get("author"),
        "search_text": plan.get("search_text"),
        "year_from": plan.get("year_from"),
        "year_to": plan.get("year_to"),
        "limit": plan.get("limit"),
        "all_results": bool(plan.get("all_results", False)),
    }

    for field in ("year_from", "year_to", "limit"):
        value = result.get(field)
        if value is not None:
            try:
                result[field] = int(value)
            except (TypeError, ValueError):
                result[field] = None

    if result.get("limit") is not None:
        result["limit"] = max(1, min(result["limit"], 100))

    return result


@lru_cache(maxsize=512)
def _llm_plan(question: str) -> dict:
    prompt = f"""
You are a query planner for a DBLP bibliographic assistant.
Return ONLY a JSON object. Never answer the factual question yourself.

Allowed intents:
- dataset_count
- author_publications
- author_publication_count
- publication_authors
- publication_venue
- publication_pages
- publication_page_count
- publication_year
- publication_volume
- publication_number
- publication_publisher
- publication_ee
- publication_details
- top_coauthors
- topic_search

Fields:
- intent
- title
- author
- search_text
- year_from
- year_to
- limit
- all_results

Use structured intents for exact bibliographic facts. Use topic_search only for
conceptual discovery where the user is looking for papers about a subject.
Preserve DBLP author disambiguation suffixes. Extract explicit year filters.
If the user asks for all/every results, set all_results=true.
For page count/how many pages, use publication_page_count, not publication_pages.
Remove conversational command wording from extracted title/search_text when it
is clearly not part of the bibliographic entity.

User question:
{question}
"""

    client = get_gemini_client()
    last_error = None

    for model in (PRIMARY_GENERATION_MODEL, FALLBACK_GENERATION_MODEL):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0,
                    response_mime_type="application/json",
                    max_output_tokens=350,
                ),
            )
            raw = (response.text or "").strip()
            return _sanitize(json.loads(raw), question)
        except Exception as exc:
            last_error = exc

    # A planner outage should degrade to semantic search, not fail the chat.
    return {
        "intent": "topic_search",
        "search_text": question.strip(),
        "limit": None,
        "planner_error": type(last_error).__name__ if last_error else "unknown",
    }


def plan_question(question: str) -> dict:
    question = (question or "").strip()
    local = fast_plan(question)
    if local is not None:
        return _sanitize(local, question)
    return _llm_plan(question)
