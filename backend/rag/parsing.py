from __future__ import annotations

import re


STOP_WORDS = {
    "a", "an", "the", "for", "of", "to", "in", "on", "with", "and", "or",
    "about", "find", "show", "give", "list", "me", "paper", "papers",
    "publication", "publications", "article", "articles", "research", "works",
    "related", "regarding", "using",
}


def normalize_text(text: str) -> str:
    text = (text or "").casefold()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_author_name(name: str) -> str:
    """Normalize a DBLP magic suffix: 2/02/002/0002 -> 0002."""
    value = re.sub(r"\s+", " ", (name or "").strip().strip("\"'“”‘’"))
    match = re.match(r"^(.*?)(?:\s+0*(\d{1,4}))?$", value)
    if not match:
        return value.casefold()

    base = (match.group(1) or "").strip()
    suffix = match.group(2)
    if suffix is not None:
        return f"{base} {int(suffix):04d}".casefold()
    return base.casefold()


def canonicalize_author_name(name: str) -> str:
    value = re.sub(r"\s+", " ", (name or "").strip().strip("\"'“”‘’"))
    match = re.match(r"^(.*?)(?:\s+0*(\d{1,4}))?$", value)
    if not match:
        return value
    base = (match.group(1) or "").strip()
    suffix = match.group(2)
    return f"{base} {int(suffix):04d}" if suffix is not None else base


def author_base_name(name: str) -> str:
    canonical = canonicalize_author_name(name)
    return re.sub(r"\s+\d{4}$", "", canonical).casefold().strip()


def author_has_suffix(name: str) -> bool:
    return bool(re.search(r"\s+\d{4}$", canonicalize_author_name(name)))


def extract_quoted_text(question: str) -> str | None:
    # Straight and curly quote pairs.
    patterns = [
        # A straight apostrophe inside a contraction (e.g. What's) is NOT
        # a quotation mark. Require straight single quotes to sit outside
        # word characters so only actual quoted spans are captured.
        r"(?<!\w)'([^']+)'(?!\w)",
        r'"([^"]+)"',
        r"‘([^’]+)’",
        r"“([^”]+)”",
    ]
    found = []
    for pattern in patterns:
        found.extend(re.findall(pattern, question or ""))
    return found[-1].strip() if found else None


def extract_year_filters(text: str) -> tuple[int | None, int | None, str]:
    """Return (year_from, year_to, text_without_year_clause)."""
    original = text or ""

    patterns = [
        (r"\bbetween\s+(19\d{2}|20\d{2})\s+and\s+(19\d{2}|20\d{2})\b", 2),
        (r"\bfrom\s+(19\d{2}|20\d{2})\s+to\s+(19\d{2}|20\d{2})\b", 2),
        (r"\b(?:in|during|published\s+in)\s+(19\d{2}|20\d{2})\b", 1),
    ]

    for pattern, groups in patterns:
        match = re.search(pattern, original, flags=re.IGNORECASE)
        if match:
            year_from = int(match.group(1))
            year_to = int(match.group(2)) if groups == 2 else year_from
            cleaned = (original[:match.start()] + " " + original[match.end():])
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            return year_from, year_to, cleaned

    return None, None, original.strip()


def clean_topic_text(text: str) -> str:
    value = text or ""
    value = re.sub(
        r"\b(find|show|give|list|search|lookup|look\s+up|me|papers?|publications?|"
        r"articles?|research|about|related\s+to|on)\b",
        " ",
        value,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", value).strip(" .?!")


def clean_title_request(title: str) -> str:
    value = (title or "").strip().strip("\"'“”‘’")
    value = re.sub(
        r"^(?:find|show|get|locate|lookup|look\s+up)\s+",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"^(?:the\s+)?(?:paper|article|publication)\s+(?:titled|called|named)\s+",
        "",
        value,
        flags=re.IGNORECASE,
    )
    return value.strip().strip("\"'“”‘’")


def _author_year_plan(question: str) -> dict | None:
    q = question.strip()

    patterns = [
        r"(?:what|which)\s+(?:paper|papers|publication|publications)\s+did\s+(.+?)\s+publish(?:ed)?\s+(?:in|during)\s+(19\d{2}|20\d{2})",
        r"what\s+did\s+(.+?)\s+publish\s+(?:in|during)\s+(19\d{2}|20\d{2})",
        r"(?:show|list|give\s+me)\s+(.+?)(?:'s)?\s+(?:papers?|publications?|articles?)\s+(?:in|during|from)\s+(19\d{2}|20\d{2})",
        r"(?:papers?|publications?|articles?)\s+(?:by|from)\s+(.+?)\s+(?:in|during)\s+(19\d{2}|20\d{2})",
    ]

    for pattern in patterns:
        match = re.search(pattern, q, flags=re.IGNORECASE)
        if match:
            year = int(match.group(2))
            return {
                "intent": "author_publications",
                "author": match.group(1).strip().strip("\"'"),
                "year_from": year,
                "year_to": year,
                "all_results": True,
            }
    return None


def fast_plan(question: str) -> dict | None:
    """High-confidence local routing. Returns None when Gemini should decide."""
    q = (question or "").strip()
    ql = q.casefold()
    title = extract_quoted_text(q)
    year_from, year_to, no_year = extract_year_filters(q)

    # Dataset-level counts. Keep common paraphrases local so a simple
    # statistics question never needs a remote planner call.
    if (
        re.search(
            r"\b(?:how many|number of|total number of)\b.*"
            r"\b(publications|papers|records|entries)\b.*"
            r"\b(dataset|dblp)\b",
            ql,
        )
        or re.search(
            r"\b(dataset|dblp)\b.*"
            r"\b(?:has|have|contains?|includes?)\b.*"
            r"\b(publications|papers|records|entries)\b",
            ql,
        )
    ):
        return {"intent": "dataset_count"}

    # Exact publication facts. Ordering matters: page count before generic pages.
    if title and re.search(
        r"\bhow many pages\b|\bnumber of pages\b|\bpage count\b|\bhow long\b.*\bpages\b",
        ql,
    ):
        return {"intent": "publication_page_count", "title": title}

    if title and re.search(r"\bpage range\b|\bwhich pages\b|\bwhat pages\b", ql):
        return {"intent": "publication_pages", "title": title}

    if title and re.search(r"\bauthors?\b|\bwho wrote\b|\bwho authored\b", ql):
        return {"intent": "publication_authors", "title": title}

    if title and re.search(
        r"\bjournal\b|\bconference\b|\bproceedings\b|\bvenue\b|\bwhere was\b.*\bpublished\b",
        ql,
    ):
        return {"intent": "publication_venue", "title": title}

    if title and re.search(r"\bwhat year\b|\bwhen was\b.*\bpublished\b|\bpublication year\b", ql):
        return {"intent": "publication_year", "title": title}

    if title and re.search(r"\bvolume\b", ql):
        return {"intent": "publication_volume", "title": title}

    if title and re.search(r"\bissue\b|\bnumber\b", ql):
        return {"intent": "publication_number", "title": title}

    if title and re.search(r"\bpublisher\b", ql):
        return {"intent": "publication_publisher", "title": title}

    if title and re.search(r"\bdoi\b|\bee\b|\belectronic edition\b|\blink\b", ql):
        return {"intent": "publication_ee", "title": title}

    if title:
        # A quoted title with no other analytical wording is an exact publication lookup.
        if re.search(
            r"\bpaper\b|\bpublication\b|\barticle\b|\bfind\b|\bshow\b|"
            r"\btell me about\b|\bwhat about\b",
            ql,
        ):
            return {"intent": "publication_details", "title": title}

    # Coauthor analytics.
    match = re.search(
        r"(?:top\s+(\d+)\s+)?(?:most\s+frequent\s+)?co-?authors?\s+(?:of|for|with)\s+(.+?)[?.!]*$",
        q,
        flags=re.IGNORECASE,
    )
    if match:
        return {
            "intent": "top_coauthors",
            "author": match.group(2).strip().strip("\"'"),
            "limit": int(match.group(1) or 3),
        }

    # Explicit author + year forms.
    author_year = _author_year_plan(q)
    if author_year:
        return author_year

    # Author publication counts.
    count_patterns = [
        r"\bhow many\s+(?:papers?|publications?|articles?|works?)\s+(?:does|did)\s+(.+?)\s+(?:have|publish|published)\b",
        r"\bhow many\s+(?:papers?|publications?|articles?|works?)\s+(?:by|from)\s+(.+?)(?:[?.!]|$)",
    ]
    for pattern in count_patterns:
        match = re.search(pattern, no_year, flags=re.IGNORECASE)
        if match:
            return {
                "intent": "author_publication_count",
                "author": match.group(1).strip().strip("\"'"),
                "year_from": year_from,
                "year_to": year_to,
            }

    # Publication list by author.
    match = re.search(
        r"\b(?:all\s+|every\s+)?(?:papers?|publications?|articles?|works?)\s+(?:by|from)\s+(.+?)(?:[?.!]|$)",
        no_year,
        flags=re.IGNORECASE,
    )
    if match:
        return {
            "intent": "author_publications",
            "author": match.group(1).strip().strip("\"'"),
            "year_from": year_from,
            "year_to": year_to,
            "all_results": bool(re.search(r"\b(all|every|complete list|full list)\b", ql)),
        }

    # Exact title command without quotes. Avoid topic forms such as "papers about X".
    if not re.search(
        r"\b(?:papers?|publications?|articles?|research)\s+(?:about|on|related to)\b",
        ql,
    ):
        direct = re.match(
            r"^\s*(?:find|show|lookup|look\s+up|get)\s+(.+?)(?:[?.!]|$)",
            no_year,
            flags=re.IGNORECASE,
        )
        if direct and len(direct.group(1).split()) >= 2:
            return {
                "intent": "publication_details",
                "title": direct.group(1).strip(),
                "year_from": year_from,
                "year_to": year_to,
            }

    # High-confidence topic-discovery forms. Route locally to avoid a planner API call.
    if re.search(
        r"\b(?:papers?|publications?|articles?|research)\s+(?:about|on|related to|regarding)\b",
        ql,
    ) or re.search(r"^\s*(?:find|show|list|search for)\s+.*\b(?:papers?|publications?|research)\b", ql):
        search_text = clean_topic_text(no_year)
        if search_text:
            return {
                "intent": "topic_search",
                "search_text": search_text,
                "year_from": year_from,
                "year_to": year_to,
                "limit": None,
            }

    return None
