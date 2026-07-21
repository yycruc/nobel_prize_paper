from __future__ import annotations

import csv
import datetime as dt
import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_CSV = ROOT / "01_validation" / "validation_sample.csv"
OUT_CSV = ROOT / "01_validation" / "01_raw_sources" / "nobel_official_pages" / "validation_official_targets.csv"
RAW_OUT = ROOT / "01_validation" / "01_raw_sources" / "nobel_api" / "nobel_laureates_probe.json"
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"

LAUREATES_API = "https://api.nobelprize.org/2.1/laureates"
CATEGORY_SLUG = {
    "Physics": "physics",
    "Chemistry": "chemistry",
    "Physiology or Medicine": "medicine",
}


def request_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "nobel-key-papers-validation/0.1"})
    with urllib.request.urlopen(req, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def read_sample() -> list[dict[str, str]]:
    with SAMPLE_CSV.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def fetch_laureates() -> dict[str, Any]:
    url = LAUREATES_API + "?" + urllib.parse.urlencode({"limit": "2000"})
    payload = request_json(url)
    RAW_OUT.parent.mkdir(parents=True, exist_ok=True)
    RAW_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def laureate_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("id") or ""): row for row in payload.get("laureates") or []}


def external_fact_url(laureate: dict[str, Any], award_year: str, category_slug: str) -> str:
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


def build_targets(sample: list[dict[str, str]], laureates: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    target_types = [
        ("summary", "summary/"),
        ("press_release", "press-release/"),
        ("popular_information", "popular-information/"),
        ("advanced_information", "advanced-information/"),
    ]
    for sample_row in sample:
        category_slug = CATEGORY_SLUG[sample_row["category"]]
        award_year = sample_row["award_year"]
        base = f"https://www.nobelprize.org/prizes/{category_slug}/{award_year}/"
        laureate = laureates.get(sample_row["laureate_id"], {})
        rows.append(
            {
                "validation_id": sample_row["validation_id"],
                "laureate_id": sample_row["laureate_id"],
                "full_name": sample_row["full_name"],
                "award_year": award_year,
                "category": sample_row["category"],
                "target_type": "facts",
                "url": external_fact_url(laureate, award_year, category_slug),
                "expected_use": "laureate biography and links",
                "fetch_status": "not_fetched",
                "notes": "",
            }
        )
        for target_type, suffix in target_types:
            rows.append(
                {
                    "validation_id": sample_row["validation_id"],
                    "laureate_id": sample_row["laureate_id"],
                    "full_name": sample_row["full_name"],
                    "award_year": award_year,
                    "category": sample_row["category"],
                    "target_type": target_type,
                    "url": base + suffix,
                    "expected_use": "official prize context and possible reference lists",
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


def append_query_log(rows: int) -> None:
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
                "query_id": "build_validation_official_targets",
                "run_at": dt.datetime.now(dt.UTC).isoformat(),
                "phase": "validation",
                "source": "Nobel Prize API and URL patterns",
                "query_or_url": LAUREATES_API,
                "parameters": "limit=2000; facts/summary/press-release/popular-information/advanced-information targets",
                "output_path": str(OUT_CSV),
                "status": "ok",
                "notes": f"target_rows={rows}",
            }
        )


def main() -> None:
    sample = read_sample()
    payload = fetch_laureates()
    rows = build_targets(sample, laureate_index(payload))
    write_csv(OUT_CSV, rows)
    append_query_log(len(rows))
    print(json.dumps({"target_rows": len(rows), "output": str(OUT_CSV)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

