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
OUT_CSV = ROOT / "01_validation" / "01_raw_sources" / "nobel_official_pages" / "validation_official_secondary_targets.csv"
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"

LINK_RE = re.compile(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)
OPTION_RE = re.compile(r"<option\b[^>]*value=[\"']([^\"']+)[\"'][^>]*>(.*?)</option>", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
TARGET_LABELS = {
    "nobel prize lecture": "lecture",
    "lecture": "lecture",
    "biographical": "biographical",
    "article": "article",
    "other resources": "other_resources",
    "perspectives": "perspectives",
    "speed read": "speedread",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def clean_html(fragment: str) -> str:
    text = TAG_RE.sub(" ", fragment)
    text = html.unescape(text)
    text = re.sub(r"^\s*--\s*", "", text)
    return re.sub(r"\s+", " ", text).strip()


def classify(label: str) -> str:
    lower = label.lower().strip()
    for needle, target_type in TARGET_LABELS.items():
        if needle == lower or needle in lower:
            return target_type
    return ""


def extract_targets(status_row: dict[str, str]) -> list[dict[str, str]]:
    page = Path(status_row["local_path"]).read_text(encoding="utf-8", errors="replace")
    base_url = status_row["final_url"] or status_row["url"]
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for href, label_html in LINK_RE.findall(page) + OPTION_RE.findall(page):
        label = clean_html(label_html)
        target_type = classify(label)
        if not target_type:
            continue
        url = urljoin(base_url, html.unescape(href))
        key = (target_type, url)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "validation_id": status_row["validation_id"],
                "laureate_id": status_row["laureate_id"],
                "full_name": status_row["full_name"],
                "award_year": status_row["award_year"],
                "category": status_row["category"],
                "target_type": f"secondary_{target_type}",
                "url": url,
                "expected_use": "secondary Nobel official page linked from facts page",
                "fetch_status": "not_fetched",
                "notes": f"link label={label}",
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
        "url",
        "expected_use",
        "fetch_status",
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
                "query_id": "extract_official_secondary_targets",
                "run_at": dt.datetime.now(dt.UTC).isoformat(),
                "phase": "validation",
                "source": "Nobel official facts pages",
                "query_or_url": str(status_csv),
                "parameters": "extract lecture, biographical, article, other resources, perspectives, speed read",
                "output_path": str(out_csv),
                "status": "ok",
                "notes": f"target_rows={rows}",
            }
        )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Extract secondary Nobel official target URLs from fetched facts pages.")
    parser.add_argument("--status-csv", type=Path, default=STATUS_CSV)
    parser.add_argument("--out-csv", type=Path, default=OUT_CSV)
    parser.add_argument("--progress-every", type=int, default=50)
    args = parser.parse_args()

    status_rows = [
        row for row in read_csv(args.status_csv)
        if row.get("fetch_status") == "ok" and row.get("target_type") == "facts" and row.get("local_path")
    ]
    out_rows: list[dict[str, str]] = []
    for idx, row in enumerate(status_rows, start=1):
        out_rows.extend(extract_targets(row))
        if args.progress_every and idx % args.progress_every == 0:
            write_csv(args.out_csv, out_rows)
            print(f"processed {idx}/{len(status_rows)} facts pages; targets={len(out_rows)}", flush=True)
    write_csv(args.out_csv, out_rows)
    append_query_log(args.status_csv, args.out_csv, len(out_rows))
    summary = {
        "facts_pages_processed": len(status_rows),
        "secondary_target_rows": len(out_rows),
        "output": str(args.out_csv),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
