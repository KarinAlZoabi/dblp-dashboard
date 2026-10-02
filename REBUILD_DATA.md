# Rebuilding the DBLP Dashboard From a Fresh Clone

This guide explains how to restore the project after cloning it from GitHub when the large generated data files are not stored in the repository.

## 1. Files intentionally excluded from GitHub

Large source/generated files should remain local:

```text
data/dblp.xml
data/dblp.dtd
data/*.gz

backend/rag_data/*.sqlite*
backend/rag_data/*.db*

backend/network_data/*.duckdb*
backend/network_data/*.tsv
```

The repository stores the source code and the scripts needed to recreate them.

## 2. Clone the repository

```powershell
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd "DBLP Dashboard"
```

## 3. Create the Python environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip check
```

## 4. Configure Gemini

Copy `.env.example` to `.env` and add your key:

```env
GEMINI_API_KEY=your_real_api_key_here
```

Never commit `.env`.

## 5. Install the frontend

```powershell
cd frontend
npm install
cd ..
```

## 6. Download DBLP

Download the official DBLP XML dataset and matching DTD, then place them in:

```text
data/
├── dblp.xml
└── dblp.dtd
```

The exact configured paths are in `backend/rag/config.py`.

# Rebuild generated data

Recommended order:

```text
1. Dashboard processed data
2. RAG FTS5 index
3. Extra RAG details
4. Unique-author statistic
5. Co-author/network database
6. Network centralities
7. Network dashboard export
```

## 7. Dashboard preprocessing

```powershell
python preprocess.py
```

This recreates the JSON files used by the dashboard under `processed/`.

## 8. RAG search index

```powershell
python -m backend.rag.indexer
```

This creates the multi-gigabyte SQLite/FTS5 search index under `backend/rag_data/`.

## 9. Additional RAG metadata

If present in the final project:

```powershell
python -m backend.rag.details_indexer
```

## 10. Unique-author statistic

```powershell
python -m backend.rag.author_stats_indexer
```

This is required for questions such as:

```text
How many authors does DBLP have?
```

## 11. Co-author/network database

```powershell
python backend/network/build_coauthor_db.py
```

This may create very large files under `backend/network_data/`, including files such as:

```text
coauthors.duckdb
coauthor_edges.tsv
paper_authors.tsv
```

These are generated files and must not be committed to GitHub.

## 12. Calculate network centralities

```powershell
python backend/network/calculate_centralities.py
```

## 13. Export network dashboard data

```powershell
python backend/network/export_network_dashboard.py
```

# Run the application

## 14. Backend

```powershell
python -m uvicorn backend.main:app --reload
```

Backend:

```text
http://127.0.0.1:8000
```

FastAPI docs:

```text
http://127.0.0.1:8000/docs
```

## 15. Frontend

In another terminal:

```powershell
cd frontend
npm run dev
```

Usually:

```text
http://localhost:5173
```

# Verify the rebuild

Check:

- dashboard charts load,
- RAG health reports an existing index,
- exact publication lookups work,
- author queries work,
- semantic topic searches work,
- network visualizations load.

Useful chatbot checks:

```text
How many publications are in the DBLP dataset?
Who wrote "Attention Is All You Need"?
How many publications does Kassem Danach have?
Find federated learning papers from 2020 to 2023.
```

## 16. Regression tests

If the final tests are under `tests/`:

```powershell
python tests/evaluate_rag_v2.py
python tests/evaluate_context_planner_v2.py
python tests/evaluate_rag_hardening.py
python tests/evaluate_input_guardrails.py
python tests/evaluate_submission_fixes.py
python tests/evaluate_professor_ui_fixes.py
```

If they remain in the project root, run them from there instead.

# Optional fast restore

Regeneration is reproducible, but it may take time.

Before deleting the original project, you may optionally archive these large folders/files to an external drive or cloud storage:

```text
data/dblp.xml
data/dblp.dtd
backend/rag_data/
backend/network_data/
processed/
```

Then future recovery can use:

```text
GitHub source code + optional large-data backup
```

instead of rebuilding everything.

# Before deleting the original laptop copy

1. Push all source-code changes to GitHub.
2. Confirm `.env` is not tracked.
3. Confirm XML, SQLite, DuckDB, and TSV files are not tracked.
4. Perform at least one clean-clone test in another folder.
5. Verify this guide still matches the final scripts.
6. Optionally back up the generated data elsewhere.

Only then delete the original multi-gigabyte project copy.
