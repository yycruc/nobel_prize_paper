from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVIEW_TABLE_CSV = ROOT / "01_validation" / "03_matched_metadata" / "narrative_candidate_review_table_all45_doi_enriched.csv"
OUT_CSV = ROOT / "01_validation" / "03_matched_metadata" / "historical_bibliographic_verification_table_all45.csv"
OUT_SUMMARY = ROOT / "01_validation" / "04_outputs" / "historical_bibliographic_verification_summary_all45.json"
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"


VERIFIED_RECORDS = {
    (
        "V001",
        "Ueber eine neue Art von Strahlen. Vorläufige Mitteilung",
    ): {
        "canonical_title": "Ueber eine neue Art von Strahlen. Vorläufige Mitteilung",
        "canonical_year": "1895",
        "canonical_source": "Sitzungsberichte der Würzburger Physik.-medic. Gesellschaft",
        "volume_issue_pages": "1895: 132-141",
        "stable_identifier": "",
        "verification_source_1": "https://cds.cern.ch/record/262879/files/18961205.pdf",
        "verification_source_2": "https://wellcomecollection.org/works/wkdfcmvw/items",
        "verification_note": "Historical source confirms the 1895 Wuerzburg preliminary communication generally treated as Röntgen's key X-ray discovery paper.",
    },
    (
        "V017",
        "Sur une substance nouvelle radioactive, contenue dans la pechblende",
    ): {
        "canonical_title": "Sur une substance nouvelle radioactive, contenue dans la pechblende",
        "canonical_year": "1898",
        "canonical_source": "Comptes Rendus de l'Académie des Sciences",
        "volume_issue_pages": "127: 175-178",
        "stable_identifier": "",
        "verification_source_1": "https://www.academie-sciences.fr/pdf/dossiers/Curie/Curie_pdf/CR1898_p175_178.pdf",
        "verification_source_2": "https://gallica.bnf.fr/ark:/12148/bpt6k3081n/f175.item",
        "verification_note": "Original Académie des Sciences PDF verifies the 1898 polonium announcement.",
    },
    (
        "V017",
        "Sur une nouvelle substance fortement radioactive, contenue dans la pechblende",
    ): {
        "canonical_title": "Sur une nouvelle substance fortement radioactive, contenue dans la pechblende",
        "canonical_year": "1898",
        "canonical_source": "Comptes Rendus de l'Académie des Sciences",
        "volume_issue_pages": "127: 1215-1217",
        "stable_identifier": "",
        "verification_source_1": "https://www.academie-sciences.fr/pdf/dossiers/Curie/Curie_pdf/CR1898_p1215_1217.pdf",
        "verification_source_2": "https://gallica.bnf.fr/ark:/12148/bpt6k3081n/f1215.item",
        "verification_note": "Original Académie des Sciences PDF verifies the 1898 radium announcement.",
    },
    (
        "V031",
        "Über das Zustandekommen der Diphtherie-Immunität und der Tetanus-Immunität bei Thieren",
    ): {
        "canonical_title": "Über das Zustandekommen der Diphtherie-Immunität und der Tetanus-Immunität bei Thieren",
        "canonical_year": "1890",
        "canonical_source": "Deutsche Medizinische Wochenschrift",
        "volume_issue_pages": "16: 1113-1114",
        "stable_identifier": "10.1055/s-0029-1207589",
        "verification_source_1": "https://www.thieme-connect.com/products/ejournals/abstract/10.1055/s-0029-1207589",
        "verification_source_2": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5415572/",
        "verification_note": "Publisher DOI page and medical-history review identify the Behring-Kitasato immunity paper.",
    },
    (
        "V031",
        "Untersuchungen ueber das Zustandekommen der Diphtherie-Immunität bei Thieren",
    ): {
        "canonical_title": "Untersuchungen über das Zustandekommen der Diphtherie-Immunität bei Thieren",
        "canonical_year": "1890",
        "canonical_source": "Deutsche Medizinische Wochenschrift",
        "volume_issue_pages": "16: 1145-1148",
        "stable_identifier": "",
        "verification_source_1": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5415572/",
        "verification_source_2": "https://journals.asm.org/doi/10.1128/mbio.00117-17",
        "verification_note": "Medical-history sources list the follow-up diphtheria immunity article as part of the 1890 serum-therapy evidence set.",
    },
    (
        "V032",
        "Ueber Kropfexstirpation und ihre Folgen",
    ): {
        "canonical_title": "Ueber Kropfexstirpation und ihre Folgen",
        "canonical_year": "1883",
        "canonical_source": "Archiv für Klinische Chirurgie",
        "volume_issue_pages": "29: 254-337",
        "stable_identifier": "",
        "verification_source_1": "https://www.jameslindlibrary.org/kocher-t-1883/",
        "verification_source_2": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1421691/",
        "verification_note": "James Lind Library and secondary medical literature verify Kocher's 1883 thyroidectomy outcomes paper.",
    },
    (
        "V007",
        "coherent visible radiation from fast electrons passing through matter",
    ): {
        "canonical_title": "Coherent visible radiation from fast electrons passing through matter",
        "canonical_year": "1937",
        "canonical_source": "C. R. Acad. Sci. USSR",
        "volume_issue_pages": "14: 109-114",
        "stable_identifier": "https://openalex.org/W2599073804",
        "verification_source_1": "https://cds.cern.ch/record/485596",
        "verification_source_2": "https://cds.cern.ch/record/485596/export/hx",
        "verification_note": "CERN bibliographic record verifies the Frank-Tamm Cherenkov-radiation interpretation paper and supplies journal/source metadata missing from OpenAlex.",
    },
    (
        "V018",
        "method of determination of carbon and hydrogen in organic compounds",
    ): {
        "canonical_title": "Eine Methode zur Bestimmung von Kohlenstoff und Wasserstoff in organischen Verbindungen",
        "canonical_year": "1905",
        "canonical_source": "Berichte der Deutschen Chemischen Gesellschaft",
        "volume_issue_pages": "38: 1434-1444",
        "stable_identifier": "10.1002/cber.19050380236",
        "verification_source_1": "https://chemistry-europe.onlinelibrary.wiley.com/doi/10.1002/cber.19050380236",
        "verification_source_2": "https://pubs.rsc.org/en/content/articlepdf/1905/ca/ca9058805414",
        "verification_note": "Publisher DOI page and RSC abstract verify Pregl's 1905 carbon-and-hydrogen determination method paper.",
    },
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
                "query_id": "build_historical_bibliographic_verification_table",
                "run_at": dt.datetime.now(dt.UTC).isoformat(),
                "phase": "validation",
                "source": "targeted historical bibliographic sources",
                "query_or_url": str(REVIEW_TABLE_CSV),
                "parameters": "analysis_eligibility=manual_seed_review",
                "output_path": str(out_csv),
                "status": "ok",
                "notes": f"verified_rows={rows}",
            }
        )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build manually verified historical bibliography table.")
    parser.add_argument("--review-table-csv", type=Path, default=REVIEW_TABLE_CSV)
    parser.add_argument("--out-csv", type=Path, default=OUT_CSV)
    parser.add_argument("--summary-json", type=Path, default=OUT_SUMMARY)
    args = parser.parse_args()

    out_rows: list[dict[str, str]] = []
    for row in read_csv(args.review_table_csv):
        key = (row.get("validation_id", ""), row.get("candidate_title_original", ""))
        verified = VERIFIED_RECORDS.get(key)
        if not verified:
            continue
        out_rows.append(
            {
                "validation_id": row.get("validation_id", ""),
                "full_name": row.get("full_name", ""),
                "award_year": row.get("award_year", ""),
                "category": row.get("category", ""),
                "candidate_title_original": row.get("candidate_title_original", ""),
                "canonical_title": verified["canonical_title"],
                "canonical_year": verified["canonical_year"],
                "canonical_source": verified["canonical_source"],
                "volume_issue_pages": verified["volume_issue_pages"],
                "stable_identifier": verified["stable_identifier"],
                "award_lag_years": str(int(row.get("award_year", "0")) - int(verified["canonical_year"])),
                "verification_source_1": verified["verification_source_1"],
                "verification_source_2": verified["verification_source_2"],
                "verification_status": "historical_bibliography_verified",
                "metadata_match_status": "manual_historical_bibliography",
                "main_journal_analysis_status": "eligible_with_manual_source_normalization",
                "verification_note": verified["verification_note"],
                "official_contribution_text": row.get("official_contribution_text", ""),
                "official_source_pages": row.get("official_source_pages", ""),
            }
        )

    fields = [
        "validation_id",
        "full_name",
        "award_year",
        "category",
        "candidate_title_original",
        "canonical_title",
        "canonical_year",
        "canonical_source",
        "volume_issue_pages",
        "stable_identifier",
        "award_lag_years",
        "verification_source_1",
        "verification_source_2",
        "verification_status",
        "metadata_match_status",
        "main_journal_analysis_status",
        "verification_note",
        "official_contribution_text",
        "official_source_pages",
    ]
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.out_csv.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out_rows)

    summary: dict[str, object] = {
        "verified_rows": len(out_rows),
        "verified_validation_records": len({row["validation_id"] for row in out_rows}),
        "by_canonical_source": {},
        "output": str(args.out_csv),
    }
    for row in out_rows:
        bucket = summary["by_canonical_source"]
        assert isinstance(bucket, dict)
        key = row["canonical_source"]
        bucket[key] = int(bucket.get(key, 0)) + 1

    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    append_query_log(len(out_rows), args.out_csv)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
