from __future__ import annotations

import time

from google.genai import types
from google.genai.errors import ServerError

from .client import get_gemini_client
from .config import FALLBACK_GENERATION_MODEL, PRIMARY_GENERATION_MODEL


def build_evidence(papers: list[dict]) -> str:
    blocks = []
    for index, paper in enumerate(papers, 1):
        blocks.append(
            "\n".join([
                f"[P{index}]",
                f"Title: {paper.get('title', '')}",
                f"Authors: {', '.join(paper.get('authors', []))}",
                f"Year: {paper.get('year', '')}",
                f"Venue: {paper.get('venue', '')}",
                f"Type: {paper.get('type', '')}",
                f"Pages: {paper.get('pages', '')}",
                f"DBLP Key: {paper.get('key', '')}",
            ])
        )
    return "\n\n".join(blocks)


def _generate(prompt: str) -> str:
    client = get_gemini_client()
    last_error = None

    for model_name in (PRIMARY_GENERATION_MODEL, FALLBACK_GENERATION_MODEL):
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=900,
                    ),
                )
                return response.text or ""
            except ServerError as exc:
                last_error = exc
                if attempt == 0:
                    time.sleep(1.0)

    if last_error:
        raise last_error
    raise RuntimeError("Generation failed without a reported error.")


def generate_grounded_answer(question: str, papers: list[dict]) -> str:
    if not papers:
        return "I could not find sufficient evidence in the DBLP dataset."

    evidence = build_evidence(papers)
    prompt = f"""
You are a DBLP bibliographic research assistant.
Answer only from the supplied DBLP evidence. Do not invent abstracts, methods,
results, conclusions, authors, years, venues, page ranges, or identifiers.
Cite supporting records as [P1], [P2], etc. If the evidence does not support a
claim, say that the DBLP metadata is insufficient. Be concise.

USER QUESTION:
{question}

DBLP EVIDENCE:
{evidence}

ANSWER:
"""
    return _generate(prompt)
