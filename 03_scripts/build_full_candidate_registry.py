from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_DOI_MATCHES = (
    ROOT
    / "02_full_collection"
    / "03_matched_metadata"
    / "official_reference_doi_matches_full.csv"
)
LI2019_MAG_MATCHES = (
    ROOT
    / "02_full_collection"
    / "03_matched_metadata"
    / "li2019_openalex_mag_matches_full.csv"
)
OUT_CSV = (
    ROOT
    / "02_full_collection"
    / "03_matched_metadata"
    / "candidate_registry_full.csv"
)
OUT_REVIEW_QUEUE = (
    ROOT
    / "02_full_collection"
    / "03_matched_metadata"
    / "candidate_registry_review_queue_full.csv"
)
OUT_SUMMARY = (
    ROOT
    / "02_full_collection"
    / "05_outputs"
    / "candidate_registry_summary_full.json"
)
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"


FIELDNAMES = [
    "registry_id",
    "validation_id",
    "laureate_id",
    "full_name",
    "award_year",
    "category",
    "work_key",
    "openalex_work_id",
    "doi",
    "title",
    "publication_year",
    "journal",
    "openalex_source_id",
    "issn_l",
    "work_type",
    "candidate_year",
    "award_lag_years",
    "evidence_sources",
    "source_record_ids",
    "li2019_candidate_ids",
    "li2019_mag_paper_ids",
    "official_reference_ids",
    "source_candidate_titles",
    "official_reference_texts",
    "metadata_match_confidence",
    "metadata_match_methods",
    "registry_status",
    "review_priority",
    "analysis_readiness",
    "notes",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def normalize_doi(value: str) -> str:
    doi = (value or "").strip().lower()
    if doi.startswith("https://doi.org/"):
        doi = doi.removeprefix("https://doi.org/")
    if doi.startswith("http://dx.doi.org/"):
        doi = doi.removeprefix("http://dx.doi.org/")
    return doi.rstrip(".,;)")


def normalize_openalex_id(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if value.startswith("https://openalex.org/"):
        return value
    return f"https://openalex.org/{value.lstrip('/')}"


def first_nonempty(*values: str) -> str:
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def append_unique(target: list[str], value: str) -> None:
    value = (value or "").strip()
    if value and value not in target:
        target.append(value)


def make_work_key(row: dict[str, str], fallback: str) -> str:
    openalex_id = normalize_openalex_id(row.get("openalex_work_id", ""))
    if openalex_id:
        return f"openalex:{openalex_id.rsplit('/', 1)[-1].lower()}"
    doi = normalize_doi(first_nonempty(row.get("openalex_doi", ""), row.get("reference_doi", "")))
    if doi:
        return f"doi:{doi}"
    mag_id = (row.get("mag_paper_id") or "").strip()
    if mag_id:
        return f"mag_unresolved:{mag_id}"
    return fallback


def new_group(validation_id: str, work_key: str) -> dict[str, object]:
    return {
        "validation_id": validation_id,
        "work_key": work_key,
        "laureate_id": "",
        "full_name": "",
        "award_year": "",
        "category": "",
        "openalex_work_id": "",
        "doi": "",
        "title": "",
        "publication_year": "",
        "journal": "",
        "openalex_source_id": "",
        "issn_l": "",
        "work_type": "",
        "candidate_year": "",
        "award_lag_years": "",
        "evidence_sources": [],
        "source_record_ids": [],
        "li2019_candidate_ids": [],
        "li2019_mag_paper_ids": [],
        "official_reference_ids": [],
        "source_candidate_titles": [],
        "official_reference_texts": [],
        "metadata_match_methods": [],
        "notes": [],
        "has_official_doi": False,
        "has_li2019": False,
        "has_li2019_openalex_match": False,
        "has_unresolved_li2019": False,
    }


def merge_common(group: dict[str, object], row: dict[str, str]) -> None:
    for field in ("laureate_id", "full_name", "award_year", "category"):
        group[field] = first_nonempty(str(group[field]), row.get(field, ""))


def merge_official(group: dict[str, object], row: dict[str, str]) -> None:
    merge_common(group, row)
    group["has_official_doi"] = True
    append_unique(group["evidence_sources"], "nobel_official_reference_doi")
    append_unique(group["source_record_ids"], row.get("reference_candidate_id", ""))
    append_unique(group["official_reference_ids"], row.get("reference_candidate_id", ""))
    append_unique(group["official_reference_texts"], row.get("reference_text", ""))
    append_unique(group["metadata_match_methods"], row.get("metadata_match_status", ""))
    append_unique(group["notes"], "Official Nobel PDF reference with exact DOI metadata match.")

    group["openalex_work_id"] = first_nonempty(
        str(group["openalex_work_id"]),
        normalize_openalex_id(row.get("openalex_work_id", "")),
    )
    group["doi"] = first_nonempty(str(group["doi"]), normalize_doi(row.get("openalex_doi", "")), normalize_doi(row.get("reference_doi", "")))
    group["title"] = first_nonempty(str(group["title"]), row.get("openalex_title", ""))
    group["publication_year"] = first_nonempty(str(group["publication_year"]), row.get("openalex_year", ""))
    group["journal"] = first_nonempty(str(group["journal"]), row.get("openalex_source", ""))
    group["openalex_source_id"] = first_nonempty(str(group["openalex_source_id"]), row.get("openalex_source_id", ""))
    group["issn_l"] = first_nonempty(str(group["issn_l"]), row.get("issn_l", ""))
    group["work_type"] = first_nonempty(str(group["work_type"]), row.get("openalex_type", ""))


def merge_li2019(group: dict[str, object], row: dict[str, str]) -> None:
    merge_common(group, row)
    group["has_li2019"] = True
    append_unique(group["evidence_sources"], "li2019_prize_winning_paper")
    append_unique(group["source_record_ids"], row.get("candidate_id", ""))
    append_unique(group["li2019_candidate_ids"], row.get("candidate_id", ""))
    append_unique(group["li2019_mag_paper_ids"], row.get("mag_paper_id", ""))
    append_unique(group["source_candidate_titles"], row.get("candidate_title", ""))
    append_unique(group["metadata_match_methods"], row.get("openalex_match_status", ""))
    append_unique(group["notes"], "Li 2019 candidate requires alignment to Nobel official contribution before final acceptance.")

    if row.get("openalex_match_status") == "matched_by_mag_id":
        group["has_li2019_openalex_match"] = True
    else:
        group["has_unresolved_li2019"] = True

    group["openalex_work_id"] = first_nonempty(
        str(group["openalex_work_id"]),
        normalize_openalex_id(row.get("openalex_work_id", "")),
    )
    group["doi"] = first_nonempty(str(group["doi"]), normalize_doi(row.get("openalex_doi", "")))
    group["title"] = first_nonempty(str(group["title"]), row.get("openalex_title", ""), row.get("candidate_title", ""))
    group["publication_year"] = first_nonempty(
        str(group["publication_year"]),
        row.get("openalex_publication_year", ""),
        row.get("candidate_year", ""),
    )
    group["journal"] = first_nonempty(str(group["journal"]), row.get("openalex_source", ""))
    group["openalex_source_id"] = first_nonempty(str(group["openalex_source_id"]), row.get("openalex_source_id", ""))
    group["issn_l"] = first_nonempty(str(group["issn_l"]), row.get("issn_l", ""))
    group["work_type"] = first_nonempty(str(group["work_type"]), row.get("openalex_type", ""))
    group["candidate_year"] = first_nonempty(str(group["candidate_year"]), row.get("candidate_year", ""))
    group["award_lag_years"] = first_nonempty(str(group["award_lag_years"]), row.get("award_lag_years", ""))


def classify_group(group: dict[str, object]) -> tuple[str, str, str, str]:
    has_official = bool(group["has_official_doi"])
    has_li = bool(group["has_li2019"])
    has_li_match = bool(group["has_li2019_openalex_match"])
    unresolved_li = bool(group["has_unresolved_li2019"])

    if has_official and has_li:
        return (
            "A",
            "strong_candidate_needs_final_acceptance_review",
            "P1",
            "metadata_ready_not_final_key_paper",
        )
    if has_li_match:
        return (
            "A",
            "supplementary_candidate_needs_official_alignment",
            "P2",
            "metadata_ready_not_final_key_paper",
        )
    if has_official:
        return (
            "A",
            "official_reference_needs_key_relevance_review",
            "P3",
            "metadata_ready_not_final_key_paper",
        )
    if has_li and unresolved_li:
        return (
            "D",
            "metadata_unresolved_needs_manual_or_identifier_search",
            "P4",
            "metadata_unresolved_not_final_key_paper",
        )
    return (
        "D",
        "unclassified_needs_review",
        "P5",
        "not_ready",
    )


def render_group(registry_id: int, group: dict[str, object]) -> dict[str, str]:
    confidence, status, priority, readiness = classify_group(group)
    row: dict[str, str] = {"registry_id": f"REGFULL_{registry_id:06d}"}
    for field in FIELDNAMES:
        if field == "registry_id":
            continue
        if field == "metadata_match_confidence":
            row[field] = confidence
        elif field == "registry_status":
            row[field] = status
        elif field == "review_priority":
            row[field] = priority
        elif field == "analysis_readiness":
            row[field] = readiness
        elif field in {
            "evidence_sources",
            "source_record_ids",
            "li2019_candidate_ids",
            "li2019_mag_paper_ids",
            "official_reference_ids",
            "source_candidate_titles",
            "official_reference_texts",
            "metadata_match_methods",
            "notes",
        }:
            row[field] = " || ".join(group[field])
        else:
            row[field] = str(group[field])
    return row


def append_query_log(summary: dict[str, object]) -> None:
    if not QUERY_LOG.exists():
        return
    fieldnames = [
        "query_id",
        "run_at",
        "phase",
        "source",
        "query_or_url",
        "parameters",
        "output_path",
        "status",
        "notes",
    ]
    row = {
        "query_id": "build_full_candidate_registry",
        "run_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "phase": "full_collection",
        "source": "Local matched metadata",
        "query_or_url": f"{OFFICIAL_DOI_MATCHES}; {LI2019_MAG_MATCHES}",
        "parameters": "merge official DOI exact matches with Li 2019 MAG exact matches; no network calls",
        "output_path": str(OUT_CSV),
        "status": "ok",
        "notes": (
            f"registry_rows={summary['registry_rows']}; "
            f"with_openalex={summary['rows_with_openalex_work_id']}; "
            f"p1={summary['by_review_priority'].get('P1', 0)}"
        ),
    }
    with QUERY_LOG.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writerow(row)


def build_registry() -> dict[str, object]:
    official_rows = read_csv(OFFICIAL_DOI_MATCHES)
    li_rows = read_csv(LI2019_MAG_MATCHES)

    groups: dict[tuple[str, str], dict[str, object]] = {}

    for row in official_rows:
        validation_id = row.get("validation_id", "")
        work_key = make_work_key(row, f"official:{row.get('reference_candidate_id', '')}")
        key = (validation_id, work_key)
        groups.setdefault(key, new_group(validation_id, work_key))
        merge_official(groups[key], row)

    for row in li_rows:
        validation_id = row.get("validation_id", "")
        work_key = make_work_key(row, f"li2019:{row.get('candidate_id', '')}")
        key = (validation_id, work_key)
        groups.setdefault(key, new_group(validation_id, work_key))
        merge_li2019(groups[key], row)

    registry_rows = [
        render_group(idx, group)
        for idx, group in enumerate(
            sorted(groups.values(), key=lambda g: (str(g["validation_id"]), str(g["work_key"]))),
            start=1,
        )
    ]

    review_rows = sorted(
        registry_rows,
        key=lambda r: (
            r["review_priority"],
            r["validation_id"],
            r["publication_year"],
            r["title"].lower(),
        ),
    )

    write_csv(OUT_CSV, registry_rows, FIELDNAMES)
    write_csv(OUT_REVIEW_QUEUE, review_rows, FIELDNAMES)

    summary = {
        "official_doi_input_rows": len(official_rows),
        "li2019_input_rows": len(li_rows),
        "registry_rows": len(registry_rows),
        "rows_with_openalex_work_id": sum(1 for r in registry_rows if r["openalex_work_id"]),
        "rows_with_doi": sum(1 for r in registry_rows if r["doi"]),
        "unique_openalex_work_ids": len({r["openalex_work_id"] for r in registry_rows if r["openalex_work_id"]}),
        "covered_validation_records": len({r["validation_id"] for r in registry_rows if r["validation_id"]}),
        "by_evidence_sources": dict(Counter(r["evidence_sources"] for r in registry_rows)),
        "by_registry_status": dict(Counter(r["registry_status"] for r in registry_rows)),
        "by_review_priority": dict(Counter(r["review_priority"] for r in registry_rows)),
        "by_analysis_readiness": dict(Counter(r["analysis_readiness"] for r in registry_rows)),
        "by_category": dict(Counter(r["category"] for r in registry_rows)),
        "output": str(OUT_CSV),
        "review_queue_output": str(OUT_REVIEW_QUEUE),
    }

    by_record_counts: defaultdict[str, int] = defaultdict(int)
    for row in registry_rows:
        by_record_counts[row["validation_id"]] += 1
    summary["records_with_multiple_registry_rows"] = sum(1 for count in by_record_counts.values() if count > 1)

    OUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    append_query_log(summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    summary = build_registry()
    if args.summary_only:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
