# DBLP Research Dashboard with Hybrid RAG Assistant

An interactive DBLP analytics dashboard with a grounded research assistant for exploring publications, authors, venues, publication metadata, co-authorship, and research topics.

The project combines:

- a **React + Vite** dashboard,
- a **FastAPI** backend,
- the official **DBLP XML dataset**,
- **SQLite FTS5 + BM25** for fast lexical retrieval,
- **semantic embeddings** for relevance reranking,
- deterministic bibliographic functions for exact facts,
- a minimal **Gemini** language layer for ambiguous query interpretation and grounded answer generation,
- multi-turn conversational context,
- DBLP source cards and citations.

---

## 1. Project Goals

The system was designed around one main principle:

> **DBLP supplies the facts. Python retrieves or calculates them. The LLM interprets language and explains verified evidence.**

The assistant is therefore not a generic chatbot over DBLP.

Questions that can be answered exactly are handled by deterministic code whenever possible. Semantic retrieval and the LLM are used only where they add value.

Examples:

- `Who wrote "Attention Is All You Need"?`
  - exact bibliographic lookup
- `How many publications does Kassem Danach have?`
  - deterministic database count
- `Find federated learning papers from 2020 to 2023`
  - metadata filtering + BM25 + semantic reranking
- `What about privacy?`
  - conversational context + semantic topic refinement
- `How many pages does it have?`
  - conversation memory + exact publication metadata

---

## 2. Dataset

The project uses the official DBLP XML bibliography.

The indexed dataset used during development contained approximately:

- **12.9 million total DBLP records**
- **8.7 million publication records** after excluding profile/web records from publication search

The exact numbers depend on the DBLP snapshot used to build the local index.

The XML is not scanned for every query. Instead, it is streamed once and transformed into structures optimized for analytics and search.

---

## 3. System Architecture

```text
                              User
                               |
                               v
                     React Chat Interface
                               |
                               v
                         FastAPI Backend
                               |
                               v
                    Query / Intent Routing
                     /                 \
                    /                   \
       deterministic/local       ambiguous/follow-up
              rules                    |
                |                      v
                |              Gemini query planner
                |                      |
                +----------+-----------+
                           |
                           v
                  Structured execution
                 /         |          \
                /          |           \
        exact lookup    analytics     topic search
             |              |              |
             |              |              v
             |              |        SQLite FTS5
             |              |          + BM25
             |              |              |
             |              |         candidate set
             |              |              |
             |              |              v
             |              |        embeddings
             |              |      semantic rerank
             |              |              |
             +--------------+--------------+
                            |
                            v
                    Verified DBLP evidence
                            |
                  +---------+---------+
                  |                   |
        deterministic response   grounded Gemini
                  |                   |
                  +---------+---------+
                            |
                            v
                  Answer + DBLP sources
```

---

## 4. Why Hybrid Retrieval?

Pure keyword search is strong for exact bibliographic information but weaker when the wording of a query differs from the wording of a paper title.

Pure semantic search is better at conceptual similarity but is less appropriate for strict bibliographic facts such as:

- exact author names,
- publication titles,
- venues,
- years,
- page ranges,
- DBLP identity suffixes.

The project therefore uses a hybrid approach.

### Stage 1 — Structured parsing and filters

The query router extracts information such as:

- author,
- exact title,
- year,
- year range,
- venue,
- publication type,
- requested result count,
- latest / oldest ordering.

Hard constraints are applied deterministically instead of being left to the LLM.

### Stage 2 — BM25 candidate retrieval

SQLite FTS5 provides fast full-text retrieval over indexed DBLP fields.

BM25 is used to obtain a relatively small candidate set from millions of records.

This gives strong lexical recall while avoiding a full semantic scan of the DBLP corpus.

### Stage 3 — Semantic reranking

Only the BM25 candidate set is embedded and compared semantically with the user's query.

This is much cheaper than embedding all 12.9 million DBLP records in advance.

Conceptually:

```text
12.9M DBLP records
        |
        v
SQLite FTS5 / BM25
        |
        v
small candidate set
        |
        v
semantic embeddings
        |
        v
cosine similarity
        |
        v
reranked top results
```

Repeated semantic requests are cached in memory to reduce unnecessary remote embedding calls.

### Stage 4 — Grounded generation

For topic-style answers, Gemini receives only retrieved DBLP evidence.

It is not treated as the bibliographic source of truth.

The response is tied back to deterministic evidence identifiers such as:

```text
P1
P2
P3
```

which are rendered as clickable source references in the frontend.

---

## 5. Minimal Role of the LLM

A design requirement of this project is to keep LLM responsibility as small as practical.

### The LLM is used for

- interpreting ambiguous natural-language questions,
- resolving flexible conversational phrasing,
- understanding follow-up questions,
- refining research-topic queries,
- turning retrieved DBLP evidence into a natural-language answer.

### The LLM is not responsible for

- publication counts,
- author counts,
- exact author lookup,
- title lookup,
- year filtering,
- venue filtering,
- publication-type filtering,
- latest/oldest ordering,
- page-range lookup,
- page-count calculation,
- co-author statistics,
- DBLP identity disambiguation,
- source creation,
- database truth.

These operations are implemented in Python and SQL.

This separation reduces hallucination risk and makes the system easier to test.

---

## 6. Conversation Memory

The chatbot maintains a lightweight server-side conversation state using a session identifier.

This allows follow-ups such as:

```text
Who wrote "Attention Is All You Need"?
→ How many pages does it have?
→ What is its page range?
```

or:

```text
What did Kassem Danach publish in 2020?
→ What about 2023?
```

or:

```text
Find papers about federated learning
→ What about privacy?
→ Only from 2020 to 2023
→ Who wrote the second one?
```

Unsupported input and accidental pasted code do not overwrite the last useful research context.

Starting a new chat creates a fresh conversational context.

---

## 7. Input Guardrails

The assistant distinguishes DBLP questions from obvious non-research input.

Examples handled explicitly include:

- pasted CSS / JavaScript / Python,
- greetings,
- random text,
- out-of-domain requests,
- vague questions,
- year-only requests such as `2023`,
- incomplete requests such as `papers???`.

Rather than forcing every input into a search intent, the assistant can:

- ask for clarification,
- identify unsupported input,
- greet the user,
- preserve the previous valid conversation state.

---

## 8. Main Chatbot Capabilities

The final assistant supports:

- exact publication-title lookup,
- typo-tolerant title lookup,
- author lookup,
- author identity disambiguation,
- DBLP numeric author suffixes,
- all publications by an author,
- author publication counts,
- author + year filtering,
- year ranges,
- venue filters,
- publication-type filters,
- latest / oldest publications,
- top-N results,
- page ranges,
- calculated page counts,
- publication years,
- publication venues,
- co-author frequency,
- dataset record counts,
- dataset unique-author count,
- semantic research-topic discovery,
- multi-turn conversational references,
- topic refinements,
- result references such as "the second one",
- missing-data handling,
- unsupported-input handling.

---

## 9. Frontend Features

The chatbot UI includes:

- compact floating chat mode,
- full-screen mode,
- new-chat control,
- staged loading indicators,
- conversational messages,
- rendered bullet lists,
- clickable `P1`, `P2`, ... citations,
- collapsible DBLP source cards,
- source metadata badges,
- direct DBLP record links,
- progressive `Show 5 more` source display,
- graceful backend-error messaging,
- responsive mobile layout.

The dashboard itself visualizes DBLP statistics and derived analytics through interactive React/Recharts components.

---

## 10. Technology Stack

### Backend

- Python
- FastAPI
- SQLite
- SQLite FTS5
- DuckDB (co-author/network analysis)
- BM25
- lxml
- Pydantic
- Google GenAI API
- python-dotenv

### Frontend

- React
- Vite
- Axios
- Recharts
- CSS

### Data

- Official DBLP XML
- DBLP DTD
- generated dashboard JSON files
- generated local SQLite FTS index

---

## 11. Repository Structure

A simplified structure is shown below.

```text
DBLP Dashboard/
|
|-- backend/
|   |-- main.py
|   |
|   |-- rag/
|   |   |-- analytics.py
|   |   |-- answer_polish.py
|   |   |-- config.py
|   |   |-- conversation.py
|   |   |-- generator.py
|   |   |-- indexer.py
|   |   |-- models.py
|   |   |-- parsing.py
|   |   |-- planner.py
|   |   |-- response_renderer.py
|   |   |-- retrieval.py
|   |   |-- semantic.py
|   |   |-- service.py
|   |   |-- author_stats_indexer.py
|   |
|   |-- rag_data/
|   |   |-- dblp_fts.sqlite          # generated locally, not committed
|   |
|   |-- network/
|       |-- build_coauthor_db.py
|       |-- *.duckdb                  # generated locally, not committed
|
|-- data/
|   |-- dblp.xml                     # downloaded locally, not committed
|   |-- dblp.dtd                     # downloaded locally, not committed
|
|-- frontend/
|   |-- src/
|   |   |-- components/
|   |   |   |-- Chatbot.jsx
|   |   |   |-- Chatbot.css
|   |   |-- App.jsx
|   |   |-- App.css
|   |
|   |-- package.json
|
|-- processed/                        # dashboard data
|
|-- evaluate_rag_v2.py
|-- evaluate_context_planner_v2.py
|-- evaluate_rag_hardening.py
|-- evaluate_input_guardrails.py
|-- evaluate_submission_fixes.py
|-- evaluate_professor_ui_fixes.py
|
|-- .env.example
|-- .gitignore
|-- requirements.txt
|-- README.md
```

The exact set of preprocessing/evaluation scripts may vary slightly depending on the final repository cleanup.

---

## 12. Environment Setup

### 12.1 Clone the repository

```bash
git clone <repository-url>
cd "DBLP Dashboard"
```

### 12.2 Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 12.3 Install backend dependencies

```powershell
python -m pip install -r requirements.txt
```

Verify the environment:

```powershell
python -m pip check
```

### 12.4 Configure Gemini

Copy:

```text
.env.example
```

to:

```text
.env
```

Then set:

```env
GEMINI_API_KEY=your_api_key_here
```

The real `.env` file must not be committed.

---

## 13. DBLP Data Setup

Download the official DBLP XML dataset and its matching DTD.

Place them in the project's `data/` directory according to the paths configured in:

```text
backend/rag/config.py
```

The raw XML and generated search database are intentionally excluded from Git because of their size.

---

## 14. Build the RAG Search Index

Run the DBLP RAG indexer from the project root.

```powershell
python -m backend.rag.indexer
```

The indexer uses streaming XML parsing so the complete DBLP XML tree is not loaded into memory at once.

It extracts bibliographic fields such as:

- title,
- authors,
- venue,
- DBLP key,
- year,
- publication type,
- pages,
- volume,
- number,
- publisher,
- electronic edition identifier where available.

The resulting SQLite FTS database is generated locally under:

```text
backend/rag_data/
```

---

## 15. Build the Unique-Author Statistic

For an existing index, run:

```powershell
python -m backend.rag.author_stats_indexer
```

This streams the DBLP XML, calculates the unique author-name count for publication records, stores the final statistic, and removes its temporary counting database.

---

## 16. Run the Backend

From the project root:

```powershell
python -m uvicorn backend.main:app --reload
```

The API is available at:

```text
http://127.0.0.1:8000
```

FastAPI documentation:

```text
http://127.0.0.1:8000/docs
```

Health endpoint:

```text
http://127.0.0.1:8000/api/health
```

---

## 17. Run the Frontend

Open a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

The Vite development server normally runs at:

```text
http://localhost:5173
```

---

## 18. Main RAG API Endpoints

### Health

```text
GET /api/rag/health
```

### Lexical search

```text
POST /api/rag/search
```

### Semantic search

```text
POST /api/rag/semantic-search
```

### Conversational assistant

```text
POST /api/rag/chat
```

The frontend primarily communicates with the conversational endpoint.

---

## 19. Evaluation

The final chatbot was tested incrementally using several regression suites.

| Test suite | Result |
|---|---:|
| Core RAG regression | 21 / 21 |
| Context planner | 7 / 7 |
| Adversarial / hardening queries | 52 / 52 |
| Hardening multi-turn chains | 4 / 4 |
| Input guardrails | 10 / 10 |
| Submission-fix regression | 5 / 5 |
| Professor-style UI fixes | 11 / 11 |

The hardening suite covered categories including:

- unusual phrasing,
- capitalization,
- punctuation,
- exact and fuzzy title lookup,
- author typos,
- author ambiguity,
- metadata filters,
- year filters,
- venue filters,
- publication-type filters,
- missing metadata,
- semantic relevance,
- malformed input,
- top-N requests,
- latest / oldest ordering,
- dataset and author counts,
- conversational result references.

Observed latency depends strongly on the execution path.

Structured local lookups are generally much faster than semantic requests because semantic reranking may require a remote embedding API call.

Repeated identical semantic searches can use the in-memory cache.

---

## 20. Example Demo Sequence

A short project demonstration can use the following sequence.

### 1. Deterministic dataset analytics

```text
How many publications are in the DBLP dataset?
```

Demonstrates that aggregate facts bypass the LLM.

### 2. Exact bibliographic lookup

```text
Who wrote "Attention Is All You Need"?
```

Demonstrates exact title matching and DBLP evidence.

### 3. Conversational context

```text
How many pages does it have?
```

Demonstrates reference resolution using conversation memory.

### 4. Author disambiguation and filtering

```text
Show me the publications by Hussein Hazimeh.
```

Demonstrates DBLP identity handling.

### 5. Hybrid topic search

```text
Find federated learning papers from 2020 to 2023.
```

Demonstrates metadata filtering, BM25 candidate retrieval, semantic embeddings, and reranking.

### 6. Topic refinement

```text
What about privacy?
```

Demonstrates multi-turn semantic refinement.

### 7. Result reference

```text
Who wrote the second one?
```

Demonstrates conversational references to retrieved source records.

---

## 21. Design Decisions

### Why not embed the entire DBLP corpus?

A full vector index over roughly 12.9 million records would require a much larger embedding job, persistent vector storage, and additional indexing infrastructure.

Instead, this project uses:

```text
BM25 -> small candidate set -> embeddings -> reranking
```

This provides semantic capability while keeping the project practical on local hardware and within external API limits.

### Why SQLite FTS5?

FTS5 provides:

- fast local full-text search,
- BM25 ranking,
- no separate search server,
- easy integration with Python,
- efficient lookup over millions of bibliographic records.

### Why not let Gemini answer DBLP facts directly?

Because the model is not the authoritative DBLP database.

Allowing it to independently answer authors, titles, years, venues, or counts would introduce unnecessary hallucination risk.

The project therefore retrieves or calculates the evidence first.

---

## 22. Limitations

The system still has practical limitations.

- Semantic reranking depends on an external embedding service.
- Remote API latency can vary.
- The in-memory conversation state is not intended as permanent chat storage.
- Semantic ranking operates over BM25 candidates rather than a complete dense-vector index of DBLP.
- DBLP is primarily a bibliographic dataset; it does not provide full paper content for every record.
- Duplicate-looking records may represent legitimate versions of the same work, such as conference and CoRR records.
- Author-name counts refer to DBLP author-name identities/names in the indexed data and should not automatically be interpreted as perfectly deduplicated real-world people.

---

## 23. Security and Repository Notes

Do not commit:

- `.env`
- API keys
- `.venv/`
- `node_modules/`
- raw DBLP XML / DTD / compressed source files
- the multi-gigabyte SQLite FTS database
- generated DuckDB network/co-author databases
- SQLite WAL/SHM files
- temporary databases
- generated logs / debug artifacts

Commit `.env.example` instead of the real `.env`.

---

## 24. Core Principle

The final architecture can be summarized in one sentence:

> **DBLP is the source of truth, deterministic code performs exact operations, semantic retrieval finds conceptually relevant evidence, and the LLM acts as the natural-language interface.**
