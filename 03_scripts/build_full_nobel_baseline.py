from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RAW_OUT = ROOT / "02_full_collection" / "01_raw_sources" / "nobel_api" / "nobel_prizes_full.json"
CSV_OUT = ROOT / "02_full_collection" / "01_raw_sources" / "nobel_api" / "nobel_award_baseline_full.csv"
SUMMARY_JSON = ROOT / "02_full_collection" / "05_outputs" / "nobel_award_baseline_full_summary.json"
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"

NOBEL_API = "https://api.nobelprize.org/2.1/nobelPrizes"
NATURAL_SCIENCE_CATEGORIES = {
    "Physics",
    "Chemistry",
    "Physiology or Medicine",
}


def request_json(url: str, timeout: float) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "nobel-key-papers-full-collection/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def text_en(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("en") or "")
    return ""


def link_href(links: list[dict[str, Any]], rel: str) -> str:
    return next((str(link.get("href") or "") for link in links if link.get("rel") == rel), "")


def rows_from_payload(payload: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    counter = 1
    for prize in payload.get("nobelPrizes") or []:
        category = text_en(prize.get("category"))
        if category not in NATURAL_SCIENCE_CATEGORIES:
            continue
        award_year = str(prize.get("awardYear") or "")
        for laureate in prize.get("laureates") or []:
            affiliations = laureate.get("affiliations") or []
            affiliation = affiliations[0] if affiliations else {}
            row = {
                "validation_id": f"FULL{counter:06d}",
                "laureate_id": str(laureate.get("id") or ""),
                "full_name": text_en(laureate.get("fullName")) or text_en(laureate.get("knownName")),
                "award_year": award_year,
                "category": category,
                "motivation": text_en(laureate.get("motivation")),
                "prize_share": str(laureate.get("portion") or ""),
                "sort_order": str(laureate.get("sortOrder") or ""),
                "affiliation_name": text_en(affiliation.get("name")),
                "affiliation_city": text_en(affiliation.get("city")),
                "affiliation_country": text_en(affiliation.get("country")),
                "nobel_url": link_href(laureate.get("links") or [], "laureate"),
            }
            rows.append(row)
            counter += 1
    rows.sort(key=lambda item: (int(item["award_year"]), item["category"], item["laureate_id"]))
    for idx, row in enumerate(rows, start=1):
        row["validation_id"] = f"FULL{idx:06d}"
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fields = [
        "validation_id",
        "laureate_id",
        "full_name",
        "award_year",
        "category",
        "motivation",
        "prize_share",
        "sort_order",
        "affiliation_name",
        "affiliation_city",
        "affiliation_country",
        "nobel_url",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def append_query_log(url: str, out_csv: Path, rows: int, status: str) -> None:
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
                "query_id": "build_full_nobel_baseline",
                "run_at": dt.datetime.now(dt.UTC).isoformat(),
                "phase": "full_collection",
                "source": "Nobel Prize API",
                "query_or_url": url,
                "parameters": "limit=2000; natural science categories only",
                "output_path": str(out_csv),
                "status": status,
                "notes": f"natural_science_laureate_award_rows={rows}",
            }
        )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build full Nobel natural-science laureate-award baseline.")
    parser.add_argument("--limit", default="2000")
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--raw-out", type=Path, default=RAW_OUT)
    parser.add_argument("--csv-out", type=Path, default=CSV_OUT)
    parser.add_argument("--summary-json", type=Path, default=SUMMARY_JSON)
    args = parser.parse_args()

    url = f"{NOBEL_API}?{urllib.parse.urlencode({'limit': args.limit})}"
    payload = request_json(url, timeout=args.timeout)
    args.raw_out.parent.mkdir(parents=True, exist_ok=True)
    args.raw_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = rows_from_payload(payload)
    write_csv(args.csv_out, rows)

    by_category: dict[str, int] = {}
    by_award_year: dict[str, int] = {}
    for row in rows:
        by_category[row["category"]] = by_category.get(row["category"], 0) + 1
        by_award_year[row["award_year"]] = by_award_year.get(row["award_year"], 0) + 1

    summary = {
        "rows": len(rows),
        "by_category": by_category,
        "min_award_year": min(by_award_year) if by_award_year else "",
        "max_award_year": max(by_award_year) if by_award_year else "",
        "output": str(args.csv_out),
        "raw": str(args.raw_out),
    }
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    append_query_log(url, args.csv_out, len(rows), "ok")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
