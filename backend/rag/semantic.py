from __future__ import annotations

import math

from google.genai import types

from .client import get_gemini_client
from .config import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL


def paper_to_text(paper: dict) -> str:
    """Compact representation for topical relevance; author lists add noise here."""
    return (
        f"Title: {paper.get('title', '')}\n"
        f"Venue: {paper.get('venue', '')}\n"
        f"Year: {paper.get('year', '')}\n"
        f"Type: {paper.get('type', '')}"
    )


def cosine_similarity(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _embed_batch(texts: list[str]) -> list[list[float]]:
    client = get_gemini_client()
    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(
            task_type="SEMANTIC_SIMILARITY",
            output_dimensionality=EMBEDDING_DIMENSIONS,
        ),
    )
    return [item.values for item in response.embeddings]


def semantic_rerank(query: str, papers: list[dict], top_k: int = 5) -> list[dict]:
    if not papers:
        return []

    documents = [paper_to_text(paper) for paper in papers]
    texts = [query] + documents

    # Gemini currently caps a batch at 100 inputs. Chunk defensively so a
    # future candidate-limit change cannot recreate the old 101-input crash.
    embeddings: list[list[float]] = []
    for start in range(0, len(texts), 100):
        embeddings.extend(_embed_batch(texts[start:start + 100]))

    query_embedding = embeddings[0]
    paper_embeddings = embeddings[1:]

    results = []
    for paper, embedding in zip(papers, paper_embeddings):
        item = dict(paper)
        item["semantic_score"] = round(
            cosine_similarity(query_embedding, embedding),
            6,
        )
        results.append(item)

    results.sort(key=lambda item: item["semantic_score"], reverse=True)
    return results[:max(1, top_k)]
