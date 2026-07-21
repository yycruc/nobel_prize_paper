from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVIEW_TABLE_CSV = ROOT / "01_validation" / "03_matched_metadata" / "narrative_candidate_review_table_all45_doi_enriched.csv"
OUT_CSV = ROOT / "01_validation" / "03_matched_metadata" / "duplicate_candidate_resolution_table_all45.csv"
OUT_SUMMARY = ROOT / "01_validation" / "04_outputs" / "duplicate_candidate_resolution_summary_all45.json"
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"


DUPLICATE_RULES = {
    (
        "V006",
        "the magnetic moment of silver atoms",
    ): {
        "duplicate_of_title": "Der experimentelle Nachweis des magnetischen Moments des Silberatoms",
        "duplicate_of_openalex_work_id": "https://openalex.org/W2069807188",
        "duplicate_of_doi": "10.1007/bf01329580",
        "duplicate_of_source": "The European Physical Journal A",
        "resolution_note": "English-title Li 2019 candidate represents the same Stern-Gerlach silver-atom magnetic-moment result as the matched German article; keep the DOI/OpenAlex-matched German record and exclude this duplicate candidate.",
    }
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


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
                "query_id": "build_duplicate_candidate_resolution_table",
                "run_at": dt.datetime.now(dt.UTC).isoformat(),
                "phase": "validation",
                "source": "narrative candidate review table",
                "query_or_url": str(REVIEW_TABLE_CSV),
                "parameters": "known duplicate title resolution rules",
                "output_path": str(out_csv),
                "status": "ok",
                "notes": f"duplicate_rows={rows}",
            }
        )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build duplicate candidate resolution table.")
    parser.add_argument("--review-table-csv", type=Path, default=REVIEW_TABLE_CSV)
    parser.add_argument("--out-csv", type=Path, default=OUT_CSV)
    parser.add_argument("--summary-json", type=Path, default=OUT_SUMMARY)
    args = parser.parse_args()

    out_rows: list[dict[str, str]] = []
    for row in read_csv(args.review_table_csv):
        key = (row.get("validation_id", ""), row.get("candidate_title_original", ""))
        rule = DUPLICATE_RULES.get(key)
        if not rule:
            continue
        out_rows.append(
            {
                "validation_id": row.get("validation_id", ""),
                "full_name": row.get("full_name", ""),
                "award_year": row.get("award_year", ""),
                "category": row.get("category", ""),
                "duplicate_candidate_title": row.get("candidate_title_original", ""),
                "duplicate_candidate_year": row.get("candidate_year_original", ""),
                "duplicate_of_title": rule["duplicate_of_title"],
                "duplicate_of_openalex_work_id": rule["duplicate_of_openalex_work_id"],
                "duplicate_of_doi": rule["duplicate_of_doi"],
                "duplicate_of_source": rule["duplicate_of_source"],
                "resolution_status": "duplicate_of_matched_candidate",
                "main_analysis_status": "excluded_duplicate_candidate",
                "resolution_note": rule["resolution_note"],
            }
        )

    fields = [
        "validation_id",
        "full_name",
        "award_year",
        "category",
        "duplicate_candidate_title",
        "duplicate_candidate_year",
        "duplicate_of_title",
        "duplicate_of_openalex_work_id",
        "duplicate_of_doi",
        "duplicate_of_source",
        "resolution_status",
        "main_analysis_status",
        "resolution_note",
    ]
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.out_csv.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out_rows)

    summary = {
        "duplicate_rows": len(out_rows),
        "duplicate_validation_records": len({row["validation_id"] for row in out_rows}),
        "output": str(args.out_csv),
    }
    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    append_query_log(len(out_rows), args.out_csv)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
