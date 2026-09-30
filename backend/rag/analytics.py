from __future__ import annotations

import re
from collections import Counter
from functools import lru_cache

from .db import connect_ro
from .parsing import normalize_author_name
from .retrieval import get_author_publications


@lru_cache(maxsize=1)
def get_dataset_statistics() -> dict:
    con = connect_ro()
    try:
        try:
            rows = con.execute("SELECT name, value FROM rag_stats").fetchall()
            if rows:
                values = {row["name"]: int(row["value"]) for row in rows}
                return {
                    "total_records": values.get("total_records", 0),
                    "publication_records": values.get("publication_records", 0),
                    "www_records": values.get("www_records", 0),
                    "type_counts": {
                        key.split(":", 1)[1]: value
                        for key, value in values.items()
                        if key.startswith("type:")
                    },
                }
        except Exception:
            pass

        total = con.execute("SELECT COUNT(*) AS c FROM papers").fetchone()["c"]
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


def get_top_coauthors(author_name: str, limit: int = 3) -> dict:
    result = get_author_publications(author_name, limit=None)
    if result["status"] not in {"ok", "multi_match"}:
        return result | {"coauthors": []}

    # For a multi-match author name, do not merge people silently.
    if result["status"] == "multi_match":
        return result | {"coauthors": []}

    target = normalize_author_name(result["resolved_author"])
    counts = Counter()
    for paper in result["publications"]:
        for author in paper.get("authors", []):
            if normalize_author_name(author) != target:
                counts[author] += 1

    return result | {
        "coauthors": [
            {"author": author, "count": count}
            for author, count in counts.most_common(max(1, limit))
        ]
    }


def page_count_from_range(pages: str):
    if not pages:
        return None

    value = pages.strip().replace("–", "-").replace("—", "-")
    if re.fullmatch(r"\d+", value):
        return 1

    # Covers normal numeric ranges. DBLP also contains article-number style
    # values; those are intentionally left as unknown rather than guessed.
    match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", value)
    if not match:
        return None

    start, end = int(match.group(1)), int(match.group(2))
    if end < start:
        return None
    return end - start + 1
