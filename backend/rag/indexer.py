"""Build the DBLP FTS5 index and structured metadata in one XML streaming pass."""

from __future__ import annotations

import argparse
import sqlite3
import time
from collections import Counter
from pathlib import Path

from lxml import etree

from .config import DBLP_XML, PUBLICATION_TAGS, RAG_DB

EXPECTED_RECORDS = 12_944_133


def _text(elem, tag):
    child = elem.find(tag)
    if child is None:
        return ""
    return " ".join(child.itertext()).strip()


def _authors(elem):
    return [
        " ".join(author.itertext()).strip()
        for author in elem.findall("author")
        if " ".join(author.itertext()).strip()
    ]


def _venue(elem, pub_type):
    if pub_type == "article":
        return _text(elem, "journal") or _text(elem, "booktitle")
    return _text(elem, "booktitle") or _text(elem, "journal")


def _duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, seconds = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m {seconds}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


def build_index(
    xml_path: Path = DBLP_XML,
    db_path: Path = RAG_DB,
    batch_size: int = 5000,
):
    xml_path, db_path = Path(xml_path), Path(db_path)
    if not xml_path.exists():
        raise FileNotFoundError(f"DBLP XML not found: {xml_path}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
        if candidate.exists():
            candidate.unlink()

    con = sqlite3.connect(db_path, timeout=60)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute("PRAGMA temp_store=MEMORY")
    con.execute("PRAGMA cache_size=-200000")

    con.execute("""
        CREATE VIRTUAL TABLE papers USING fts5(
            title,
            authors,
            venue,
            key UNINDEXED,
            year UNINDEXED,
            pub_type UNINDEXED,
            tokenize='unicode61 remove_diacritics 1'
        )
    """)
    con.execute("""
        CREATE TABLE paper_details(
            key TEXT PRIMARY KEY,
            pages TEXT,
            volume TEXT,
            number TEXT,
            publisher TEXT,
            ee TEXT
        )
    """)
    con.execute("""
        CREATE TABLE rag_stats(
            name TEXT PRIMARY KEY,
            value INTEGER NOT NULL
        )
    """)
    con.commit()

    fts_insert = """
        INSERT INTO papers(title, authors, venue, key, year, pub_type)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    detail_insert = """
        INSERT OR REPLACE INTO paper_details(key, pages, volume, number, publisher, ee)
        VALUES (?, ?, ?, ?, ?, ?)
    """

    fts_batch, detail_batch = [], []
    total = publication_records = 0
    type_counts = Counter()
    started = last_log = time.time()

    print("[RAG INDEXER] Starting combined FTS + metadata indexing...", flush=True)
    print(f"[RAG INDEXER] XML: {xml_path}", flush=True)
    print(f"[RAG INDEXER] DB : {db_path}", flush=True)

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
            title = _text(elem, "title")
            authors = _authors(elem)
            year_text = _text(elem, "year")
            try:
                year = int(year_text) if year_text else None
            except ValueError:
                year = None

            fts_batch.append((
                title,
                " ; ".join(authors),
                _venue(elem, pub_type),
                key,
                year,
                pub_type,
            ))

            if key:
                detail_values = (
                    key,
                    _text(elem, "pages"),
                    _text(elem, "volume"),
                    _text(elem, "number"),
                    _text(elem, "publisher"),
                    _text(elem, "ee"),
                )
                if any(detail_values[1:]):
                    detail_batch.append(detail_values)

            total += 1
            type_counts[pub_type] += 1
            if pub_type != "www":
                publication_records += 1

            if len(fts_batch) >= batch_size:
                try:
                    con.executemany(fts_insert, fts_batch)
                    if detail_batch:
                        con.executemany(detail_insert, detail_batch)
                    con.commit()
                except Exception:
                    con.rollback()
                    raise
                fts_batch.clear()
                detail_batch.clear()

            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]

            now = time.time()
            if now - last_log >= 5:
                elapsed = now - started
                rate = total / elapsed if elapsed else 0
                percent = total / EXPECTED_RECORDS * 100 if EXPECTED_RECORDS else 0
                print(
                    f"[RAG INDEXER] {total:,} records ({percent:.2f}%) | "
                    f"{rate:,.0f} rec/s | {_duration(elapsed)}",
                    flush=True,
                )
                last_log = now
    finally:
        del context

    if fts_batch:
        con.executemany(fts_insert, fts_batch)
    if detail_batch:
        con.executemany(detail_insert, detail_batch)
    con.commit()

    stats = {
        "total_records": total,
        "publication_records": publication_records,
        "www_records": type_counts.get("www", 0),
    }
    stats.update({f"type:{k}": v for k, v in type_counts.items()})
    con.executemany(
        "INSERT OR REPLACE INTO rag_stats(name, value) VALUES (?, ?)",
        list(stats.items()),
    )
    con.commit()

    print("[RAG INDEXER] Optimizing FTS5 index...", flush=True)
    con.execute("INSERT INTO papers(papers) VALUES('optimize')")
    con.commit()
    con.execute("ANALYZE")
    con.commit()
    con.close()

    elapsed = time.time() - started
    result = {
        "records": total,
        "publication_records": publication_records,
        "seconds": round(elapsed, 2),
        "db": str(db_path),
    }
    print(f"[RAG INDEXER] COMPLETE: {result}", flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--xml", type=Path, default=DBLP_XML)
    parser.add_argument("--db", type=Path, default=RAG_DB)
    parser.add_argument("--batch-size", type=int, default=5000)
    args = parser.parse_args()
    build_index(args.xml, args.db, args.batch_size)
