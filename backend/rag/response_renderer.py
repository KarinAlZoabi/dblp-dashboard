from __future__ import annotations

"""Natural-language response rendering for deterministic DBLP results.

This module deliberately does *not* call an LLM. Facts stay deterministic and
come from SQLite/retrieval; this layer only turns those verified facts into
concise, human-sounding responses.
"""

from typing import Iterable, Optional


def _plural(count: int, singular: str, plural: Optional[str] = None) -> str:
    if count == 1:
        return singular
    return plural or f"{singular}s"


def _clean(value) -> str:
    return str(value).strip() if value not in (None, "") else ""


def _year_phrase(year_from=None, year_to=None, *, leading: bool = False) -> str:
    if year_from is None and year_to is None:
        return ""

    if year_from is not None and year_to is not None:
        if year_from == year_to:
            phrase = f"in {year_from}"
        else:
            phrase = f"between {year_from} and {year_to}"
    elif year_from is not None:
        phrase = f"from {year_from} onward"
    else:
        phrase = f"up to {year_to}"

    if leading:
        return phrase[:1].upper() + phrase[1:]
    return phrase


def _publication_type_label(pub_type: str) -> str:
    labels = {
        "article": "article",
        "inproceedings": "conference paper",
        "proceedings": "proceedings",
        "book": "book",
        "incollection": "book chapter",
        "phdthesis": "PhD thesis",
        "mastersthesis": "master's thesis",
        "data": "data publication",
    }
    return labels.get((pub_type or "").casefold(), pub_type or "publication")


def render_dataset_count(stats: dict) -> str:
    total = int(stats.get("total_records", 0))
    publications = int(stats.get("publication_records", 0))

    if total == publications:
        return f"The indexed DBLP dataset contains {publications:,} publication records."

    return (
        f"The indexed DBLP dataset contains {publications:,} publication records. "
        f"There are {total:,} DBLP records in total when profile/web records are included."
    )


def render_author_not_found(author: str) -> str:
    return f"I couldn't find a DBLP author matching '{author}'."


def render_author_ambiguous(requested_author: str, identities: Iterable[str]) -> str:
    identities = list(identities)
    if not identities:
        return f"I found more than one DBLP identity for '{requested_author}'. Which one do you mean?"

    options = ", ".join(identities)
    return (
        f"DBLP has multiple author identities matching '{requested_author}': {options}. "
        "Which one do you mean?"
    )


def render_author_publication_count(
    author: str,
    count: int,
    year_from=None,
    year_to=None,
) -> str:
    noun = _plural(count, "publication")
    years = _year_phrase(year_from, year_to)

    if years:
        return f"{author} has {count} {noun} {years} in the indexed DBLP data."
    return f"{author} has {count} {noun} in the indexed DBLP data."


def render_author_publications(
    author: str,
    count: int,
    year_from=None,
    year_to=None,
    *,
    all_results: bool = False,
) -> str:
    noun = _plural(count, "publication")
    years = _year_phrase(year_from, year_to)

    if count == 0:
        if years:
            return f"I found {author} in DBLP, but no publications {years}."
        return f"I found {author} in DBLP, but no publications matched your request."

    if count == 1:
        if years:
            return f"I found 1 publication by {author} {years}. It's listed below."
        return f"I found 1 publication by {author}. It's listed below."

    if years:
        lead = f"I found {count} {noun} by {author} {years}."
    else:
        lead = f"I found {count} {noun} by {author}."

    if all_results:
        return lead + " I've listed all of the matching records below."
    return lead + " I've listed the matching records below."


def render_author_multi_match(
    requested_author: str,
    identities: Iterable[str],
    count: int,
    year_from=None,
    year_to=None,
) -> str:
    identities = list(identities)
    years = _year_phrase(year_from, year_to)
    identity_text = ", ".join(identities)
    noun = _plural(count, "publication")

    where = f" {years}" if years else ""
    return (
        f"More than one DBLP identity for '{requested_author}' has matching publications{where}. "
        f"I found {count} {noun} across {identity_text}, and kept the identities separate below."
    )


def render_publication_not_found(title: str) -> str:
    return f"I couldn't find a DBLP publication matching '{title}'."


def render_publication_authors(title: str, authors: Iterable[str]) -> str:
    authors = [a for a in authors if a]
    if not authors:
        return f"I found '{title}', but DBLP doesn't list any authors for that record."

    return f"'{title}' was written by {', '.join(authors)}."


def render_publication_venue(title: str, papers: list[dict]) -> str:
    if not papers:
        return render_publication_not_found(title)

    entries = []
    for paper in papers:
        venue = _clean(paper.get("venue")) or "venue not specified"
        year = _clean(paper.get("year"))
        kind = _publication_type_label(paper.get("type", ""))

        if year:
            entries.append(f"{venue} in {year} ({kind})")
        else:
            entries.append(f"{venue} ({kind})")

    if len(entries) == 1:
        return f"'{title}' was published in {entries[0]}."

    return (
        f"DBLP lists {len(entries)} versions of '{title}': "
        + "; ".join(entries)
        + "."
    )


def render_publication_pages(title: str, papers: list[dict]) -> str:
    entries = []
    for paper in papers:
        pages = _clean(paper.get("pages"))
        if not pages:
            continue
        venue = _clean(paper.get("venue")) or _publication_type_label(paper.get("type", ""))
        entries.append((venue, pages))

    if not entries:
        return f"I found '{title}', but DBLP doesn't store a page range for the matching record."

    if len(entries) == 1:
        venue, pages = entries[0]
        return f"The {venue} version of '{title}' spans pages {pages}."

    rendered = "; ".join(f"{venue}: {pages}" for venue, pages in entries)
    return f"DBLP lists these page ranges for '{title}': {rendered}."


def render_publication_page_count(title: str, papers: list[dict], counter) -> str:
    entries = []
    for paper in papers:
        pages = _clean(paper.get("pages"))
        count = counter(pages)
        if count is None:
            continue
        venue = _clean(paper.get("venue")) or _publication_type_label(paper.get("type", ""))
        entries.append((venue, pages, count))

    if not entries:
        return (
            f"I found '{title}', but I can't reliably calculate its page count "
            "from the page information stored in DBLP."
        )

    if len(entries) == 1:
        venue, pages, count = entries[0]
        return (
            f"The {venue} version of '{title}' is {count} "
            f"{_plural(count, 'page')} long ({pages})."
        )

    rendered = "; ".join(
        f"{venue}: {count} {_plural(count, 'page')} ({pages})"
        for venue, pages, count in entries
    )
    return f"DBLP has these page counts for '{title}': {rendered}."


def render_publication_year(title: str, papers: list[dict]) -> str:
    years = sorted({p.get("year") for p in papers if p.get("year") is not None})
    if not years:
        return f"I found '{title}', but DBLP doesn't list a publication year for it."
    if len(years) == 1:
        return f"'{title}' was published in {years[0]}."
    return f"DBLP lists versions of '{title}' from {', '.join(map(str, years))}."


def render_publication_field(title: str, papers: list[dict], field: str) -> str:
    values = sorted({_clean(p.get(field)) for p in papers if _clean(p.get(field))})

    labels = {
        "volume": "volume",
        "number": "issue/number",
        "publisher": "publisher",
    }
    label = labels.get(field, field)

    if not values:
        return f"I found '{title}', but DBLP doesn't list {label} information for it."

    if len(values) == 1:
        if field == "publisher":
            return f"DBLP lists {values[0]} as the publisher of '{title}'."
        return f"DBLP lists {label} {values[0]} for '{title}'."

    return f"DBLP lists these {label} values for '{title}': {', '.join(values)}."


def render_publication_ee(title: str, papers: list[dict]) -> str:
    values = []
    for paper in papers:
        value = _clean(paper.get("ee"))
        if value and value not in values:
            values.append(value)

    if not values:
        return f"I found '{title}', but DBLP doesn't list an electronic-edition link for it."
    if len(values) == 1:
        return f"DBLP lists this electronic-edition link for '{title}': {values[0]}"
    return f"DBLP lists these electronic-edition links for '{title}': " + "; ".join(values)


def render_publication_details(title: str, paper: dict) -> str:
    authors = ", ".join(paper.get("authors", [])) or "authors not specified"
    venue = _clean(paper.get("venue")) or "venue not specified"
    year = _clean(paper.get("year")) or "year not specified"
    kind = _publication_type_label(paper.get("type", ""))

    answer = (
        f"'{title}' was written by {authors}. "
        f"DBLP lists it as a {kind} from {year}, published in {venue}."
    )
    if paper.get("pages"):
        answer += f" Its page range is {paper['pages']}."
    return answer


def render_coauthors(author: str, coauthors: list[dict]) -> str:
    if not coauthors:
        return f"I couldn't find any coauthors for {author} in the indexed DBLP publications."

    lines = [f"The top {len(coauthors)} most frequent coauthors of {author} are:"]
    for index, item in enumerate(coauthors, 1):
        count = int(item.get("count", 0))
        lines.append(
            f"{index}. {item.get('author', 'Unknown')} — {count} shared "
            f"{_plural(count, 'publication')}"
        )
    return "\n".join(lines)


def render_topic_results(
    count: int,
    search_text: str,
    year_from=None,
    year_to=None,
) -> str:
    noun = _plural(count, "publication")
    topic = (search_text or "that topic").strip()
    years = _year_phrase(year_from, year_to)

    if years:
        return f"I found {count} relevant DBLP {noun} on {topic} {years}. I've listed them below."
    return f"I found {count} relevant DBLP {noun} on {topic}. I've listed them below."


def render_topic_not_found(search_text: str, year_from=None, year_to=None) -> str:
    topic = (search_text or "that topic").strip()
    years = _year_phrase(year_from, year_to)
    if years:
        return f"I couldn't find DBLP publications on {topic} {years}."
    return f"I couldn't find DBLP publications on {topic}."
