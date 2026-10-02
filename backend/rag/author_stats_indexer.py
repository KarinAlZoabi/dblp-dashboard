"""Build the unique DBLP publication-author statistic without bloating the RAG DB.

This is a one-time upgrade for an existing index. It streams dblp.xml, writes
unique author names to a temporary SQLite database, stores only the final count
in rag_stats, then deletes the temporary database.
"""

from __future__ import annotations

import argparse
import sqlite3
import time
from pathlib import Path

from lxml import etree

from .config import DBLP_XML, PUBLICATION_TAGS, RAG_DB


def _author_text(author) -> str:
    return " ".join(author.itertext()).strip()


def build_author_stats(
    xml_path: Path = DBLP_XML,
    db_path: Path = RAG_DB,
    batch_size: int = 20_000,
):
    xml_path = Path(xml_path)
    db_path = Path(db_path)

    if not xml_path.exists():
        raise FileNotFoundError(f"DBLP XML not found: {xml_path}")

    if not db_path.exists():
        raise FileNotFoundError(f"RAG database not found: {db_path}")

    temp_path = db_path.parent / "_author_stats_temp.sqlite"

    for candidate in (
        temp_path,
        Path(str(temp_path) + "-wal"),
        Path(str(temp_path) + "-shm"),
    ):
        if candidate.exists():
            candidate.unlink()

    temp = sqlite3.connect(temp_path, timeout=60)
    temp.execute("PRAGMA journal_mode=OFF")
    temp.execute("PRAGMA synchronous=OFF")
    temp.execute("PRAGMA temp_store=MEMORY")
    temp.execute("PRAGMA cache_size=-100000")
    temp.execute("""
        CREATE TABLE unique_authors(
            name TEXT PRIMARY KEY
        ) WITHOUT ROWID
    """)
    temp.commit()

    insert_sql = "INSERT OR IGNORE INTO unique_authors(name) VALUES (?)"

    batch = []
    records = 0
    author_occurrences = 0
    started = last_log = time.time()

    print("[AUTHOR STATS] Building unique publication-author count...", flush=True)
    print(f"[AUTHOR STATS] XML: {xml_path}", flush=True)

    context = etree.iterparse(
        str(xml_path),
        events=("end",),
        tag=tuple(PUBLICATION_TAGS),
        load_dtd=True,
        resolve_entities=True,
        huge_tree=True,
    )

    try:
        for _, elem in context:
            records += 1

            # DBLP www entries are person/homepage/profile records rather than
            # bibliographic publications. Count authors appearing on actual
            # publication records only.
            if elem.tag != "www":
                for author in elem.findall("author"):
                    value = _author_text(author)
                    if value:
                        batch.append((value,))
                        author_occurrences += 1

            if len(batch) >= batch_size:
                temp.executemany(insert_sql, batch)
                temp.commit()
                batch.clear()

            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]

            now = time.time()
            if now - last_log >= 5:
                unique_so_far = temp.execute(
                    "SELECT COUNT(*) FROM unique_authors"
                ).fetchone()[0]
                elapsed = now - started
                rate = records / elapsed if elapsed else 0
                print(
                    f"[AUTHOR STATS] {records:,} records | "
                    f"{unique_so_far:,} unique authors so far | "
                    f"{rate:,.0f} rec/s",
                    flush=True,
                )
                last_log = now
    finally:
        del context

    if batch:
        temp.executemany(insert_sql, batch)
        temp.commit()

    unique_authors = int(
        temp.execute("SELECT COUNT(*) FROM unique_authors").fetchone()[0]
    )
    temp.close()

    rag = sqlite3.connect(db_path, timeout=60)
    try:
        rag.execute("""
            CREATE TABLE IF NOT EXISTS rag_stats(
                name TEXT PRIMARY KEY,
                value INTEGER NOT NULL
            )
        """)
        rag.execute(
            "INSERT OR REPLACE INTO rag_stats(name, value) VALUES (?, ?)",
            ("unique_authors", unique_authors),
        )
        rag.commit()
    finally:
        rag.close()

    if temp_path.exists():
        temp_path.unlink()

    result = {
        "unique_authors": unique_authors,
        "author_occurrences": author_occurrences,
        "records_scanned": records,
        "seconds": round(time.time() - started, 2),
    }

    print("[AUTHOR STATS] COMPLETE", flush=True)
    print(result, flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--xml", type=Path, default=DBLP_XML)
    parser.add_argument("--db", type=Path, default=RAG_DB)
    parser.add_argument("--batch-size", type=int, default=20_000)
    args = parser.parse_args()

    build_author_stats(
        xml_path=args.xml,
        db_path=args.db,
        batch_size=args.batch_size,
    )
