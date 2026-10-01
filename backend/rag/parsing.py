from __future__ import annotations

import re


STOP_WORDS = {
    "a", "an", "the", "for", "of", "to", "in", "on", "with", "and", "or",
    "about", "find", "show", "give", "list", "me", "paper", "papers",
    "publication", "publications", "article", "articles", "research", "works",
    "related", "regarding", "using",
}

YEAR_RE = r"(?:1\d{3}|20\d{2}|21\d{2})"


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
    patterns = [
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
        (rf"\bbetween\s+({YEAR_RE})\s+and\s+({YEAR_RE})\b", 2),
        (rf"\bfrom\s+({YEAR_RE})\s+to\s+({YEAR_RE})\b", 2),
        (rf"\b(?:in|during|published\s+in)\s+({YEAR_RE})\b", 1),
    ]

    for pattern, groups in patterns:
        match = re.search(pattern, original, flags=re.IGNORECASE)
        if match:
            year_from = int(match.group(1))
            year_to = int(match.group(2)) if groups == 2 else year_from
            cleaned = original[:match.start()] + " " + original[match.end():]
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            return year_from, year_to, cleaned

    return None, None, original.strip()


def clean_topic_text(text: str) -> str:
    value = text or ""
    value = re.sub(
        r"\b(?:i(?:'m| am)\s+looking\s+for|looking\s+for|interested\s+in)\b",
        " ",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"\btop\s+\d{1,2}\b", " ", value, flags=re.IGNORECASE)
    value = re.sub(
        r"^\s*(?:show|give|list)(?:\s+me)?\s+\d{1,2}\s+",
        " ",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"\b(find|show|give|list|search|lookup|look\s+up|me|papers?|publications?|"
        r"articles?|research|work|works|about|related\s+to|on|relevant|conference|journal)\b",
        " ",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"\s+", " ", value).strip(" .?!")
    value = re.sub(r"^the\s+", "", value, flags=re.IGNORECASE)
    return value


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


def _requested_limit(question: str) -> int | None:
    patterns = [
        r"\btop\s+(\d{1,2})\b",
        r"\b(?:show|give|list)(?:\s+me)?\s+(\d{1,2})\s+(?:relevant\s+)?(?:papers?|publications?|articles?)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, question, flags=re.IGNORECASE)
        if match:
            return max(1, min(int(match.group(1)), 20))
    return None


def _publication_type_filter(question: str) -> str | None:
    q = question.casefold()
    if re.search(r"\bconference\s+(?:papers?|publications?|articles?)\b", q):
        return "inproceedings"
    if re.search(r"\bjournal\s+(?:papers?|publications?|articles?)\b", q):
        return "article"
    if re.search(r"\bphd\s+(?:theses|thesis)\b", q):
        return "phdthesis"
    if re.search(r"\bbooks?\b", q):
        return "book"
    return None


def _venue_filter(no_year: str) -> str | None:
    # Conservative local venue extraction. Arbitrary/ambiguous venue wording is
    # intentionally left to the LLM planner instead of guessed here.
    match = re.search(
        r"\b(?:in|at)\s+([A-Z][A-Za-z0-9.&+()\-]*(?:\s+[A-Z0-9][A-Za-z0-9.&+()\-]*){0,3})\s*$",
        no_year.strip(),
    )
    if match:
        candidate = match.group(1).strip()
        if candidate.casefold() not in {"machine learning", "deep learning"}:
            return candidate
    return None


def _author_year_plan(question: str) -> dict | None:
    q = question.strip()

    patterns = [
        rf"(?:what|which)\s+(?:paper|papers|publication|publications)\s+did\s+(.+?)\s+publish(?:ed)?\s+(?:in|during)\s+({YEAR_RE})",
        rf"what\s+did\s+(.+?)\s+publish\s+(?:in|during)\s+({YEAR_RE})",
        rf"(?:show\s+me\s+)?what\s+(.+?)\s+(?:put\s+out|published|produced)\s+(?:in|during)\s+({YEAR_RE})",
        rf"(?:show|list|give\s+me)\s+(.+?)(?:'s)?\s+(?:papers?|publications?|articles?)\s+(?:in|during|from)\s+({YEAR_RE})",
        rf"(?:papers?|publications?|articles?)\s+(?:by|from)\s+(.+?)\s+(?:in|during)\s+({YEAR_RE})",
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

    # Dataset counts.
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
        or re.search(
            r"\b(?:what(?:'s| is)\s+)?(?:the\s+)?(?:total\s+)?"
            r"(?:publication|paper|record|entry)\s+count\b.*\b(?:dataset|dblp)\b",
            ql,
        )
    ):
        return {"intent": "dataset_count"}

    # Exact publication facts. Ordering matters.
    if title and re.search(
        r"\bhow many pages\b|\bnumber of pages\b|\bpage[-\s]?count\b|\bhow long\b.*\bpages\b",
        ql,
    ):
        return {"intent": "publication_page_count", "title": title}

    if title and re.search(
        r"\bpage range\b|\bwhich pages\b|\bwhat pages\b|\bwhat (?:are|were) the pages\b",
        ql,
    ):
        return {"intent": "publication_pages", "title": title}

    if title and re.search(r"\bauthors?\b|\bwho wrote\b|\bwho authored\b", ql):
        return {"intent": "publication_authors", "title": title}

    if title and re.search(
        r"\bjournal\b|\bconference\b|\bproceedings\b|\bvenue\b|"
        r"\bwhere was\b.*\bpublished\b|"
        r"\bwhere did\b.*\b(?:appear|publish(?:ed)?)\b|"
        r"\bwhich venue\b",
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

    if title and re.search(
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

    # Author + year.
    author_year = _author_year_plan(q)
    if author_year:
        return author_year

    # Possessive publication counts: "What's Kassem Danach's publication count?"
    match = re.search(
        r"^(?:what(?:'s| is)\s+)?(.+?)'s\s+(?:publication|paper|article)\s+count\b",
        no_year,
        flags=re.IGNORECASE,
    )
    if match:
        return {
            "intent": "author_publication_count",
            "author": match.group(1).strip(),
            "year_from": year_from,
            "year_to": year_to,
        }

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

    # Latest/oldest author publication.
    ranking_patterns = [
        (r"(?:what is|show me|find)\s+(.+?)'s\s+(?:most recent|latest|newest)\s+(?:paper|publication|article)", "latest"),
        (r"(?:what is|show me|find)\s+(.+?)'s\s+(?:earliest|oldest|first)\s+(?:paper|publication|article)", "oldest"),
        (r"(?:latest|newest|most recent)\s+(?:paper|publication|article)\s+(?:by|from)\s+(.+?)(?:[?.!]|$)", "latest"),
        (r"(?:earliest|oldest|first)\s+(?:paper|publication|article)\s+(?:by|from)\s+(.+?)(?:[?.!]|$)", "oldest"),
    ]
    for pattern, order in ranking_patterns:
        match = re.search(pattern, no_year, flags=re.IGNORECASE)
        if match:
            return {
                "intent": "author_publications",
                "author": match.group(1).strip().strip("\"'"),
                "year_from": year_from,
                "year_to": year_to,
                "limit": 1,
                "sort_order": order,
            }

    # Publication lists by author: "papers by X" and "show X publications".
    match = re.search(
        r"\b(?:all\s+|every\s+)?(?:papers?|publications?|articles?|works?)\s+(?:by|from)\s+(.+?)(?:[?.!]|$)",
        no_year,
        flags=re.IGNORECASE,
    )
    if not match:
        match = re.search(
            r"^(?:show|list|give\s+me)\s+(?:all\s+)?(.+?)\s+(?:papers?|publications?|articles?|works?)\s*[?.!]*$",
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

    # Topic discovery MUST be checked before unquoted exact-title commands.
    topic_form = bool(
        re.search(
            r"\b(?:papers?|publications?|articles?|research|work)\s+(?:about|on|related to|regarding)\b",
            ql,
        )
        or re.search(
            r"^\s*(?:find|show|list|search(?:\s+for)?|give\s+me)\s+.+\b(?:papers?|publications?|articles?|research|work)\b",
            ql,
        )
        or re.search(
            r"\b(?:i(?:'m| am)\s+looking\s+for|looking\s+for|interested\s+in)\b.*\b(?:work|research|papers?|publications?)\b",
            ql,
        )
    )
    if topic_form:
        search_text = clean_topic_text(no_year)
        if search_text:
            venue = _venue_filter(no_year)
            if venue:
                search_text = re.sub(
                    rf"\b(?:in|at)\s+{re.escape(venue)}\s*$",
                    "",
                    search_text,
                    flags=re.IGNORECASE,
                ).strip()
            return {
                "intent": "topic_search",
                "search_text": search_text,
                "year_from": year_from,
                "year_to": year_to,
                "limit": _requested_limit(q),
                "venue": venue,
                "pub_type": _publication_type_filter(q),
            }

    # Exact title command without quotes.
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

    return None
