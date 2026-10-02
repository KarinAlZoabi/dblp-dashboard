# DBLP Dashboard — Architecture

This document describes the **implemented architecture** of the final DBLP Dashboard and its hybrid RAG research assistant.

It intentionally documents what is actually present in the project rather than earlier design ideas that were considered during development.

---

## 1. Architectural Principle

The system follows one rule throughout the backend:

> **DBLP is the source of truth. Deterministic code performs exact operations. Semantic retrieval finds relevant evidence. The LLM acts as the natural-language interface.**

This separation was chosen to minimize hallucination risk in a bibliographic domain where details such as author identity, year, venue, page range, publication type, and DBLP record key must be exact.

The LLM is therefore **not** used as the database.

---

## 2. High-Level Architecture

```text
                                USER
                                  |
                                  v
                      React / Vite Dashboard
                                  |
                                  v
                       FastAPI REST Backend
                                  |
                                  v
                    +--------------------------+
                    | Query / Intent Resolution|
                    +--------------------------+
                         |                |
                         |                |
                  obvious/local      ambiguous/follow-up
                         |                |
                         |                v
                         |         Gemini Query Planner
                         |                |
                         +--------+-------+
                                  |
                                  v
                       Deterministic Execution
                    /             |              \
                   /              |               \
          exact metadata       analytics        topic search
              lookup              |                 |
                 |                |                 v
                 |                |          SQLite FTS5 / BM25
                 |                |                 |
                 |                |          candidate records
                 |                |                 |
                 |                |                 v
                 |                |        semantic embeddings
                 |                |                 |
                 |                |          cosine reranking
                 |                |                 |
                 +----------------+-----------------+
                                  |
                                  v
                        Verified DBLP Evidence
                         /                 \
                        /                   \
          deterministic response       grounded Gemini
                        \                   /
                         \                 /
                          +---------------+
                                  |
                                  v
                       Answer + P1/P2 Sources
                                  |
                                  v
                     React Chatbot Presentation
```

---

## 3. Two Data Pipelines

The project contains two related but separate data pipelines.

### 3.1 Dashboard analytics pipeline

```text
dblp.xml
   |
   v
streaming preprocessing
   |
   v
processed/*.json
   |
   v
FastAPI analytics endpoints
   |
   v
React + Recharts visualizations
```

This pipeline supports dashboard charts and aggregate indicators.

Examples include:

- publications by year,
- publication types,
- publication types over time,
- collaboration statistics,
- venues,
- data-quality statistics,
- topic trends.

### 3.2 RAG / chatbot pipeline

```text
dblp.xml
   |
   v
streaming RAG indexer
   |
   v
SQLite FTS5 database
   |
   +--> exact metadata retrieval
   |
   +--> BM25 lexical retrieval
           |
           v
      candidate set
           |
           v
    semantic reranking
           |
           v
     grounded answer
```

The chatbot does not query the dashboard JSON files for individual publications. It uses the DBLP-derived search index because the chatbot needs record-level bibliographic evidence.

---

## 4. Backend API Layer

### Main file

```text
backend/main.py
```

This file defines the FastAPI application and exposes both dashboard and RAG endpoints.

Important responsibilities:

- application creation,
- CORS configuration,
- loading processed dashboard JSON,
- exposing analytics endpoints,
- exposing RAG endpoints,
- forwarding chatbot requests to the RAG service layer.

Main RAG endpoints:

```text
GET  /api/rag/health
POST /api/rag/search
POST /api/rag/semantic-search
POST /api/rag/chat
```

The frontend chatbot primarily uses:

```text
POST /api/rag/chat
```

---

## 5. RAG Module Structure

The RAG backend is split into focused modules rather than one large file.

```text
backend/rag/
|
|-- config.py
|-- models.py
|-- parsing.py
|-- planner.py
|-- conversation.py
|-- service.py
|-- retrieval.py
|-- semantic.py
|-- generator.py
|-- response_renderer.py
|-- answer_polish.py
|-- analytics.py
|-- indexer.py
|-- details_indexer.py
|-- author_stats_indexer.py
```

### Module responsibilities

| Module | Responsibility |
|---|---|
| `config.py` | paths, environment variables, model configuration |
| `models.py` | Pydantic request/response models |
| `parsing.py` | deterministic intent detection and structured filter extraction |
| `planner.py` | Gemini-based interpretation for ambiguous/flexible language |
| `conversation.py` | session state and follow-up resolution |
| `service.py` | central orchestration and routing |
| `retrieval.py` | exact lookup, author lookup, BM25 retrieval, filters, ranking |
| `semantic.py` | embedding generation and semantic reranking |
| `generator.py` | grounded LLM answer generation |
| `response_renderer.py` | deterministic natural-language answers |
| `answer_polish.py` | presentation-only cleanup of grounded answers |
| `analytics.py` | dataset-level statistics |
| `indexer.py` | DBLP XML -> SQLite FTS5 index |
| `details_indexer.py` | additional publication metadata indexing |
| `author_stats_indexer.py` | one-time unique-author statistic generation |

---

## 6. Query Resolution

The system does not send every user message directly to Gemini.

It uses a two-stage strategy.

### 6.1 Deterministic local routing

`parsing.py` recognizes high-confidence query forms locally.

Examples:

```text
How many publications are in DBLP?
Who wrote "Attention Is All You Need"?
How many pages does "Attention Is All You Need" have?
Give me the top 3 publications by Kassem Danach.
What did Kassem Danach publish in 2023?
```

Local routing is preferred because it is:

- faster,
- reproducible,
- easy to test,
- less prone to hallucination,
- appropriate for strict bibliographic operations.

It also extracts structured values such as:

```text
author
title
year_from
year_to
venue
publication type
limit
sort order
```

### 6.2 Gemini planner

If the local parser cannot confidently interpret the question, `planner.py` uses Gemini to convert flexible natural language into a structured plan.

Example:

```text
Roughly speaking, what's Kassem Danach's publication output?
```

may become conceptually:

```json
{
  "intent": "author_publication_count",
  "author": "Kassem Danach"
}
```

The planner is also useful for conversational language such as:

```text
What about privacy?
Tell me about the newest one instead.
How many did he have that year?
```

The planner is an **interpreter**, not an evidence source.

---

## 7. Supported Intent Families

The final system handles several intent families.

### Dataset / analytics

```text
dataset_count
dataset_author_count
```

### Author

```text
author_publications
author_publication_count
author_summary
top_coauthors
author_disambiguation
```

### Publication metadata

```text
publication_authors
publication_venue
publication_year
publication_pages
publication_page_count
publication_details
```

### Discovery

```text
topic_search
```

### Conversation / safety

```text
smalltalk
clarify
unsupported
```

This routing prevents unrelated input from being forced into a DBLP search.

---

## 8. Exact Bibliographic Retrieval

Strict facts are resolved through deterministic retrieval functions.

Examples:

- exact paper title,
- publication authors,
- publication year,
- venue,
- page range,
- calculated page count,
- publication type,
- author publications,
- publication counts,
- latest / oldest publication,
- venue and type filters,
- co-author frequency.

For bibliographic questions, this path is preferred over semantic generation.

### Why?

A semantic model may consider two records similar, but bibliographic queries often require exact identity.

For example:

```text
Attention Is All You Need
```

is not the same request as:

```text
Not All Attention Is All You Need
```

The retrieval layer therefore includes bibliographic-specific title comparison and typo recovery rather than relying only on general semantic similarity.

---

## 9. Author Identity Handling

DBLP may contain multiple people with the same display name.

The system therefore supports DBLP-style identity suffixes such as:

```text
Hussein Hazimeh
Hussein Hazimeh 0002
```

It also supports shortened numeric suffix input where possible, such as:

```text
Hussein Hazimeh 002
```

When an author name is ambiguous, the assistant returns a disambiguation response instead of silently mixing publication records from different people.

Profile / `www` records are not returned as publications.

---

## 10. FTS5 + BM25 Retrieval

The local search index uses:

```text
SQLite FTS5
```

with BM25 ranking.

The FTS index contains publication-level DBLP metadata such as:

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
- electronic edition where available.

### Why SQLite FTS5?

It provides:

- fast local full-text search,
- BM25 ranking,
- no separate search server,
- easy Python integration,
- practical indexing over millions of DBLP records.

---

## 11. Topic Search Pipeline

Topic discovery follows this flow:

```text
User topic query
      |
      v
structured filters extracted
      |
      v
SQLite FTS5 / BM25
      |
      v
candidate publications
      |
      v
semantic embedding comparison
      |
      v
cosine-similarity reranking
      |
      v
top evidence records
      |
      v
grounded answer generation
```

Example:

```text
Find papers about machine learning for detecting cyber attacks
```

BM25 first finds lexically relevant candidate records.

The embedding stage then improves ordering by meaning, allowing conceptually relevant titles to rank well even when wording is not identical.

---

## 12. Why the Entire DBLP Corpus Is Not Embedded

The implemented system does **not** precompute dense embeddings for all approximately 12.9 million records.

Instead:

```text
DBLP corpus
   |
   v
BM25 candidate retrieval
   |
   v
small candidate pool
   |
   v
embedding API
   |
   v
semantic reranking
```

This was chosen because a full dense-vector index would require:

- millions of embedding operations,
- substantially more storage,
- additional vector-index infrastructure,
- a longer ingestion pipeline.

The implemented design provides semantic relevance while keeping the project practical on local hardware and external API limits.

---

## 13. Semantic Cache

Repeated identical topic queries are cached in memory.

Conceptually:

```text
normalized semantic query
        |
        v
     cache?
     /    \
   yes     no
    |       |
    |      BM25
    |       |
    |   embeddings
    |       |
    |   reranking
    |       |
    +---- cache result
            |
            v
          answer
```

This avoids repeated remote embedding calls for the same request during the lifetime of the backend process.

---

## 14. Grounded Answer Generation

`generator.py` receives verified DBLP records and asks Gemini to formulate a natural-language answer.

Important constraint:

> The model is given retrieved evidence; it is not asked to independently invent DBLP facts.

Evidence is assigned deterministic identifiers:

```text
P1
P2
P3
...
```

The frontend connects those identifiers to the actual source cards.

If generation fails, verified retrieval results can still be returned rather than fabricating an answer.

---

## 15. Answer Presentation Layer

`answer_polish.py` modifies **presentation only**.

It may:

- remove robotic phrases such as "Based on the provided DBLP records",
- normalize bullet formatting,
- improve list introductions,
- preserve citations.

It does not alter bibliographic evidence.

The frontend renders:

- paragraphs,
- bullet lists,
- bold text,
- clickable `P1`, `P2`, ... citations.

---

## 16. Conversation Architecture

Conversation memory is handled by:

```text
conversation.py
```

Each chatbot session receives a session identifier.

The server stores recent context such as:

- last publication title,
- last author,
- last topic query,
- last filters,
- previous returned sources,
- last interpreted intent.

Example:

```text
User: Who wrote "Attention Is All You Need"?
Assistant: ...

User: How many pages does it have?
```

The second request can inherit the previously resolved publication.

Another example:

```text
User: What did Kassem Danach publish in 2020?
Assistant: ...

User: What about 2023?
```

The author is inherited and only the year changes.

---

## 17. Context Resolution Strategy

Gemini is the primary interpreter for genuinely flexible conversational language.

A small deterministic fallback exists for high-confidence follow-ups so the assistant does not completely break during a temporary planner/API outage.

Examples include:

```text
What about 2023?
What is its page range?
What about privacy?
```

The fallback is intentionally limited.

The architecture does **not** attempt to replace the LLM planner with a giant list of handcrafted sentence rules.

---

## 18. Input Guardrails

The assistant supports explicit non-search outcomes.

### `smalltalk`

Example:

```text
hello
```

### `clarify`

Examples:

```text
2023
papers???
tell me something
```

### `unsupported`

Examples:

```text
pasted CSS
pasted Python
write me a poem about cats
random non-DBLP text
```

This prevents arbitrary input from being incorrectly routed to dataset counts or semantic search.

Unsupported turns do not erase the last useful conversation state.

---

## 19. Deduplication Strategy

Duplicate-looking DBLP records must be treated carefully.

For example, a work may legitimately have:

- a conference record,
- a CoRR/arXiv record.

The backend therefore does not merge records merely because title, authors, and year look similar.

Records are suppressed only when sameness can be verified, such as:

- repeated DBLP key,
- repeated non-empty electronic edition identifier.

This preserves legitimate publication versions.

---

## 20. Author Result Limits

Semantic topic searches use a small default result limit.

Exact author queries behave differently.

Example:

```text
Get me the publications by Kassem Danach
```

returns the complete matching author publication set.

Example:

```text
Give me the top 3 publications by Kassem Danach
```

returns exactly three.

The frontend can progressively display large source sets using:

```text
Show 5 more
```

without truncating the actual backend result.

---

## 21. Frontend Chat Architecture

Main component:

```text
frontend/src/components/Chatbot.jsx
```

Styling:

```text
frontend/src/components/Chatbot.css
```

Main UI features:

- floating launcher,
- compact popup mode,
- full-screen mode,
- new-chat reset,
- staged loading messages,
- message history,
- natural multi-turn interaction,
- source expansion,
- clickable citations,
- direct DBLP links,
- progressive source display,
- mobile layout,
- backend outage handling.

---

## 22. Full-Screen Mode

The chatbot can switch between:

```text
compact floating mode
```

and:

```text
full-screen research-assistant mode
```

The same session state is retained while toggling the layout.

Starting a **new chat** clears the frontend messages and starts a fresh backend conversation session.

---

## 23. Error and Failure Behavior

The architecture avoids turning infrastructure failures into fabricated DBLP answers.

### Backend unavailable

The frontend displays a connection-oriented message rather than an Axios traceback.

### Gemini generation unavailable

Verified DBLP retrieval evidence can still be returned.

### Gemini planner unavailable

High-confidence deterministic questions still work locally.

Flexible questions either use a narrow emergency fallback or fail safely with a clarification message.

### Missing bibliographic data

The assistant reports that the requested metadata is unavailable instead of inventing it.

---

## 24. Analytics and Network Components

The project also includes non-RAG analysis code.

A co-author/network preprocessing component uses:

```text
DuckDB
```

for generated network-analysis data.

These generated database files are local build artifacts and should not be committed to Git.

---

## 25. Indexing Strategy

The DBLP XML is very large, so the project uses streaming XML parsing through `lxml`.

Conceptually:

```text
dblp.xml
   |
   v
iterparse()
   |
   v
one record at a time
   |
   +--> extract fields
   +--> insert/index
   |
   v
clear XML element from memory
```

This avoids loading the complete XML document into RAM.

---

## 26. Repository Artifacts

Large generated files are intentionally excluded from Git.

Examples:

```text
data/*.xml
data/*.dtd
data/*.gz
backend/rag_data/*.sqlite*
backend/network/*.duckdb
.env
.venv/
node_modules/
```

The repository should contain:

- source code,
- preprocessing/indexing scripts,
- evaluation scripts,
- dependency declarations,
- `.env.example`,
- documentation.

---

## 27. Evaluation Architecture

The chatbot was developed using regression tests rather than only manual testing.

Final recorded suites:

| Suite | Result |
|---|---:|
| Core RAG regression | 21 / 21 |
| Context planner | 7 / 7 |
| Adversarial hardening | 52 / 52 |
| Multi-turn hardening chains | 4 / 4 |
| Input guardrails | 10 / 10 |
| Submission fixes | 5 / 5 |
| Professor-style UI fixes | 11 / 11 |

The hardening tests cover:

- weird phrasing,
- capitalization,
- punctuation,
- title typos,
- author typos,
- author ambiguity,
- metadata lookup,
- year filters,
- venue filters,
- publication type,
- latest / oldest,
- top-N,
- missing records,
- malformed input,
- semantic relevance,
- conversation chains.

---

## 28. Latency Characteristics

The system has two broad performance classes.

### Local deterministic queries

Examples:

```text
exact title
author publication count
page range
dataset count
```

These are usually very fast because they use local SQLite/Python logic.

### Semantic queries

Examples:

```text
Find research about privacy in federated learning
```

These may be slower because semantic reranking uses a remote embedding service.

The project therefore uses:

- BM25 preselection,
- small semantic candidate sets,
- in-memory semantic caching,
- local deterministic routing where possible.

---

## 29. What Is Not Part of the Implemented Architecture

Earlier project design documents considered additional techniques.

The final submitted architecture does **not** depend on:

- a full 12.9M-record vector database,
- Reciprocal Rank Fusion,
- a cross-encoder reranker,
- LangChain,
- autonomous agents,
- paper-PDF ingestion,
- live web search.

These ideas are intentionally excluded from this architecture document because they are not required by the implemented system.

---

## 30. Design Rationale Summary

### Exact operations stay deterministic

Because bibliographic facts must be correct.

### BM25 reduces the search space

Because it is efficient over millions of DBLP records.

### Embeddings are used only on candidates

Because full-corpus dense indexing is unnecessary for this project scale and deadline.

### The LLM interprets language, not database truth

Because an LLM should not be trusted to invent bibliographic metadata.

### Evidence is exposed to the user

Because answers should be traceable to DBLP source records.

### Conversation state is explicit

Because follow-up questions require context that a stateless search endpoint does not provide.

### Regression tests protect behavior

Because fixing one query type should not silently break another.

---

## 31. Final Architecture in One Diagram

```text
                         OFFICIAL DBLP XML
                          /            \
                         /              \
                        v                v
              dashboard preprocess    RAG indexer
                        |                |
                        v                v
               processed JSON       SQLite FTS5
                        |                |
                        |                |
                        +------ FastAPI -+
                                 |
                                 v
                             user query
                                 |
                                 v
                     deterministic parser
                          /            \
                  understood          ambiguous
                      |                   |
                      |                   v
                      |             Gemini planner
                      |                   |
                      +---------+---------+
                                |
                                v
                         structured plan
                         /      |       \
                        /       |        \
                    exact   analytics   topic
                      |        |          |
                      |        |        BM25
                      |        |          |
                      |        |      candidates
                      |        |          |
                      |        |      embeddings
                      |        |          |
                      |        |       rerank
                      \        |          /
                       \       |         /
                        +------+--------+
                               |
                               v
                       verified evidence
                        /             \
                deterministic       grounded
                   renderer          Gemini
                        \             /
                         +-----------+
                               |
                               v
                    answer + citations
                               |
                               v
                         React chatbot
```

---

## 32. Architectural Principle to Defend

If the system has to be summarized during a project defense, use this:

> **The assistant uses deterministic Python and SQLite operations for facts, filters, counts, and metadata. BM25 narrows millions of DBLP records to a candidate set, semantic embeddings rerank only those candidates, and Gemini is used mainly to interpret flexible natural language and phrase answers from verified DBLP evidence.**
