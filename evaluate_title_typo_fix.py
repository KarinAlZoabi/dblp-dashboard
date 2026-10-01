import json
import sys
from urllib import request

API_URL = "http://127.0.0.1:8000/api/rag/chat"

payload = {
    "question": "Who wrote 'Attentin Is All You Need'?",
    "top_k": 5,
    "session_id": None,
}

req = request.Request(
    API_URL,
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)

with request.urlopen(req, timeout=120) as response:
    body = json.loads(response.read().decode("utf-8"))

print(json.dumps(body, indent=2, ensure_ascii=False))

ok = (
    body.get("intent") == "publication_authors"
    and len(body.get("sources") or []) >= 1
    and any(
        "attention is all you need"
        in (source.get("title") or "").casefold()
        for source in body.get("sources") or []
    )
)

if not ok:
    print("FAIL: typo title was not safely recovered.")
    sys.exit(1)

print("PASS: typo title safely resolved.")
