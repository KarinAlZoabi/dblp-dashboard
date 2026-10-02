from __future__ import annotations

import re


_BULLET_RE = re.compile(
    r"(?m)^\s*[*•-]\s+"
)

_ROBOTIC_OPENERS = (
    r"based on (?:the )?(?:provided|retrieved) dblp "
    r"(?:records|evidence|results),?\s*",
    r"according to (?:the )?(?:provided|retrieved) dblp "
    r"(?:records|evidence|results),?\s*",
    r"from (?:the )?(?:provided|retrieved) dblp "
    r"(?:records|evidence|results),?\s*",
)


def _capitalize_first(text: str) -> str:
    for index, char in enumerate(text):
        if char.isalpha():
            return (
                text[:index]
                + char.upper()
                + text[index + 1:]
            )
    return text


def _natural_topic(search_text: str | None) -> str:
    topic = re.sub(
        r"\s+",
        " ",
        (search_text or "").strip(),
    )

    if not topic:
        return "this topic"

    return topic


def polish_grounded_answer(
    answer: str,
    *,
    search_text: str | None = None,
) -> str:
    """
    Presentation-only cleanup for grounded LLM answers.

    This function NEVER changes bibliographic facts or citations. It only:
    - removes internal/RAG-sounding preambles,
    - normalizes bullet markers,
    - makes list introductions more conversational,
    - trims excessive blank lines.

    DBLP/retrieval remains the source of truth.
    """
    text = (answer or "").strip()

    if not text:
        return text

    has_bullets = bool(_BULLET_RE.search(text))

    # Remove common internal-sounding opening phrases.
    lowered = text.casefold()

    for opener in _ROBOTIC_OPENERS:
        match = re.match(
            opener,
            lowered,
            flags=re.IGNORECASE,
        )

        if match:
            text = text[match.end():].lstrip()
            break

    # If the model produced a list after an explanatory "through several
    # works:" style sentence, use a compact natural intro instead.
    if has_bullets:
        bullet_match = re.search(
            r"(?m)^\s*[*•-]\s+",
            text,
        )

        if bullet_match:
            prefix = text[:bullet_match.start()].strip()
            bullets = text[bullet_match.start():].strip()

            robotic_prefix = bool(
                re.search(
                    r"\b(?:through|across)\s+(?:several|these)\s+"
                    r"(?:works|papers|publications)\s*:?\s*$",
                    prefix,
                    flags=re.IGNORECASE,
                )
                or re.search(
                    r"\b(?:several|the following)\s+"
                    r"(?:works|papers|publications)\s*:?\s*$",
                    prefix,
                    flags=re.IGNORECASE,
                )
            )

            if robotic_prefix or not prefix:
                topic = _natural_topic(search_text)
                text = (
                    f"Here are some relevant DBLP publications "
                    f"on {topic}:\n\n{bullets}"
                )

    # Standardize Markdown bullets for the frontend renderer.
    text = re.sub(
        r"(?m)^\s*[•*]\s+",
        "- ",
        text,
    )

    # Avoid excessive whitespace from model formatting.
    text = re.sub(
        r"\n[ \t]+\n",
        "\n\n",
        text,
    )
    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return _capitalize_first(text.strip())
