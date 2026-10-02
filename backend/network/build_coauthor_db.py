from pathlib import Path

import sqlite3

import time



import duckdb





# ============================================================

# PATHS

# ============================================================



BACKEND_DIR = Path(__file__).resolve().parent.parent



RAG_DB = BACKEND_DIR / "rag_data" / "dblp_fts.sqlite"



NETWORK_DIR = BACKEND_DIR / "network_data"

NETWORK_DIR.mkdir(parents=True, exist_ok=True)



NETWORK_DB = NETWORK_DIR / "coauthors.duckdb"

EDGE_FILE = NETWORK_DIR / "coauthor_edges.tsv"

PAPER_AUTHORS_FILE = NETWORK_DIR / "paper_authors.tsv"





# ============================================================

# SETTINGS

# ============================================================



SOURCE_FETCH_SIZE = 10_000

INSERT_BATCH_SIZE = 50_000

PROGRESS_EVERY = 100_000





# ============================================================

# HELPERS

# ============================================================



def format_number(value: int) -> str:

    return f"{value:,}"





def clean_authors(authors_text: str):

    """

    Convert DBLP's stored author string:



        Alice ; Bob ; Carol



    into:



        ["Alice", "Bob", "Carol"]



    Duplicate author names inside the same publication are removed,

    while the exact DBLP author identity is preserved.

    """



    if not authors_text:

        return []



    authors = [

        author.strip()

        for author in authors_text.split(" ; ")

        if author.strip()

    ]



    # Remove duplicates while preserving order.

    return list(dict.fromkeys(authors))





# ============================================================

# DATABASE INITIALIZATION

# ============================================================



def create_network_database():

    print("=" * 70)

    print("DBLP COAUTHOR NETWORK BUILDER")

    print("=" * 70)



    if not RAG_DB.exists():

        raise FileNotFoundError(

            f"RAG database was not found:\n{RAG_DB}"

        )



    print(f"Source database : {RAG_DB}")

    print(f"Network database: {NETWORK_DB}")

    print()



    # --------------------------------------------------------

    # SOURCE SQLITE DATABASE

    # --------------------------------------------------------



    source = sqlite3.connect(

        f"file:{RAG_DB}?mode=ro",

        uri=True

    )



    source.row_factory = sqlite3.Row



    # --------------------------------------------------------

    # TARGET DUCKDB DATABASE

    # --------------------------------------------------------



    db = duckdb.connect(str(NETWORK_DB))



    return source, db





# ============================================================

# STAGE 1

# EXTRACT PAPER -> AUTHOR RELATIONSHIPS

# ============================================================



def stage_publication_authors(source, db):

    print()

    print("=" * 70)

    print("STAGE 1 — EXTRACTING AUTHORS")

    print("=" * 70)



    cursor = source.execute(

        """

        SELECT

            rowid AS paper_id,

            authors

        FROM papers

        WHERE authors IS NOT NULL

        """

    )



    rows_processed = 0

    author_rows_written = 0



    start_time = time.time()

    last_report = start_time



    # ========================================================

    # STEP 1:

    # Write everything sequentially to a TSV file.

    # This avoids millions of DuckDB INSERT operations.

    # ========================================================



    with open(

        PAPER_AUTHORS_FILE,

        "w",

        encoding="utf-8",

        newline=""

    ) as output:



        while True:



            rows = cursor.fetchmany(SOURCE_FETCH_SIZE)



            if not rows:

                break



            lines = []



            for row in rows:



                paper_id = row["paper_id"]



                authors = clean_authors(

                    row["authors"]

                )



                for author in authors:



                    safe_author = (

                        author

                        .replace("\t", " ")

                        .replace("\n", " ")

                        .replace("\r", " ")

                    )



                    lines.append(

                        f"{paper_id}\t{safe_author}\n"

                    )



                author_rows_written += len(authors)

                rows_processed += 1



            output.writelines(lines)



            # Print progress roughly every 5 seconds

            now = time.time()



            if now - last_report >= 5:



                elapsed = now - start_time



                rate = (

                    rows_processed / elapsed

                    if elapsed > 0

                    else 0

                )



                print(

                    f"Papers: {rows_processed:,} | "

                    f"Author rows: {author_rows_written:,} | "

                    f"Rate: {rate:,.0f} papers/sec | "

                    f"Elapsed: {elapsed / 60:.1f} min",

                    flush=True

                )



                last_report = now



    print()

    print(

        f"Extraction complete: "

        f"{rows_processed:,} publications, "

        f"{author_rows_written:,} author rows."

    )



    # ========================================================

    # STEP 2:

    # Let DuckDB bulk-load the finished TSV in one operation.

    # ========================================================



    print()

    print("Bulk-loading author data into DuckDB...")



    db.execute(

        "DROP TABLE IF EXISTS paper_authors"

    )



    file_path = (

        PAPER_AUTHORS_FILE

        .as_posix()

        .replace("'", "''")

    )



    load_start = time.time()



    db.execute(

        f"""

        CREATE TABLE paper_authors AS



        SELECT

            column0::BIGINT AS paper_id,

            column1::VARCHAR AS author



        FROM read_csv(

            '{file_path}',

            delim = '\\t',

            header = false,

            columns = {{

                'column0': 'BIGINT',

                'column1': 'VARCHAR'

            }}

        )

        """

    )



    load_elapsed = time.time() - load_start



    print(

        f"DuckDB bulk load complete "

        f"in {load_elapsed:.1f} seconds."

    )

# ============================================================

# STAGE 2

# CREATE UNIQUE AUTHORS

# ============================================================



def create_authors(db):

    print()

    print("=" * 70)

    print("STAGE 2 — CREATING AUTHOR NODES")

    print("=" * 70)



    db.execute("DROP TABLE IF EXISTS authors")



    db.execute(

        """

        CREATE TABLE authors AS



        SELECT

            ROW_NUMBER() OVER (

                ORDER BY author

            ) - 1 AS author_id,



            author AS name,



            COUNT(*) AS publication_count



        FROM paper_authors



        GROUP BY author

        """

    )



    author_count = db.execute(

        """

        SELECT COUNT(*)

        FROM authors

        """

    ).fetchone()[0]



    print(

        f"Unique authors: "

        f"{format_number(author_count)}"

    )



    db.execute(

        """

        CREATE INDEX idx_authors_id

        ON authors(author_id)

        """

    )



    db.execute(

        """

        CREATE INDEX idx_authors_name

        ON authors(name)

        """

    )





# ============================================================

# STAGE 3

# REPLACE AUTHOR NAMES WITH INTEGER IDS

# ============================================================



def create_numeric_publication_authors(db):

    print()

    print("=" * 70)

    print("STAGE 3 — MAPPING AUTHORS TO NODE IDS")

    print("=" * 70)



    db.execute(

        """

        DROP TABLE IF EXISTS paper_author_ids

        """

    )



    db.execute(

        """

        CREATE TABLE paper_author_ids AS



        SELECT

            pa.paper_id,

            a.author_id



        FROM paper_authors pa



        INNER JOIN authors a

            ON pa.author = a.name

        """

    )



    print("Author names mapped to numeric node IDs.")





# ============================================================

# STAGE 4

# BUILD COAUTHOR EDGES

# ============================================================



def create_edges(db):

    print()

    print("=" * 70)

    print("STAGE 4 — BUILDING COAUTHOR EDGES")

    print("=" * 70)



    db.execute("DROP TABLE IF EXISTS edges")



    # --------------------------------------------------------

    # For every publication:

    #

    # A, B, C

    #

    # becomes:

    #

    # A-B

    # A-C

    # B-C

    #

    # If a pair publishes together repeatedly, COUNT(*)

    # becomes the edge weight.

    # --------------------------------------------------------



    db.execute(

        """

        CREATE TABLE edges AS



        SELECT

            p1.author_id AS source,

            p2.author_id AS target,

            COUNT(*) AS weight



        FROM paper_author_ids p1



        INNER JOIN paper_author_ids p2



            ON p1.paper_id = p2.paper_id



            AND p1.author_id < p2.author_id



        GROUP BY

            p1.author_id,

            p2.author_id

        """

    )



    edge_count = db.execute(

        """

        SELECT COUNT(*)

        FROM edges

        """

    ).fetchone()[0]



    print(

        f"Unique collaboration edges: "

        f"{format_number(edge_count)}"

    )



    db.execute(

        """

        CREATE INDEX idx_edges_source

        ON edges(source)

        """

    )



    db.execute(

        """

        CREATE INDEX idx_edges_target

        ON edges(target)

        """

    )





# ============================================================

# STAGE 5

# EXACT DEGREE MEASURES

# ============================================================



def calculate_basic_centrality(db):

    print()

    print("=" * 70)

    print("STAGE 5 — CALCULATING DEGREE CENTRALITY")

    print("=" * 70)



    db.execute(

        """

        DROP TABLE IF EXISTS author_stats

        """

    )



    db.execute(

        """

        CREATE TABLE author_stats AS



        WITH all_edges AS (



            SELECT

                source AS author_id,

                target AS collaborator_id,

                weight

            FROM edges



            UNION ALL



            SELECT

                target AS author_id,

                source AS collaborator_id,

                weight

            FROM edges



        ),



        degree_stats AS (



            SELECT

                author_id,



                COUNT(*) AS degree,



                SUM(weight) AS weighted_degree



            FROM all_edges



            GROUP BY author_id



        )



        SELECT

            a.author_id,

            a.name,

            a.publication_count,



            COALESCE(d.degree, 0)

                AS degree,



            COALESCE(d.weighted_degree, 0)

                AS weighted_degree



        FROM authors a



        LEFT JOIN degree_stats d

            ON a.author_id = d.author_id

        """

    )



    total_authors = db.execute(

        """

        SELECT COUNT(*)

        FROM author_stats

        """

    ).fetchone()[0]



    connected_authors = db.execute(

        """

        SELECT COUNT(*)

        FROM author_stats

        WHERE degree > 0

        """

    ).fetchone()[0]



    print(

        f"Authors: {format_number(total_authors)}"

    )



    print(

        f"Authors with >= 1 collaborator: "

        f"{format_number(connected_authors)}"

    )





# ============================================================

# STAGE 6

# EXPORT EDGES FOR NETWORKIT

# ============================================================



def export_edge_list(db):

    print()

    print("=" * 70)

    print("STAGE 6 — EXPORTING NETWORK EDGE LIST")

    print("=" * 70)



    path = EDGE_FILE.as_posix().replace("'", "''")



    db.execute(

        f"""

        COPY (

            SELECT

                source,

                target,

                weight



            FROM edges



            ORDER BY

                source,

                target

        )



        TO '{path}'



        (

            DELIMITER '\t',

            HEADER FALSE

        )

        """

    )



    print(f"Edge list written to:")

    print(EDGE_FILE)





# ============================================================

# SUMMARY

# ============================================================



def print_summary(db):

    print()

    print("=" * 70)

    print("NETWORK SUMMARY")

    print("=" * 70)



    authors = db.execute(

        "SELECT COUNT(*) FROM authors"

    ).fetchone()[0]



    edges = db.execute(

        "SELECT COUNT(*) FROM edges"

    ).fetchone()[0]



    collaborations = db.execute(

        """

        SELECT COALESCE(SUM(weight), 0)

        FROM edges

        """

    ).fetchone()[0]



    max_degree = db.execute(

        """

        SELECT MAX(degree)

        FROM author_stats

        """

    ).fetchone()[0]



    print(

        f"Nodes / authors        : "

        f"{format_number(authors)}"

    )



    print(

        f"Unique edges           : "

        f"{format_number(edges)}"

    )



    print(

        f"Coauthorship instances : "

        f"{format_number(collaborations)}"

    )



    print(

        f"Maximum degree         : "

        f"{format_number(max_degree or 0)}"

    )



    print()

    print("Top 10 authors by degree:")

    print()



    top_authors = db.execute(

        """

        SELECT

            name,

            publication_count,

            degree,

            weighted_degree



        FROM author_stats



        ORDER BY degree DESC



        LIMIT 10

        """

    ).fetchall()



    for rank, row in enumerate(

        top_authors,

        start=1

    ):



        name, publications, degree, weighted = row



        print(

            f"{rank:>2}. "

            f"{name:<40} "

            f"degree={degree:<8,} "

            f"weighted={weighted:<8,} "

            f"papers={publications:,}"

        )





# ============================================================

# MAIN

# ============================================================



def main():



    source, db = create_network_database()



    try:



        stage_publication_authors(

            source,

            db

        )



        create_authors(db)



        create_numeric_publication_authors(db)



        create_edges(db)



        calculate_basic_centrality(db)



        export_edge_list(db)



        print_summary(db)



        print()

        print("=" * 70)

        print("COAUTHOR NETWORK BUILD COMPLETE")

        print("=" * 70)



    finally:



        source.close()

        db.close()





if __name__ == "__main__":

    main()