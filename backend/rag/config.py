from __future__ import annotations

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
PROCESSED_DIR = PROJECT_DIR / "processed"
RAG_DIR = BACKEND_DIR / "rag_data"

DBLP_XML = DATA_DIR / "dblp.xml"
RAG_DB = RAG_DIR / "dblp_fts.sqlite"

PUBLICATION_TAGS = {
    "article",
    "inproceedings",
    "proceedings",
    "book",
    "incollection",
    "phdthesis",
    "mastersthesis",
    "www",
    "data",
}

# Runtime tuning. Change through environment variables without editing code.
SEMANTIC_CANDIDATE_LIMIT = max(
    10,
    min(int(os.getenv("RAG_SEMANTIC_CANDIDATES", "60")), 99),
)
DEFAULT_TOPIC_TOP_K = max(
    1,
    min(int(os.getenv("RAG_DEFAULT_TOPIC_TOP_K", "5")), 20),
)
EMBEDDING_DIMENSIONS = int(os.getenv("RAG_EMBEDDING_DIMENSIONS", "768"))

EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
PRIMARY_GENERATION_MODEL = os.getenv(
    "GEMINI_GENERATION_MODEL",
    "gemini-3.5-flash-lite",
)
FALLBACK_GENERATION_MODEL = os.getenv(
    "GEMINI_GENERATION_FALLBACK_MODEL",
    "gemini-3.8-flash",
)
