from __future__ import annotations

import csv
import datetime as dt
import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_CSV = ROOT / "01_validation" / "validation_sample.csv"
PAGE_CLUES_CSV = ROOT / "01_validation" / "02_candidate_key_papers" / "official_page_bibliographic_clues.csv"
SECONDARY_CLUES_CSV = ROOT / "01_validation" / "02_candidate_key_papers" / "official_secondary_page_bibliographic_clues.csv"
PDF_CLUES_CSV = ROOT / "01_validation" / "02_candidate_key_papers" / "official_pdf_bibliographic_clues.csv"
PDF_REFS_CSV = ROOT / "01_validation" / "02_candidate_key_papers" / "official_pdf_reference_section_candidates.csv"
OUT_CSV = ROOT / "01_validation" / "02_candidate_key_papers" / "early_official_narrative_review_queue.csv"
OUT_SUMMARY = ROOT / "01_validation" / "04_outputs" / "early_official_narrative_review_queue_summary.json"
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def compact(value: str, max_len: int = 420) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) <= max_len:
        return value
    return value[: max_len - 3].rstrip() + "..."


def group_clues(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row.get("validation_id", ""), []).append(row)
    return grouped


def source_pages(rows: list[dict[str, str]]) -> str:
    pages = []
    seen = set()
    for row in rows:
        page = row.get("source_page") or row.get("pdf_url") or row.get("local_pdf_path") or ""
        if page and page not in seen:
            pages.append(page)
            seen.add(page)
    return "; ".join(pages[:5])


def evidence_snippets(rows: list[dict[str, str]]) -> str:
    snippets = []
    for row in rows:
        clue = row.get("clue_text") or row.get("reference_text") or ""
        if clue and row.get("clue_type", "reference_like") == "reference_like":
            snippets.append(compact(clue))
        if len(snippets) >= 3:
            break
    return " || ".join(snippets)


def recommended_query(sample: dict[str, str]) -> str:
    name = sample["full_name"]
    motivation = sample.get("notes", "")
    year = int(sample["award_year"])
    lower = motivation.casefold()
    if "x-ray" in lower or "rays" in lower or "röntgen" in name.casefold():
        topic = "X-rays discovery"
    elif "wireless telegraphy" in lower:
        topic = "wireless telegraphy"
    elif "osmotic pressure" in lower or "chemical dynamics" in lower:
        topic = "osmotic pressure chemical dynamics"
    elif "radium" in lower or "polonium" in lower:
        topic = "radium polonium"
    elif "serum" in lower or "diphtheria" in lower:
        topic = "diphtheria serum therapy"
    elif "neuron" in lower or "nervous" in lower:
        topic = "function of neurons nervous system"
    else:
        topic = motivation
    return f'"{name}" "{topic}" publication OR paper {max(1800, year - 40)}-{year}'


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
                "query_id": "build_early_official_review_queue",
                "run_at": dt.datetime.now(dt.UTC).isoformat(),
                "phase": "validation",
                "source": "Nobel official pages and extracted clues",
                "query_or_url": str(sample_csv),
                "parameters": "validation records with no structured official PDF references",
                "output_path": str(out_csv),
                "status": "ok",
                "notes": f"rows={rows}",
            }
        )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build review queue for official narrative-only validation records.")
    parser.add_argument("--sample-csv", type=Path, default=SAMPLE_CSV)
    parser.add_argument("--page-clues-csv", type=Path, default=PAGE_CLUES_CSV)
    parser.add_argument("--secondary-clues-csv", type=Path, default=SECONDARY_CLUES_CSV)
    parser.add_argument("--pdf-clues-csv", type=Path, default=PDF_CLUES_CSV)
    parser.add_argument("--pdf-refs-csv", type=Path, default=PDF_REFS_CSV)
    parser.add_argument("--out-csv", type=Path, default=OUT_CSV)
    parser.add_argument("--summary-json", type=Path, default=OUT_SUMMARY)
    args = parser.parse_args()

    sample_rows = read_csv(args.sample_csv)
    page_clues = group_clues(read_csv(args.page_clues_csv))
    secondary_clues = group_clues(read_csv(args.secondary_clues_csv))
    pdf_clues = group_clues(read_csv(args.pdf_clues_csv))
    structured_ref_ids = {row["validation_id"] for row in read_csv(args.pdf_refs_csv) if row.get("reference_text")}

    out_rows: list[dict[str, str]] = []
    for sample in sample_rows:
        validation_id = sample["validation_id"]
        if validation_id in structured_ref_ids:
            continue
        all_clues = page_clues.get(validation_id, []) + secondary_clues.get(validation_id, []) + pdf_clues.get(validation_id, [])
        if not all_clues:
            continue
        clue_types = sorted(set(row.get("target_type") or row.get("pdf_type") or "" for row in all_clues if row.get("target_type") or row.get("pdf_type")))
        out_rows.append(
            {
                "validation_id": validation_id,
                "laureate_id": sample["laureate_id"],
                "full_name": sample["full_name"],
                "award_year": sample["award_year"],
                "category": sample["category"],
                "period_bucket": sample["period_bucket"],
                "official_contribution_text": sample.get("notes", ""),
                "official_evidence_level": "narrative_only_no_structured_reference_section",
                "official_clue_types": "; ".join(clue_types),
                "official_source_pages": source_pages(all_clues),
                "official_evidence_snippets": evidence_snippets(all_clues),
                "external_metadata_needed": "yes",
                "recommended_external_query": recommended_query(sample),
                "review_action": "Use Nobel official narrative to define contribution, then identify publication metadata in OpenAlex/Crossref/PubMed/Wikidata or discipline archives.",
                "review_status": "needs_manual_bibliographic_review",
            }
        )

    fields = [
        "validation_id",
        "laureate_id",
        "full_name",
        "award_year",
        "category",
        "period_bucket",
        "official_contribution_text",
        "official_evidence_level",
        "official_clue_types",
        "official_source_pages",
        "official_evidence_snippets",
        "external_metadata_needed",
        "recommended_external_query",
        "review_action",
        "review_status",
    ]
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.out_csv.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out_rows)

    summary = {
        "queue_rows": len(out_rows),
        "validation_ids": [row["validation_id"] for row in out_rows],
        "output": str(args.out_csv),
    }
    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    append_query_log(args.sample_csv, args.out_csv, len(out_rows))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
