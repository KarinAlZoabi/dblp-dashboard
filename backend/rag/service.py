from __future__ import annotations

import re

from .analytics import get_dataset_statistics, get_top_coauthors, page_count_from_range
from .conversation import (
    get_or_create_session,
    resolve_followup,
    update_session_from_response,
)
from .generator import generate_grounded_answer
from .parsing import extract_year_filters, normalize_text
from .planner import plan_question
from .response_renderer import (
    render_author_ambiguous,
    render_author_multi_match,
    render_author_not_found,
    render_author_publication_count,
    render_author_publications,
    render_coauthors,
    render_dataset_count,
    render_publication_authors,
    render_publication_details,
    render_publication_ee,
    render_publication_field,
    render_publication_not_found,
    render_publication_page_count,
    render_publication_pages,
    render_publication_venue,
    render_publication_year,
    render_topic_not_found,
    render_topic_results,
)
from .retrieval import (
    find_publication_by_title,
    get_author_publications,
    lexical_search,
    semantic_topic_search,
)


def source_cards(papers: list[dict]) -> list[dict]:
    cards = []
    for index, paper in enumerate(papers, 1):
        card = {
            "id": f"P{index}",
            "title": paper.get("title", ""),
            "authors": paper.get("authors", []),
            "venue": paper.get("venue", ""),
            "year": paper.get("year"),
            "type": paper.get("type", ""),
            "key": paper.get("key", ""),
            "pages": paper.get("pages", ""),
            "volume": paper.get("volume", ""),
            "number": paper.get("number", ""),
            "publisher": paper.get("publisher", ""),
            "ee": paper.get("ee", ""),
        }
        if paper.get("semantic_score") is not None:
            card["semantic_score"] = paper["semantic_score"]
        if paper.get("matched_author"):
            card["matched_author"] = paper["matched_author"]
        cards.append(card)
    return cards


def _ambiguous_author(question: str, result: dict, intent: str) -> dict:
    identities = result.get("identities", [])
    return {
        "question": question,
        "intent": "author_disambiguation",
        "requested_intent": intent,
        "answer": render_author_ambiguous(
            result.get("requested_author", ""),
            identities,
        ),
        "count": 0,
        "sources": [],
        "author_identities": identities,
    }


def _publication_fact_answer(question: str, intent: str, title: str) -> dict:
    papers = find_publication_by_title(title)
    if not papers:
        return {
            "question": question,
            "intent": intent,
            "answer": render_publication_not_found(title),
            "count": 0,
            "sources": [],
        }

    first = papers[0]
    actual_title = first.get("title", title)

    if intent == "publication_authors":
        answer = render_publication_authors(actual_title, first.get("authors", []))
    elif intent == "publication_venue":
        answer = render_publication_venue(actual_title, papers)
    elif intent == "publication_pages":
        answer = render_publication_pages(actual_title, papers)
    elif intent == "publication_page_count":
        answer = render_publication_page_count(
            actual_title, papers, page_count_from_range
        )
    elif intent == "publication_year":
        answer = render_publication_year(actual_title, papers)
    elif intent == "publication_volume":
        answer = render_publication_field(actual_title, papers, "volume")
    elif intent == "publication_number":
        answer = render_publication_field(actual_title, papers, "number")
    elif intent == "publication_publisher":
        answer = render_publication_field(actual_title, papers, "publisher")
    elif intent == "publication_ee":
        answer = render_publication_ee(actual_title, papers)
    else:
        answer = render_publication_details(actual_title, first)

    return {
        "question": question,
        "intent": intent,
        "answer": answer,
        "count": len(papers),
        "sources": source_cards(papers),
    }


def _is_simple_discovery(question: str) -> bool:
    q = question.casefold()
    return bool(
        re.search(r"\b(find|show|list|search)\b", q)
        and re.search(r"\b(papers?|publications?|articles?|research)\b", q)
    )


def _answer_resolved_question(question: str, default_top_k: int = 5) -> dict:
    question = (question or "").strip()
    if not question:
        return {
            "question": question,
            "intent": "invalid",
            "answer": "Please enter a DBLP question.",
            "count": 0,
            "sources": [],
        }

    plan = plan_question(question)
    intent = plan["intent"]

    if intent == "dataset_count":
        stats = get_dataset_statistics()
        return {
            "question": question,
            "intent": intent,
            "answer": render_dataset_count(stats),
            "count": stats["publication_records"],
            "sources": [],
            "statistics": stats,
        }

    if intent in {"author_publications", "author_publication_count"}:
        author = plan.get("author") or ""
        all_results = bool(plan.get("all_results"))
        limit = None if all_results or intent == "author_publication_count" else (plan.get("limit") or default_top_k)
        result = get_author_publications(
            author,
            year_from=plan.get("year_from"),
            year_to=plan.get("year_to"),
            limit=limit,
        )

        if result["status"] == "ambiguous":
            return _ambiguous_author(question, result, intent)
        if result["status"] == "not_found":
            return {
                "question": question,
                "intent": intent,
                "answer": render_author_not_found(author),
                "count": 0,
                "sources": [],
            }

        papers = result.get("publications", [])
        if intent == "author_publication_count":
            return {
                "question": question,
                "intent": intent,
                "answer": render_author_publication_count(
                    result.get("resolved_author") or author,
                    len(papers),
                    plan.get("year_from"),
                    plan.get("year_to"),
                ),
                "count": len(papers),
                "sources": [],
                "resolved_author": result.get("resolved_author"),
                "matched_identities": result.get("matched_identities", []),
            }

        if not papers:
            return {
                "question": question,
                "intent": intent,
                "answer": render_author_publications(
                    result.get("resolved_author") or author,
                    0,
                    plan.get("year_from"),
                    plan.get("year_to"),
                ),
                "count": 0,
                "sources": [],
            }

        if result["status"] == "multi_match":
            identities = result.get("matched_identities", [])
            intro = render_author_multi_match(
                author,
                identities,
                len(papers),
                plan.get("year_from"),
                plan.get("year_to"),
            )
        else:
            resolved = result.get("resolved_author", author)
            intro = render_author_publications(
                resolved,
                len(papers),
                plan.get("year_from"),
                plan.get("year_to"),
                all_results=all_results,
            )

        return {
            "question": question,
            "intent": intent,
            "answer": intro,
            "count": len(papers),
            "sources": source_cards(papers),
            "resolved_author": result.get("resolved_author"),
            "matched_identities": result.get("matched_identities", []),
        }

    if intent == "top_coauthors":
        author = plan.get("author") or ""
        result = get_top_coauthors(author, limit=plan.get("limit") or 3)
        if result["status"] == "ambiguous":
            return _ambiguous_author(question, result, intent)
        if result["status"] == "not_found":
            return {
                "question": question,
                "intent": intent,
                "answer": render_author_not_found(author),
                "count": 0,
                "sources": [],
            }
        if result["status"] == "multi_match":
            return _ambiguous_author(question, result, intent)

        coauthors = result.get("coauthors", [])
        resolved_author = result.get("resolved_author", author)
        return {
            "question": question,
            "intent": intent,
            "answer": render_coauthors(resolved_author, coauthors),
            "count": len(coauthors),
            "sources": [],
            "coauthors": coauthors,
            "resolved_author": result.get("resolved_author"),
        }

    publication_intents = {
        "publication_authors", "publication_venue", "publication_pages",
        "publication_page_count", "publication_year", "publication_volume",
        "publication_number", "publication_publisher", "publication_ee",
        "publication_details",
    }
    if intent in publication_intents:
        return _publication_fact_answer(question, intent, plan.get("title") or "")

    # Conceptual topic discovery.
    search_text = plan.get("search_text") or question
    top_k = plan.get("limit") or default_top_k
    results, retrieval_mode, retrieval_error = semantic_topic_search(
        search_text,
        year_from=plan.get("year_from"),
        year_to=plan.get("year_to"),
        top_k=top_k,
    )

    if not results:
        return {
            "question": question,
            "intent": "topic_search",
            "answer": render_topic_not_found(
                search_text,
                plan.get("year_from"),
                plan.get("year_to"),
            ),
            "count": 0,
            "sources": [],
            "retrieval_mode": retrieval_mode,
        }

    # For simple search/list requests, a deterministic answer is both faster
    # and safer; the semantic reranker has already done the ML work.
    if _is_simple_discovery(question):
        answer = render_topic_results(
            len(results),
            search_text,
            plan.get("year_from"),
            plan.get("year_to"),
        )
    else:
        try:
            answer = generate_grounded_answer(question, results)
        except Exception:
            answer = f"I found {len(results)} relevant DBLP publication{'s' if len(results) != 1 else ''}; the generation service is temporarily unavailable, so I am returning the verified sources directly."

    payload = {
        "question": question,
        "intent": "topic_search",
        "answer": answer,
        "count": len(results),
        "sources": source_cards(results),
        "retrieval_mode": retrieval_mode,
        "plan": plan,
    }
    if retrieval_error:
        payload["retrieval_warning"] = retrieval_error
    return payload


def answer_chat_question(
    question: str,
    default_top_k: int = 5,
    session_id: str | None = None,
) -> dict:
    """
    Answer one chat turn while preserving lightweight conversational context.

    The DBLP facts remain deterministic. Conversation memory is only used to
    resolve references such as "it", "that paper", "they", and "the second one".
    """
    session_id, state = get_or_create_session(session_id)

    resolved_question, context_used = resolve_followup(
        question,
        state,
    )

    response = _answer_resolved_question(
        resolved_question,
        default_top_k=default_top_k,
    )

    # Preserve the literal user message for frontend/debug display.
    response["question"] = question
    response["session_id"] = session_id

    if resolved_question != question:
        response["resolved_question"] = resolved_question

    if context_used:
        response["context_used"] = context_used

    update_session_from_response(
        state,
        response,
    )

    return response


def lexical_search_payload(question: str, top_k: int = 5) -> dict:
    year_from, year_to, search_text = extract_year_filters(question)
    results = lexical_search(question, top_k=top_k)
    return {
        "question": question,
        "interpreted_query": {
            "search_text": search_text,
            "year_from": year_from,
            "year_to": year_to,
        },
        "count": len(results),
        "results": results,
    }


def semantic_search_payload(question: str, top_k: int = 5) -> dict:
    year_from, year_to, no_year = extract_year_filters(question)
    from .parsing import clean_topic_text
    search_text = clean_topic_text(no_year) or no_year
    results, mode, error = semantic_topic_search(
        search_text, year_from, year_to, top_k=top_k
    )
    payload = {
        "question": question,
        "interpreted_query": {
            "search_text": search_text,
            "year_from": year_from,
            "year_to": year_to,
        },
        "count": len(results),
        "results": results,
        "retrieval_mode": mode,
    }
    if error:
        payload["retrieval_warning"] = error
    return payload
