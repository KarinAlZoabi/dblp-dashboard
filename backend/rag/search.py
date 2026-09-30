"""Lexical DBLP retrieval using SQLite FTS5 BM25."""

import re
import sqlite3
from pathlib import Path
from typing import Optional

from .config import RAG_DB
from .models import SearchResult


def _fts_query(text: str) -> str:
    # FTS5 syntax is powerful but user input should not be allowed to inject
    # operators accidentally. We turn the query into quoted tokens.
    tokens = re.findall(r"[\w\-]+", text, flags=re.UNICODE)
    return " AND ".join(f'"{token.replace(chr(34), "")}"' for token in tokens)


class DBLPSearch:
    def __init__(self, db_path: Path = RAG_DB):
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"RAG index not found: {self.db_path}. Run `python -m rag.indexer` first."
            )

    def search(
        self,
        query: str,
        top_k: int = 10,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        pub_type: Optional[str] = None,
    ):
        fts_query = _fts_query(query)
        if not fts_query:
            return []

        where = ["papers MATCH ?"]
        params = [fts_query]

        if year_from is not None:
            where.append("year >= ?")
            params.append(year_from)
        if year_to is not None:
            where.append("year <= ?")
            params.append(year_to)
        if pub_type:
            where.append("pub_type = ?")
            params.append(pub_type)

        sql = f"""
            SELECT key, title, authors, year, venue, pub_type,
                   bm25(papers, 2.0, 1.2, 1.0) AS score
            FROM papers
            WHERE {' AND '.join(where)}
            ORDER BY score
            LIMIT ?
        """
        params.append(top_k)

        with sqlite3.connect(self.db_path) as con:
            rows = con.execute(sql, params).fetchall()

        results = []
        for key, title, authors, year, venue, pub_type, score in rows:
            author_list = [a.strip() for a in (authors or "").split(";") if a.strip()]
            results.append(SearchResult(
                key=key or "",
                title=title or "",
                authors=author_list,
                year=year,
                venue=venue or None,
                pub_type=pub_type or "",
                score=float(score),
            ))
        return results
