import json
import sys
import time
from urllib import request, error

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

    started = time.perf_counter()

    try:
        with request.urlopen(req, timeout=120) as response:
            body = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code} for: {question}")
        print("Response body:", raw)
        raise

    return body, time.perf_counter() - started


def check(condition, label, response):
    if condition:
        print(
            f"PASS  {label:32} "
            f"planner={response.get('planner_mode')}"
        )
        return 1

    print(f"FAIL  {label}")
    print(json.dumps(response, indent=2, ensure_ascii=False))
    return 0


def main():
    passed = 0
    total = 0

    a, _ = ask("Who wrote 'Attention Is All You Need'?")
    sid = a["session_id"]

    b, _ = ask("Where did it appear?", sid)
    total += 1
    passed += check(
        b.get("intent") == "publication_venue",
        "paper pronoun -> venue",
        b,
    )

    c, _ = ask("and how long is it?", sid)
    total += 1
    passed += check(
        c.get("intent") == "publication_page_count"
        and "11" in json.dumps(c),
        "natural follow-up -> page count",
        c,
    )

    a, _ = ask("Find federated learning papers from 2020 to 2023")
    sid = a["session_id"]

    b, _ = ask("Who wrote the second result?", sid)
    total += 1
    passed += check(
        b.get("intent") == "publication_authors"
        and bool(b.get("sources")),
        "second result -> authors",
        b,
    )

    c, _ = ask("Tell me about the newest one instead", sid)
    total += 1
    passed += check(
        c.get("intent") == "publication_details"
        and bool(c.get("sources")),
        "newest result selection",
        c,
    )

    a, _ = ask("What did Kassem Danach publish in 2020?")
    sid = a["session_id"]

    b, _ = ask("and in 2023?", sid)
    total += 1
    passed += check(
        b.get("intent") == "author_publications",
        "elliptical year follow-up",
        b,
    )

    c, _ = ask("how many did they have that year?", sid)
    total += 1
    passed += check(
        c.get("intent") == "author_publication_count",
        "pronoun + inherited year",
        c,
    )

    a, _ = ask("Find papers about federated learning")
    sid = a["session_id"]

    b, _ = ask("what about privacy?", sid)
    total += 1
    passed += check(
        b.get("intent") == "topic_search"
        and bool(b.get("sources")),
        "topic refinement from context",
        b,
    )

    print("=" * 68)
    print(f"Passed: {passed}/{total}")
    print("=" * 68)

    if passed != total:
        sys.exit(1)


if __name__ == "__main__":
    main()
