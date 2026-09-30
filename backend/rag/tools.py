"""Deterministic DBLP tools used by the chat planner.

Rule of thumb:
- Exact facts / counts / authors / venues / pages / coauthors -> these tools.
- Conceptual topic discovery -> BM25 candidates + embeddings.
"""

from __future__ import annotations

import re
import sqlite3
from collections import Counter
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Optional

from .config import RAG_DB
from .semantic import semantic_rerank


PUBLICATION_TYPES = {
    "article",
    "inproceedings",
    "proceedings",
    "book",
    "incollection",
    "phdthesis",
    "mastersthesis",
    "data",
}

STOP_WORDS = {
    "a", "an", "the", "for", "of", "to", "in", "on", "with", "and", "or",
    "about", "find", "show", "give", "list", "me", "paper", "papers",
    "publication", "publications", "article", "articles", "research", "works",
}


def _connect():
    con = sqlite3.connect(
        f"file:{Path(RAG_DB)}?mode=ro",
        uri=True,
        timeout=30,
    )
    con.row_factory = sqlite3.Row
    return con


def normalize_text(text: str) -> str:
    text = (text or "").casefold()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_author_name(name: str) -> str:
    """Normalize DBLP suffixes: 'Name 2'/'Name 02'/'Name 002' -> 'Name 0002'."""
    name = re.sub(r"\s+", " ", (name or "").strip().strip("\"'"))
    match = re.match(r"^(.*?)(?:\s+0*(\d{1,4}))?$", name)
    if not match:
        return name.casefold()

    base = (match.group(1) or "").strip()
    suffix = match.group(2)

    if suffix is not None:
        return f"{base} {int(suffix):04d}".casefold()

    return base.casefold()


def author_base_name(name: str) -> str:
    value = re.sub(r"\s+", " ", (name or "").strip().strip("\"'"))
    return re.sub(r"\s+\d{4}$", "", value).casefold()


def _row_to_paper(row) -> dict:
    return {
        "title": row["title"] or "",
        "authors": row["authors"].split(" ; ") if row["authors"] else [],
        "venue": row["venue"] or "",
        "key": row["key"] or "",
        "year": row["year"],
        "type": row["pub_type"] or "",
    }


def _attach_details(con, paper: dict) -> dict:
    try:
        row = con.execute(
            """
            SELECT pages, volume, number, publisher, ee
            FROM paper_details
            WHERE key = ?
            """,
            (paper["key"],),
        ).fetchone()
    except sqlite3.OperationalError:
        row = None

    result = dict(paper)
    if row:
        result.update({
            "pages": row["pages"] or "",
            "volume": row["volume"] or "",
            "number": row["number"] or "",
            "publisher": row["publisher"] or "",
            "ee": row["ee"] or "",
        })
    else:
        result.update({
            "pages": "",
            "volume": "",
            "number": "",
            "publisher": "",
            "ee": "",
        })
    return result


@lru_cache(maxsize=1)
def get_dataset_statistics() -> dict:
    con = _connect()
    try:
        try:
            rows = con.execute(
                "SELECT name, value FROM rag_stats"
            ).fetchall()
            if rows:
                values = {row["name"]: row["value"] for row in rows}
                type_counts = {
                    k.split(":", 1)[1]: v
                    for k, v in values.items()
                    if k.startswith("type:")
                }
                return {
                    "total_records": values.get("total_records", 0),
                    "publication_records": values.get("publication_records", 0),
                    "www_records": values.get("www_records", 0),
                    "type_counts": type_counts,
                }
        except sqlite3.OperationalError:
            pass

        # Fallback if details_indexer has not been run yet.
        total = con.execute(
            "SELECT COUNT(*) AS c FROM papers"
        ).fetchone()["c"]
        publications = con.execute(
            "SELECT COUNT(*) AS c FROM papers WHERE pub_type != 'www'"
        ).fetchone()["c"]
        return {
            "total_records": total,
            "publication_records": publications,
            "www_records": total - publications,
            "type_counts": {},
        }
    finally:
        con.close()


def _clean_title_request(title: str) -> str:
    title = (title or "").strip().strip("\"'")
    title = re.sub(
        r"^(?:find|show|get|locate)\s+",
        "",
        title,
        flags=re.IGNORECASE,
    )
    title = re.sub(
        r"^(?:the\s+)?(?:paper|article|publication)\s+(?:titled|called)\s+",
        "",
        title,
        flags=re.IGNORECASE,
    )
    return title.strip().strip("\"'")


def find_publication_by_title(title: str) -> list[dict]:
    """Return exact DBLP versions; use a close-title fallback only if exact fails."""
    target = _clean_title_request(title)
    normalized_target = normalize_text(target)
    terms = re.findall(r"[\wÀ-ÖØ-öø-ÿ]+", target, flags=re.UNICODE)

    if not terms:
        return []

    phrase = " ".join(terms)
    con = _connect()
    try:
        rows = con.execute(
            """
            SELECT title, authors, venue, key, year, pub_type
            FROM papers
            WHERE papers MATCH ?
              AND pub_type != 'www'
            LIMIT 100
            """,
            (f'title : "{phrase}"',),
        ).fetchall()

        exact = []
        candidates = []

        for row in rows:
            paper = _row_to_paper(row)
            nt = normalize_text(paper["title"])

            if nt == normalized_target:
                exact.append(_attach_details(con, paper))
            else:
                similarity = SequenceMatcher(
                    None, normalized_target, nt
                ).ratio()
                candidates.append((similarity, paper))

        if exact:
            return exact

        # Flexible fallback for user wording such as
        # "'Find Attention Is All You Need'".
        candidates.sort(key=lambda x: x[0], reverse=True)
        if candidates and candidates[0][0] >= 0.72:
            best_score = candidates[0][0]
            return [
                _attach_details(con, paper)
                for score, paper in candidates
                if score >= best_score - 0.03
            ][:5]

        # Last fallback: AND title words after removing command filler.
        useful_terms = [
            t for t in terms
            if t.casefold() not in STOP_WORDS
        ]
        if not useful_terms:
            return []

        query = " AND ".join(f'title : "{t}"' for t in useful_terms)
        rows = con.execute(
            """
            SELECT title, authors, venue, key, year, pub_type
            FROM papers
            WHERE papers MATCH ?
              AND pub_type != 'www'
            LIMIT 50
            """,
            (query,),
        ).fetchall()

        candidates = []
        for row in rows:
            paper = _row_to_paper(row)
            score = SequenceMatcher(
                None,
                normalize_text(target),
                normalize_text(paper["title"]),
            ).ratio()
            candidates.append((score, paper))

        candidates.sort(key=lambda x: x[0], reverse=True)
        return [
            _attach_details(con, paper)
            for score, paper in candidates[:3]
            if score >= 0.65
        ]
    finally:
        con.close()


def resolve_author_identities(author_name: str) -> list[str]:
    """Return DBLP author identities that correspond to the requested base name."""
    raw = (author_name or "").strip().strip("\"'")
    if not raw:
        return []

    desired_normalized = normalize_author_name(raw)
    requested_has_suffix = bool(re.search(r"\s+\d{1,4}$", raw))

    # Search base name so that 'Name' can discover 'Name 0001'/'Name 0002'.
    base = re.sub(r"\s+\d{1,4}$", "", raw).strip()
    terms = re.findall(r"[\wÀ-ÖØ-öø-ÿ]+", base, flags=re.UNICODE)
    if not terms:
        return []

    fts_query = " AND ".join(f'authors : "{t}"' for t in terms)

    con = _connect()
    try:
        rows = con.execute(
            """
            SELECT authors
            FROM papers
            WHERE papers MATCH ?
              AND pub_type != 'www'
            LIMIT 2000
            """,
            (fts_query,),
        ).fetchall()

        found = set()
        requested_base = author_base_name(raw)

        for row in rows:
            for author in (
                row["authors"].split(" ; ")
                if row["authors"] else []
            ):
                if requested_has_suffix:
                    if normalize_author_name(author) == desired_normalized:
                        found.add(author)
                else:
                    if author_base_name(author) == requested_base:
                        found.add(author)

        return sorted(found, key=normalize_author_name)
    finally:
        con.close()


def get_author_publications(
    author_name: str,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    limit: Optional[int] = None,
) -> dict:
    identities = resolve_author_identities(author_name)

    if not identities:
        return {
            "status": "not_found",
            "requested_author": author_name,
            "identities": [],
            "publications": [],
        }

    requested_has_suffix = bool(
        re.search(r"\s+\d{1,4}$", (author_name or "").strip().strip("\"'"))
    )

    # If the user did not disambiguate, try the year filter first.
    # If exactly one identity has results in that year/range, we can safely use it.
    if len(identities) > 1 and not requested_has_suffix and (
        year_from is not None or year_to is not None
    ):
        per_identity = {}
        for identity in identities:
            result = get_author_publications(
                identity,
                year_from=year_from,
                year_to=year_to,
                limit=limit,
            )
            if result["publications"]:
                per_identity[identity] = result["publications"]

        if len(per_identity) == 1:
            identity, publications = next(iter(per_identity.items()))
            return {
                "status": "ok",
                "requested_author": author_name,
                "resolved_author": identity,
                "identities": identities,
                "publications": publications,
            }

    if len(identities) > 1 and not requested_has_suffix:
        return {
            "status": "ambiguous",
            "requested_author": author_name,
            "identities": identities,
            "publications": [],
        }

    identity = identities[0]
    target = normalize_author_name(identity)

    # Exact author phrase narrows the FTS candidates first.
    fts_query = f'authors : "{identity}"'

    con = _connect()
    try:
        rows = con.execute(
            """
            SELECT title, authors, venue, key, year, pub_type
            FROM papers
            WHERE papers MATCH ?
              AND pub_type != 'www'
              AND (? IS NULL OR year >= ?)
              AND (? IS NULL OR year <= ?)
            ORDER BY year DESC, title ASC
            """,
            (
                fts_query,
                year_from, year_from,
                year_to, year_to,
            ),
        )

        publications = []
        for row in rows:
            paper = _row_to_paper(row)

            if not any(
                normalize_author_name(a) == target
                for a in paper["authors"]
            ):
                continue

            publications.append(_attach_details(con, paper))

            if limit is not None and len(publications) >= limit:
                break

        return {
            "status": "ok",
            "requested_author": author_name,
            "resolved_author": identity,
            "identities": identities,
            "publications": publications,
        }
    finally:
        con.close()


def get_top_coauthors(author_name: str, limit: int = 3) -> dict:
    result = get_author_publications(author_name, limit=None)

    if result["status"] != "ok":
        return result | {"coauthors": []}

    target = normalize_author_name(result["resolved_author"])
    counts = Counter()

    for paper in result["publications"]:
        for author in paper["authors"]:
            if normalize_author_name(author) != target:
                counts[author] += 1

    return result | {
        "coauthors": [
            {"author": author, "count": count}
            for author, count in counts.most_common(max(1, limit))
        ]
    }


def retrieve_semantic_candidates(
    search_text: str,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    limit: int = 99,
) -> list[dict]:
    terms = [
        term
        for term in re.findall(
            r"[\wÀ-ÖØ-öø-ÿ]+",
            search_text or "",
            flags=re.UNICODE,
        )
        if term.casefold() not in STOP_WORDS
    ]

    if not terms:
        return []

    # Broad recall for the semantic reranker.
    fts_query = " OR ".join(f'"{term}"' for term in terms)

    con = _connect()
    try:
        rows = con.execute(
            """
            SELECT
                title, authors, venue, key, year, pub_type,
                bm25(papers, 10.0, 2.0, 1.0) AS bm25_score
            FROM papers
            WHERE papers MATCH ?
              AND pub_type != 'www'
              AND (? IS NULL OR year >= ?)
              AND (? IS NULL OR year <= ?)
            ORDER BY bm25_score
            LIMIT ?
            """,
            (
                fts_query,
                year_from, year_from,
                year_to, year_to,
                min(limit, 99),
            ),
        ).fetchall()

        results = []
        for row in rows:
            paper = _row_to_paper(row)
            paper["bm25_score"] = row["bm25_score"]
            results.append(paper)
        return results
    finally:
        con.close()


def semantic_topic_search(
    search_text: str,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    top_k: int = 5,
) -> list[dict]:
    candidates = retrieve_semantic_candidates(
        search_text,
        year_from=year_from,
        year_to=year_to,
        limit=99,
    )
    if not candidates:
        return []

    return semantic_rerank(
        search_text,
        candidates,
        top_k=max(1, min(top_k, 20)),
    )


def page_count_from_range(pages: str):
    """
    Convert common DBLP page ranges like '5998-6008'
    into an inclusive page count: 11.
    """

    if not pages:
        return None

    value = (
        pages.strip()
        .replace("–", "-")
        .replace("—", "-")
    )

    # Single numeric page.
    if re.fullmatch(r"\d+", value):
        return 1

    match = re.fullmatch(
        r"(\d+)\s*-\s*(\d+)",
        value
    )

    if not match:
        return None

    start = int(match.group(1))
    end = int(match.group(2))

    if end < start:
        return None

    return end - start + 1

def page_count_from_range(
    pages: str
):
    if not pages:
        return None

    value = (
        pages.strip()
        .replace("–", "-")
        .replace("—", "-")
    )

    # One page
    if re.fullmatch(
        r"\d+",
        value
    ):
        return 1

    match = re.fullmatch(
        r"(\d+)\s*-\s*(\d+)",
        value
    )

    if not match:
        return None

    start = int(
        match.group(1)
    )

    end = int(
        match.group(2)
    )

    if end < start:
        return None

    # Inclusive range:
    # 5998-6008 = 11 pages
    return end - start + 1