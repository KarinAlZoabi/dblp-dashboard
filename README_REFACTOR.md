# DBLP Backend Refactor

This package replaces the current `backend/main.py` and `backend/rag/` code.
It preserves the existing HTTP endpoints used by the React frontend:

- `GET /api/health`
- dashboard JSON endpoints
- `GET /api/rag/health`
- `POST /api/rag/search`
- `POST /api/rag/semantic-search`
- `POST /api/rag/chat`

## Important: keep your database

Do NOT delete or replace:

- `backend/rag_data/dblp_fts.sqlite`
- `data/dblp.xml`
- `processed/`

If you already ran `details_indexer.py`, no reindex is needed.

## Replace files

1. Back up your current `backend/main.py` and `backend/rag/` folder.
2. Replace `backend/main.py` with the supplied file.
3. Replace the contents of `backend/rag/` with the supplied folder.
4. Leave `backend/rag_data/` untouched.

The old `search.py`, `router.py`, `pipeline.py`, and monolithic `tools.py` are intentionally removed. Their responsibilities are now separated across `db.py`, `parsing.py`, `retrieval.py`, `analytics.py`, `planner.py`, and `service.py`.

## Run

In the PowerShell session containing `GEMINI_API_KEY`:

```powershell
python -m uvicorn backend.main:app --reload
```

Then run the stronger evaluation suite from the project root:

```powershell
python evaluate_rag_v2.py
```

## If paper_details does not exist

Only if page/volume/publisher queries say metadata is unavailable because the sidecar table was never built:

```powershell
python -m backend.rag.details_indexer
```

You do NOT need to rebuild the FTS index.

## Architecture

`main.py` is API wiring only.

`rag/parsing.py`
: Fast deterministic routing and entity/year parsing. This is checked before any LLM planner call.

`rag/planner.py`
: Gemini fallback planner only for wording the local router cannot confidently classify.

`rag/retrieval.py`
: FTS5/BM25, exact title lookup, author resolution, semantic candidate retrieval, and embedding fallback behavior.

`rag/analytics.py`
: Dataset counts, coauthor frequency, and page-count calculations.

`rag/semantic.py`
: Gemini embeddings and cosine reranking. Candidate text is compact to reduce latency.

`rag/generator.py`
: Grounded LLM synthesis for questions that actually benefit from generation.

`rag/service.py`
: Central orchestration and stable API response format.

## Key reliability/performance changes

- Structured DBLP questions no longer call Gemini planner first.
- Simple topic searches skip the generation call after semantic reranking.
- Embedding failure falls back to BM25 evidence instead of falsely saying no evidence exists.
- Semantic candidates default to 60 instead of 99; tune with `RAG_SEMANTIC_CANDIDATES`.
- Gemini client is cached and reused.
- Semantic documents no longer embed long author lists, reducing tokens and noise.
- The 100-input embedding batch limit is handled defensively.
- Year-filtered ambiguous authors return matching publications with identity labels instead of failing immediately.
- `www` profile records remain excluded from publication results.
- N+1 metadata queries are removed by joining `paper_details` where available.
- Exact title, page range, page count, venue, year, volume, number, publisher and electronic-edition questions are deterministic.
- Indexer no longer depends on semantic/Gemini modules and can create FTS + detail tables in one pass on future rebuilds.

## Tuning

Optional environment variables:

```powershell
$env:RAG_SEMANTIC_CANDIDATES="60"
$env:RAG_EMBEDDING_DIMENSIONS="768"
$env:GEMINI_EMBEDDING_MODEL="gemini-embedding-001"
$env:GEMINI_GENERATION_MODEL="gemini-3.5-flash-lite"
$env:GEMINI_GENERATION_FALLBACK_MODEL="gemini-3.8-flash"
```

For lower latency, try `RAG_SEMANTIC_CANDIDATES=40` after evaluation. For higher recall, use 60-80. Keep it <=99 unless you intentionally want multiple embedding batches.

## Conversational response rendering

Structured DBLP facts remain deterministic. `backend/rag/response_renderer.py`
turns verified results into concise natural-language answers without making an
extra LLM/API call. This keeps structured-query latency low and prevents the
response-style layer from changing facts.

Examples:

- `Kassem Danach has 3 publications between 2015 and 2020 in the indexed DBLP data.`
- `'Attention Is All You Need.' was written by ...`
- `The NIPS version of 'Attention Is All You Need.' is 11 pages long (5998-6008).`

`service.py` is the only integration point; retrieval and analytics are unchanged.
