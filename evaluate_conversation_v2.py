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


def main():
    a = ask("How many publications does Kassem Danach have?")
    sid = a.get("session_id")
    assert sid, a

    b = ask("What did he publish in 2020?", sid)
    assert b.get("intent") == "author_publications", b
    assert "He" not in b.get("answer", ""), b
    assert b.get("context_used", {}).get("author"), b

    c = ask("how about 2023?", sid)
    assert c.get("intent") == "author_publications", c
    assert c.get("context_used", {}).get("year") == 2023, c
    assert c.get("resolved_question"), c

    print("PASS: pronoun follow-up")
    print("PASS: bare-year follow-up")
    print("Session:", sid)
    print("Resolved second turn:", b.get("resolved_question"))
    print("Resolved third turn :", c.get("resolved_question"))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("FAIL:", exc)
        sys.exit(1)
