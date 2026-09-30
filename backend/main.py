from pathlib import Path
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.rag.config import PROCESSED_DIR, RAG_DB
from backend.rag.models import RAGChatRequest, RAGSearchRequest
from backend.rag.service import (
    answer_chat_question,
    lexical_search_payload,
    semantic_search_payload,
)


app = FastAPI(
    title="DBLP Dashboard API",
    description="Backend API for the DBLP publication dashboard and RAG assistant",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_json(filename: str):
    path = PROCESSED_DIR / filename
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Processed data file not found: {filename}",
        )
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


@app.get("/")
def root():
    return {"message": "DBLP Dashboard API is running"}


@app.get("/api/health")
def health():
    return {"status": "healthy"}


@app.get("/api/kpis")
def get_kpis():
    return load_json("kpis.json")


@app.get("/api/publications/yearly")
def get_yearly_publications():
    return load_json("yearly_publications.json")


@app.get("/api/publications/types")
def get_publication_types():
    return load_json("publication_types.json")


@app.get("/api/publications/types-by-year")
def get_publication_types_by_year():
    return load_json("publication_types_by_year.json")


@app.get("/api/authors/distribution")
def get_author_distribution():
    return load_json("author_distribution.json")


@app.get("/api/collaboration")
def get_collaboration():
    return load_json("collaboration.json")


@app.get("/api/venues")
def get_venues():
    return load_json("venues.json")


@app.get("/api/data-quality")
def get_data_quality():
    return load_json("missing_data.json")


@app.get("/api/topics-over-time")
def topics_over_time():
    return load_json("topics_over_time.json")


@app.get("/api/rag/health")
def rag_health():
    return {
        "index_exists": RAG_DB.exists(),
        "index_path": str(RAG_DB),
    }


@app.post("/api/rag/search")
def rag_search(request: RAGSearchRequest):
    return lexical_search_payload(request.question, request.top_k)


@app.post("/api/rag/semantic-search")
def rag_semantic_search(request: RAGSearchRequest):
    return semantic_search_payload(request.question, request.top_k)


@app.post("/api/rag/chat")
def rag_chat(request: RAGChatRequest):
    return answer_chat_question(
        request.question,
        default_top_k=request.top_k,
        session_id=request.session_id,
    )
