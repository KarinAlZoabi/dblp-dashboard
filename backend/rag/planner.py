from __future__ import annotations

import json
from functools import lru_cache

from google.genai import types

from .client import get_gemini_client
from .config import (
    FALLBACK_GENERATION_MODEL,
    PRIMARY_GENERATION_MODEL,
)
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

ALLOWED_SOURCE_SELECTORS = {
    "latest",
    "oldest",
}


def _sanitize(
    plan: dict,
    question: str,
) -> dict:
    if (
        not isinstance(plan, dict)
        or plan.get("intent") not in ALLOWED_INTENTS
    ):
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
        "all_results": bool(
            plan.get("all_results", False)
        ),
        "source_index": plan.get("source_index"),
        "source_selector": plan.get("source_selector"),
        "reuse_previous_year": bool(
            plan.get("reuse_previous_year", False)
        ),
        "venue": plan.get("venue"),
        "pub_type": plan.get("pub_type"),
        "sort_order": plan.get("sort_order"),
    }

    for field in (
        "year_from",
        "year_to",
        "limit",
        "source_index",
    ):
        value = result.get(field)

        if value is not None:
            try:
                result[field] = int(value)
            except (TypeError, ValueError):
                result[field] = None

    if result.get("limit") is not None:
        result["limit"] = max(
            1,
            min(result["limit"], 100),
        )

    if result.get("source_index") is not None:
        result["source_index"] = max(
            1,
            min(result["source_index"], 20),
        )

    selector = result.get("source_selector")

    if selector not in ALLOWED_SOURCE_SELECTORS:
        result["source_selector"] = None

    if result.get("sort_order") not in {None, "latest", "oldest"}:
        result["sort_order"] = None

    pub_type = result.get("pub_type")
    type_aliases = {
        "conference": "inproceedings",
        "conference paper": "inproceedings",
        "inproceedings": "inproceedings",
        "journal": "article",
        "journal article": "article",
        "article": "article",
        "book": "book",
        "phd thesis": "phdthesis",
        "phdthesis": "phdthesis",
        "master thesis": "mastersthesis",
        "mastersthesis": "mastersthesis",
    }
    if pub_type is not None:
        result["pub_type"] = type_aliases.get(str(pub_type).casefold())

    if result.get("venue") is not None:
        result["venue"] = str(result["venue"]).strip() or None

    return result


def _context_is_empty(context: dict | None) -> bool:
    if not context:
        return True

    return not any([
        context.get("last_title"),
        context.get("last_author"),
        context.get("last_intent"),
        context.get("previous_plan"),
        context.get("recent_results"),
    ])


@lru_cache(maxsize=512)
def _llm_plan_cached(
    question: str,
    context_json: str,
) -> dict:
    context = (
        json.loads(context_json)
        if context_json
        else {}
    )

    prompt = f"""
You are a QUERY PLANNER for a DBLP bibliographic assistant.

Your ONLY job is to understand the user's language and return a structured
query plan as JSON.

You MUST NOT answer any DBLP factual question yourself.
Python/SQLite functions will perform every factual lookup, count, filter,
sort, comparison, and calculation after your plan is returned.

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

Allowed fields:
- intent
- title
- author
- search_text
- year_from
- year_to
- limit
- all_results
- source_index
- source_selector
- reuse_previous_year
- venue
- pub_type
- sort_order

CONVERSATION CONTEXT:
{json.dumps(context, ensure_ascii=False)}

CONTEXT RULES:
1. The conversation context contains VERIFIED information from previous DBLP
   tool results. Use it only to resolve what the user is referring to.
2. Resolve pronouns and elliptical follow-ups naturally:
   "it", "that paper", "that author", "they", "what about 2023?",
   "and the year after?", etc.
3. If the user refers to a numbered previous result such as "the second one",
   return source_index=2. Do not invent a title.
4. If the user refers to "the newest/latest one", use
   source_selector="latest". For "oldest/earliest one", use
   source_selector="oldest". Python will choose the record.
5. If a publication fact question refers to the previously discussed paper,
   choose the correct publication_* intent. It is acceptable to omit title;
   Python will fill it from verified state.
6. If an author question refers to the previously discussed author, choose the
   appropriate author_* intent. It is acceptable to omit author; Python will
   fill it from verified state.
7. If the user says "that year", "same year", or asks to keep the previous
   year filter, set reuse_previous_year=true.
8. For "what about 2023?" after an author-publication question, preserve the
   previous author/intent and set year_from=2023 and year_to=2023.
9. For a follow-up topic refinement, expand search_text enough to preserve the
   previous research topic when needed. Example:
   previous topic "federated learning", user "what about privacy?"
   -> search_text="federated learning privacy".
10. Never infer bibliographic facts that are not in the context.

GENERAL ROUTING RULES:
11. Use structured intents for exact bibliographic facts.
12. Use topic_search only for conceptual discovery where the user wants papers
    about a research subject.
13. Preserve DBLP author disambiguation suffixes such as 0002.
14. Extract explicit year filters/ranges.
15. If the user asks for all/every results, set all_results=true.
16. "how many pages" / "page count" -> publication_page_count.
17. "page range" / "what pages" -> publication_pages.
18. "who wrote/authored" -> publication_authors.
19. journal/conference/venue -> publication_venue when the user asks WHERE a named publication appeared.
20. For topic/author searches filtered to a venue, put the venue name in venue.
21. For explicit publication-type filters, use pub_type. Examples:
    "conference papers" -> "inproceedings"; "journal articles" -> "article".
22. For an author's latest/newest/most recent publication, use
    intent="author_publications", limit=1, sort_order="latest".
    For earliest/oldest/first, use sort_order="oldest".
23. Respect requested result counts such as "top 3" or "show me 7" by setting limit.
24. Return ONLY one JSON object. No explanation and no answer text.

USER MESSAGE:
{question}
"""

    last_error = None

    try:
        client = get_gemini_client()
    except Exception as exc:
        return {
            "intent": "topic_search",
            "search_text": question.strip(),
            "limit": None,
            "_planner": "failed",
            "planner_error": type(exc).__name__,
        }

    for model in (
        PRIMARY_GENERATION_MODEL,
        FALLBACK_GENERATION_MODEL,
    ):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0,
                    response_mime_type="application/json",
                    max_output_tokens=400,
                ),
            )

            raw = (response.text or "").strip()
            parsed = json.loads(raw)
            result = _sanitize(parsed, question)
            result["_planner"] = "llm"
            return result

        except Exception as exc:
            last_error = exc

    return {
        "intent": "topic_search",
        "search_text": question.strip(),
        "limit": None,
        "_planner": "failed",
        "planner_error": (
            type(last_error).__name__
            if last_error
            else "unknown"
        ),
    }


def plan_question(
    question: str,
    context: dict | None = None,
) -> dict:
    """
    Fast path:
        obvious standalone question -> local deterministic parser

    Flexible path:
        ambiguous/new wording or conversational follow-up -> Gemini planner

    Gemini only interprets language. It never supplies DBLP facts.
    """
    question = (question or "").strip()

    local = fast_plan(question)

    if local is not None:
        result = _sanitize(local, question)
        result["_planner"] = "local"
        return result

    context_json = ""

    if not _context_is_empty(context):
        context_json = json.dumps(
            context,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    return _llm_plan_cached(
        question,
        context_json,
    )
