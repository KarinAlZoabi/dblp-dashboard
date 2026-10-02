from __future__ import annotations

import re

from .analytics import get_dataset_statistics, get_top_coauthors, page_count_from_range
from .conversation import (
    apply_context_to_plan,
    get_or_create_session,
    planner_context,
    resolve_followup_fallback,
    update_session_from_response,
)
from .generator import generate_grounded_answer
from .answer_polish import polish_grounded_answer
from .parsing import extract_year_filters, normalize_text
from .planner import plan_question
from .response_renderer import (
    render_author_ambiguous,
    render_author_multi_match,
    render_author_not_found,
    render_author_publication_count,
    render_author_publications,
    render_coauthors,
    render_dataset_author_count,
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
        (
            re.search(r"\b(find|show|list|search|looking for|interested in)\b", q)
            and re.search(r"\b(papers?|publications?|articles?|research|work)\b", q)
        )
        or re.search(r"\b(?:papers?|publications?|articles?|research|work)\s+(?:about|on|regarding)\b", q)
    )


def _answer_resolved_question(
    question: str,
    default_top_k: int = 5,
    plan: dict | None = None,
) -> dict:
    question = (question or "").strip()
    if not question:
        return {
            "question": question,
            "intent": "invalid",
            "answer": "Please enter a DBLP question.",
            "count": 0,
            "sources": [],
        }

    plan = plan or plan_question(question)
    intent = plan["intent"]

    if intent == "smalltalk":
        return {
            "question": question,
            "intent": intent,
            "answer": (
                "Hi! I can help you search and analyze DBLP publications, "
                "authors, venues, years, co-authors, and research topics."
            ),
            "count": 0,
            "sources": [],
        }

    if intent == "clarify":
        reason = plan.get("reason")

        if reason == "year_only":
            year = plan.get("year_from")
            answer = (
                f"What would you like to know about {year}? "
                "For example, I can find papers from that year, "
                "filter an author's publications, or search a research topic."
            )
        elif reason == "missing_topic":
            answer = (
                "Sure — what kind of papers are you looking for? "
                "You can give me a research topic, author, title, year, or venue."
            )
        else:
            answer = (
                "Sure — what would you like to explore in DBLP? "
                "You can ask about a paper, author, research topic, venue, or year."
            )

        return {
            "question": question,
            "intent": intent,
            "answer": answer,
            "count": 0,
            "sources": [],
            "reason": reason,
        }

    if intent == "unsupported":
        reason = plan.get("reason")

        if reason == "code":
            answer = (
                "That looks like pasted code rather than a DBLP research "
                "question. I can help with publications, authors, venues, "
                "years, co-authors, and research topics."
            )
        elif reason == "planner_unavailable":
            answer = (
                "I could not confidently interpret that as a DBLP request "
                "right now. Try asking about a publication, author, venue, "
                "year, co-author relationship, or research topic."
            )
        elif reason == "out_of_domain":
            answer = (
                "That is outside this assistant's DBLP research scope. "
                "I can help with publications, authors, titles, venues, years, "
                "co-authors, and research topics."
            )
        elif reason == "noise":
            answer = (
                "I couldn't identify a DBLP question in that message. "
                "Try giving me a paper title, author, research topic, venue, or year."
            )
        else:
            answer = (
                "That does not look like a DBLP bibliographic question. "
                "Try asking me to find papers, look up an author or title, "
                "filter publications, or explore a research topic."
            )

        return {
            "question": question,
            "intent": intent,
            "answer": answer,
            "count": 0,
            "sources": [],
            "reason": reason,
        }

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

    if intent == "dataset_author_count":
        stats = get_dataset_statistics()
        count = stats.get("unique_authors")
        return {
            "question": question,
            "intent": intent,
            "answer": render_dataset_author_count(stats),
            "count": count,
            "sources": [],
            "statistics": stats,
            "setup_required": count is None,
        }

    if intent == "author_summary":
        author = plan.get("author") or ""
        result = get_author_publications(
            author,
            limit=None,
            sort_order="latest",
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
        resolved = result.get("resolved_author") or author
        years = sorted({
            paper.get("year")
            for paper in papers
            if isinstance(paper.get("year"), int)
        })

        venues = {}
        for paper in papers:
            venue = (paper.get("venue") or "").strip()
            if venue:
                venues[venue] = venues.get(venue, 0) + 1

        top_venues = sorted(
            venues.items(),
            key=lambda item: (-item[1], item[0]),
        )[:3]

        parts = [
            f"{resolved} is an author identity in the indexed DBLP data "
            f"with {len(papers)} publication"
            f"{'s' if len(papers) != 1 else ''}."
        ]

        if years:
            parts.append(
                f"The indexed publications span {years[0]} to {years[-1]}."
            )

        if top_venues:
            venue_text = ", ".join(
                f"{venue} ({count})"
                for venue, count in top_venues
            )
            parts.append(
                f"The most frequent venues in these records are {venue_text}."
            )

        parts.append(
            "DBLP is bibliographic, so I won't invent biographical details "
            "that are not present in the dataset."
        )

        return {
            "question": question,
            "intent": intent,
            "answer": " ".join(parts),
            "count": len(papers),
            "sources": source_cards(papers[:5]),
            "resolved_author": result.get("resolved_author"),
        }

    if intent in {"author_publications", "author_publication_count"}:
        author = plan.get("author") or ""

        # Exact author queries are deterministic database lookups, not topic
        # search. Return all matching publications unless the user explicitly
        # requested a numeric limit (e.g. "latest 3").
        if intent == "author_publication_count":
            limit = None
            all_results = True
        elif plan.get("limit") is not None:
            limit = plan["limit"]
            all_results = False
        else:
            limit = None
            all_results = True

        result = get_author_publications(
            author,
            year_from=plan.get("year_from"),
            year_to=plan.get("year_to"),
            limit=limit,
            venue=plan.get("venue"),
            pub_type=plan.get("pub_type"),
            sort_order=plan.get("sort_order") or "latest",
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
                # Keep the resolved identity in the conversation state even
                # when the requested year/filter has zero publications.
                "resolved_author": result.get("resolved_author"),
                "matched_identities": result.get("matched_identities", []),
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
        venue=plan.get("venue"),
        pub_type=plan.get("pub_type"),
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
            answer = generate_grounded_answer(
                question,
                results,
            )
            answer = polish_grounded_answer(
                answer,
                search_text=search_text,
            )
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


def _plan_missing_required_entity(plan: dict) -> bool:
    intent = plan.get("intent")

    publication_intents = {
        "publication_authors",
        "publication_venue",
        "publication_pages",
        "publication_page_count",
        "publication_year",
        "publication_volume",
        "publication_number",
        "publication_publisher",
        "publication_ee",
        "publication_details",
    }

    author_intents = {
        "author_publications",
        "author_publication_count",
        "author_summary",
        "top_coauthors",
    }

    if intent in publication_intents:
        return not plan.get("title")

    if intent in author_intents:
        return not plan.get("author")

    return False


def answer_chat_question(
    question: str,
    default_top_k: int = 5,
    session_id: str | None = None,
) -> dict:
    """
    Hybrid conversational orchestration.

    1. Obvious standalone questions are planned locally in milliseconds.
    2. Ambiguous/follow-up language goes to Gemini WITH compact verified
       conversation context.
    3. Python resolves concrete stored entities and performs every DBLP lookup.
    4. Gemini never supplies bibliographic facts.
    """
    session_id, state = get_or_create_session(
        session_id
    )

    context = planner_context(state)

    planner_exception = None

    try:
        plan = plan_question(
            question,
            context=context,
        )
    except Exception as exc:
        # Conversation understanding is optional infrastructure. A temporary
        # planner/API error must never turn an otherwise usable DBLP endpoint
        # into HTTP 500.
        planner_exception = type(exc).__name__
        plan = {
            "intent": "unsupported",
            "reason": "planner_unavailable",
            "_planner": "failed",
            "planner_error": planner_exception,
        }

    plan, context_used = apply_context_to_plan(
        plan,
        state,
    )

    # If the remote planner is unavailable or returned a plan that still lacks
    # a required entity, use the tiny deterministic rewrite layer as a backup.
    # This is resilience, not the primary conversation mechanism.
    if (
        plan.get("_planner") == "failed"
        or _plan_missing_required_entity(plan)
    ):
        fallback_question, fallback_context = (
            resolve_followup_fallback(
                question,
                state,
            )
        )

        if fallback_question != question:
            fallback_plan = plan_question(
                fallback_question,
                context=None,
            )

            fallback_plan, fallback_used = (
                apply_context_to_plan(
                    fallback_plan,
                    state,
                )
            )

            # Prefer the fallback only if it produced a usable plan.
            if not _plan_missing_required_entity(
                fallback_plan
            ):
                plan = fallback_plan
                context_used.update(
                    fallback_context
                )
                context_used.update(
                    fallback_used
                )

    response = _answer_resolved_question(
        question,
        default_top_k=default_top_k,
        plan=plan,
    )

    response["question"] = question
    response["session_id"] = session_id

    if context_used:
        response["context_used"] = context_used

    # Helpful during development/evaluation; the frontend can ignore it.
    response["planner_mode"] = plan.get(
        "_planner",
        "unknown",
    )

    planner_warning = (
        planner_exception
        or plan.get("planner_error")
    )
    if planner_warning:
        response["planner_warning"] = planner_warning

    update_session_from_response(
        state,
        response,
        plan=plan,
        question=question,
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
