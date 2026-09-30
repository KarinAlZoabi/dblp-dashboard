"""High-level DBLP chat engine.

Structured questions are answered deterministically from SQLite.
Only conceptual topic-search questions use embeddings + LLM generation.
"""

from __future__ import annotations

from .generator import generate_grounded_answer
from .planner import plan_question
from .tools import (
    find_publication_by_title,
    get_author_publications,
    get_dataset_statistics,
    get_top_coauthors,
    semantic_topic_search,
)

from .tools import page_count_from_range


def _source_cards(papers: list[dict]) -> list[dict]:
    cards = []
    for i, paper in enumerate(papers, 1):
        cards.append({
            "id": f"P{i}",
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
            "semantic_score": paper.get("semantic_score"),
        })
    return cards


def _ambiguous_author_response(question: str, result: dict) -> dict:
    identities = result.get("identities", [])
    text = (
        f"I found multiple DBLP author identities matching "
        f"'{result.get('requested_author', '')}': "
        + ", ".join(identities)
        + ". Please specify which identity you mean."
    )
    return {
        "question": question,
        "intent": "author_disambiguation",
        "answer": text,
        "count": 0,
        "sources": [],
        "author_identities": identities,
    }


def answer_chat_question(question: str, default_top_k: int = 5) -> dict:
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

    # --------------------------------------------------------
    # Dataset statistics
    # --------------------------------------------------------
    if intent == "dataset_count":
        stats = get_dataset_statistics()
        answer = (
            f"The indexed DBLP dataset contains "
            f"{stats['total_records']:,} total DBLP records. "
            f"{stats['publication_records']:,} are publication records "
            f"when DBLP 'www' profile/web records are excluded."
        )
        return {
            "question": question,
            "intent": intent,
            "answer": answer,
            "count": stats["publication_records"],
            "sources": [],
            "statistics": stats,
        }

    # --------------------------------------------------------
    # Author publications / counts
    # --------------------------------------------------------
    if intent in {"author_publications", "author_publication_count"}:
        author = plan.get("author") or ""
        all_results = bool(plan.get("all_results"))
        limit = None if all_results or intent == "author_publication_count" else (
            plan.get("limit") or default_top_k
        )

        result = get_author_publications(
            author,
            year_from=plan.get("year_from"),
            year_to=plan.get("year_to"),
            limit=limit,
        )

        if result["status"] == "ambiguous":
            return _ambiguous_author_response(question, result)

        if result["status"] == "not_found":
            return {
                "question": question,
                "intent": intent,
                "answer": f"I could not find a DBLP author matching '{author}'.",
                "count": 0,
                "sources": [],
            }

        papers = result["publications"]
        resolved = result.get("resolved_author", author)

        if intent == "author_publication_count":
            year_phrase = ""
            if plan.get("year_from") is not None:
                if plan.get("year_to") == plan.get("year_from"):
                    year_phrase = f" in {plan['year_from']}"
                else:
                    year_phrase = (
                        f" from {plan['year_from']} to {plan['year_to']}"
                    )
            return {
                "question": question,
                "intent": intent,
                "answer": (
                    f"{resolved} has {len(papers)} publication"
                    f"{'s' if len(papers) != 1 else ''}{year_phrase} "
                    f"in the indexed DBLP data."
                ),
                "count": len(papers),
                "sources": [],
                "resolved_author": resolved,
            }

        if not papers:
            return {
                "question": question,
                "intent": intent,
                "answer": (
                    f"I found the DBLP author identity '{resolved}', "
                    "but no matching publications for the requested filters."
                ),
                "count": 0,
                "sources": [],
                "resolved_author": resolved,
            }

        return {
            "question": question,
            "intent": intent,
            "answer": (
                f"I found {len(papers)} matching publication"
                f"{'s' if len(papers) != 1 else ''} for {resolved}."
            ),
            "count": len(papers),
            "sources": _source_cards(papers),
            "resolved_author": resolved,
        }

    # --------------------------------------------------------
    # Coauthor analytics
    # --------------------------------------------------------
    if intent == "top_coauthors":
        author = plan.get("author") or ""
        limit = plan.get("limit") or 3
        result = get_top_coauthors(author, limit=limit)

        if result["status"] == "ambiguous":
            return _ambiguous_author_response(question, result)

        if result["status"] == "not_found":
            return {
                "question": question,
                "intent": intent,
                "answer": f"I could not find a DBLP author matching '{author}'.",
                "count": 0,
                "sources": [],
            }

        coauthors = result.get("coauthors", [])
        resolved = result.get("resolved_author", author)

        if not coauthors:
            answer = f"I found no coauthors for {resolved} in the indexed publications."
        else:
            rendered = "; ".join(
                f"{i}. {item['author']} ({item['count']} shared publication"
                f"{'s' if item['count'] != 1 else ''})"
                for i, item in enumerate(coauthors, 1)
            )
            answer = f"Top {len(coauthors)} coauthors of {resolved}: {rendered}."

        return {
            "question": question,
            "intent": intent,
            "answer": answer,
            "count": len(coauthors),
            "sources": [],
            "coauthors": coauthors,
            "resolved_author": resolved,
        }

    # --------------------------------------------------------
    # Exact publication facts
    # --------------------------------------------------------
    if intent in {
         "publication_authors",
    "publication_venue",
    "publication_pages",
    "publication_page_count",
    "publication_details",
    }:
        title = plan.get("title") or ""
        papers = find_publication_by_title(title)

        if not papers:
            return {
                "question": question,
                "intent": intent,
                "answer": (
                    f"I could not find a sufficiently close DBLP publication "
                    f"matching '{title}'."
                ),
                "count": 0,
                "sources": [],
            }

        if intent == "publication_authors":
            # Usually versions share the same authors, so use the first exact/best record.
            authors = papers[0].get("authors", [])
            answer = (
                f"Authors of '{papers[0]['title']}': "
                + ", ".join(authors)
                + "."
            )

        elif intent == "publication_venue":
            entries = []
            for paper in papers:
                venue = paper.get("venue") or "venue not specified"
                entries.append(
                    f"{paper.get('year')}: {venue} ({paper.get('type')})"
                )
            answer = (
                f"DBLP contains {len(papers)} matching version"
                f"{'s' if len(papers) != 1 else ''} of '{papers[0]['title']}': "
                + "; ".join(entries)
                + "."
            )

        elif intent == "publication_pages":
            page_entries = [
                f"{paper.get('venue') or paper.get('type')}: {paper.get('pages')}"
                for paper in papers
                if paper.get("pages")
            ]
            if page_entries:
                answer = (
                    f"Page range information for '{papers[0]['title']}': "
                    + "; ".join(page_entries)
                    + "."
                )
            else:
                answer = (
                    f"I found '{papers[0]['title']}', but no page range is "
                    "stored for the matching DBLP record(s)."
                )

        elif intent == "publication_page_count":

            entries = []

            for paper in papers:

                pages = paper.get(
                    "pages",
                    ""
                )

                count = page_count_from_range(
                    pages
                )

                if count is not None:

                    entries.append(
                        {
                            "venue": (
                                paper.get("venue")
                                or paper.get("type")
                            ),
                            "range": pages,
                            "count": count
                        }
                    )

            if not entries:

                answer = (
                    f"I found '{papers[0]['title']}', "
                    "but the DBLP record does not contain "
                    "a page range from which I can reliably "
                    "calculate the number of pages."
                )

            else:

                descriptions = []

                for entry in entries:

                    descriptions.append(
                        f"{entry['count']} page"
                        f"{'s' if entry['count'] != 1 else ''} "
                        f"({entry['range']}, "
                        f"{entry['venue']})"
                    )

                answer = (
                    f"'{papers[0]['title']}' has "
                    + "; ".join(descriptions)
                    + "."
                )    

        else:
            p = papers[0]
            answer = (
                f"'{p['title']}' — authors: {', '.join(p['authors'])}; "
                f"year: {p.get('year')}; venue: {p.get('venue') or 'not specified'}; "
                f"type: {p.get('type')}."
            )
            if p.get("pages"):
                answer += f" Pages: {p['pages']}."

        return {
            "question": question,
            "intent": intent,
            "answer": answer,
            "count": len(papers),
            "sources": _source_cards(papers),
        }

    # --------------------------------------------------------
    # Conceptual topic discovery -> actual RAG path
    # --------------------------------------------------------
    search_text = plan.get("search_text") or question
    top_k = plan.get("limit") or default_top_k

    try:
        papers = semantic_topic_search(
            search_text,
            year_from=plan.get("year_from"),
            year_to=plan.get("year_to"),
            top_k=top_k,
        )
    except Exception:
        papers = []

    if not papers:
        return {
            "question": question,
            "intent": "topic_search",
            "answer": (
                "I could not find sufficient DBLP evidence for that topic query."
            ),
            "count": 0,
            "sources": [],
        }

    try:
        answer = generate_grounded_answer(question, papers)
    except Exception:
        # Never lose retrieved evidence because the generation API is unavailable.
        answer = (
            f"I found {len(papers)} relevant DBLP publication"
            f"{'s' if len(papers) != 1 else ''}. "
            "The generation service is temporarily unavailable, "
            "so I am returning the verified sources directly."
        )

    return {
        "question": question,
        "intent": "topic_search",
        "answer": answer,
        "count": len(papers),
        "sources": _source_cards(papers),
        "plan": plan,
    }
