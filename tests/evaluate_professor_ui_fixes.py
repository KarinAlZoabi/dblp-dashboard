import json
import sys
from urllib import request

API_URL = "http://127.0.0.1:8000/api/rag/chat"


def ask(question, session_id=None):
    req = request.Request(
        API_URL,
        data=json.dumps({
            "question": question,
            "top_k": 5,
            "session_id": session_id,
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with request.urlopen(req, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def check(condition, label, response):
    if condition:
        print(f"PASS  {label}")
        return 1

    print(f"FAIL  {label}")
    print(json.dumps(response, indent=2, ensure_ascii=False))
    return 0


def main():
    passed = total = 0

    # Standalone UI failures.
    cases = [
        (
            "total records incl profiles",
            "How many total DBLP records are there including profile/web records?",
            "dataset_count",
        ),
        (
            "unquoted exact title",
            "who wrote attention is all you need",
            "publication_authors",
        ),
        (
            "author output phrasing",
            "Roughly speaking, what's Kassem Danach's publication output?",
            "author_publication_count",
        ),
        (
            "author summary",
            "who is kassem danach",
            "author_summary",
        ),
        (
            "bare year clarification",
            "2023",
            "clarify",
        ),
        (
            "bare papers clarification",
            "papers???",
            "clarify",
        ),
        (
            "vague request clarification",
            "tell me something",
            "clarify",
        ),
    ]

    for label, question, expected in cases:
        response = ask(question)
        total += 1
        passed += check(
            response.get("intent") == expected,
            label,
            response,
        )

    top3 = ask("Give me the top 3 publications by Kassem Danach.")
    total += 1
    passed += check(
        top3.get("intent") == "author_publications"
        and len(top3.get("sources") or []) == 3,
        "top 3 author publications",
        top3,
    )

    # Paper follow-up chain.
    first = ask("How many pages does 'Attention Is All You Need' have?")
    sid = first.get("session_id")
    second = ask("What is its page range?", sid)

    total += 1
    passed += check(
        second.get("intent") == "publication_pages",
        "possessive paper follow-up",
        second,
    )

    # Author year follow-up chain.
    first = ask("What did Kassem Danach publish in 2020?")
    sid = first.get("session_id")
    second = ask("What about 2023?", sid)

    total += 1
    passed += check(
        second.get("intent") == "author_publications"
        and second.get("context_used", {}).get("year") == 2023,
        "author year follow-up",
        second,
    )

    # Topic refinement chain.
    first = ask("Find papers about federated learning")
    sid = first.get("session_id")
    second = ask("What about privacy?", sid)

    total += 1
    passed += check(
        second.get("intent") == "topic_search"
        and bool(second.get("sources")),
        "topic refinement follow-up",
        second,
    )

    print("=" * 68)
    print(f"Passed: {passed}/{total}")
    print("=" * 68)

    if passed != total:
        sys.exit(1)


if __name__ == "__main__":
    main()
