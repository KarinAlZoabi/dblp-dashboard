"""Upgrade an existing FTS index with paper_details and rag_stats without rebuilding FTS."""

from __future__ import annotations

import argparse
import sqlite3
import time
from collections import Counter
from pathlib import Path

from lxml import etree

from .config import DBLP_XML, PUBLICATION_TAGS, RAG_DB


def _text(elem, tag):
    child = elem.find(tag)
    if child is None:
        return ""
    return " ".join(child.itertext()).strip()


def build_details_index(
    xml_path: Path = DBLP_XML,
    db_path: Path = RAG_DB,
    batch_size: int = 10_000,
):
    xml_path, db_path = Path(xml_path), Path(db_path)
    if not xml_path.exists():
        raise FileNotFoundError(f"DBLP XML not found: {xml_path}")
    if not db_path.exists():
        raise FileNotFoundError(f"RAG database not found: {db_path}")

    con = sqlite3.connect(db_path, timeout=60)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute("""
        CREATE TABLE IF NOT EXISTS paper_details(
            key TEXT PRIMARY KEY,
            pages TEXT,
            volume TEXT,
            number TEXT,
            publisher TEXT,
            ee TEXT
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS rag_stats(
            name TEXT PRIMARY KEY,
            value INTEGER NOT NULL
        )
    """)
    con.commit()

    insert_sql = """
        INSERT INTO paper_details(key, pages, volume, number, publisher, ee)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            pages=excluded.pages,
            volume=excluded.volume,
            number=excluded.number,
            publisher=excluded.publisher,
            ee=excluded.ee
    """

    batch = []
    total = publication_records = detail_rows = 0
    counts = Counter()
    started = last_log = time.time()

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
            pub_type = elem.tag
            key = elem.get("key", "")
            total += 1
            counts[pub_type] += 1
            if pub_type != "www":
                publication_records += 1

            values = (
                key,
                _text(elem, "pages"),
                _text(elem, "volume"),
                _text(elem, "number"),
                _text(elem, "publisher"),
                _text(elem, "ee"),
            )
            if key and any(values[1:]):
                batch.append(values)
                detail_rows += 1

            if len(batch) >= batch_size:
                con.executemany(insert_sql, batch)
                con.commit()
                batch.clear()

            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]

            now = time.time()
            if now - last_log >= 5:
                elapsed = now - started
                rate = total / elapsed if elapsed else 0
                print(
                    f"[DETAILS] {total:,} records | {detail_rows:,} details | {rate:,.0f} rec/s",
                    flush=True,
                )
                last_log = now
    finally:
        del context

    if batch:
        con.executemany(insert_sql, batch)
        con.commit()

    stats = {
        "total_records": total,
        "publication_records": publication_records,
        "www_records": counts.get("www", 0),
    }
    stats.update({f"type:{k}": v for k, v in counts.items()})
    con.executemany(
        "INSERT OR REPLACE INTO rag_stats(name, value) VALUES (?, ?)",
        list(stats.items()),
    )
    con.commit()
    con.execute("ANALYZE")
    con.commit()
    con.close()

    result = {
        "total_records": total,
        "publication_records": publication_records,
        "detail_rows": detail_rows,
        "seconds": round(time.time() - started, 2),
    }
    print(f"[DETAILS] COMPLETE: {result}", flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--xml", type=Path, default=DBLP_XML)
    parser.add_argument("--db", type=Path, default=RAG_DB)
    parser.add_argument("--batch-size", type=int, default=10_000)
    args = parser.parse_args()
    build_details_index(args.xml, args.db, args.batch_size)
