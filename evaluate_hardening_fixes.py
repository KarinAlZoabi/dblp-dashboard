import json
import sys
import time
from urllib import request, error

API_URL = "http://127.0.0.1:8000/api/rag/chat"


def ask(question, session_id=None, top_k=5):
    req = request.Request(
        API_URL,
        data=json.dumps({
            "question": question,
            "top_k": top_k,
            "session_id": session_id,
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with request.urlopen(req, timeout=120) as response:
            body = json.loads(response.read().decode("utf-8"))
        return body, time.perf_counter() - started, None
    except error.HTTPError as exc:
        return None, time.perf_counter() - started, (
            f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}"
        )


def fail(label, reason, response=None):
    print(f"FAIL  {label}: {reason}")
    if response is not None:
        print(json.dumps(response, indent=2, ensure_ascii=False))
    return 0


def ok(label, latency):
    suffix = "  SLOW" if latency > 5 else ""
    print(f"PASS  {latency:6.2f}s  {label}{suffix}")
    return 1


def check_case(label, question, *, intent=None, min_sources=None, max_sources=None,
               years=None, venues=None, types=None, contains=None):
    r, latency, err = ask(question)
    if err:
        return fail(label, err), None
    if intent and r.get("intent") != intent:
        return fail(label, f"intent {r.get('intent')!r} != {intent!r}", r), r

    sources = r.get("sources") or []
    if min_sources is not None and len(sources) < min_sources:
        return fail(label, f"expected >= {min_sources} sources, got {len(sources)}", r), r
    if max_sources is not None and len(sources) > max_sources:
        return fail(label, f"expected <= {max_sources} sources, got {len(sources)}", r), r

    if years and sources:
        lo, hi = years
        bad = [s.get("year") for s in sources if s.get("year") is not None and not lo <= s.get("year") <= hi]
        if bad:
            return fail(label, f"years outside [{lo},{hi}]: {bad}", r), r

    if venues and sources:
        allowed = {x.casefold() for x in venues}
        bad = [s.get("venue") for s in sources if (s.get("venue") or "").casefold() not in allowed]
        if bad:
            return fail(label, f"unexpected venues: {bad}", r), r

    if types and sources:
        allowed = {x.casefold() for x in types}
        bad = [s.get("type") for s in sources if (s.get("type") or "").casefold() not in allowed]
        if bad:
            return fail(label, f"unexpected publication types: {bad}", r), r

    if contains:
        blob = json.dumps(r, ensure_ascii=False).casefold()
        if not any(x.casefold() in blob for x in contains):
            return fail(label, f"missing any of {contains}", r), r

    return ok(label, latency), r


def main():
    passed = 0
    total = 0

    cases = [
        ("dataset_count_fast", "what's the total paper count in dblp?", dict(intent="dataset_count")),
        ("author_count_fast", "what's Kassem Danach's publication count?", dict(intent="author_publication_count")),
        ("author_put_out", "show me what Kassem Danach put out in 2020", dict(intent="author_publications", years=(2020, 2020))),
        ("topic_range", "Find federated learning papers from 2020 to 2023", dict(intent="topic_search", min_sources=1, years=(2020, 2023))),
        ("topic_year", "Find network intrusion detection papers published in 2022", dict(intent="topic_search", min_sources=1, years=(2022, 2022))),
        ("venue_filter", "Find federated learning papers in CoRR from 2020 to 2023", dict(intent="topic_search", min_sources=1, years=(2020, 2023), venues=["CoRR"])),
        ("type_filter", "Find conference papers about federated learning from 2020 to 2023", dict(intent="topic_search", min_sources=1, years=(2020, 2023), types=["inproceedings"])),
        ("top3", "Give me the top 3 papers about federated learning", dict(intent="topic_search", min_sources=1, max_sources=3)),
        ("missing_title", "Who wrote 'This Paper Definitely Does Not Exist In DBLP 123456'?", dict(intent="publication_authors", max_sources=0, contains=["could not find"])),
        ("missing_year", "Show Kassem Danach publications in 1800", dict(intent="author_publications", max_sources=0)),
        ("missing_pages", "What are the pages for 'This Paper Definitely Does Not Exist In DBLP 123456'?", dict(intent="publication_pages", max_sources=0)),
        ("typo_title", "Who wrote 'Attentin Is All You Need'?", dict(intent="publication_authors", min_sources=1, contains=["Vaswani", "Attention Is All You Need"])),
        ("typo_author", "show publications by Kassem Danah", dict(intent="author_publications", min_sources=1)),
    ]

    for label, q, kwargs in cases:
        total += 1
        score, _ = check_case(label, q, **kwargs)
        passed += score

    # Latest / oldest should both return exactly one publication, and latest
    # must not predate oldest.
    total += 1
    s1, latest = check_case(
        "latest_author",
        "What is Kassem Danach's most recent publication?",
        intent="author_publications",
        min_sources=1,
        max_sources=1,
    )
    passed += s1

    total += 1
    s2, oldest = check_case(
        "oldest_author",
        "What is Kassem Danach's earliest publication?",
        intent="author_publications",
        min_sources=1,
        max_sources=1,
    )
    passed += s2

    if latest and oldest and latest.get("sources") and oldest.get("sources"):
        ly = latest["sources"][0].get("year")
        oy = oldest["sources"][0].get("year")
        total += 1
        if ly is not None and oy is not None and ly >= oy:
            passed += ok("latest_vs_oldest_order", 0.0)
        else:
            fail("latest_vs_oldest_order", f"latest={ly}, oldest={oy}")

    # Previously broken result-selection chain.
    first, latency, err = ask("Find federated learning papers from 2020 to 2023")
    total += 1
    if err or first.get("intent") != "topic_search" or not first.get("sources"):
        fail("result_chain_turn1", err or "bad first turn", first)
    else:
        passed += ok("result_chain_turn1", latency)
        sid = first.get("session_id")
        second, latency2, err2 = ask("Who wrote the second one?", sid)
        total += 1
        if err2 or second.get("intent") != "publication_authors":
            fail("result_chain_turn2", err2 or "did not resolve second result", second)
        else:
            passed += ok("result_chain_turn2", latency2)

    print("=" * 70)
    print(f"Passed: {passed}/{total}")
    print("=" * 70)
    if passed != total:
        sys.exit(1)


if __name__ == "__main__":
    main()
