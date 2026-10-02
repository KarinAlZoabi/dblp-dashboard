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

    cases = [
        (
            "css paste",
            """.chat-source-more span {
  color: #9499aa;
  font-size: 9px;
  font-weight: 600;
}""",
            "unsupported",
        ),
        (
            "javascript paste",
            "const x = 5; function hello() { return x; }",
            "unsupported",
        ),
        (
            "python paste",
            "def hello():\\n    return 123",
            "unsupported",
        ),
        (
            "out of domain",
            "write me a poem about cats",
            "unsupported",
        ),
        (
            "greeting",
            "hello!",
            "smalltalk",
        ),
        (
            "dataset count stays valid",
            "how many publications are in DBLP?",
            "dataset_count",
        ),
        (
            "dataset author count stays valid",
            "how many authors does DBLP have?",
            "dataset_author_count",
        ),
        (
            "topic search stays valid",
            "find papers about graph neural networks",
            "topic_search",
        ),
    ]

    for label, question, intent in cases:
        response = ask(question)
        total += 1
        passed += check(
            response.get("intent") == intent,
            label,
            response,
        )

    # Verify an accidental paste does not erase the useful previous context.
    first = ask("Who wrote 'Attention Is All You Need'?")
    sid = first.get("session_id")

    accidental = ask(
        ".foo { color: red; font-size: 12px; }",
        sid,
    )
    total += 1
    passed += check(
        accidental.get("intent") == "unsupported",
        "accidental paste inside conversation",
        accidental,
    )

    followup = ask("how many pages does it have?", sid)
    total += 1
    passed += check(
        followup.get("intent") == "publication_page_count"
        and "11" in json.dumps(followup),
        "conversation survives accidental paste",
        followup,
    )

    print("=" * 64)
    print(f"Passed: {passed}/{total}")
    print("=" * 64)

    if passed != total:
        sys.exit(1)


if __name__ == "__main__":
    main()
