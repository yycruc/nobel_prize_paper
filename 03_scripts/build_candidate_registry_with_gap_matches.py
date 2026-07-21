from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_REGISTRY = ROOT / "02_full_collection" / "03_matched_metadata" / "candidate_registry_full.csv"
GAP_MATCHES = ROOT / "02_full_collection" / "03_matched_metadata" / "official_gap_a_tier_metadata_matches_full.csv"
OUT_CSV = ROOT / "02_full_collection" / "03_matched_metadata" / "candidate_registry_with_gap_matches_full.csv"
OUT_REVIEW_QUEUE = ROOT / "02_full_collection" / "03_matched_metadata" / "candidate_registry_with_gap_matches_review_queue_full.csv"
OUT_SUMMARY = ROOT / "02_full_collection" / "05_outputs" / "candidate_registry_with_gap_matches_summary_full.json"
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


def append_unique(existing: str, value: str) -> str:
    values = [item.strip() for item in (existing or "").split(" || ") if item.strip()]
    value = (value or "").strip()
    if value and value not in values:
        values.append(value)
    return " || ".join(values)


def first_nonempty(*values: str) -> str:
    for value in values:
        if value and str(value).strip():
            return str(value).strip()
    return ""


def work_key_for_gap(row: dict[str, str]) -> str:
    openalex_id = normalize_openalex_id(row.get("openalex_work_id", ""))
    if openalex_id:
        return f"openalex:{openalex_id.rsplit('/', 1)[-1].lower()}"
    doi = normalize_doi(first_nonempty(row.get("openalex_doi", ""), row.get("crossref_doi", ""), row.get("detected_doi", "")))
    if doi:
        return f"doi:{doi}"
    return f"gap:{row.get('gap_candidate_id', '')}"


def row_from_gap(row: dict[str, str]) -> dict[str, str]:
    confidence = row.get("metadata_match_confidence", "")
    review_status = row.get("review_status", "")
    if review_status == "metadata_matched_needs_official_alignment":
        registry_status = "official_gap_metadata_matched_needs_official_alignment"
        review_priority = "P1"
        readiness = "metadata_ready_not_final_key_paper"
    else:
        registry_status = "official_gap_metadata_candidate_needs_review"
        review_priority = "P2"
        readiness = "metadata_candidate_not_final_key_paper"

    publication_year = first_nonempty(row.get("openalex_year", ""), row.get("crossref_year", ""))
    try:
        lag = str(int(row.get("award_year", "")) - int(publication_year)) if publication_year else ""
    except ValueError:
        lag = ""

    return {
        "registry_id": "",
        "validation_id": row.get("validation_id", ""),
        "laureate_id": row.get("laureate_id", ""),
        "full_name": row.get("full_name", ""),
        "award_year": row.get("award_year", ""),
        "category": row.get("category", ""),
        "work_key": work_key_for_gap(row),
        "openalex_work_id": normalize_openalex_id(row.get("openalex_work_id", "")),
        "doi": normalize_doi(first_nonempty(row.get("openalex_doi", ""), row.get("crossref_doi", ""), row.get("detected_doi", ""))),
        "title": first_nonempty(row.get("openalex_title", ""), row.get("crossref_title", "")),
        "publication_year": publication_year,
        "journal": first_nonempty(row.get("openalex_source", ""), row.get("crossref_journal", "")),
        "openalex_source_id": row.get("openalex_source_id", ""),
        "issn_l": row.get("issn_l", ""),
        "work_type": first_nonempty(row.get("openalex_type", ""), row.get("crossref_type", "")),
        "candidate_year": publication_year,
        "award_lag_years": lag,
        "evidence_sources": "nobel_official_gap_reference_a_tier",
        "source_record_ids": row.get("gap_candidate_id", ""),
        "li2019_candidate_ids": "",
        "li2019_mag_paper_ids": "",
        "official_reference_ids": row.get("reference_candidate_id", ""),
        "source_candidate_titles": first_nonempty(row.get("openalex_title", ""), row.get("crossref_title", "")),
        "official_reference_texts": row.get("reference_text", ""),
        "metadata_match_confidence": confidence,
        "metadata_match_methods": row.get("metadata_match_method", ""),
        "registry_status": registry_status,
        "review_priority": review_priority,
        "analysis_readiness": readiness,
        "notes": "Added from official gap A-tier metadata matching; still requires Nobel official contribution alignment.",
    }


def merge_row(existing: dict[str, str], incoming: dict[str, str]) -> None:
    for field in (
        "evidence_sources",
        "source_record_ids",
        "official_reference_ids",
        "source_candidate_titles",
        "official_reference_texts",
        "metadata_match_methods",
        "notes",
    ):
        existing[field] = append_unique(existing.get(field, ""), incoming.get(field, ""))

    for field in (
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
    ):
        existing[field] = first_nonempty(existing.get(field, ""), incoming.get(field, ""))

    if existing.get("metadata_match_confidence") == "D" and incoming.get("metadata_match_confidence"):
        existing["metadata_match_confidence"] = incoming["metadata_match_confidence"]
    if incoming.get("review_priority", "P9") < existing.get("review_priority", "P9"):
        existing["review_priority"] = incoming["review_priority"]
        existing["registry_status"] = incoming["registry_status"]
        existing["analysis_readiness"] = incoming["analysis_readiness"]


def build_registry() -> dict[str, object]:
    base_rows = read_csv(BASE_REGISTRY)
    gap_rows = [
        row
        for row in read_csv(GAP_MATCHES)
        if row.get("metadata_match_confidence") != "D"
        and row.get("review_status") in {"metadata_matched_needs_official_alignment", "metadata_candidate_needs_review"}
    ]

    merged: dict[tuple[str, str], dict[str, str]] = {}
    for row in base_rows:
        merged[(row["validation_id"], row["work_key"])] = dict(row)

    added_rows = 0
    merged_rows = 0
    for gap in gap_rows:
        incoming = row_from_gap(gap)
        key = (incoming["validation_id"], incoming["work_key"])
        if key in merged:
            merge_row(merged[key], incoming)
            merged_rows += 1
        else:
            merged[key] = incoming
            added_rows += 1

    out_rows = sorted(merged.values(), key=lambda r: (r["validation_id"], r["work_key"]))
    for idx, row in enumerate(out_rows, start=1):
        row["registry_id"] = f"REGFULLPLUS_{idx:06d}"

    review_rows = sorted(
        out_rows,
        key=lambda r: (r["review_priority"], r["validation_id"], r["publication_year"], r["title"].lower()),
    )

    write_csv(OUT_CSV, out_rows, FIELDNAMES)
    write_csv(OUT_REVIEW_QUEUE, review_rows, FIELDNAMES)

    summary = {
        "base_registry_rows": len(base_rows),
        "gap_metadata_input_rows_non_d": len(gap_rows),
        "gap_rows_added": added_rows,
        "gap_rows_merged_with_existing": merged_rows,
        "registry_rows": len(out_rows),
        "rows_with_openalex_work_id": sum(1 for r in out_rows if r["openalex_work_id"]),
        "rows_with_doi": sum(1 for r in out_rows if r["doi"]),
        "covered_validation_records": len({r["validation_id"] for r in out_rows if r["validation_id"]}),
        "by_registry_status": dict(Counter(r["registry_status"] for r in out_rows)),
        "by_evidence_sources": dict(Counter(r["evidence_sources"] for r in out_rows)),
        "by_review_priority": dict(Counter(r["review_priority"] for r in out_rows)),
        "output": str(OUT_CSV),
        "review_queue_output": str(OUT_REVIEW_QUEUE),
    }
    OUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    append_query_log(summary)
    return summary


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
        "query_id": "build_candidate_registry_with_gap_matches",
        "run_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "phase": "full_collection",
        "source": "Local candidate registry; official gap A-tier metadata matches",
        "query_or_url": f"{BASE_REGISTRY}; {GAP_MATCHES}",
        "parameters": "merge non-D A-tier gap metadata matches into candidate registry; no network calls",
        "output_path": str(OUT_CSV),
        "status": "ok",
        "notes": (
            f"base_rows={summary['base_registry_rows']}; "
            f"added={summary['gap_rows_added']}; "
            f"merged={summary['gap_rows_merged_with_existing']}; "
            f"registry_rows={summary['registry_rows']}"
        ),
    }
    with QUERY_LOG.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    summary = build_registry()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
