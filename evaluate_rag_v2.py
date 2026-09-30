import json
import re
import statistics
import sys
import time
from pathlib import Path
from urllib import request

API_URL = "http://127.0.0.1:8000/api/rag/chat"
CASES_FILE = Path(__file__).with_name("rag_eval_cases_v2.json")


def normalize(text):
    text = (text or "").casefold()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def author_base(name):
    return re.sub(r"\s+\d{4}$", "", normalize(name))


def canonical_author(name):
    value = normalize(name)
    m = re.match(r"^(.*?)(?:\s+0*(\d{1,4}))?$", value)
    if not m:
        return value
    base, suffix = m.group(1).strip(), m.group(2)
    return f"{base} {int(suffix):04d}" if suffix is not None else base


def post_json(payload):
    req = request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type":"application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def check_case(case, response):
    failures=[]
    intent=response.get("intent")
    if case.get("intents") and intent not in case["intents"]:
        failures.append(f"intent expected one of {case['intents']}, got {intent!r}")

    count=response.get("count",0)
    if "expected_count" in case and count != case["expected_count"]:
        failures.append(f"count expected {case['expected_count']}, got {count}")

    sources=response.get("sources") or []
    if len(sources) < case.get("min_sources",0):
        failures.append(f"expected >= {case['min_sources']} sources, got {len(sources)}")

    blob=json.dumps(response,ensure_ascii=False).casefold()
    required=[x.casefold() for x in case.get("answer_any",[])]
    if required and not any(x in blob for x in required):
        failures.append("missing all required fragments: "+", ".join(case["answer_any"]))

    if case.get("year_range"):
        lo,hi=case["year_range"]
        bad=[s.get("year") for s in sources if s.get("year") is None or not (lo <= s.get("year") <= hi)]
        if bad:
            failures.append(f"source years outside [{lo},{hi}]: {bad}")

    exact=case.get("exact_title")
    if exact:
        bad=[s.get("title") for s in sources if normalize(s.get("title")) != normalize(exact)]
        if bad:
            failures.append(f"non-exact titles returned: {bad}")

    expected_author=case.get("source_author_exact")
    if expected_author:
        expected=canonical_author(expected_author)
        bad=[]
        for source in sources:
            actual=[canonical_author(a) for a in source.get("authors",[])]
            if expected not in actual:
                bad.append(source.get("title"))
        if bad:
            failures.append(f"sources missing exact author {expected}: {bad}")

    expected_base=case.get("source_author_base")
    if expected_base:
        expected=normalize(expected_base)
        bad=[]
        for source in sources:
            bases=[author_base(a) for a in source.get("authors",[])]
            if expected not in bases:
                bad.append(source.get("title"))
        if bad:
            failures.append(f"sources missing author base {expected}: {bad}")

    www=[s.get("title") for s in sources if s.get("type") == "www"]
    if www:
        failures.append(f"www/profile records leaked into publications: {www}")

    return failures


def main():
    cases=json.loads(CASES_FILE.read_text(encoding="utf-8"))
    results=[]
    print(f"Running {len(cases)} DBLP RAG regression tests...\n")
    for i,case in enumerate(cases,1):
        started=time.perf_counter()
        try:
            response=post_json({"question":case["question"],"top_k":5})
            latency=time.perf_counter()-started
            failures=check_case(case,response)
        except Exception as exc:
            latency=time.perf_counter()-started
            response=None
            failures=[f"HTTP/error: {exc}"]
        passed=not failures
        results.append({"case":case,"passed":passed,"latency":latency,"failures":failures,"response":response})
        print(f"[{i:02d}/{len(cases):02d}] {'PASS' if passed else 'FAIL':4} {latency:6.2f}s  {case['name']}")
        for failure in failures:
            print("    "+failure)
        if latency > 5:
            print("    SLOW (>5s)")

    passed=sum(r["passed"] for r in results)
    latencies=[r["latency"] for r in results]
    print("\n"+"="*68)
    print(f"Passed: {passed}/{len(results)}")
    print(f"Average latency: {statistics.mean(latencies):.2f}s")
    print(f"Median latency : {statistics.median(latencies):.2f}s")
    print(f"Max latency    : {max(latencies):.2f}s")
    print("="*68)

    Path("rag_eval_results_v2.json").write_text(
        json.dumps(results,indent=2,ensure_ascii=False),encoding="utf-8"
    )
    if passed != len(results):
        sys.exit(1)

if __name__ == "__main__":
    main()
