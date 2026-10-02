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


def require(condition, label, response):
    if condition:
        print(f"PASS  {label}")
        return 1

    print(f"FAIL  {label}")
    print(json.dumps(response, indent=2, ensure_ascii=False))
    return 0


def main():
    passed = total = 0

    r, _ = ask("How many authors does DBLP have?")
    total += 1
    passed += require(
        r.get("intent") == "dataset_author_count",
        "dataset author-count intent",
        r,
    )

    total += 1
    passed += require(
        isinstance(r.get("count"), int) and r["count"] > 0,
        "dataset author count available",
        r,
    )

    r, _ = ask("get me the publications by Kassem Danach")
    total += 1
    passed += require(
        r.get("intent") == "author_publications"
        and len(r.get("sources") or []) > 5,
        "author query returns complete list",
        r,
    )

    r3, _ = ask("Give me the top 3 papers about federated learning")
    total += 1
    passed += require(
        r3.get("intent") == "topic_search"
        and len(r3.get("sources") or []) <= 3,
        "topic search still respects top-k",
        r3,
    )

    q = "Find papers about graph neural networks"
    first, first_latency = ask(q)
    second, second_latency = ask(q)

    total += 1
    passed += require(
        first.get("intent") == "topic_search"
        and second.get("intent") == "topic_search"
        and bool(second.get("sources")),
        "semantic cache preserves results",
        second,
    )

    print(
        f"Semantic repeated-query latency: "
        f"{first_latency:.2f}s -> {second_latency:.2f}s"
    )

    print("=" * 64)
    print(f"Passed: {passed}/{total}")
    print("=" * 64)

    if passed != total:
        sys.exit(1)


if __name__ == "__main__":
    main()
