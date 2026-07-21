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
BASELINE_CSV = ROOT / "02_full_collection" / "01_raw_sources" / "nobel_api" / "nobel_award_baseline_full.csv"
RAW_LAUREATES_OUT = ROOT / "02_full_collection" / "01_raw_sources" / "nobel_api" / "nobel_laureates_full.json"
OUT_CSV = ROOT / "02_full_collection" / "01_raw_sources" / "nobel_official_pages" / "official_targets_full.csv"
SUMMARY_JSON = ROOT / "02_full_collection" / "05_outputs" / "official_targets_full_summary.json"
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"

LAUREATES_API = "https://api.nobelprize.org/2.1/laureates"
CATEGORY_SLUG = {
    "Physics": "physics",
    "Chemistry": "chemistry",
    "Physiology or Medicine": "medicine",
}


def request_json(url: str, timeout: float) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "nobel-key-papers-full-collection/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def text_en(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("en") or "")
    return ""


def laureate_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("id") or ""): row for row in payload.get("laureates") or []}


def fact_url(laureate: dict[str, Any], award_year: str, category_slug: str) -> str:
    for prize in laureate.get("nobelPrizes") or []:
        if str(prize.get("awardYear") or "") != award_year:
            continue
        for link in prize.get("links") or []:
            href = str(link.get("href") or "")
            classes = " ".join(link.get("class") or [])
            if "facts" in classes and category_slug in href:
                return href
    file_name = str(laureate.get("fileName") or "")
    if file_name:
        return f"https://www.nobelprize.org/prizes/{category_slug}/{award_year}/{file_name}/facts/"
    return ""


def target_rows(baseline_rows: list[dict[str, str]], laureates: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    target_types = [
        ("summary", "summary/", "official prize summary"),
        ("press_release", "press-release/", "official prize announcement"),
        ("popular_information", "popular-information/", "official popular background"),
        ("advanced_information", "advanced-information/", "official scientific background"),
    ]
    for base_row in baseline_rows:
        category_slug = CATEGORY_SLUG[base_row["category"]]
        award_year = base_row["award_year"]
        base = f"https://www.nobelprize.org/prizes/{category_slug}/{award_year}/"
        laureate = laureates.get(base_row["laureate_id"], {})
        common = {
            "validation_id": base_row["validation_id"],
            "laureate_id": base_row["laureate_id"],
            "full_name": base_row["full_name"],
            "award_year": award_year,
            "category": base_row["category"],
        }
        rows.append(
            {
                **common,
                "target_type": "facts",
                "url": fact_url(laureate, award_year, category_slug),
                "expected_use": "official laureate facts page and official links",
                "fetch_status": "not_fetched",
                "notes": "",
            }
        )
        for target_type, suffix, expected_use in target_types:
            rows.append(
                {
                    **common,
                    "target_type": target_type,
                    "url": base + suffix,
                    "expected_use": expected_use,
                    "fetch_status": "not_fetched",
                    "notes": "",
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


def append_query_log(rows: int, out_csv: Path, url: str) -> None:
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
                "query_id": "build_full_official_targets",
                "run_at": dt.datetime.now(dt.UTC).isoformat(),
                "phase": "full_collection",
                "source": "Nobel Prize API and official URL patterns",
                "query_or_url": url,
                "parameters": "facts/summary/press-release/popular-information/advanced-information targets",
                "output_path": str(out_csv),
                "status": "ok",
                "notes": f"target_rows={rows}",
            }
        )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build full Nobel official page target list.")
    parser.add_argument("--baseline-csv", type=Path, default=BASELINE_CSV)
    parser.add_argument("--limit", default="2000")
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--raw-laureates-out", type=Path, default=RAW_LAUREATES_OUT)
    parser.add_argument("--out-csv", type=Path, default=OUT_CSV)
    parser.add_argument("--summary-json", type=Path, default=SUMMARY_JSON)
    args = parser.parse_args()

    url = f"{LAUREATES_API}?{urllib.parse.urlencode({'limit': args.limit})}"
    payload = request_json(url, timeout=args.timeout)
    args.raw_laureates_out.parent.mkdir(parents=True, exist_ok=True)
    args.raw_laureates_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    baseline_rows = read_csv(args.baseline_csv)
    rows = target_rows(baseline_rows, laureate_index(payload))
    write_csv(args.out_csv, rows)

    summary: dict[str, object] = {
        "baseline_rows": len(baseline_rows),
        "target_rows": len(rows),
        "empty_url_rows": sum(1 for row in rows if not row["url"]),
        "by_target_type": {},
        "output": str(args.out_csv),
    }
    for row in rows:
        bucket = summary["by_target_type"]
        assert isinstance(bucket, dict)
        bucket[row["target_type"]] = int(bucket.get(row["target_type"], 0)) + 1
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    append_query_log(len(rows), args.out_csv, url)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
