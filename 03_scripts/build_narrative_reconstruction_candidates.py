from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NARRATIVE_QUEUE_CSV = ROOT / "01_validation" / "02_candidate_key_papers" / "early_official_narrative_review_queue_all45.csv"
LI_CANDIDATES_CSV = ROOT / "01_validation" / "02_candidate_key_papers" / "key_paper_candidates_validation.csv"
MANUAL_SEEDS_CSV = ROOT / "01_validation" / "02_candidate_key_papers" / "manual_seed_candidates_no_public_dataset_all45.csv"
OUT_CSV = ROOT / "01_validation" / "02_candidate_key_papers" / "narrative_reconstruction_candidates_all45.csv"
OUT_SUMMARY = ROOT / "01_validation" / "04_outputs" / "narrative_reconstruction_candidates_summary_all45.json"
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    ascii_text = ascii_text.lower()
    ascii_text = re.sub(r"[^a-z0-9]+", " ", ascii_text)
    return re.sub(r"\s+", " ", ascii_text).strip()


def token_overlap(a: str, b: str) -> float:
    a_tokens = {tok for tok in normalize(a).split() if len(tok) >= 4}
    b_tokens = {tok for tok in normalize(b).split() if len(tok) >= 4}
    if not a_tokens or not b_tokens:
        return 0.0
    return len(a_tokens & b_tokens) / len(a_tokens)


def group_by_validation(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row.get("validation_id", ""), []).append(row)
    return grouped


def compact(value: str, max_len: int = 600) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    if len(value) <= max_len:
        return value
    return value[: max_len - 3].rstrip() + "..."


def lag(candidate_year: str, award_year: str) -> str:
    try:
        return str(int(award_year) - int(candidate_year))
    except ValueError:
        return ""


def title_query(full_name: str, title: str, year: str) -> str:
    if title:
        if year:
            return f'"{title}" "{full_name}" {year}'
        return f'"{title}" "{full_name}"'
    return ""


def append_query_log(rows: int, covered: int, out_csv: Path) -> None:
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
                "query_id": "build_narrative_reconstruction_candidates",
                "run_at": dt.datetime.now(dt.UTC).isoformat(),
                "phase": "validation",
                "source": "Nobel official narrative queue; Li et al. 2019 candidates",
                "query_or_url": f"{NARRATIVE_QUEUE_CSV}; {LI_CANDIDATES_CSV}",
                "parameters": "join narrative-only official records to supplementary public-dataset candidates",
                "output_path": str(out_csv),
                "status": "ok",
                "notes": f"candidate_rows={rows}; records_with_public_dataset_candidates={covered}",
            }
        )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build candidate reconstruction queue for official narrative-only Nobel records.")
    parser.add_argument("--narrative-queue-csv", type=Path, default=NARRATIVE_QUEUE_CSV)
    parser.add_argument("--li-candidates-csv", type=Path, default=LI_CANDIDATES_CSV)
    parser.add_argument("--manual-seeds-csv", type=Path, default=MANUAL_SEEDS_CSV)
    parser.add_argument("--out-csv", type=Path, default=OUT_CSV)
    parser.add_argument("--summary-json", type=Path, default=OUT_SUMMARY)
    args = parser.parse_args()

    queue_rows = read_csv(args.narrative_queue_csv)
    li_by_id = group_by_validation(read_csv(args.li_candidates_csv))
    manual_by_id = group_by_validation(read_csv(args.manual_seeds_csv))
    out_rows: list[dict[str, str]] = []
    counter = 1
    records_with_li = 0
    records_with_manual_seed = 0

    for queue in queue_rows:
        validation_id = queue["validation_id"]
        li_rows = li_by_id.get(validation_id, [])
        if li_rows:
            records_with_li += 1
            for li_row in li_rows:
                title = li_row.get("candidate_title", "")
                overlap = max(
                    token_overlap(title, queue.get("official_contribution_text", "")),
                    token_overlap(title, queue.get("official_evidence_snippets", "")),
                )
                out_rows.append(
                    {
                        "reconstruction_id": f"NARRREC_{counter:04d}",
                        "validation_id": validation_id,
                        "laureate_id": queue.get("laureate_id", ""),
                        "full_name": queue.get("full_name", ""),
                        "award_year": queue.get("award_year", ""),
                        "category": queue.get("category", ""),
                        "period_bucket": queue.get("period_bucket", ""),
                        "official_contribution_text": queue.get("official_contribution_text", ""),
                        "official_source_pages": queue.get("official_source_pages", ""),
                        "official_evidence_snippets": compact(queue.get("official_evidence_snippets", "")),
                        "candidate_title": title,
                        "candidate_year": li_row.get("candidate_year", ""),
                        "award_lag_years": lag(li_row.get("candidate_year", ""), queue.get("award_year", "")),
                        "candidate_journal": li_row.get("candidate_journal", ""),
                        "candidate_doi": li_row.get("candidate_doi", ""),
                        "candidate_pmid": li_row.get("candidate_pmid", ""),
                        "candidate_source": li_row.get("source_name", ""),
                        "candidate_source_detail": li_row.get("notes", ""),
                        "official_title_overlap_score": f"{overlap:.3f}",
                        "metadata_needed": "journal; doi/openalex_id/pmid where available; author verification",
                        "recommended_metadata_query": title_query(queue.get("full_name", ""), title, li_row.get("candidate_year", "")),
                        "reconstruction_status": "public_dataset_candidate_needs_official_alignment_and_metadata",
                        "review_notes": "Li 2019 is supplementary. Accept only if aligned with Nobel official contribution and bibliographic metadata is verified.",
                    }
                )
                counter += 1
        elif manual_by_id.get(validation_id):
            records_with_manual_seed += 1
            for seed in manual_by_id[validation_id]:
                title = seed.get("candidate_title", "")
                year = seed.get("candidate_year", "")
                out_rows.append(
                    {
                        "reconstruction_id": f"NARRREC_{counter:04d}",
                        "validation_id": validation_id,
                        "laureate_id": queue.get("laureate_id", ""),
                        "full_name": queue.get("full_name", ""),
                        "award_year": queue.get("award_year", ""),
                        "category": queue.get("category", ""),
                        "period_bucket": queue.get("period_bucket", ""),
                        "official_contribution_text": queue.get("official_contribution_text", ""),
                        "official_source_pages": queue.get("official_source_pages", ""),
                        "official_evidence_snippets": compact(queue.get("official_evidence_snippets", "")),
                        "candidate_title": title,
                        "candidate_year": year,
                        "award_lag_years": lag(year, queue.get("award_year", "")),
                        "candidate_journal": seed.get("candidate_journal_or_source", ""),
                        "candidate_doi": seed.get("candidate_doi_or_identifier", ""),
                        "candidate_pmid": "",
                        "candidate_source": "manual targeted bibliographic seed",
                        "candidate_source_detail": f"{seed.get('source_label', '')}; {seed.get('source_url', '')}; {seed.get('notes', '')}",
                        "official_title_overlap_score": "",
                        "metadata_needed": "manual verification of title, year, journal/source, pages, and contribution alignment",
                        "recommended_metadata_query": title_query(queue.get("full_name", ""), title, year) or queue.get("recommended_external_query", ""),
                        "reconstruction_status": seed.get("review_status", "") or "manual_seed_needs_verification",
                        "review_notes": seed.get("alignment_to_official_contribution", ""),
                    }
                )
                counter += 1
        else:
            out_rows.append(
                {
                    "reconstruction_id": f"NARRREC_{counter:04d}",
                    "validation_id": validation_id,
                    "laureate_id": queue.get("laureate_id", ""),
                    "full_name": queue.get("full_name", ""),
                    "award_year": queue.get("award_year", ""),
                    "category": queue.get("category", ""),
                    "period_bucket": queue.get("period_bucket", ""),
                    "official_contribution_text": queue.get("official_contribution_text", ""),
                    "official_source_pages": queue.get("official_source_pages", ""),
                    "official_evidence_snippets": compact(queue.get("official_evidence_snippets", "")),
                    "candidate_title": "",
                    "candidate_year": "",
                    "award_lag_years": "",
                    "candidate_journal": "",
                    "candidate_doi": "",
                    "candidate_pmid": "",
                    "candidate_source": "",
                    "candidate_source_detail": "",
                    "official_title_overlap_score": "",
                    "metadata_needed": "title; publication year; journal; doi/openalex_id/pmid where available; author verification",
                    "recommended_metadata_query": queue.get("recommended_external_query", ""),
                    "reconstruction_status": "no_public_dataset_candidate_needs_targeted_bibliographic_search",
                    "review_notes": "Use Nobel official narrative as anchor; search discipline-specific historical bibliographies, Wikidata, OpenAlex, Crossref, PubMed, and archival sources.",
                }
            )
            counter += 1

    fields = [
        "reconstruction_id",
        "validation_id",
        "laureate_id",
        "full_name",
        "award_year",
        "category",
        "period_bucket",
        "official_contribution_text",
        "official_source_pages",
        "official_evidence_snippets",
        "candidate_title",
        "candidate_year",
        "award_lag_years",
        "candidate_journal",
        "candidate_doi",
        "candidate_pmid",
        "candidate_source",
        "candidate_source_detail",
        "official_title_overlap_score",
        "metadata_needed",
        "recommended_metadata_query",
        "reconstruction_status",
        "review_notes",
    ]
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.out_csv.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out_rows)

    summary: dict[str, object] = {
        "narrative_records": len(queue_rows),
        "records_with_public_dataset_candidates": records_with_li,
        "records_with_manual_seed_candidates": records_with_manual_seed,
        "records_without_any_seed_candidates": len(queue_rows) - records_with_li - records_with_manual_seed,
        "candidate_rows": len(out_rows),
        "by_reconstruction_status": {},
        "output": str(args.out_csv),
    }
    for row in out_rows:
        bucket = summary["by_reconstruction_status"]
        assert isinstance(bucket, dict)
        status = row["reconstruction_status"]
        bucket[status] = int(bucket.get(status, 0)) + 1

    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    append_query_log(len(out_rows), records_with_li, args.out_csv)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
