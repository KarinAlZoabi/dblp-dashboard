from pathlib import Path
import json
import duckdb

BACKEND_DIR = Path(__file__).resolve().parent.parent
NETWORK_DB = BACKEND_DIR / "network_data" / "coauthors.duckdb"
OUTPUT_DIR = BACKEND_DIR.parent / "processed" / "network"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

VISUAL_NODE_LIMIT = 120
RANKING_LIMIT = 15
MIN_EDGE_WEIGHT = 2
MAX_DISPLAY_EDGES = 1800

METRICS = {
    "degree": ("degree_centrality", "Degree Centrality"),
    "pagerank": ("pagerank", "PageRank"),
    "eigenvector": ("eigenvector_centrality", "Eigenvector Centrality"),
    "betweenness": ("approx_betweenness", "Approximate Betweenness Centrality"),
}

def export_metric(db, key, column, label):
    rows = db.execute(f"""
        SELECT author_id, name, publication_count, degree, weighted_degree,
               degree_centrality, pagerank, eigenvector_centrality,
               approx_betweenness
        FROM author_centrality
        ORDER BY {column} DESC
        LIMIT ?
    """, [VISUAL_NODE_LIMIT]).fetchall()

    cols = [
        "author_id", "name", "publication_count", "degree", "weighted_degree",
        "degree_centrality", "pagerank", "eigenvector_centrality",
        "approx_betweenness"
    ]
    nodes = [dict(zip(cols, r)) for r in rows]

    db.execute("DROP TABLE IF EXISTS selected_network_nodes")
    db.execute("CREATE TEMP TABLE selected_network_nodes(author_id BIGINT)")
    db.executemany(
        "INSERT INTO selected_network_nodes VALUES (?)",
        [(n["author_id"],) for n in nodes]
    )

    edge_rows = db.execute("""
    SELECT
        e.source,
        e.target,
        e.weight
    FROM edges e
    JOIN selected_network_nodes s1
        ON e.source = s1.author_id
    JOIN selected_network_nodes s2
        ON e.target = s2.author_id
    WHERE e.weight >= ?
    ORDER BY e.weight DESC
    LIMIT ?
    """, [MIN_EDGE_WEIGHT, MAX_DISPLAY_EDGES]).fetchall()

    links = [
        {
            "source": s,
            "target": t,
            "weight": w,
        }
        for s, t, w in edge_rows
    ]

    connected_ids = set()

    for link in links:
        connected_ids.add(link["source"])
        connected_ids.add(link["target"])

    nodes = [
        node
        for node in nodes
        if node["author_id"] in connected_ids
    ]

    ranking = [
        {
            "author_id": n["author_id"],
            "name": n["name"],
            "value": n[column],
            "degree": n["degree"],
            "publication_count": n["publication_count"],
        }
        for n in nodes[:RANKING_LIMIT]
    ]

    payload = {
        "metric": key,
        "metric_label": label,
        "full_network": {
            "nodes": 4314707,
            "edges": 32641915,
            "coauthorship_instances": 61154534,
        },
        "visualization": {
            "node_limit": VISUAL_NODE_LIMIT,
            "nodes": nodes,
            "links": links,
        },
        "ranking": ranking,
    }

    out = OUTPUT_DIR / f"{key}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    print(f"{label}: {len(nodes)} nodes, {len(links)} links -> {out}")

def main():
    db = duckdb.connect(str(NETWORK_DB), read_only=True)
    try:
        for key, (column, label) in METRICS.items():
            export_metric(db, key, column, label)
    finally:
        db.close()

if __name__ == "__main__":
    main()
