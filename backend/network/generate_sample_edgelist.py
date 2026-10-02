from pathlib import Path
import sqlite3
import csv
from itertools import combinations


# ============================================================
# PATHS
# ============================================================

BACKEND_DIR = Path(__file__).resolve().parent.parent

RAG_DB = BACKEND_DIR / "rag_data" / "dblp_fts.sqlite"

OUTPUT_FILE = (
    BACKEND_DIR
    / "network_data"
    / "dblp_sample_edgelist.txt"
)


# ============================================================
# SETTINGS
# ============================================================

SAMPLE_SIZE = 10000


# ============================================================
# HELPERS
# ============================================================

def clean_authors(authors_text):
    if not authors_text:
        return []

    authors = [
        author.strip()
        for author in authors_text.split(" ; ")
        if author.strip()
    ]

    # Remove accidental duplicates within a publication
    return list(dict.fromkeys(authors))


# ============================================================
# GENERATE SAMPLE EDGE LIST
# ============================================================

def main():

    if not RAG_DB.exists():
        raise FileNotFoundError(
            f"DBLP database not found: {RAG_DB}"
        )

    print("Generating DBLP sample edge-list dataset...")
    print(f"Target edges: {SAMPLE_SIZE:,}")

    connection = sqlite3.connect(
        f"file:{RAG_DB}?mode=ro",
        uri=True
    )

    cursor = connection.execute(
        """
        SELECT authors
        FROM papers
        WHERE authors IS NOT NULL
        """
    )

    edges = set()

    papers_processed = 0

    for row in cursor:

        authors = clean_authors(row[0])

        # A paper needs at least two authors
        if len(authors) < 2:
            continue

        # Generate all coauthor combinations
        for author1, author2 in combinations(authors, 2):

            # Sort so:
            #
            # A,B
            # B,A
            #
            # are treated as the same edge.
            edge = tuple(
                sorted(
                    (author1, author2)
                )
            )

            edges.add(edge)

            if len(edges) >= SAMPLE_SIZE:
                break

        papers_processed += 1

        if len(edges) >= SAMPLE_SIZE:
            break

    connection.close()

    # ========================================================
    # WRITE TEXT FILE
    # ========================================================

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
        newline=""
    ) as file:

        writer = csv.writer(file)

        # No header, because teacher's format is:
        #
        # A,B
        # A,C
        # etc.

        for author1, author2 in sorted(edges):
            writer.writerow(
                [author1, author2]
            )

    print()
    print("Done!")
    print(f"Edges written: {len(edges):,}")
    print(f"Output file: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()