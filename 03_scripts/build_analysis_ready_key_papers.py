from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "02_full_collection" / "01_raw_sources" / "nobel_api" / "nobel_award_baseline_full.csv"
REGISTRY = ROOT / "02_full_collection" / "03_matched_metadata" / "candidate_registry_with_gap_matches_full.csv"
OUT_CSV = ROOT / "02_full_collection" / "06_analysis" / "analysis_ready_key_papers_full.csv"
OUT_EXCLUDED = ROOT / "02_full_collection" / "06_analysis" / "analysis_excluded_or_review_key_paper_candidates_full.csv"
OUT_SUMMARY = ROOT / "02_full_collection" / "05_outputs" / "analysis_ready_key_papers_summary_full.json"
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"


FIELDNAMES = [
    "analysis_id",
    "registry_id",
    "validation_id",
    "laureate_id",
    "full_name",
    "award_year",
    "category",
    "title",
    "publication_year",
    "award_lag_years",
    "journal",
    "openalex_source_id",
    "issn_l",
    "doi",
    "openalex_work_id",
    "work_type",
    "evidence_sources",
    "registry_status",
    "analysis_inclusion",
    "analysis_confidence",
    "analysis_role",
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


def parse_int(value: str) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def classify(row: dict[str, str]) -> tuple[str, str, str, str]:
    status = row.get("registry_status", "")
    evidence = row.get("evidence_sources", "")
    title = row.get("title", "").strip()
    journal = row.get("journal", "").strip()
    publication_year = parse_int(row.get("publication_year", ""))
    award_year = parse_int(row.get("award_year", ""))
    openalex_work_id = row.get("openalex_work_id", "").strip()

    if not title or not publication_year:
        return "excluded", "D", "missing_publication_metadata", "Missing title or publication year."
    if award_year is not None and publication_year > award_year:
        return "excluded", "D", "post_award_publication", "Publication year is after award year."
    if not journal:
        return "review_only", "D", "missing_journal", "Missing journal/source, excluded from journal analysis."

    if status == "supplementary_candidate_needs_official_alignment" and openalex_work_id:
        return (
            "main",
            "B",
            "li2019_exact_mag_candidate",
            "Li 2019 prize-winning paper candidate with exact OpenAlex MAG metadata; official contribution alignment still documented as required.",
        )
    if status == "official_gap_metadata_matched_needs_official_alignment":
        return (
            "main",
            "B",
            "official_gap_reference_metadata_matched",
            "Nobel official gap reference matched to metadata; official contribution alignment still required.",
        )
    if status == "official_gap_metadata_candidate_needs_review":
        return (
            "sensitivity",
            "C",
            "official_gap_reference_candidate_review",
            "Official gap reference metadata candidate retained for sensitivity/review, not main analysis.",
        )
    if status == "official_reference_needs_key_relevance_review":
        return (
            "sensitivity",
            "C",
            "official_doi_reference_relevance_review",
            "Official DOI reference retained for sensitivity/review because it may be contextual.",
        )
    if "nobel_official_gap_reference_a_tier" in evidence and row.get("metadata_match_confidence") in {"A", "B"}:
        return (
            "main",
            "B",
            "official_gap_reference_metadata_matched",
            "Nobel official gap reference matched to metadata.",
        )
    return "review_only", "D", "not_main_analysis_ready", "Candidate not ready for main analysis."


def build() -> dict[str, object]:
    baseline = read_csv(BASELINE)
    registry = read_csv(REGISTRY)
    main_rows: list[dict[str, str]] = []
    excluded_rows: list[dict[str, str]] = []

    for row in registry:
        inclusion, confidence, role, note = classify(row)
        publication_year = parse_int(row.get("publication_year", ""))
        award_year = parse_int(row.get("award_year", ""))
        lag = ""
        if publication_year is not None and award_year is not None:
            lag = str(award_year - publication_year)
        out = {
            "analysis_id": "",
            "registry_id": row.get("registry_id", ""),
            "validation_id": row.get("validation_id", ""),
            "laureate_id": row.get("laureate_id", ""),
            "full_name": row.get("full_name", ""),
            "award_year": row.get("award_year", ""),
            "category": row.get("category", ""),
            "title": row.get("title", ""),
            "publication_year": "" if publication_year is None else str(publication_year),
            "award_lag_years": lag,
            "journal": row.get("journal", ""),
            "openalex_source_id": row.get("openalex_source_id", ""),
            "issn_l": row.get("issn_l", ""),
            "doi": row.get("doi", ""),
            "openalex_work_id": row.get("openalex_work_id", ""),
            "work_type": row.get("work_type", ""),
            "evidence_sources": row.get("evidence_sources", ""),
            "registry_status": row.get("registry_status", ""),
            "analysis_inclusion": inclusion,
            "analysis_confidence": confidence,
            "analysis_role": role,
            "notes": note,
        }
        if inclusion == "main":
            main_rows.append(out)
        else:
            excluded_rows.append(out)

    main_rows.sort(key=lambda r: (r["validation_id"], r["publication_year"], r["title"].lower()))
    excluded_rows.sort(key=lambda r: (r["validation_id"], r["analysis_inclusion"], r["publication_year"], r["title"].lower()))
    for idx, row in enumerate(main_rows, start=1):
        row["analysis_id"] = f"ANALYSISKP_{idx:06d}"
    for idx, row in enumerate(excluded_rows, start=1):
        row["analysis_id"] = f"REVIEWKP_{idx:06d}"

    write_csv(OUT_CSV, main_rows, FIELDNAMES)
    write_csv(OUT_EXCLUDED, excluded_rows, FIELDNAMES)

    baseline_ids = {row["validation_id"] for row in baseline}
    covered_main = {row["validation_id"] for row in main_rows}
    summary = {
        "baseline_records": len(baseline),
        "registry_rows": len(registry),
        "main_analysis_rows": len(main_rows),
        "excluded_or_review_rows": len(excluded_rows),
        "main_covered_records": len(covered_main),
        "records_without_main_analysis_key_paper": len(baseline_ids - covered_main),
        "main_coverage_rate": round(len(covered_main) / len(baseline), 4) if baseline else 0,
        "by_category_main_rows": dict(Counter(row["category"] for row in main_rows)),
        "by_analysis_role": dict(Counter(row["analysis_role"] for row in main_rows)),
        "by_publication_year_missing_or_excluded_role": dict(Counter(row["analysis_role"] for row in excluded_rows)),
        "output": str(OUT_CSV),
        "excluded_output": str(OUT_EXCLUDED),
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
        "query_id": "build_analysis_ready_key_papers",
        "run_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "phase": "analysis",
        "source": "candidate registry with gap matches",
        "query_or_url": str(REGISTRY),
        "parameters": "main analysis includes Li2019 exact MAG candidates and official gap metadata matched candidates; sensitivity/review rows separated",
        "output_path": str(OUT_CSV),
        "status": "ok",
        "notes": (
            f"main_rows={summary['main_analysis_rows']}; "
            f"covered_records={summary['main_covered_records']}; "
            f"coverage_rate={summary['main_coverage_rate']}"
        ),
    }
    with QUERY_LOG.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    print(json.dumps(build(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
