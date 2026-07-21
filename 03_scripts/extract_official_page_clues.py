from __future__ import annotations

import csv
import datetime as dt
import argparse
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin


ROOT = Path(__file__).resolve().parents[1]
STATUS_CSV = ROOT / "01_validation" / "01_raw_sources" / "nobel_official_pages" / "official_page_fetch_status.csv"
OUT_CSV = ROOT / "01_validation" / "02_candidate_key_papers" / "official_page_bibliographic_clues.csv"
OUT_SUMMARY = ROOT / "01_validation" / "04_outputs" / "official_page_clues_summary.json"
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"

DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s\"<>]+", re.IGNORECASE)
LINK_RE = re.compile(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)
BLOCK_RE = re.compile(r"<(?:p|li|td|h[1-6])\b[^>]*>(.*?)</(?:p|li|td|h[1-6])>", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
REFERENCE_KEYWORDS = [
    "doi",
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
    "nejm",
    "new england journal",
    "vol.",
    "volume",
    "pp.",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def clean_html(fragment: str) -> str:
    text = re.sub(r"<br\s*/?>", " ", fragment, flags=re.IGNORECASE)
    text = TAG_RE.sub(" ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


def looks_reference_like(text: str) -> bool:
    lower = text.lower()
    if DOI_RE.search(text):
        return True
    if any(keyword in lower for keyword in REFERENCE_KEYWORDS) and re.search(r"\b(18|19|20)\d{2}\b", text):
        return True
    if re.search(r"\bet al\.?\b", lower) and re.search(r"\b(18|19|20)\d{2}\b", text):
        return True
    if re.search(r"\bvol\.?\s*\d+", lower) and re.search(r"\b(18|19|20)\d{2}\b", text):
        return True
    return False


def extract_rows(status_row: dict[str, str]) -> list[dict[str, str]]:
    text = read_text(status_row["local_path"])
    base_url = status_row["final_url"] or status_row["url"]
    rows: list[dict[str, str]] = []

    for href, label_html in LINK_RE.findall(text):
        label = clean_html(label_html)
        full_href = urljoin(base_url, html.unescape(href))
        if ".pdf" in full_href.lower():
            rows.append(
                {
                    "validation_id": status_row["validation_id"],
                    "laureate_id": status_row["laureate_id"],
                    "full_name": status_row["full_name"],
                    "award_year": status_row["award_year"],
                    "category": status_row["category"],
                    "target_type": status_row["target_type"],
                    "clue_type": "pdf_link",
                    "clue_text": label,
                    "href": full_href,
                    "source_page": status_row["url"],
                    "local_page_path": status_row["local_path"],
                    "notes": "Official Nobel PDF link",
                }
            )

    seen_texts: set[str] = set()
    for block_html in BLOCK_RE.findall(text):
        block_text = clean_html(block_html)
        if not block_text or len(block_text) < 30:
            continue
        if block_text in seen_texts:
            continue
        seen_texts.add(block_text)
        for doi in DOI_RE.findall(block_text):
            rows.append(
                {
                    "validation_id": status_row["validation_id"],
                    "laureate_id": status_row["laureate_id"],
                    "full_name": status_row["full_name"],
                    "award_year": status_row["award_year"],
                    "category": status_row["category"],
                    "target_type": status_row["target_type"],
                    "clue_type": "doi",
                    "clue_text": doi.rstrip(".,;)"),
                    "href": "",
                    "source_page": status_row["url"],
                    "local_page_path": status_row["local_path"],
                    "notes": "DOI found in official Nobel page HTML",
                }
            )
        if looks_reference_like(block_text):
            rows.append(
                {
                    "validation_id": status_row["validation_id"],
                    "laureate_id": status_row["laureate_id"],
                    "full_name": status_row["full_name"],
                    "award_year": status_row["award_year"],
                    "category": status_row["category"],
                    "target_type": status_row["target_type"],
                    "clue_type": "reference_like",
                    "clue_text": block_text,
                    "href": "",
                    "source_page": status_row["url"],
                    "local_page_path": status_row["local_path"],
                    "notes": "Reference-like text found in official Nobel page HTML",
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
        "target_type",
        "clue_type",
        "clue_text",
        "href",
        "source_page",
        "local_page_path",
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
                "query_id": "extract_official_page_clues",
                "run_at": dt.datetime.now(dt.UTC).isoformat(),
                "phase": "validation",
                "source": "Fetched Nobel official HTML pages",
                "query_or_url": str(status_csv),
                "parameters": "HTTP 200 pages only; pdf links, DOI, reference-like text",
                "output_path": str(out_csv),
                "status": "ok",
                "notes": f"clue_rows={rows}",
            }
        )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Extract bibliographic clues from fetched Nobel official HTML pages.")
    parser.add_argument("--status-csv", type=Path, default=STATUS_CSV)
    parser.add_argument("--out-csv", type=Path, default=OUT_CSV)
    parser.add_argument("--summary-json", type=Path, default=OUT_SUMMARY)
    parser.add_argument("--progress-every", type=int, default=100)
    args = parser.parse_args()

    status_rows = [
        row for row in read_csv(args.status_csv)
        if row.get("fetch_status") == "ok" and row.get("local_path")
    ]
    clue_rows: list[dict[str, str]] = []
    for idx, row in enumerate(status_rows, start=1):
        clue_rows.extend(extract_rows(row))
        if args.progress_every and idx % args.progress_every == 0:
            write_csv(args.out_csv, clue_rows)
            print(f"processed {idx}/{len(status_rows)} html pages; clues={len(clue_rows)}", flush=True)

    write_csv(args.out_csv, clue_rows)
    summary: dict[str, object] = {
        "html_pages_processed": len(status_rows),
        "clue_rows": len(clue_rows),
        "by_clue_type": {},
        "by_validation_id": {},
        "output": str(args.out_csv),
    }
    for row in clue_rows:
        by_type = summary["by_clue_type"]
        assert isinstance(by_type, dict)
        by_type[row["clue_type"]] = int(by_type.get(row["clue_type"], 0)) + 1
        by_id = summary["by_validation_id"]
        assert isinstance(by_id, dict)
        by_id[row["validation_id"]] = int(by_id.get(row["validation_id"], 0)) + 1
    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    append_query_log(args.status_csv, args.out_csv, len(clue_rows))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
