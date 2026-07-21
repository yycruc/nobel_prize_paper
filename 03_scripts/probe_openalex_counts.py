from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "01_validation" / "04_outputs" / "openalex_counts_probe.json"
OUT_CSV = ROOT / "01_validation" / "04_outputs" / "openalex_counts_probe.csv"
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"

OPENALEX_WORKS = "https://api.openalex.org/works"


def request_json(url: str, retries: int = 5) -> dict[str, Any]:
    api_key = os.environ.get("OPENALEX_API_KEY", "")
    if api_key:
        sep = "&" if "?" in url else "?"
        url = url + sep + urllib.parse.urlencode({"api_key": api_key})
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "nobel-key-papers-validation/0.1"},
    )
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=90) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code in {429, 500, 502, 503, 504}:
                retry_after = exc.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else min(60, 2**attempt)
                time.sleep(delay)
                continue
            raise
    if last_error:
        raise last_error
    raise RuntimeError("OpenAlex request failed")


def append_query_log(url: str, status: str, notes: str) -> None:
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
                "query_id": "openalex_counts_probe",
                "run_at": dt.datetime.now(dt.UTC).isoformat(),
                "phase": "validation",
                "source": "OpenAlex",
                "query_or_url": url,
                "parameters": "",
                "output_path": str(OUT_CSV),
                "status": status,
                "notes": notes,
            }
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe OpenAlex country-journal-year counts for one source.")
    parser.add_argument("--source-id", default="S137773608", help="OpenAlex source id, default Nature")
    parser.add_argument("--country", default="US", help="OpenAlex country code")
    parser.add_argument("--from-year", type=int, default=1880)
    parser.add_argument("--to-year", type=int, default=1885)
    args = parser.parse_args()

    filters = ",".join(
        [
            f"primary_location.source.id:{args.source_id}",
            f"authorships.countries:{args.country}",
            f"from_publication_date:{args.from_year}-01-01",
            f"to_publication_date:{args.to_year}-12-31",
        ]
    )
    params = {
        "filter": filters,
        "group_by": "publication_year",
        "per-page": "200",
    }
    url = OPENALEX_WORKS + "?" + urllib.parse.urlencode(params)
    payload = request_json(url)

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    rows: list[dict[str, Any]] = []
    counts = {str(item.get("key")): int(item.get("count") or 0) for item in payload.get("group_by") or []}
    for year in range(args.from_year, args.to_year + 1):
        rows.append(
            {
                "source_id": args.source_id,
                "country": args.country,
                "year": year,
                "publication_count": counts.get(str(year), 0),
            }
        )

    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["source_id", "country", "year", "publication_count"])
        writer.writeheader()
        writer.writerows(rows)

    append_query_log(url, "ok", f"rows={len(rows)}")
    print(json.dumps({"rows": len(rows), "output": str(OUT_CSV), "raw": str(OUT_JSON)}, indent=2))


if __name__ == "__main__":
    main()

