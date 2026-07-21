from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVIEW_TABLE_CSV = ROOT / "01_validation" / "03_matched_metadata" / "narrative_candidate_review_table_all45_doi_enriched.csv"
OUT_CSV = ROOT / "01_validation" / "03_matched_metadata" / "non_paper_contribution_table_all45.csv"
OUT_SUMMARY = ROOT / "01_validation" / "04_outputs" / "non_paper_contribution_table_summary_all45.json"
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"


EXTRA_NON_PAPER_RECORDS = {
    (
        "V022",
        "Chemical kinetics and chain reactions",
    ): {
        "contribution_type": "monograph_or_book",
        "source_or_record": "Oxford University Press / Clarendon Press",
        "identifier": "",
        "review_note": "Li 2019 candidate is Semenov's monograph, not a journal article; retain for comprehensive Nobel coverage and exclude from top-journal main analysis.",
    }
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def contribution_type(row: dict[str, str]) -> str:
    text = f"{row.get('candidate_title', '')} {row.get('matched_journal', '')}".casefold()
    if "patent" in text or "process" in text:
        return "patent_or_process"
    if "monograph" in text or "press" in text or "silliman" in text:
        return "monograph_or_book"
    return "non_journal_contribution"


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
                "query_id": "build_non_paper_contribution_table",
                "run_at": dt.datetime.now(dt.UTC).isoformat(),
                "phase": "validation",
                "source": "narrative candidate review table",
                "query_or_url": str(REVIEW_TABLE_CSV),
                "parameters": "analysis_eligibility=non_paper_review plus known monograph records",
                "output_path": str(out_csv),
                "status": "ok",
                "notes": f"rows={rows}",
            }
        )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build separate non-paper contribution table from narrative review rows.")
    parser.add_argument("--review-table-csv", type=Path, default=REVIEW_TABLE_CSV)
    parser.add_argument("--out-csv", type=Path, default=OUT_CSV)
    parser.add_argument("--summary-json", type=Path, default=OUT_SUMMARY)
    args = parser.parse_args()

    out_rows: list[dict[str, str]] = []
    for row in read_csv(args.review_table_csv):
        key = (row.get("validation_id", ""), row.get("candidate_title_original", ""))
        extra = EXTRA_NON_PAPER_RECORDS.get(key)
        if row.get("analysis_eligibility") != "non_paper_review" and not extra:
            continue
        title = row.get("candidate_title_original", "")
        source_or_record = row.get("matched_journal", "")
        identifier = row.get("doi", "")
        note = "Kept for comprehensive Nobel contribution coverage; excluded from top-journal main analysis unless a documented proxy-paper rule is adopted."
        ctype = contribution_type({"candidate_title": title, "matched_journal": source_or_record})
        if extra:
            ctype = extra["contribution_type"]
            source_or_record = extra["source_or_record"]
            identifier = extra["identifier"]
            note = extra["review_note"]
        out_rows.append(
            {
                "validation_id": row.get("validation_id", ""),
                "full_name": row.get("full_name", ""),
                "award_year": row.get("award_year", ""),
                "category": row.get("category", ""),
                "official_contribution_text": row.get("official_contribution_text", ""),
                "contribution_type": ctype,
                "candidate_title_or_record": title,
                "candidate_year": row.get("matched_year", "") or row.get("candidate_year_original", ""),
                "source_or_record": source_or_record,
                "identifier": identifier,
                "official_source_pages": row.get("official_source_pages", ""),
                "main_journal_analysis_status": "excluded_non_journal_contribution",
                "comprehensive_dataset_status": "documented_non_paper_contribution",
                "sensitivity_analysis_status": "proxy_paper_optional_after_rule_decision",
                "review_note": note,
            }
        )

    fields = [
        "validation_id",
        "full_name",
        "award_year",
        "category",
        "official_contribution_text",
        "contribution_type",
        "candidate_title_or_record",
        "candidate_year",
        "source_or_record",
        "identifier",
        "official_source_pages",
        "main_journal_analysis_status",
        "comprehensive_dataset_status",
        "sensitivity_analysis_status",
        "review_note",
    ]
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.out_csv.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out_rows)

    summary: dict[str, object] = {
        "non_paper_rows": len(out_rows),
        "by_contribution_type": {},
        "output": str(args.out_csv),
    }
    for row in out_rows:
        bucket = summary["by_contribution_type"]
        assert isinstance(bucket, dict)
        key = row["contribution_type"]
        bucket[key] = int(bucket.get(key, 0)) + 1

    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    append_query_log(len(out_rows), args.out_csv)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
