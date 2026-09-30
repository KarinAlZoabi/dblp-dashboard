from __future__ import annotations

import sqlite3
from functools import lru_cache
from pathlib import Path

from .config import RAG_DB


def connect_ro(db_path: Path = RAG_DB) -> sqlite3.Connection:
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(
            f"RAG index not found: {db_path}. Run the DBLP indexer first."
        )

    con = sqlite3.connect(
        f"file:{db_path}?mode=ro",
        uri=True,
        timeout=30,
    )
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    con.execute("PRAGMA busy_timeout=30000")
    return con


@lru_cache(maxsize=8)
def has_table(table_name: str, db_path: str = str(RAG_DB)) -> bool:
    con = connect_ro(Path(db_path))
    try:
        row = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()
        return row is not None
    finally:
        con.close()


def fts_phrase(value: str) -> str:
    """Quote arbitrary text safely as an FTS5 phrase."""
    return (value or "").replace('"', '""')


def authors_from_db(value: str | None) -> list[str]:
    if not value:
        return []
    return [a.strip() for a in value.split(" ; ") if a.strip()]


def row_to_publication(row: sqlite3.Row) -> dict:
    item = {
        "title": row["title"] or "",
        "authors": authors_from_db(row["authors"]),
        "venue": row["venue"] or "",
        "key": row["key"] or "",
        "year": row["year"],
        "type": row["pub_type"] or "",
    }

    keys = set(row.keys())
    for field in (
        "pages", "volume", "number", "publisher", "ee",
        "bm25_score", "score", "matched_author",
    ):
        if field in keys:
            item[field] = row[field] if row[field] is not None else ""

    return item
