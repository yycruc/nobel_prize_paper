from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT_CSV = ROOT / "01_validation" / "03_matched_metadata" / "narrative_reconstruction_openalex_mag_matches_all45.csv"
OUT_CSV = ROOT / "01_validation" / "03_matched_metadata" / "narrative_candidate_review_table_all45.csv"
OUT_SUMMARY = ROOT / "01_validation" / "04_outputs" / "narrative_candidate_review_table_summary_all45.json"
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def normalized_doi(value: str) -> str:
    return (value or "").replace("https://doi.org/", "").strip().lower()


def choose_title(row: dict[str, str]) -> str:
    return row.get("openalex_title") or row.get("candidate_title", "")


def choose_year(row: dict[str, str]) -> str:
    return row.get("openalex_publication_year") or row.get("candidate_year", "")


def choose_journal(row: dict[str, str]) -> str:
    return row.get("openalex_journal") or row.get("candidate_journal", "")


def eligibility(row: dict[str, str]) -> tuple[str, str, str]:
    status = row.get("reconstruction_status", "")
    match_status = row.get("openalex_match_status", "")
    journal = choose_journal(row)
    doi = normalized_doi(row.get("openalex_doi") or row.get("candidate_doi", ""))
    if status == "non_paper_contribution_review":
        return "non_paper_review", "needs_manual_review", "Contribution appears patent/process/monograph-centered."
    if match_status == "matched_by_mag_id" and journal:
        return "journal_candidate_matched", "provisionally_accept_metadata", "OpenAlex exact MAG match has journal/source metadata."
    if match_status == "matched_by_mag_id" and not journal:
        return "matched_missing_source", "needs_manual_review", "OpenAlex exact MAG match lacks primary source metadata."
    if status == "needs_manual_verification":
        return "manual_seed_review", "needs_manual_review", "Manual seed candidate requires bibliographic verification."
    if match_status == "no_openalex_result_for_mag_id":
        return "mag_unresolved", "needs_manual_review", "Li 2019 MAG id did not resolve in OpenAlex."
    if doi:
        return "identifier_present_needs_review", "needs_manual_review", "Identifier exists but no OpenAlex exact MAG match."
    return "unresolved_metadata", "needs_manual_review", "No stable metadata match yet."


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
                "query_id": "build_narrative_candidate_review_table",
                "run_at": dt.datetime.now(dt.UTC).isoformat(),
                "phase": "validation",
                "source": "narrative reconstruction metadata matches",
                "query_or_url": str(INPUT_CSV),
                "parameters": "derive review status and analysis eligibility",
                "output_path": str(out_csv),
                "status": "ok",
                "notes": f"rows={rows}",
            }
        )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build review table from narrative reconstruction metadata matches.")
    parser.add_argument("--input-csv", type=Path, default=INPUT_CSV)
    parser.add_argument("--out-csv", type=Path, default=OUT_CSV)
    parser.add_argument("--summary-json", type=Path, default=OUT_SUMMARY)
    args = parser.parse_args()

    rows = read_csv(args.input_csv)
    out_rows: list[dict[str, str]] = []
    for row in rows:
        analysis_eligibility, review_status, note = eligibility(row)
        doi = normalized_doi(row.get("openalex_doi") or row.get("candidate_doi", ""))
        out_rows.append(
            {
                "validation_id": row.get("validation_id", ""),
                "laureate_id": row.get("laureate_id", ""),
                "full_name": row.get("full_name", ""),
                "award_year": row.get("award_year", ""),
                "category": row.get("category", ""),
                "period_bucket": row.get("period_bucket", ""),
                "candidate_title_original": row.get("candidate_title", ""),
                "candidate_year_original": row.get("candidate_year", ""),
                "matched_title": choose_title(row),
                "matched_year": choose_year(row),
                "award_lag_years": row.get("award_lag_years", ""),
                "matched_journal": choose_journal(row),
                "doi": doi,
                "openalex_work_id": row.get("openalex_work_id", ""),
                "openalex_source_id": row.get("openalex_source_id", ""),
                "issn_l": row.get("issn_l", ""),
                "candidate_source": row.get("candidate_source", ""),
                "mag_paper_id": row.get("mag_paper_id", ""),
                "openalex_match_status": row.get("openalex_match_status", ""),
                "reconstruction_status": row.get("reconstruction_status", ""),
                "analysis_eligibility": analysis_eligibility,
                "review_status": review_status,
                "review_note": note,
                "official_contribution_text": row.get("official_contribution_text", ""),
                "official_source_pages": row.get("official_source_pages", ""),
            }
        )

    fields = [
        "validation_id",
        "laureate_id",
        "full_name",
        "award_year",
        "category",
        "period_bucket",
        "candidate_title_original",
        "candidate_year_original",
        "matched_title",
        "matched_year",
        "award_lag_years",
        "matched_journal",
        "doi",
        "openalex_work_id",
        "openalex_source_id",
        "issn_l",
        "candidate_source",
        "mag_paper_id",
        "openalex_match_status",
        "reconstruction_status",
        "analysis_eligibility",
        "review_status",
        "review_note",
        "official_contribution_text",
        "official_source_pages",
    ]
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.out_csv.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out_rows)

    summary: dict[str, object] = {
        "input_rows": len(rows),
        "output_rows": len(out_rows),
        "by_analysis_eligibility": {},
        "by_review_status": {},
        "output": str(args.out_csv),
    }
    for row in out_rows:
        for bucket_name, field in [
            ("by_analysis_eligibility", "analysis_eligibility"),
            ("by_review_status", "review_status"),
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
