DBLP TITLE TYPO HOTFIX

Replace only:
    backend/rag/retrieval.py

No database rebuild is needed.

Why:
The previous typo fallback used an OR FTS query with LIMIT 500 but no BM25
ordering. Common words such as "all", "you", and "need" could fill the first
500 rows before the real title was considered.

The hotfix:
1. Orders the fuzzy candidate pool by title-weighted BM25.
2. Expands the candidate pool to 1000 rows.
3. Applies a conservative whole-title similarity threshold (>= 0.86).

This keeps typo recovery deterministic and prevents fuzzy title lookup from
turning into a broad semantic search.

Then run:
    python evaluate_title_typo_fix.py
    python evaluate_rag_v2.py
    python evaluate_context_planner_v2.py
    python evaluate_rag_hardening.py
