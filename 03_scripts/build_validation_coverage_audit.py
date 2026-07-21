from __future__ import annotations

import csv
import datetime as dt
import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_CSV = ROOT / "01_validation" / "validation_sample.csv"
LI_CANDIDATES_CSV = ROOT / "01_validation" / "02_candidate_key_papers" / "key_paper_candidates_validation.csv"
OFFICIAL_REFS_CSV = ROOT / "01_validation" / "02_candidate_key_papers" / "official_pdf_reference_section_candidates.csv"
CLASSIFICATION_CSV = ROOT / "01_validation" / "02_candidate_key_papers" / "official_reference_classification_validation.csv"
EARLY_QUEUE_CSV = ROOT / "01_validation" / "02_candidate_key_papers" / "early_official_narrative_review_queue.csv"
METADATA_MATCHES_CSV = ROOT / "01_validation" / "03_matched_metadata" / "official_reference_metadata_matches_validation_partial_220.csv"
NARRATIVE_REVIEW_CSV = ROOT / "01_validation" / "03_matched_metadata" / "narrative_candidate_review_table_all45.csv"
NON_PAPER_CSV = ROOT / "01_validation" / "03_matched_metadata" / "non_paper_contribution_table_all45.csv"
HISTORICAL_VERIFICATION_CSV = ROOT / "01_validation" / "03_matched_metadata" / "historical_bibliographic_verification_table_all45.csv"
OUT_CSV = ROOT / "01_validation" / "04_outputs" / "validation_coverage_audit.csv"
OUT_SUMMARY = ROOT / "01_validation" / "04_outputs" / "validation_coverage_audit_summary.json"
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def count_by_id(rows: list[dict[str, str]], id_field: str = "validation_id") -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        key = row.get(id_field, "")
        if key:
            out[key] = out.get(key, 0) + 1
    return out


def append_query_log(sample_csv: Path, out_csv: Path, rows: int) -> None:
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
                "query_id": "build_validation_coverage_audit",
                "run_at": dt.datetime.now(dt.UTC).isoformat(),
                "phase": "validation",
                "source": "validation derived tables",
                "query_or_url": str(sample_csv),
                "parameters": "coverage by validation_id",
                "output_path": str(out_csv),
                "status": "ok",
                "notes": f"rows={rows}",
            }
        )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build coverage audit by validation sample record.")
    parser.add_argument("--sample-csv", type=Path, default=SAMPLE_CSV)
    parser.add_argument("--li-candidates-csv", type=Path, default=LI_CANDIDATES_CSV)
    parser.add_argument("--official-refs-csv", type=Path, default=OFFICIAL_REFS_CSV)
    parser.add_argument("--classification-csv", type=Path, default=CLASSIFICATION_CSV)
    parser.add_argument("--early-queue-csv", type=Path, default=EARLY_QUEUE_CSV)
    parser.add_argument("--metadata-matches-csv", type=Path, default=METADATA_MATCHES_CSV)
    parser.add_argument("--narrative-review-csv", type=Path, default=NARRATIVE_REVIEW_CSV)
    parser.add_argument("--non-paper-csv", type=Path, default=NON_PAPER_CSV)
    parser.add_argument("--historical-verification-csv", type=Path, default=HISTORICAL_VERIFICATION_CSV)
    parser.add_argument("--out-csv", type=Path, default=OUT_CSV)
    parser.add_argument("--summary-json", type=Path, default=OUT_SUMMARY)
    args = parser.parse_args()

    sample = read_csv(args.sample_csv)
    li_counts = count_by_id(read_csv(args.li_candidates_csv))
    official_ref_counts = count_by_id(read_csv(args.official_refs_csv))
    class_rows = read_csv(args.classification_csv)
    matchable_counts: dict[str, int] = {}
    manual_counts: dict[str, int] = {}
    for row in class_rows:
        validation_id = row.get("validation_id", "")
        if row.get("api_matchable") == "yes":
            matchable_counts[validation_id] = matchable_counts.get(validation_id, 0) + 1
        else:
            manual_counts[validation_id] = manual_counts.get(validation_id, 0) + 1

    early_queue_ids = {row.get("validation_id", "") for row in read_csv(args.early_queue_csv)}
    metadata_rows = read_csv(args.metadata_matches_csv)
    accepted_counts: dict[str, int] = {}
    for row in metadata_rows:
        if row.get("match_confidence") in {"A", "B"}:
            validation_id = row.get("validation_id", "")
            accepted_counts[validation_id] = accepted_counts.get(validation_id, 0) + 1

    narrative_rows = read_csv(args.narrative_review_csv)
    narrative_provisional_counts: dict[str, int] = {}
    narrative_review_counts: dict[str, int] = {}
    for row in narrative_rows:
        validation_id = row.get("validation_id", "")
        if not validation_id:
            continue
        if row.get("review_status") == "provisionally_accept_metadata":
            narrative_provisional_counts[validation_id] = narrative_provisional_counts.get(validation_id, 0) + 1
        else:
            narrative_review_counts[validation_id] = narrative_review_counts.get(validation_id, 0) + 1

    non_paper_counts = count_by_id(read_csv(args.non_paper_csv))
    historical_verified_counts = count_by_id(read_csv(args.historical_verification_csv))

    out_rows: list[dict[str, str]] = []
    for row in sample:
        validation_id = row["validation_id"]
        has_candidate = bool(li_counts.get(validation_id) or official_ref_counts.get(validation_id) or validation_id in early_queue_ids)
        status = "covered_pending_review" if has_candidate else "no_candidate_evidence"
        if accepted_counts.get(validation_id):
            status = "metadata_matched_partial"
        elif narrative_provisional_counts.get(validation_id):
            status = "narrative_metadata_provisionally_matched"
        elif non_paper_counts.get(validation_id):
            status = "non_paper_contribution_documented"
        elif historical_verified_counts.get(validation_id):
            status = "historical_bibliography_verified"
        elif validation_id in early_queue_ids:
            status = "official_narrative_manual_review"
        out_rows.append(
            {
                "validation_id": validation_id,
                "laureate_id": row["laureate_id"],
                "full_name": row["full_name"],
                "award_year": row["award_year"],
                "category": row["category"],
                "li2019_candidate_rows": str(li_counts.get(validation_id, 0)),
                "official_pdf_reference_rows": str(official_ref_counts.get(validation_id, 0)),
                "api_matchable_official_reference_rows": str(matchable_counts.get(validation_id, 0)),
                "manual_or_later_official_reference_rows": str(manual_counts.get(validation_id, 0)),
                "accepted_metadata_match_rows_partial": str(accepted_counts.get(validation_id, 0)),
                "narrative_provisional_metadata_rows": str(narrative_provisional_counts.get(validation_id, 0)),
                "narrative_manual_review_rows": str(narrative_review_counts.get(validation_id, 0)),
                "non_paper_contribution_rows": str(non_paper_counts.get(validation_id, 0)),
                "historical_bibliography_verified_rows": str(historical_verified_counts.get(validation_id, 0)),
                "in_early_narrative_review_queue": "yes" if validation_id in early_queue_ids else "no",
                "coverage_status": status,
            }
        )

    fields = [
        "validation_id",
        "laureate_id",
        "full_name",
        "award_year",
        "category",
        "li2019_candidate_rows",
        "official_pdf_reference_rows",
        "api_matchable_official_reference_rows",
        "manual_or_later_official_reference_rows",
        "accepted_metadata_match_rows_partial",
        "narrative_provisional_metadata_rows",
        "narrative_manual_review_rows",
        "non_paper_contribution_rows",
        "historical_bibliography_verified_rows",
        "in_early_narrative_review_queue",
        "coverage_status",
    ]
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.out_csv.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out_rows)

    summary: dict[str, object] = {
        "sample_rows": len(out_rows),
        "by_coverage_status": {},
        "output": str(args.out_csv),
    }
    for row in out_rows:
        bucket = summary["by_coverage_status"]
        assert isinstance(bucket, dict)
        bucket[row["coverage_status"]] = int(bucket.get(row["coverage_status"], 0)) + 1

    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    append_query_log(args.sample_csv, args.out_csv, len(out_rows))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
