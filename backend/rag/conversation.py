from __future__ import annotations

import re
import threading
import time
import uuid
from dataclasses import dataclass, field


# Small, ephemeral conversation state for the local/demo backend.
# It resets when Uvicorn restarts.
SESSION_TTL_SECONDS = 2 * 60 * 60
MAX_SESSIONS = 1000
MAX_REMEMBERED_SOURCES = 20
MAX_CONTEXT_SOURCES = 10


@dataclass
class ConversationState:
    last_title: str | None = None
    last_author: str | None = None
    last_sources: list[dict] = field(default_factory=list)
    last_intent: str | None = None
    last_plan: dict = field(default_factory=dict)
    last_question: str | None = None
    updated_at: float = field(default_factory=time.monotonic)


_sessions: dict[str, ConversationState] = {}
_lock = threading.RLock()


PUBLICATION_INTENTS = {
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
}

AUTHOR_INTENTS = {
    "author_publications",
    "author_publication_count",
    "author_summary",
    "top_coauthors",
}


def _cleanup_locked(now: float) -> None:
    expired = [
        session_id
        for session_id, state in _sessions.items()
        if now - state.updated_at > SESSION_TTL_SECONDS
    ]

    for session_id in expired:
        _sessions.pop(session_id, None)

    if len(_sessions) <= MAX_SESSIONS:
        return

    oldest = sorted(
        _sessions.items(),
        key=lambda item: item[1].updated_at,
    )

    for session_id, _ in oldest[: len(_sessions) - MAX_SESSIONS]:
        _sessions.pop(session_id, None)


def get_or_create_session(
    session_id: str | None,
) -> tuple[str, ConversationState]:
    now = time.monotonic()

    with _lock:
        _cleanup_locked(now)

        if session_id and session_id in _sessions:
            state = _sessions[session_id]
            state.updated_at = now
            return session_id, state

        new_id = uuid.uuid4().hex
        state = ConversationState(updated_at=now)
        _sessions[new_id] = state
        return new_id, state


def clear_session(session_id: str | None) -> None:
    if not session_id:
        return

    with _lock:
        _sessions.pop(session_id, None)


def planner_context(state: ConversationState) -> dict:
    """
    Give the LLM planner only compact VERIFIED conversation state.

    We do NOT send a giant raw chat transcript. The model only receives the
    entities/filters/results it may need to resolve phrases such as:
      - "it"
      - "that author"
      - "the second one"
      - "what about 2023?"
      - "the newest one"
    """
    previous_plan = {
        key: state.last_plan.get(key)
        for key in (
            "intent",
            "title",
            "author",
            "search_text",
            "year_from",
            "year_to",
            "limit",
            "all_results",
            "venue",
            "pub_type",
            "sort_order",
        )
        if state.last_plan.get(key) is not None
    }

    recent_results = []

    for index, source in enumerate(
        state.last_sources[:MAX_CONTEXT_SOURCES],
        start=1,
    ):
        recent_results.append({
            "index": index,
            "title": source.get("title"),
            "authors": source.get("authors", []),
            "year": source.get("year"),
            "venue": source.get("venue"),
            "type": source.get("type"),
            "key": source.get("key"),
        })

    return {
        "last_question": state.last_question,
        "last_intent": state.last_intent,
        "last_title": state.last_title,
        "last_author": state.last_author,
        "previous_plan": previous_plan,
        "recent_results": recent_results,
    }


def _select_source(
    state: ConversationState,
    source_index: int | None = None,
    source_selector: str | None = None,
) -> dict | None:
    sources = state.last_sources

    if not sources:
        return None

    if source_index is not None:
        index = source_index - 1
        if 0 <= index < len(sources):
            return sources[index]
        return None

    selector = (source_selector or "").casefold()

    with_year = [
        source
        for source in sources
        if isinstance(source.get("year"), int)
    ]

    if selector == "latest" and with_year:
        return max(
            with_year,
            key=lambda source: source["year"],
        )

    if selector == "oldest" and with_year:
        return min(
            with_year,
            key=lambda source: source["year"],
        )

    return None


def apply_context_to_plan(
    plan: dict,
    state: ConversationState,
) -> tuple[dict, dict]:
    """
    Deterministically fill entity references after the LLM has interpreted
    the user's language.

    The LLM says WHAT the user means. Python chooses the concrete verified
    DBLP entity from stored session state.
    """
    plan = dict(plan)
    used = {}

    source = _select_source(
        state,
        source_index=plan.get("source_index"),
        source_selector=plan.get("source_selector"),
    )

    if source:
        title = source.get("title")

        if title and not plan.get("title"):
            plan["title"] = title
            used["title"] = title

        used["source"] = {
            "title": source.get("title"),
            "year": source.get("year"),
            "venue": source.get("venue"),
            "key": source.get("key"),
        }

    intent = plan.get("intent")

    if (
        intent in PUBLICATION_INTENTS
        and not plan.get("title")
        and state.last_title
    ):
        plan["title"] = state.last_title
        used["title"] = state.last_title

    if (
        intent in AUTHOR_INTENTS
        and not plan.get("author")
        and state.last_author
    ):
        plan["author"] = state.last_author
        used["author"] = state.last_author

    # Optional planner instruction: reuse a previous year filter.
    if plan.get("reuse_previous_year"):
        previous_from = state.last_plan.get("year_from")
        previous_to = state.last_plan.get("year_to")

        if plan.get("year_from") is None and previous_from is not None:
            plan["year_from"] = previous_from
            used["year_from"] = previous_from

        if plan.get("year_to") is None and previous_to is not None:
            plan["year_to"] = previous_to
            used["year_to"] = previous_to

    return plan, used


# ---------------------------------------------------------------------
# Emergency fallback only
# ---------------------------------------------------------------------
# The functions below are NOT the primary conversation system anymore.
# They are retained only for graceful degradation if the remote planner
# becomes unavailable.


_ORDINALS = {
    "first": 0,
    "1st": 0,
    "second": 1,
    "2nd": 1,
    "third": 2,
    "3rd": 2,
    "fourth": 3,
    "4th": 3,
    "fifth": 4,
    "5th": 4,
}


def _quoted_title(title: str) -> str:
    return '"' + title.replace('"', '\\"') + '"'


def resolve_followup_fallback(
    question: str,
    state: ConversationState,
) -> tuple[str, dict]:
    """
    Emergency-only conversational rewrite.

    Gemini remains the primary interpreter. These few generic rewrites exist
    only so a temporary planner/API outage does not break obvious references.
    """
    original = (question or "").strip()
    rewritten = original
    used = {}

    # "What about 2023?" after an author query.
    year_followup = re.fullmatch(
        r"\s*(?:(?:and\s+)?(?:what|how)\s+about\s+|(?:and\s+)?in\s+)?"
        r"((?:19|20)\d{2})\s*[?.!]*\s*",
        original,
        flags=re.IGNORECASE,
    )
    if year_followup and state.last_author:
        year = int(year_followup.group(1))

        if state.last_intent == "author_publication_count":
            rewritten = (
                f"How many publications did {state.last_author} "
                f"have in {year}?"
            )
        else:
            rewritten = (
                f"What did {state.last_author} publish in {year}?"
            )

        used["author"] = state.last_author
        used["year"] = year
        return rewritten, used

    # Topic refinement: "What about privacy?" after a topic search.
    topic_followup = re.fullmatch(
        r"\s*(?:and\s+)?(?:what|how)\s+about\s+(.+?)[?.!]*\s*",
        original,
        flags=re.IGNORECASE,
    )
    previous_topic = state.last_plan.get("search_text")

    if (
        topic_followup
        and previous_topic
        and state.last_intent == "topic_search"
    ):
        refinement = topic_followup.group(1).strip()

        if refinement:
            rewritten = (
                f"Find papers about {previous_topic} {refinement}"
            )
            used["search_text"] = previous_topic
            used["refinement"] = refinement
            return rewritten, used

    ordinal = re.search(
        r"\b(?:the\s+)?"
        r"(first|1st|second|2nd|third|3rd|fourth|4th|fifth|5th)"
        r"(?:\s+(?:one|paper|publication|article|result))?\b",
        rewritten,
        flags=re.IGNORECASE,
    )

    if ordinal and state.last_sources:
        index = _ORDINALS[ordinal.group(1).casefold()]

        if index < len(state.last_sources):
            title = state.last_sources[index].get("title")

            if title:
                rewritten = (
                    rewritten[:ordinal.start()]
                    + _quoted_title(title)
                    + rewritten[ordinal.end():]
                )
                used["title"] = title

    if state.last_title:
        title = _quoted_title(state.last_title)
        before = rewritten

        # Possessive "its" needs a possessive replacement so phrases like
        # "What is its page range?" remain grammatical.
        rewritten = re.sub(
            r"\bits\b",
            f"{title}'s",
            rewritten,
            flags=re.IGNORECASE,
        )

        rewritten = re.sub(
            r"\b(?:it|that paper|this paper|that publication|this publication)\b",
            title,
            rewritten,
            flags=re.IGNORECASE,
        )

        if rewritten != before:
            used["title"] = state.last_title

    if state.last_author:
        before = rewritten

        rewritten = re.sub(
            r"\b(?:he|she|they|that author|the author)\b",
            state.last_author,
            rewritten,
            flags=re.IGNORECASE,
        )

        rewritten = re.sub(
            r"\b(?:his|her|their)\b",
            f"{state.last_author}'s",
            rewritten,
            flags=re.IGNORECASE,
        )

        if rewritten != before:
            used["author"] = state.last_author

    return rewritten, used


def update_session_from_response(
    state: ConversationState,
    response: dict,
    plan: dict | None = None,
    question: str | None = None,
) -> None:
    response_intent = response.get("intent")

    # Irrelevant input should not destroy the last useful conversational
    # reference. A user can paste code accidentally and then continue with
    # "how many pages does it have?" about the paper discussed beforehand.
    if response_intent in {"unsupported", "smalltalk", "invalid"}:
        state.updated_at = time.monotonic()
        return

    state.last_question = question or state.last_question
    state.last_intent = response_intent or state.last_intent

    if plan:
        state.last_plan = {
            key: value
            for key, value in plan.items()
            if key in {
                "intent",
                "title",
                "author",
                "search_text",
                "year_from",
                "year_to",
                "limit",
                "all_results",
                "venue",
                "pub_type",
                "sort_order",
                "source_index",
                "source_selector",
            }
            and value is not None
        }

    resolved_author = response.get("resolved_author")

    if resolved_author:
        state.last_author = resolved_author

    sources = response.get("sources") or []

    if sources:
        state.last_sources = [
            dict(source)
            for source in sources[:MAX_REMEMBERED_SOURCES]
        ]

        titles = []

        for source in sources:
            title = (source.get("title") or "").strip()

            if title and title.casefold() not in {
                existing.casefold()
                for existing in titles
            }:
                titles.append(title)

        intent = response.get("intent") or ""

        if (
            len(titles) == 1
            and (
                intent.startswith("publication_")
                or intent == "publication_details"
            )
        ):
            state.last_title = titles[0]

    # If a successful exact-publication plan had an explicit title, remember
    # it even if the response source list is empty because metadata is missing.
    if (
        plan
        and plan.get("intent") in PUBLICATION_INTENTS
        and plan.get("title")
        and response.get("intent") != "topic_search"
    ):
        state.last_title = plan["title"]

    state.updated_at = time.monotonic()
