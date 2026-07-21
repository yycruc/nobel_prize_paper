from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT_CSV = ROOT / "01_validation" / "03_matched_metadata" / "narrative_candidate_review_table_all45_doi_enriched.csv"
NON_PAPER_CSV = ROOT / "01_validation" / "03_matched_metadata" / "non_paper_contribution_table_all45.csv"
HISTORICAL_VERIFICATION_CSV = ROOT / "01_validation" / "03_matched_metadata" / "historical_bibliographic_verification_table_all45.csv"
DUPLICATE_RESOLUTION_CSV = ROOT / "01_validation" / "03_matched_metadata" / "duplicate_candidate_resolution_table_all45.csv"
OUT_CSV = ROOT / "01_validation" / "03_matched_metadata" / "remaining_manual_review_queue_all45.csv"
OUT_SUMMARY = ROOT / "01_validation" / "04_outputs" / "remaining_manual_review_queue_summary_all45.json"
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def row_keys(rows: list[dict[str, str]], title_field: str) -> set[tuple[str, str]]:
    return {
        (row.get("validation_id", ""), row.get(title_field, ""))
        for row in rows
        if row.get("validation_id", "") and row.get(title_field, "")
    }


def review_priority(row: dict[str, str]) -> tuple[str, str]:
    eligibility = row.get("analysis_eligibility", "")
    if eligibility == "non_paper_review":
        return "P1", "method decision needed: non-paper contribution"
    if eligibility == "manual_seed_review":
        return "P2", "manual bibliographic verification needed"
    if eligibility == "mag_unresolved":
        return "P3", "MAG id did not resolve in OpenAlex; try alternate exact metadata source"
    if eligibility == "matched_missing_source":
        return "P3", "OpenAlex match lacks source metadata"
    return "P4", "general unresolved metadata"


def append_query_log(rows: int, out_csv: Path) -> None:
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
                "query_id": "build_remaining_manual_review_queue",
                "run_at": dt.datetime.now(dt.UTC).isoformat(),
                "phase": "validation",
                "source": "narrative candidate review table",
                "query_or_url": str(INPUT_CSV),
                "parameters": "review_status=needs_manual_review",
                "output_path": str(out_csv),
                "status": "ok",
                "notes": f"rows={rows}",
            }
        )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build remaining manual review queue from narrative review table.")
    parser.add_argument("--input-csv", type=Path, default=INPUT_CSV)
    parser.add_argument("--non-paper-csv", type=Path, default=NON_PAPER_CSV)
    parser.add_argument("--historical-verification-csv", type=Path, default=HISTORICAL_VERIFICATION_CSV)
    parser.add_argument("--duplicate-resolution-csv", type=Path, default=DUPLICATE_RESOLUTION_CSV)
    parser.add_argument("--out-csv", type=Path, default=OUT_CSV)
    parser.add_argument("--summary-json", type=Path, default=OUT_SUMMARY)
    args = parser.parse_args()

    documented_non_paper_keys = row_keys(read_csv(args.non_paper_csv), "candidate_title_or_record")
    historical_verified_keys = row_keys(read_csv(args.historical_verification_csv), "candidate_title_original")
    duplicate_resolved_keys = row_keys(read_csv(args.duplicate_resolution_csv), "duplicate_candidate_title")
    out_rows: list[dict[str, str]] = []
    for row in read_csv(args.input_csv):
        if row.get("review_status") != "needs_manual_review":
            continue
        key = (row.get("validation_id", ""), row.get("candidate_title_original", ""))
        if key in documented_non_paper_keys or key in historical_verified_keys or key in duplicate_resolved_keys:
            continue
        priority, next_action = review_priority(row)
        out_rows.append(
            {
                "validation_id": row.get("validation_id", ""),
                "full_name": row.get("full_name", ""),
                "award_year": row.get("award_year", ""),
                "category": row.get("category", ""),
                "candidate_title": row.get("candidate_title_original", ""),
                "candidate_year": row.get("candidate_year_original", ""),
                "matched_journal": row.get("matched_journal", ""),
                "doi": row.get("doi", ""),
                "mag_paper_id": row.get("mag_paper_id", ""),
                "analysis_eligibility": row.get("analysis_eligibility", ""),
                "reconstruction_status": row.get("reconstruction_status", ""),
                "review_priority": priority,
                "next_action": next_action,
                "official_contribution_text": row.get("official_contribution_text", ""),
                "official_source_pages": row.get("official_source_pages", ""),
                "review_note": row.get("review_note", ""),
            }
        )

    out_rows.sort(key=lambda item: (item["review_priority"], item["validation_id"], item["candidate_title"]))
    fields = [
        "validation_id",
        "full_name",
        "award_year",
        "category",
        "candidate_title",
        "candidate_year",
        "matched_journal",
        "doi",
        "mag_paper_id",
        "analysis_eligibility",
        "reconstruction_status",
        "review_priority",
        "next_action",
        "official_contribution_text",
        "official_source_pages",
        "review_note",
    ]
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.out_csv.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out_rows)

    summary: dict[str, object] = {
        "manual_review_rows": len(out_rows),
        "by_review_priority": {},
        "by_analysis_eligibility": {},
        "output": str(args.out_csv),
    }
    for row in out_rows:
        for bucket_name, field in [
            ("by_review_priority", "review_priority"),
            ("by_analysis_eligibility", "analysis_eligibility"),
        ]:
            bucket = summary[bucket_name]
            assert isinstance(bucket, dict)
            key = row[field]
            bucket[key] = int(bucket.get(key, 0)) + 1

    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    append_query_log(len(out_rows), args.out_csv)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
