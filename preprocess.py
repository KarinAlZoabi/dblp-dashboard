from collections import Counter, defaultdict
from pathlib import Path
import json

from lxml import etree


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

XML_FILE = BASE_DIR / "data" / "dblp.xml"
OUTPUT_DIR = BASE_DIR / "processed"

OUTPUT_DIR.mkdir(exist_ok=True)


# ============================================================
# PUBLICATION TYPES
# ============================================================

PUBLICATION_TAGS = {
    "article",
    "inproceedings",
    "proceedings",
    "book",
    "incollection",
    "phdthesis",
    "mastersthesis",
}


# ============================================================
# STORAGE FOR DERIVED DATA
# ============================================================

publication_types = Counter()

year_counts = Counter()

author_count_distribution = Counter()

collaboration_by_year = defaultdict(
    lambda: {
        "publications": 0,
        "total_authors": 0,
        "single_author": 0,
        "multi_author": 0,
    }
)

journal_counts = Counter()
conference_counts = Counter()

type_by_year = defaultdict(Counter)

missing_data = defaultdict(
    lambda: {
        "total": 0,
        "missing_author": 0,
        "missing_title": 0,
        "missing_year": 0,
    }
)

duplicate_keys = set()
duplicate_count = 0


# ============================================================
# PARSE XML
# ============================================================

print("Starting DBLP preprocessing...")
print(f"Reading: {XML_FILE}")

context = etree.iterparse(
    str(XML_FILE),
    events=("end",),
    tag=PUBLICATION_TAGS,
    load_dtd=True,
    resolve_entities=True,
)

processed = 0

for event, elem in context:

    publication_type = elem.tag

    # --------------------------------------------------------
    # Basic publication count
    # --------------------------------------------------------

    publication_types[publication_type] += 1

    missing_data[publication_type]["total"] += 1

    # --------------------------------------------------------
    # Key / duplicates
    # --------------------------------------------------------

    key = elem.get("key")

    if key:
        if key in duplicate_keys:
            duplicate_count += 1
        else:
            duplicate_keys.add(key)

    # --------------------------------------------------------
    # Fields
    # --------------------------------------------------------

    title = elem.findtext("title")
    year = elem.findtext("year")

    authors = elem.findall("author")
    author_count = len(authors)

    # --------------------------------------------------------
    # Missing data
    # --------------------------------------------------------

    if not authors:
        missing_data[publication_type]["missing_author"] += 1

    if not title or not title.strip():
        missing_data[publication_type]["missing_title"] += 1

    if not year or not year.strip():
        missing_data[publication_type]["missing_year"] += 1

    # --------------------------------------------------------
    # Author distribution
    # --------------------------------------------------------

    author_count_distribution[author_count] += 1

    # --------------------------------------------------------
    # Year-based analysis
    # --------------------------------------------------------

    if year and year.strip():

        year = year.strip()

        # Only use numeric years
        if year.isdigit():

            year_int = int(year)

            year_counts[year_int] += 1

            # Collaboration
            collaboration_by_year[year_int]["publications"] += 1
            collaboration_by_year[year_int]["total_authors"] += author_count

            if author_count == 1:
                collaboration_by_year[year_int]["single_author"] += 1

            elif author_count >= 2:
                collaboration_by_year[year_int]["multi_author"] += 1

            # Publication type by year
            type_by_year[year_int][publication_type] += 1

    # --------------------------------------------------------
    # Venue analysis
    # --------------------------------------------------------

    if publication_type == "article":

        journal = elem.findtext("journal")

        if journal and journal.strip():
            journal_counts[journal.strip()] += 1

    elif publication_type in {
        "inproceedings",
        "incollection",
        "proceedings",
    }:

        booktitle = elem.findtext("booktitle")

        if booktitle and booktitle.strip():
            conference_counts[booktitle.strip()] += 1

    # --------------------------------------------------------
    # Progress
    # --------------------------------------------------------

    processed += 1

    if processed % 500_000 == 0:
        print(f"Processed {processed:,} records...")

    # --------------------------------------------------------
    # IMPORTANT:
    # Free XML memory
    # --------------------------------------------------------

    elem.clear()

    while elem.getprevious() is not None:
        del elem.getparent()[0]


print(f"\nFinished processing {processed:,} records.")


# ============================================================
# DERIVED COLLABORATION DATA
# ============================================================

collaboration_output = {}

for year in sorted(collaboration_by_year):

    data = collaboration_by_year[year]

    publications = data["publications"]

    collaboration_output[str(year)] = {
        "publications": publications,
        "total_authors": data["total_authors"],
        "single_author": data["single_author"],
        "multi_author": data["multi_author"],
        "avg_authors": round(
            data["total_authors"] / publications,
            2
        ) if publications else 0,
        "multi_author_pct": round(
            data["multi_author"] / publications * 100,
            2
        ) if publications else 0,
    }


# ============================================================
# PUBLICATION TYPE BY YEAR
# ============================================================

type_by_year_output = {}

for year in sorted(type_by_year):

    type_by_year_output[str(year)] = dict(
        type_by_year[year]
    )


# ============================================================
# AUTHOR DISTRIBUTION
# ============================================================

author_distribution_output = {
    str(author_count): count
    for author_count, count
    in sorted(author_count_distribution.items())
}


# ============================================================
# VENUES
# ============================================================

top_journals = [
    {
        "venue": venue,
        "count": count
    }
    for venue, count
    in journal_counts.most_common(100)
]

top_conferences = [
    {
        "venue": venue,
        "count": count
    }
    for venue, count
    in conference_counts.most_common(100)
]


# ============================================================
# MISSING DATA
# ============================================================

missing_data_output = {}

for publication_type, data in missing_data.items():

    total = data["total"]

    missing_data_output[publication_type] = {
        "total": total,
        "missing_author": data["missing_author"],
        "missing_title": data["missing_title"],
        "missing_year": data["missing_year"],
        "missing_author_pct": round(
            data["missing_author"] / total * 100,
            2
        ) if total else 0,
        "missing_title_pct": round(
            data["missing_title"] / total * 100,
            2
        ) if total else 0,
        "missing_year_pct": round(
            data["missing_year"] / total * 100,
            2
        ) if total else 0,
    }


# ============================================================
# GLOBAL KPIs
# ============================================================

total_publications = sum(publication_types.values())

total_authors = sum(
    author_count * count
    for author_count, count
    in author_count_distribution.items()
)

average_authors = (
    total_authors / total_publications
    if total_publications
    else 0
)

zero_author = author_count_distribution.get(0, 0)
single_author = author_count_distribution.get(1, 0)

multi_author = total_publications - zero_author - single_author

# Median
cumulative = 0
median_authors = 0
middle = total_publications / 2

for author_count, count in sorted(
    author_count_distribution.items()
):

    cumulative += count

    if cumulative >= middle:
        median_authors = author_count
        break


kpis = {
    "total_analyzed_publications": total_publications,
    "average_authors": round(average_authors, 2),
    "median_authors": median_authors,
    "maximum_authors": max(author_count_distribution),
    "zero_author_publications": zero_author,
    "single_author_publications": single_author,
    "multi_author_publications": multi_author,
    "single_author_pct": round(
        single_author / total_publications * 100,
        2
    ),
    "multi_author_pct": round(
        multi_author / total_publications * 100,
        2
    ),
    "duplicate_keys": duplicate_count,
}


# ============================================================
# SAVE JSON FILES
# ============================================================

def save_json(filename, data):

    path = OUTPUT_DIR / filename

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )

    print(f"Saved: {path}")


save_json(
    "kpis.json",
    kpis
)

save_json(
    "publication_types.json",
    dict(publication_types)
)

save_json(
    "yearly_publications.json",
    dict(sorted(year_counts.items()))
)

save_json(
    "author_distribution.json",
    author_distribution_output
)

save_json(
    "collaboration.json",
    collaboration_output
)

save_json(
    "publication_types_by_year.json",
    type_by_year_output
)

save_json(
    "venues.json",
    {
        "journals": top_journals,
        "conferences": top_conferences,
    }
)

save_json(
    "missing_data.json",
    missing_data_output
)


print("\n========================================")
print("PREPROCESSING COMPLETE")
print("========================================")
print(f"Total analyzed publications: {total_publications:,}")
print(f"Total DBLP records: {total_publications + missing_data['www']['total']:,}")
print(f"Duplicate keys: {duplicate_count:,}")
print(f"Average authors: {average_authors:.2f}")
print(f"Median authors: {median_authors}")
print(f"Maximum authors: {max(author_count_distribution)}")
print("========================================")