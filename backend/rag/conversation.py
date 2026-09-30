from __future__ import annotations

import re
import threading
import time
import uuid
from dataclasses import dataclass, field


# In-memory conversational context is intentionally small and ephemeral.
# It is enough for a local/demo assistant and resets when the backend restarts.
SESSION_TTL_SECONDS = 2 * 60 * 60
MAX_SESSIONS = 1000
MAX_REMEMBERED_SOURCES = 20


@dataclass
class ConversationState:
    last_title: str | None = None
    last_author: str | None = None
    last_sources: list[dict] = field(default_factory=list)
    last_intent: str | None = None
    updated_at: float = field(default_factory=time.monotonic)


_sessions: dict[str, ConversationState] = {}
_lock = threading.RLock()


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


def get_or_create_session(session_id: str | None) -> tuple[str, ConversationState]:
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
    "sixth": 5,
    "6th": 5,
    "seventh": 6,
    "7th": 6,
    "eighth": 7,
    "8th": 7,
    "ninth": 8,
    "9th": 8,
    "tenth": 9,
    "10th": 9,
}


def _quoted_title(title: str) -> str:
    # Titles may contain apostrophes; double quotes are safer for rewriting.
    return '"' + title.replace('"', '\\"') + '"'


def _replace_ordinal_reference(question: str, state: ConversationState):
    if not state.last_sources:
        return question, None

    pattern = (
        r"\b(?:the\s+)?"
        r"(first|1st|second|2nd|third|3rd|fourth|4th|fifth|5th|"
        r"sixth|6th|seventh|7th|eighth|8th|ninth|9th|tenth|10th)"
        r"(?:\s+(?:one|paper|publication|article|result))?\b"
    )

    match = re.search(pattern, question, flags=re.IGNORECASE)
    if not match:
        return question, None

    index = _ORDINALS[match.group(1).casefold()]
    if index >= len(state.last_sources):
        return question, None

    source = state.last_sources[index]
    title = source.get("title")
    if not title:
        return question, None

    rewritten = (
        question[: match.start()]
        + _quoted_title(title)
        + question[match.end() :]
    )

    # "What about the second one?" should become an exact publication-details
    # question instead of being sent to semantic search.
    if re.match(r"^\s*what\s+about\b", rewritten, flags=re.IGNORECASE):
        rewritten = f"Tell me about {_quoted_title(title)}."

    return rewritten, title


def resolve_followup(question: str, state: ConversationState) -> tuple[str, dict]:
    """
    Rewrite lightweight conversational references into explicit DBLP entities.

    Examples:
      "How many pages does it have?"
        -> "How many pages does \"Attention Is All You Need.\" have?"

      "Who wrote the second one?"
        -> "Who wrote \"<second title from previous results>\"?"

      "What did they publish in 2025?"
        -> "What did Kassem Danach publish in 2025?"
    """
    original = (question or "").strip()
    rewritten = original
    used: dict = {}

    rewritten, ordinal_title = _replace_ordinal_reference(rewritten, state)
    if ordinal_title:
        used["title"] = ordinal_title
        used["source_reference"] = "ordinal"

    # Publication references. Avoid touching the question if it already
    # contains an explicit quoted title.
    if state.last_title and "title" not in used:
        title = _quoted_title(state.last_title)

        substitutions = [
            (r"\bthat\s+(?:paper|publication|article)\b", title),
            (r"\bthis\s+(?:paper|publication|article)\b", title),
            (r"\bthe\s+(?:paper|publication|article)\b", title),
            (r"\bits\b", f"{title}'s"),
            (r"\bit\b", title),
        ]

        changed = False
        for pattern, replacement in substitutions:
            new_value = re.sub(
                pattern,
                replacement,
                rewritten,
                flags=re.IGNORECASE,
            )
            if new_value != rewritten:
                changed = True
                rewritten = new_value

        if changed:
            used["title"] = state.last_title
            used["source_reference"] = "previous_title"

    # Author references. These are only used when a previously resolved author
    # exists. Publication-title rewrites above take precedence.
    if state.last_author:
        author = state.last_author
        author_possessive = author + ("'" if author.endswith("s") else "'s")

        substitutions = [
            (r"\bthat\s+author\b", author),
            (r"\bthe\s+author\b", author),
            (r"\btheir\b", author_possessive),
            (r"\bhis\b", author_possessive),
            (r"\bher\b", author_possessive),
            (r"\bthey\b", author),
            (r"\bthem\b", author),
            (r"\bhe\b", author),
            (r"\bshe\b", author),
        ]

        changed = False
        for pattern, replacement in substitutions:
            new_value = re.sub(
                pattern,
                replacement,
                rewritten,
                flags=re.IGNORECASE,
            )
            if new_value != rewritten:
                changed = True
                rewritten = new_value

        if changed:
            used["author"] = author

    return rewritten, used


def update_session_from_response(
    state: ConversationState,
    response: dict,
) -> None:
    state.last_intent = response.get("intent") or state.last_intent

    resolved_author = response.get("resolved_author")
    if resolved_author:
        state.last_author = resolved_author

    sources = response.get("sources") or []
    if sources:
        state.last_sources = [
            dict(source)
            for source in sources[:MAX_REMEMBERED_SOURCES]
        ]

        # Exact publication fact lookups often contain multiple DBLP versions
        # of the same title. Remember the title only when the current response
        # clearly refers to one publication title.
        titles = []
        for source in sources:
            title = (source.get("title") or "").strip()
            if title and title.casefold() not in {
                existing.casefold() for existing in titles
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

    state.updated_at = time.monotonic()
