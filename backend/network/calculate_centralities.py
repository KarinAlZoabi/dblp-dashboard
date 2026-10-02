from pathlib import Path
import gc
import time

import duckdb
import networkit as nk


# ============================================================
# PATHS
# ============================================================

BACKEND_DIR = Path(__file__).resolve().parent.parent

NETWORK_DIR = BACKEND_DIR / "network_data"

NETWORK_DB = NETWORK_DIR / "coauthors.duckdb"
EDGE_FILE = NETWORK_DIR / "coauthor_edges.tsv"

SCORE_DIR = NETWORK_DIR / "centrality_temp"
SCORE_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# SETTINGS
# ============================================================

# Reproducible sampling for approximate betweenness.
RANDOM_SEED = 42

# PageRank settings.
PAGERANK_DAMPING = 0.85
PAGERANK_TOLERANCE = 1e-8

# Eigenvector convergence tolerance.
EIGENVECTOR_TOLERANCE = 1e-8

# Approximate betweenness:
# each sample requires traversing a very large graph.
# 200 is a reasonable first value for this dashboard.
BETWEENNESS_SAMPLES = 200

# False uses less memory. The graph is already very large.
BETWEENNESS_PARALLEL = False

# If False, completed metric tables are reused on reruns.
FORCE_RECOMPUTE = False


# ============================================================
# HELPERS
# ============================================================

def elapsed_text(seconds):
    if seconds < 60:
        return f"{seconds:.1f} seconds"

    minutes = seconds / 60

    if minutes < 60:
        return f"{minutes:.1f} minutes"

    hours = minutes / 60
    return f"{hours:.2f} hours"


def table_exists(db, table_name):
    result = db.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_name = ?
        """,
        [table_name]
    ).fetchone()[0]

    return result > 0


def metric_is_complete(db, table_name, expected_rows):
    if FORCE_RECOMPUTE:
        return False

    if not table_exists(db, table_name):
        return False

    row_count = db.execute(
        f"""
        SELECT COUNT(*)
        FROM {table_name}
        """
    ).fetchone()[0]

    return row_count == expected_rows


def save_scores_to_duckdb(
    db,
    scores,
    metric_name,
    table_name
):
    """
    Write a NetworKit score vector to a temporary TSV, then let
    DuckDB bulk-load it. This avoids millions of individual SQL
    INSERT statements.
    """

    score_file = SCORE_DIR / f"{metric_name}.tsv"

    print(
        f"Writing {metric_name} scores to temporary TSV...",
        flush=True
    )

    start = time.time()

    with open(
        score_file,
        "w",
        encoding="utf-8",
        newline=""
    ) as output:

        buffer = []

        for node_id, score in enumerate(scores):

            buffer.append(
                f"{node_id}\t{float(score):.17g}\n"
            )

            if len(buffer) >= 100_000:
                output.writelines(buffer)
                buffer.clear()

        if buffer:
            output.writelines(buffer)

    print(
        f"TSV written in "
        f"{elapsed_text(time.time() - start)}."
    )

    print(
        f"Bulk-loading {metric_name} into DuckDB...",
        flush=True
    )

    path = score_file.as_posix().replace("'", "''")

    db.execute(
        f"""
        DROP TABLE IF EXISTS {table_name}
        """
    )

    db.execute(
        f"""
        CREATE TABLE {table_name} AS

        SELECT
            column0::BIGINT AS author_id,
            column1::DOUBLE AS score

        FROM read_csv(
            '{path}',
            delim = '\\t',
            header = false,
            columns = {{
                'column0': 'BIGINT',
                'column1': 'DOUBLE'
            }}
        )
        """
    )

    rows = db.execute(
        f"""
        SELECT COUNT(*)
        FROM {table_name}
        """
    ).fetchone()[0]

    print(
        f"Saved {rows:,} {metric_name} scores."
    )

    # The scores are now safely inside DuckDB.
    try:
        score_file.unlink()
    except OSError:
        pass


def print_metric_top10(db, column_name, label):
    print()
    print(f"Top 10 authors by {label}:")
    print()

    rows = db.execute(
        f"""
        SELECT
            name,
            publication_count,
            degree,
            {column_name}

        FROM author_centrality

        ORDER BY {column_name} DESC

        LIMIT 10
        """
    ).fetchall()

    for rank, row in enumerate(rows, start=1):
        name, publications, degree, score = row

        print(
            f"{rank:>2}. "
            f"{name:<40} "
            f"score={score:.10g} "
            f"degree={degree:,} "
            f"papers={publications:,}"
        )


# ============================================================
# LOAD GRAPH
# ============================================================

def load_graph(total_authors):
    print()
    print("=" * 70)
    print("LOADING FULL COAUTHOR GRAPH INTO NETWORKIT")
    print("=" * 70)

    print(f"Edge list: {EDGE_FILE}")
    print(f"Expected authors: {total_authors:,}")
    print()

    start = time.time()

    # File format:
    #
    # source<TAB>target<TAB>weight
    #
    # first node id = 0
    # continuous numeric node IDs
    # undirected graph
    reader = nk.graphio.EdgeListReader(
        "\t",
        0,
        "#",
        True,
        False
    )

    graph = reader.read(str(EDGE_FILE))

    # Edge-list readers infer the node range from nodes appearing
    # in edges. Authors with no collaborators do not appear in the
    # edge list, so add any missing trailing isolated nodes.
    missing_nodes = total_authors - graph.numberOfNodes()

    if missing_nodes < 0:
        raise RuntimeError(
            "The edge list contains more node IDs than the "
            "authors table."
        )

    if missing_nodes > 0:
        graph.addNodes(missing_nodes)

    print(
        f"Graph loaded in "
        f"{elapsed_text(time.time() - start)}."
    )

    print(
        f"Nodes   : {graph.numberOfNodes():,}"
    )

    print(
        f"Edges   : {graph.numberOfEdges():,}"
    )

    print(
        f"Weighted: {graph.isWeighted()}"
    )

    return graph


# ============================================================
# PAGERANK
# ============================================================

def calculate_pagerank(graph, db):
    print()
    print("=" * 70)
    print("CENTRALITY 1 — PAGERANK")
    print("=" * 70)

    print(
        "Using collaboration frequency as edge weight."
    )

    start = time.time()

    algorithm = nk.centrality.PageRank(
        graph,
        damp=PAGERANK_DAMPING,
        tol=PAGERANK_TOLERANCE,
        normalized=False
    )

    algorithm.run()

    print(
        f"PageRank calculation finished in "
        f"{elapsed_text(time.time() - start)}."
    )

    scores = algorithm.scores()

    save_scores_to_duckdb(
        db,
        scores,
        "pagerank",
        "pagerank_scores"
    )

    del scores
    del algorithm
    gc.collect()


# ============================================================
# EIGENVECTOR CENTRALITY
# ============================================================

def calculate_eigenvector(graph, db):
    print()
    print("=" * 70)
    print("CENTRALITY 2 — EIGENVECTOR CENTRALITY")
    print("=" * 70)

    print(
        "Using collaboration frequency as edge weight."
    )

    start = time.time()

    algorithm = nk.centrality.EigenvectorCentrality(
        graph,
        tol=EIGENVECTOR_TOLERANCE
    )

    algorithm.run()

    print(
        f"Eigenvector centrality finished in "
        f"{elapsed_text(time.time() - start)}."
    )

    scores = algorithm.scores()

    save_scores_to_duckdb(
        db,
        scores,
        "eigenvector",
        "eigenvector_scores"
    )

    del scores
    del algorithm
    gc.collect()


# ============================================================
# APPROXIMATE BETWEENNESS
# ============================================================

def calculate_betweenness(weighted_graph, db):
    print()
    print("=" * 70)
    print("CENTRALITY 3 — APPROXIMATE BETWEENNESS")
    print("=" * 70)

    print(
        f"Samples: {BETWEENNESS_SAMPLES}"
    )

    print(
        "Converting to an unweighted graph first."
    )

    print(
        "Reason: collaboration count represents relationship "
        "strength, not path distance."
    )

    conversion_start = time.time()

    graph = nk.graphtools.toUnweighted(
        weighted_graph
    )

    print(
        f"Unweighted copy created in "
        f"{elapsed_text(time.time() - conversion_start)}."
    )

    start = time.time()

    algorithm = nk.centrality.EstimateBetweenness(
        graph,
        nSamples=BETWEENNESS_SAMPLES,
        normalized=True,
        parallel=BETWEENNESS_PARALLEL
    )

    algorithm.run()

    print(
        f"Approximate betweenness finished in "
        f"{elapsed_text(time.time() - start)}."
    )

    scores = algorithm.scores()

    save_scores_to_duckdb(
        db,
        scores,
        "approx_betweenness",
        "betweenness_scores"
    )

    del scores
    del algorithm
    del graph
    gc.collect()


# ============================================================
# BUILD FINAL CENTRALITY TABLE
# ============================================================

def build_final_table(db, total_authors):
    print()
    print("=" * 70)
    print("BUILDING FINAL AUTHOR CENTRALITY TABLE")
    print("=" * 70)

    denominator = max(total_authors - 1, 1)

    db.execute(
        """
        DROP TABLE IF EXISTS author_centrality
        """
    )

    db.execute(
        f"""
        CREATE TABLE author_centrality AS

        SELECT
            s.author_id,
            s.name,
            s.publication_count,
            s.degree,
            s.weighted_degree,

            s.degree::DOUBLE
                / {denominator}
                AS degree_centrality,

            COALESCE(p.score, 0.0)
                AS pagerank,

            COALESCE(e.score, 0.0)
                AS eigenvector_centrality,

            COALESCE(b.score, 0.0)
                AS approx_betweenness

        FROM author_stats s

        LEFT JOIN pagerank_scores p
            ON s.author_id = p.author_id

        LEFT JOIN eigenvector_scores e
            ON s.author_id = e.author_id

        LEFT JOIN betweenness_scores b
            ON s.author_id = b.author_id
        """
    )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
            idx_author_centrality_id
        ON author_centrality(author_id)
        """
    )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
            idx_author_centrality_name
        ON author_centrality(name)
        """
    )

    rows = db.execute(
        """
        SELECT COUNT(*)
        FROM author_centrality
        """
    ).fetchone()[0]

    print(
        f"Final rows: {rows:,}"
    )


# ============================================================
# SUMMARY
# ============================================================

def print_summary(db):
    print()
    print("=" * 70)
    print("CENTRALITY SUMMARY")
    print("=" * 70)

    print_metric_top10(
        db,
        "degree_centrality",
        "degree centrality"
    )

    print_metric_top10(
        db,
        "pagerank",
        "PageRank"
    )

    print_metric_top10(
        db,
        "eigenvector_centrality",
        "eigenvector centrality"
    )

    print_metric_top10(
        db,
        "approx_betweenness",
        "approximate betweenness"
    )


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 70)
    print("DBLP CENTRALITY CALCULATOR")
    print("=" * 70)

    if not NETWORK_DB.exists():
        raise FileNotFoundError(
            f"Network database not found:\n{NETWORK_DB}"
        )

    if not EDGE_FILE.exists():
        raise FileNotFoundError(
            f"Edge list not found:\n{EDGE_FILE}"
        )

    # Deterministic random sampling.
    nk.setSeed(
        RANDOM_SEED,
        False
    )

    print(
        f"NetworKit threads available: "
        f"{nk.getMaxNumberOfThreads()}"
    )

    db = duckdb.connect(
        str(NETWORK_DB)
    )

    try:
        total_authors = db.execute(
            """
            SELECT COUNT(*)
            FROM authors
            """
        ).fetchone()[0]

        expected_edges = db.execute(
            """
            SELECT COUNT(*)
            FROM edges
            """
        ).fetchone()[0]

        print(
            f"Authors in DuckDB: "
            f"{total_authors:,}"
        )

        print(
            f"Edges in DuckDB  : "
            f"{expected_edges:,}"
        )

        pagerank_done = metric_is_complete(
            db,
            "pagerank_scores",
            total_authors
        )

        eigenvector_done = metric_is_complete(
            db,
            "eigenvector_scores",
            total_authors
        )

        betweenness_done = metric_is_complete(
            db,
            "betweenness_scores",
            total_authors
        )

        print()
        print("Existing results:")
        print(
            f"  PageRank              : "
            f"{'DONE' if pagerank_done else 'NOT DONE'}"
        )
        print(
            f"  Eigenvector           : "
            f"{'DONE' if eigenvector_done else 'NOT DONE'}"
        )
        print(
            f"  Approx. betweenness   : "
            f"{'DONE' if betweenness_done else 'NOT DONE'}"
        )

        # Only load the huge graph if at least one metric still
        # needs to be computed.
        if not (
            pagerank_done
            and eigenvector_done
            and betweenness_done
        ):
            graph = load_graph(
                total_authors
            )

            if graph.numberOfEdges() != expected_edges:
                raise RuntimeError(
                    "Loaded NetworKit edge count does not "
                    "match DuckDB.\n"
                    f"DuckDB: {expected_edges:,}\n"
                    f"NetworKit: {graph.numberOfEdges():,}"
                )

            if not pagerank_done:
                calculate_pagerank(
                    graph,
                    db
                )
            else:
                print()
                print(
                    "Skipping PageRank: "
                    "complete table already exists."
                )

            if not eigenvector_done:
                calculate_eigenvector(
                    graph,
                    db
                )
            else:
                print()
                print(
                    "Skipping eigenvector: "
                    "complete table already exists."
                )

            if not betweenness_done:
                calculate_betweenness(
                    graph,
                    db
                )
            else:
                print()
                print(
                    "Skipping approximate betweenness: "
                    "complete table already exists."
                )

            del graph
            gc.collect()

        build_final_table(
            db,
            total_authors
        )

        print_summary(db)

        print()
        print("=" * 70)
        print("ALL CENTRALITY CALCULATIONS COMPLETE")
        print("=" * 70)

        print()
        print(
            "Final table:"
        )
        print(
            "  author_centrality"
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()
