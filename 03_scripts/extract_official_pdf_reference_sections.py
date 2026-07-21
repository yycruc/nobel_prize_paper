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
OUT_CSV = ROOT / "01_validation" / "02_candidate_key_papers" / "official_pdf_reference_section_candidates.csv"
OUT_SUMMARY = ROOT / "01_validation" / "04_outputs" / "official_pdf_reference_section_summary.json"
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"

MARKER_RE = re.compile(r"(?i)\b(references|further reading|selected literature|bibliography)\b")
REF_START_RE = re.compile(r"^\s*(?:\[\d+\]|\d+[\).])\s+")
DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s\"<>]+", re.IGNORECASE)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def normalize_line(line: str) -> str:
    line = line.replace("\u00ad", "")
    return re.sub(r"\s+", " ", line).strip()


def extract_full_text(path: str) -> str:
    reader = PdfReader(path)
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def reference_section(text: str) -> tuple[str, str]:
    matches = list(MARKER_RE.finditer(text))
    if not matches:
        return "", ""
    marker = matches[-1].group(1)
    return marker, text[matches[-1].end():]


def split_references(section: str) -> list[str]:
    lines = [normalize_line(line) for line in section.splitlines()]
    lines = [line for line in lines if line]
    refs: list[str] = []
    current: list[str] = []
    for line in lines:
        if REF_START_RE.match(line) and current:
            refs.append(normalize_line(" ".join(current)))
            current = [line]
        else:
            if not current:
                current = [line]
            else:
                current.append(line)
    if current:
        refs.append(normalize_line(" ".join(current)))

    cleaned: list[str] = []
    for ref in refs:
        ref = re.sub(r"^\s*(?:\[\d+\]|\d+[\).])\s+", "", ref).strip()
        if len(ref) < 25:
            continue
        if DOI_RE.search(ref) or re.search(r"\b(18|19|20)\d{2}\b", ref):
            cleaned.append(ref)
    return cleaned


def append_query_log(pdf_status_csv: Path, out_csv: Path, rows: int) -> None:
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
                "query_id": "extract_official_pdf_reference_sections",
                "run_at": dt.datetime.now(dt.UTC).isoformat(),
                "phase": "validation",
                "source": "Downloaded Nobel official PDFs",
                "query_or_url": str(pdf_status_csv),
                "parameters": "last References/Further reading/Selected literature/Bibliography section",
                "output_path": str(out_csv),
                "status": "ok",
                "notes": f"reference_rows={rows}",
            }
        )


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fields = [
        "reference_candidate_id",
        "validation_id",
        "laureate_id",
        "full_name",
        "award_year",
        "category",
        "pdf_type",
        "pdf_label",
        "section_marker",
        "reference_text",
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


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Extract reference section candidates from downloaded Nobel official PDFs.")
    parser.add_argument("--pdf-status-csv", type=Path, default=PDF_STATUS_CSV)
    parser.add_argument("--out-csv", type=Path, default=OUT_CSV)
    parser.add_argument("--summary-json", type=Path, default=OUT_SUMMARY)
    parser.add_argument("--progress-every", type=int, default=50)
    args = parser.parse_args()

    pdf_rows = [row for row in read_csv(args.pdf_status_csv) if row.get("fetch_status") == "ok" and row.get("local_path")]
    out_rows: list[dict[str, str]] = []
    missing_marker: list[dict[str, str]] = []
    counter = 1
    errors: list[dict[str, str]] = []
    for idx, pdf_row in enumerate(pdf_rows, start=1):
        try:
            text = extract_full_text(pdf_row["local_path"])
        except Exception as exc:
            errors.append(
                {
                    "validation_id": pdf_row.get("validation_id", ""),
                    "pdf_url": pdf_row.get("url", ""),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            if args.progress_every and idx % args.progress_every == 0:
                write_csv(args.out_csv, out_rows)
                print(f"processed {idx}/{len(pdf_rows)} pdfs; refs={len(out_rows)}; errors={len(errors)}", flush=True)
            continue
        marker, section = reference_section(text)
        if not marker:
            missing_marker.append(
                {
                    "validation_id": pdf_row["validation_id"],
                    "pdf_type": pdf_row["pdf_type"],
                    "label": pdf_row["label"],
                }
            )
            continue
        refs = split_references(section)
        for ref in refs:
            out_rows.append(
                {
                    "reference_candidate_id": f"OFFPDFREF_{counter:05d}",
                    "validation_id": pdf_row["validation_id"],
                    "laureate_id": pdf_row["laureate_id"],
                    "full_name": pdf_row["full_name"],
                    "award_year": pdf_row["award_year"],
                    "category": pdf_row["category"],
                    "pdf_type": pdf_row["pdf_type"],
                    "pdf_label": pdf_row["label"],
                    "section_marker": marker,
                    "reference_text": ref,
                    "doi": "; ".join(doi.rstrip(".,;)") for doi in DOI_RE.findall(ref)),
                    "pdf_url": pdf_row["url"],
                    "local_pdf_path": pdf_row["local_path"],
                    "notes": "Reference extracted from official Nobel PDF reference section",
                }
            )
            counter += 1
        if args.progress_every and idx % args.progress_every == 0:
            write_csv(args.out_csv, out_rows)
            print(f"processed {idx}/{len(pdf_rows)} pdfs; refs={len(out_rows)}; errors={len(errors)}", flush=True)

    write_csv(args.out_csv, out_rows)
    summary: dict[str, object] = {
        "pdfs_processed": len(pdf_rows),
        "reference_rows": len(out_rows),
        "missing_reference_marker_count": len(missing_marker),
        "missing_reference_marker": missing_marker,
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
