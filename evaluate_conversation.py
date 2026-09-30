import json
import sys
import time
from urllib import request

API_URL = "http://127.0.0.1:8000/api/rag/chat"


def ask(question, session_id=None):
    payload = {
        "question": question,
        "top_k": 5,
        "session_id": session_id,
    }
    req = request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    with request.urlopen(req, timeout=120) as response:
        body = json.loads(response.read().decode("utf-8"))
    return body, time.perf_counter() - started


def check(condition, label, response):
    if condition:
        print(f"PASS  {label}")
        return True
    print(f"FAIL  {label}")
    print(json.dumps(response, indent=2, ensure_ascii=False))
    return False


def main():
    passed = 0
    total = 0

    # Conversation 1: title pronoun memory.
    first, t1 = ask("Who wrote 'Attention Is All You Need'?")
    sid = first.get("session_id")
    total += 1
    passed += check(bool(sid), "session_created", first)

    second, t2 = ask("How many pages does it have?", sid)
    total += 1
    passed += check(
        second.get("intent") == "publication_page_count"
        and "11" in json.dumps(second, ensure_ascii=False),
        "followup_it_page_count",
        second,
    )

    third, t3 = ask("Where was it published?", sid)
    total += 1
    passed += check(
        third.get("intent") == "publication_venue"
        and any(
            token in json.dumps(third, ensure_ascii=False)
            for token in ("NIPS", "CoRR")
        ),
        "followup_it_venue",
        third,
    )

    # Conversation 2: author pronoun memory.
    first, _ = ask("How many publications does Kassem Danach have?")
    sid2 = first.get("session_id")
    second, _ = ask("What did they publish in 2020?", sid2)
    total += 1
    passed += check(
        second.get("intent") == "author_publications",
        "followup_author_pronoun",
        second,
    )

    # Conversation 3: ordinal result reference.
    first, _ = ask("Find papers about federated learning from 2020 to 2023")
    sid3 = first.get("session_id")
    second, _ = ask("Who wrote the second one?", sid3)
    total += 1
    passed += check(
        second.get("intent") == "publication_authors"
        and bool(second.get("sources")),
        "followup_second_result",
        second,
    )

    print("=" * 60)
    print(f"Passed: {passed}/{total}")
    print(
        "Title-memory turn latency: "
        f"{t1:.2f}s -> {t2:.2f}s -> {t3:.2f}s"
    )
    print("=" * 60)

    if passed != total:
        sys.exit(1)


if __name__ == "__main__":
    main()
