from __future__ import annotations

import re
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Optional

from .config import SEMANTIC_CANDIDATE_LIMIT
from .db import connect_ro, fts_phrase, has_table, row_to_publication
from .parsing import (
    STOP_WORDS,
    author_base_name,
    author_has_suffix,
    canonicalize_author_name,
    clean_title_request,
    extract_year_filters,
    normalize_author_name,
    normalize_text,
)
from .semantic import semantic_rerank


def _details_select() -> tuple[str, str]:
    if has_table("paper_details"):
        return (
            ", d.pages, d.volume, d.number, d.publisher, d.ee",
            " LEFT JOIN paper_details d ON d.key = papers.key ",
        )
    return ("", "")


def lexical_search(question: str, top_k: int = 5) -> list[dict]:
    """Exact/lexical DBLP search using title phrase retrieval + BM25."""
    question = (question or "").strip()
    if not question:
        return []

    year_from, year_to, search_text = extract_year_filters(question)
    search_text = search_text or question
    terms = re.findall(r"[\wÀ-ÖØ-öø-ÿ]+", search_text, flags=re.UNICODE)
    if not terms:
        return []

    normalized_query = normalize_text(search_text)
    query_words = set(normalized_query.split())
    and_query = " AND ".join(f'"{fts_phrase(t)}"' for t in terms)
    phrase = " ".join(terms)
    title_phrase = f'title : "{fts_phrase(phrase)}"'

    extra, join = _details_select()
    con = connect_ro()
    try:
        sql = f"""
            SELECT papers.rowid, papers.title, papers.authors, papers.venue,
                   papers.key, papers.year, papers.pub_type
                   {extra},
                   bm25(papers, 10.0, 2.0, 1.0) AS bm25_score
            FROM papers
            {join}
            WHERE papers MATCH ?
              AND papers.pub_type != 'www'
              AND (? IS NULL OR papers.year >= ?)
              AND (? IS NULL OR papers.year <= ?)
            ORDER BY bm25_score
            LIMIT ?
        """

        phrase_rows = con.execute(
            sql,
            (title_phrase, year_from, year_from, year_to, year_to, 100),
        ).fetchall()
        bm25_rows = con.execute(
            sql,
            (and_query, year_from, year_from, year_to, year_to, 200),
        ).fetchall()

        unique = {}
        for row in phrase_rows:
            unique[row["rowid"]] = row
        for row in bm25_rows:
            unique.setdefault(row["rowid"], row)

        candidates = []
        for row in unique.values():
            paper = row_to_publication(row)
            nt = normalize_text(paper["title"])
            title_words = set(nt.split())
            paper["score"] = float(row["bm25_score"])
            paper["_exact"] = nt == normalized_query
            paper["_phrase"] = normalized_query in nt
            paper["_coverage"] = (
                len(query_words.intersection(title_words)) / len(query_words)
                if query_words else 0.0
            )
            paper["_length"] = abs(len(nt) - len(normalized_query))
            candidates.append(paper)

        candidates.sort(
            key=lambda item: (
                not item["_exact"],
                not item["_phrase"],
                -item["_coverage"],
                item["_length"],
                item["score"],
            )
        )

        results = []
        for item in candidates[:max(1, min(top_k, 50))]:
            for field in ("_exact", "_phrase", "_coverage", "_length"):
                item.pop(field, None)
            results.append(item)
        return results
    finally:
        con.close()


@lru_cache(maxsize=1024)
def find_publication_by_title_cached(title: str) -> tuple[tuple, ...]:
    return tuple(_find_publication_by_title_uncached(title))


def find_publication_by_title(title: str) -> list[dict]:
    # Return copies so callers can safely enrich/mutate the result.
    return [dict(item) for item in find_publication_by_title_cached(title)]


def _find_publication_by_title_uncached(title: str) -> list[dict]:
    target = clean_title_request(title)
    normalized_target = normalize_text(target)
    terms = re.findall(r"[\wÀ-ÖØ-öø-ÿ]+", target, flags=re.UNICODE)
    if not terms:
        return []

    extra, join = _details_select()
    con = connect_ro()
    try:
        phrase = " ".join(terms)
        rows = con.execute(
            f"""
            SELECT papers.title, papers.authors, papers.venue, papers.key,
                   papers.year, papers.pub_type {extra}
            FROM papers
            {join}
            WHERE papers MATCH ?
              AND papers.pub_type != 'www'
            LIMIT 100
            """,
            (f'title : "{fts_phrase(phrase)}"',),
        ).fetchall()

        exact, candidates = [], []
        for row in rows:
            paper = row_to_publication(row)
            nt = normalize_text(paper["title"])
            if nt == normalized_target:
                exact.append(paper)
            else:
                candidates.append((SequenceMatcher(None, normalized_target, nt).ratio(), paper))

        if exact:
            return exact

        candidates.sort(key=lambda x: x[0], reverse=True)
        if candidates and candidates[0][0] >= 0.72:
            best = candidates[0][0]
            return [paper for score, paper in candidates if score >= best - 0.03][:5]

        useful = [t for t in terms if t.casefold() not in STOP_WORDS]
        if not useful:
            return []

        query = " AND ".join(f'title : "{fts_phrase(t)}"' for t in useful)
        rows = con.execute(
            f"""
            SELECT papers.title, papers.authors, papers.venue, papers.key,
                   papers.year, papers.pub_type {extra}
            FROM papers
            {join}
            WHERE papers MATCH ?
              AND papers.pub_type != 'www'
            LIMIT 50
            """,
            (query,),
        ).fetchall()

        scored = []
        for row in rows:
            paper = row_to_publication(row)
            score = SequenceMatcher(
                None, normalized_target, normalize_text(paper["title"])
            ).ratio()
            scored.append((score, paper))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [paper for score, paper in scored[:3] if score >= 0.65]
    finally:
        con.close()


@lru_cache(maxsize=2048)
def resolve_author_identities(author_name: str) -> tuple[str, ...]:
    raw = canonicalize_author_name(author_name)
    if not raw:
        return tuple()

    requested_has_suffix = author_has_suffix(raw)
    desired = normalize_author_name(raw)
    base = re.sub(r"\s+\d{4}$", "", raw).strip()
    terms = re.findall(r"[\wÀ-ÖØ-öø-ÿ]+", base, flags=re.UNICODE)
    if not terms:
        return tuple()

    query = " AND ".join(f'authors : "{fts_phrase(t)}"' for t in terms)
    con = connect_ro()
    try:
        rows = con.execute(
            """
            SELECT authors
            FROM papers
            WHERE papers MATCH ?
              AND pub_type != 'www'
            LIMIT 10000
            """,
            (query,),
        ).fetchall()

        found = set()
        requested_base = author_base_name(raw)
        for row in rows:
            for author in (row["authors"].split(" ; ") if row["authors"] else []):
                if requested_has_suffix:
                    if normalize_author_name(author) == desired:
                        found.add(canonicalize_author_name(author))
                elif author_base_name(author) == requested_base:
                    found.add(canonicalize_author_name(author))

        return tuple(sorted(found, key=normalize_author_name))
    finally:
        con.close()


def _publications_for_exact_author(
    identity: str,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    limit: Optional[int] = None,
) -> list[dict]:
    identity = canonicalize_author_name(identity)
    target = normalize_author_name(identity)
    extra, join = _details_select()

    con = connect_ro()
    try:
        rows = con.execute(
            f"""
            SELECT papers.title, papers.authors, papers.venue, papers.key,
                   papers.year, papers.pub_type {extra}
            FROM papers
            {join}
            WHERE papers MATCH ?
              AND papers.pub_type != 'www'
              AND (? IS NULL OR papers.year >= ?)
              AND (? IS NULL OR papers.year <= ?)
            ORDER BY papers.year DESC, papers.title ASC
            """,
            (
                f'authors : "{fts_phrase(identity)}"',
                year_from, year_from,
                year_to, year_to,
            ),
        )

        publications = []
        for row in rows:
            paper = row_to_publication(row)
            if not any(normalize_author_name(a) == target for a in paper["authors"]):
                continue
            paper["matched_author"] = identity
            publications.append(paper)
            if limit is not None and len(publications) >= limit:
                break
        return publications
    finally:
        con.close()


def get_author_publications(
    author_name: str,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    limit: Optional[int] = None,
) -> dict:
    identities = list(resolve_author_identities(author_name))
    if not identities:
        return {
            "status": "not_found",
            "requested_author": author_name,
            "identities": [],
            "publications": [],
        }

    explicit_identity = author_has_suffix(author_name)
    if explicit_identity or len(identities) == 1:
        identity = identities[0]
        return {
            "status": "ok",
            "requested_author": author_name,
            "resolved_author": identity,
            "identities": identities,
            "publications": _publications_for_exact_author(
                identity, year_from, year_to, limit
            ),
        }

    # Plain visible names may map to multiple people. If the user supplied a
    # year/range, answer the filtered question across identities rather than
    # failing with a disambiguation prompt. Each source retains matched_author.
    if year_from is not None or year_to is not None:
        groups = {}
        combined = []
        for identity in identities:
            pubs = _publications_for_exact_author(
                identity, year_from, year_to, limit=None
            )
            if pubs:
                groups[identity] = pubs
                combined.extend(pubs)

        combined.sort(key=lambda p: ((p.get("year") or 0), p.get("title", "")), reverse=True)
        if limit is not None:
            combined = combined[:limit]

        if groups:
            return {
                "status": "multi_match" if len(groups) > 1 else "ok",
                "requested_author": author_name,
                "resolved_author": next(iter(groups)) if len(groups) == 1 else None,
                "identities": identities,
                "matched_identities": list(groups),
                "publications": combined,
            }

    return {
        "status": "ambiguous",
        "requested_author": author_name,
        "identities": identities,
        "publications": [],
    }


def semantic_candidates(
    search_text: str,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    limit: int = SEMANTIC_CANDIDATE_LIMIT,
) -> list[dict]:
    terms = [
        term for term in re.findall(r"[\wÀ-ÖØ-öø-ÿ]+", search_text or "", flags=re.UNICODE)
        if term.casefold() not in STOP_WORDS
    ]
    if not terms:
        return []

    query = " OR ".join(f'"{fts_phrase(term)}"' for term in terms)
    con = connect_ro()
    try:
        rows = con.execute(
            """
            SELECT title, authors, venue, key, year, pub_type,
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
                query,
                year_from, year_from,
                year_to, year_to,
                max(1, min(limit, 99)),
            ),
        ).fetchall()
        return [row_to_publication(row) | {"bm25_score": float(row["bm25_score"])} for row in rows]
    finally:
        con.close()


def semantic_topic_search(
    search_text: str,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    top_k: int = 5,
) -> tuple[list[dict], str, str | None]:
    """Return (results, mode, error_name). Never discard lexical evidence."""
    candidates = semantic_candidates(search_text, year_from, year_to)
    if not candidates:
        return [], "none", None

    try:
        results = semantic_rerank(search_text, candidates, top_k=top_k)
        return results, "hybrid_semantic", None
    except Exception as exc:
        # Critical reliability fix: an embedding outage must not masquerade as
        # "no DBLP evidence". Fall back to the BM25 candidates we already have.
        return candidates[:max(1, top_k)], "bm25_fallback", type(exc).__name__
