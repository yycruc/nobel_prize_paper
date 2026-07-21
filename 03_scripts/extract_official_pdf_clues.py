from __future__ import annotations

import csv
import datetime as dt
import argparse
import json
import re
import sys
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
PDF_STATUS_CSV = ROOT / "01_validation" / "01_raw_sources" / "nobel_official_pages" / "official_pdf_fetch_status.csv"
OUT_CSV = ROOT / "01_validation" / "02_candidate_key_papers" / "official_pdf_bibliographic_clues.csv"
OUT_SUMMARY = ROOT / "01_validation" / "04_outputs" / "official_pdf_clues_summary.json"
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"

DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s\"<>]+", re.IGNORECASE)
REFERENCE_KEYWORDS = [
    "physical review",
    "phys. rev.",
    "nature",
    "science",
    "cell",
    "journal",
    "proceedings",
    "proc.",
    "annalen",
    "berichte",
    "comptes rendus",
    "lancet",
    "new england journal",
    "j. ",
    "rev.",
    "vol.",
    "doi",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def normalize_text(text: str) -> str:
    text = text.replace("\u00ad", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def looks_reference_like(text: str) -> bool:
    lower = text.lower()
    if DOI_RE.search(text):
        return True
    if re.match(r"^\s*(\[\d+\]|\d+[\).])\s+", text) and re.search(r"\b(18|19|20)\d{2}\b", text):
        return True
    if "et al" in lower and re.search(r"\b(18|19|20)\d{2}\b", text):
        return True
    if any(keyword in lower for keyword in REFERENCE_KEYWORDS) and re.search(r"\b(18|19|20)\d{2}\b", text):
        return True
    return False


def page_chunks(page_text: str) -> list[str]:
    lines = [normalize_text(line) for line in page_text.splitlines()]
    lines = [line for line in lines if len(line) >= 20]
    chunks: list[str] = []
    for idx, line in enumerate(lines):
        chunks.append(line)
        if idx + 1 < len(lines):
            chunks.append(normalize_text(line + " " + lines[idx + 1]))
        if idx + 2 < len(lines):
            chunks.append(normalize_text(line + " " + lines[idx + 1] + " " + lines[idx + 2]))
    return chunks


def extract_pdf_rows(pdf_row: dict[str, str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    reader = PdfReader(pdf_row["local_path"])
    seen: set[tuple[int, str]] = set()
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        for chunk in page_chunks(text):
            if not looks_reference_like(chunk):
                continue
            key = (page_number, chunk)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "validation_id": pdf_row["validation_id"],
                    "laureate_id": pdf_row["laureate_id"],
                    "full_name": pdf_row["full_name"],
                    "award_year": pdf_row["award_year"],
                    "category": pdf_row["category"],
                    "pdf_type": pdf_row["pdf_type"],
                    "pdf_label": pdf_row["label"],
                    "page_number": str(page_number),
                    "clue_type": "pdf_reference_like",
                    "clue_text": chunk,
                    "doi": "; ".join(doi.rstrip(".,;)") for doi in DOI_RE.findall(chunk)),
                    "pdf_url": pdf_row["url"],
                    "local_pdf_path": pdf_row["local_path"],
                    "notes": "Reference-like text extracted from official Nobel PDF",
                }
            )
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fields = [
        "validation_id",
        "laureate_id",
        "full_name",
        "award_year",
        "category",
        "pdf_type",
        "pdf_label",
        "page_number",
        "clue_type",
        "clue_text",
        "doi",
        "pdf_url",
        "local_pdf_path",
        "notes",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def append_query_log(status_csv: Path, out_csv: Path, rows: int) -> None:
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
                "query_id": "extract_official_pdf_clues",
                "run_at": dt.datetime.now(dt.UTC).isoformat(),
                "phase": "validation",
                "source": "Downloaded Nobel official PDFs",
                "query_or_url": str(status_csv),
                "parameters": "pypdf text extraction; reference-like chunks",
                "output_path": str(out_csv),
                "status": "ok",
                "notes": f"clue_rows={rows}",
            }
        )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Extract reference-like clues from downloaded Nobel official PDFs.")
    parser.add_argument("--pdf-status-csv", type=Path, default=PDF_STATUS_CSV)
    parser.add_argument("--out-csv", type=Path, default=OUT_CSV)
    parser.add_argument("--summary-json", type=Path, default=OUT_SUMMARY)
    args = parser.parse_args()

    pdf_rows = [row for row in read_csv(args.pdf_status_csv) if row.get("fetch_status") == "ok" and row.get("local_path")]
    out_rows: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    for row in pdf_rows:
        try:
            out_rows.extend(extract_pdf_rows(row))
        except Exception as exc:
            errors.append(
                {
                    "validation_id": row.get("validation_id", ""),
                    "pdf_url": row.get("url", ""),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    write_csv(args.out_csv, out_rows)
    summary: dict[str, object] = {
        "pdfs_processed": len(pdf_rows),
        "clue_rows": len(out_rows),
        "errors": errors,
        "by_validation_id": {},
        "by_pdf_type": {},
        "output": str(args.out_csv),
    }
    for row in out_rows:
        by_id = summary["by_validation_id"]
        assert isinstance(by_id, dict)
        by_id[row["validation_id"]] = int(by_id.get(row["validation_id"], 0)) + 1
        by_type = summary["by_pdf_type"]
        assert isinstance(by_type, dict)
        by_type[row["pdf_type"]] = int(by_type.get(row["pdf_type"], 0)) + 1
    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    append_query_log(args.pdf_status_csv, args.out_csv, len(out_rows))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
