from __future__ import annotations

import csv
import datetime as dt
import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RAW_OUT = ROOT / "01_validation" / "01_raw_sources" / "nobel_api" / "nobel_api_probe.json"
CSV_OUT = ROOT / "01_validation" / "04_outputs" / "nobel_award_baseline_probe.csv"
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"

NOBEL_API = "https://api.nobelprize.org/2.1/nobelPrizes"
NATURAL_SCIENCE_CATEGORIES = {
    "Physics",
    "Chemistry",
    "Physiology or Medicine",
}


def request_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "nobel-key-papers-validation/0.1"},
    )
    with urllib.request.urlopen(req, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def text_en(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("en") or "")
    return ""


def laureate_rows(payload: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for prize in payload.get("nobelPrizes") or []:
        category = text_en(prize.get("category"))
        if category not in NATURAL_SCIENCE_CATEGORIES:
            continue
        award_year = str(prize.get("awardYear") or "")
        for laureate in prize.get("laureates") or []:
            rows.append(
                {
                    "laureate_id": str(laureate.get("id") or ""),
                    "full_name": text_en(laureate.get("fullName")) or text_en(laureate.get("knownName")),
                    "award_year": award_year,
                    "category": category,
                    "motivation": text_en(laureate.get("motivation")),
                    "prize_share": str(laureate.get("portion") or ""),
                    "nobel_url": next(
                        (
                            link.get("href", "")
                            for link in laureate.get("links") or []
                            if link.get("rel") == "laureate"
                        ),
                        "",
                    ),
                }
            )
    rows.sort(key=lambda r: (int(r["award_year"]), r["category"], r["laureate_id"]))
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "laureate_id",
        "full_name",
        "award_year",
        "category",
        "motivation",
        "prize_share",
        "nobel_url",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def append_query_log(url: str, rows: int, status: str) -> None:
    QUERY_LOG.parent.mkdir(parents=True, exist_ok=True)
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
                "query_id": "nobel_api_probe",
                "run_at": dt.datetime.now(dt.UTC).isoformat(),
                "phase": "validation",
                "source": "Nobel Prize API",
                "query_or_url": url,
                "parameters": "limit=2000",
                "output_path": str(CSV_OUT),
                "status": status,
                "notes": f"natural_science_laureate_award_rows={rows}",
            }
        )


def main() -> None:
    params = urllib.parse.urlencode({"limit": "2000"})
    url = f"{NOBEL_API}?{params}"
    payload = request_json(url)
    RAW_OUT.parent.mkdir(parents=True, exist_ok=True)
    RAW_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = laureate_rows(payload)
    write_csv(CSV_OUT, rows)
    append_query_log(url, len(rows), "ok")

    by_category: dict[str, int] = {}
    for row in rows:
        by_category[row["category"]] = by_category.get(row["category"], 0) + 1
    print(
        json.dumps(
            {
                "rows": len(rows),
                "by_category": by_category,
                "output": str(CSV_OUT),
                "raw": str(RAW_OUT),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

