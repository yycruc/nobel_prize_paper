from __future__ import annotations

import csv
import datetime as dt
import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REFS_CSV = ROOT / "01_validation" / "02_candidate_key_papers" / "official_pdf_reference_section_candidates.csv"
OUT_CSV = ROOT / "01_validation" / "02_candidate_key_papers" / "official_reference_classification_validation.csv"
OUT_SUMMARY = ROOT / "01_validation" / "04_outputs" / "official_reference_classification_summary.json"
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"

DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s\"<>]+", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(18|19|20)\d{2}\b")
VOLUME_PAGE_RE = re.compile(r"\b\d{1,4}\s*[:;,]\s*[A-Z]?\d{1,5}\b")
JOURNAL_HINT_RE = re.compile(
    r"\b("
    r"Nature|Science|Cell|PNAS|Proc\.?\s+Natl|Proc\.?\s+Roy|Physical\s+Review|Phys\.?\s+Rev|"
    r"Astrophys\.?\s+J|Class\.?\s+Quantum\s+Grav|Ann\.?\s+Phys|Int\.?\s+J|Mod\.?\s+Phys|"
    r"J\.?\s+Am\.?\s+Chem\.?\s+Soc|J\.?\s+Org\.?\s+Chem|Angew|Chem|Biol|Biotechnol|"
    r"Lancet|BMJ|JAMA|Journal|Proceedings|Transactions|Zeitschrift|Annalen|"
    r"Berichte|Comptes\s+Rendus|Acad|Sitzungber|Philosophical\s+Transactions|"
    r"Structure|Neuron|Genetics|Development|Genes\s+Devel|J\.?\s+Biol\.?\s+Chem|"
    r"Metabolic\s+Engineering|Curr\.?\s+Opin|arXiv"
    r")\b",
    re.IGNORECASE,
)
BOOK_HINT_RE = re.compile(
    r"\b("
    r"book|books|press|publisher|university press|springer|wiley|elsevier|"
    r"cambridge|oxford|princeton|yale|mit press|knopf|norton|chapter|"
    r"lecture notes|monograph|thesis|dissertation"
    r")\b",
    re.IGNORECASE,
)
AGGREGATE_HINTS = [
    "additional information",
    "websites",
    "books",
    "videos",
    "scientific article",
    "further reading",
]
NON_ARTICLE_HINT_RE = re.compile(r"\b(video|website|http|www\.|exhibition|museum|press release)\b", re.IGNORECASE)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def clean_text(value: str) -> str:
    value = value.replace("\u00ad", "")
    value = re.sub(r"\s+", " ", value).strip()
    return re.sub(r"\s+\d{1,3}\s*\(\d{1,3}\)\s*$", "", value)


def years(value: str) -> list[int]:
    return sorted({int(match.group(0)) for match in YEAR_RE.finditer(value)})


def doi(value: str) -> str:
    match = DOI_RE.search(value)
    if not match:
        return ""
    return match.group(0).strip().rstrip(".,;:)").lower()


def is_aggregate(value: str, detected_years: list[int]) -> bool:
    lowered = value.casefold()
    hits = sum(1 for hint in AGGREGATE_HINTS if hint in lowered)
    return (len(value) > 800 and hits >= 2) or (len(value) > 1800 and len(detected_years) >= 8)


def classify(row: dict[str, str]) -> dict[str, str]:
    text = clean_text(row.get("reference_text", ""))
    detected_years = years(text)
    detected_doi = doi(text) or row.get("doi", "")
    reasons: list[str] = []

    aggregate = is_aggregate(text, detected_years)
    bookish = bool(BOOK_HINT_RE.search(text))
    non_article = bool(NON_ARTICLE_HINT_RE.search(text))
    journalish = bool(JOURNAL_HINT_RE.search(text) or VOLUME_PAGE_RE.search(text))
    old_year = bool(detected_years and min(detected_years) < 1945)

    if detected_doi:
        cls = "doi_present"
        api_matchable = "yes"
        priority = "1"
        reasons.append("doi detected in official reference")
    elif aggregate:
        cls = "aggregate_further_reading"
        api_matchable = "no"
        priority = "5"
        reasons.append("long mixed further-reading block")
    elif bookish and not journalish:
        cls = "book_or_chapter"
        api_matchable = "no"
        priority = "4"
        reasons.append("book/chapter/publisher terms without clear journal pattern")
    elif journalish and detected_years:
        if old_year:
            cls = "historical_nonindexed_reference"
            api_matchable = "yes"
            priority = "3"
            reasons.append("journal-like historical reference; may need manual verification")
        else:
            cls = "likely_journal_article"
            api_matchable = "yes"
            priority = "2"
            reasons.append("journal-like pattern with publication year")
    elif non_article:
        cls = "needs_manual_review"
        api_matchable = "no"
        priority = "5"
        reasons.append("non-article web/video/resource hint")
    else:
        cls = "needs_manual_review"
        api_matchable = "no"
        priority = "5"
        reasons.append("insufficient structured bibliographic pattern")

    if bookish:
        reasons.append("book-like terms found")
    if journalish:
        reasons.append("journal-like terms or volume-page pattern found")
    if old_year:
        reasons.append("pre-1945 reference")

    return {
        "reference_candidate_id": row.get("reference_candidate_id", ""),
        "validation_id": row.get("validation_id", ""),
        "laureate_id": row.get("laureate_id", ""),
        "full_name": row.get("full_name", ""),
        "award_year": row.get("award_year", ""),
        "category": row.get("category", ""),
        "pdf_type": row.get("pdf_type", ""),
        "reference_text": text,
        "detected_doi": detected_doi,
        "detected_years": ";".join(str(year) for year in detected_years),
        "reference_class": cls,
        "api_matchable": api_matchable,
        "matching_priority": priority,
        "classification_reason": " | ".join(reasons),
        "review_status": "ready_for_metadata_matching" if api_matchable == "yes" else "manual_or_later_review",
    }


def append_query_log(refs_csv: Path, out_csv: Path, rows: int) -> None:
    exists = QUERY_LOG.exists()
    with QUERY_LOG.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "query_id",
                "run_at",
                "phase",
                "source",
                "query_or_url",
                "parameters",
                "output_path",
                "status",
                "notes",
            ],
        )
        if not exists:
            writer.writeheader()
        writer.writerow(
            {
                "query_id": "classify_official_references",
                "run_at": dt.datetime.now(dt.UTC).isoformat(),
                "phase": "validation",
                "source": "Nobel official PDF references",
                "query_or_url": str(refs_csv),
                "parameters": "rule-based classification before API metadata matching",
                "output_path": str(out_csv),
                "status": "ok",
                "notes": f"rows={rows}",
            }
        )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Classify official Nobel PDF reference strings before API matching.")
    parser.add_argument("--refs-csv", type=Path, default=REFS_CSV)
    parser.add_argument("--out-csv", type=Path, default=OUT_CSV)
    parser.add_argument("--summary-json", type=Path, default=OUT_SUMMARY)
    args = parser.parse_args()

    rows = [classify(row) for row in read_csv(args.refs_csv)]
    fields = [
        "reference_candidate_id",
        "validation_id",
        "laureate_id",
        "full_name",
        "award_year",
        "category",
        "pdf_type",
        "reference_text",
        "detected_doi",
        "detected_years",
        "reference_class",
        "api_matchable",
        "matching_priority",
        "classification_reason",
        "review_status",
    ]
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.out_csv.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    summary: dict[str, object] = {
        "input_rows": len(rows),
        "by_reference_class": {},
        "by_api_matchable": {},
        "by_validation_id": {},
        "output": str(args.out_csv),
    }
    for row in rows:
        for bucket_name, field in [
            ("by_reference_class", "reference_class"),
            ("by_api_matchable", "api_matchable"),
            ("by_validation_id", "validation_id"),
        ]:
            bucket = summary[bucket_name]
            assert isinstance(bucket, dict)
            bucket[row[field]] = int(bucket.get(row[field], 0)) + 1

    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    append_query_log(args.refs_csv, args.out_csv, len(rows))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
