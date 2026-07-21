from __future__ import annotations

import csv
import datetime as dt
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_CSV = ROOT / "02_full_collection" / "06_analysis" / "analysis_ready_key_papers_full.csv"
RAW_DIR = ROOT / "02_full_collection" / "01_raw_sources" / "openalex_work_counts"
OUT_DIR = ROOT / "02_full_collection" / "06_analysis"
ANNUAL_CSV = RAW_DIR / "openalex_global_work_counts_by_year_1880_2022.csv"
METADATA_JSON = RAW_DIR / "openalex_global_work_counts_by_year_1880_2022_metadata.json"
SUMMARY_CSV = OUT_DIR / "nobel_key_paper_share_of_openalex_by_publication_decade.csv"
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"

OPENALEX_WORKS = "https://api.openalex.org/works"
START_YEAR = 1880
END_YEAR = 2022


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def paper_key(row: dict[str, str]) -> str:
    for field in ("openalex_work_id", "doi"):
        value = (row.get(field) or "").strip().lower()
        if value:
            return f"{field}:{value}"
    title = " ".join((row.get("title") or "").lower().split())
    year = (row.get("publication_year") or "").strip()
    return f"title_year:{title}|{year}"


def public_url(work_type: str | None) -> str:
    filters = [
        f"from_publication_date:{START_YEAR}-01-01",
        f"to_publication_date:{END_YEAR}-12-31",
    ]
    if work_type:
        filters.append(f"type:{work_type}")
    params = {
        "filter": ",".join(filters),
        "group_by": "publication_year",
        "per-page": "200",
    }
    return OPENALEX_WORKS + "?" + urllib.parse.urlencode(params)


def request_json(url: str, retries: int = 5) -> dict[str, Any]:
    api_key = os.environ.get("OPENALEX_API_KEY", "")
    request_url = url
    if api_key:
        request_url += "&" + urllib.parse.urlencode({"api_key": api_key})
    req = urllib.request.Request(
        request_url,
        headers={"User-Agent": "nobel-key-papers-analysis/0.3 (global work counts)"},
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
        except urllib.error.URLError as exc:
            last_error = exc
            time.sleep(min(60, 2**attempt))
    if last_error:
        raise last_error
    raise RuntimeError("OpenAlex request failed")


def counts_by_year(payload: dict[str, Any]) -> dict[int, int]:
    return {
        int(item["key"]): int(item["count"])
        for item in payload.get("group_by") or []
        if str(item.get("key", "")).isdigit()
    }


def append_query_log(url: str, output_path: Path, notes: str) -> None:
    if not QUERY_LOG.exists():
        return
    fieldnames = ["query_id", "run_at", "phase", "source", "query_or_url", "parameters", "output_path", "status", "notes"]
    with QUERY_LOG.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writerow(
            {
                "query_id": "openalex_global_work_counts_by_year",
                "run_at": dt.datetime.now(dt.UTC).isoformat(),
                "phase": "analysis_extension",
                "source": "OpenAlex Works API",
                "query_or_url": url,
                "parameters": f"publication years {START_YEAR}-{END_YEAR}; group_by=publication_year",
                "output_path": str(output_path),
                "status": "ok",
                "notes": notes,
            }
        )


def run() -> dict[str, Any]:
    rows = read_csv(ANALYSIS_CSV)
    unique_papers: dict[str, dict[str, str]] = {}
    for row in rows:
        unique_papers.setdefault(paper_key(row), row)

    article_key_counts: Counter[int] = Counter()
    all_key_counts: Counter[int] = Counter()
    for row in unique_papers.values():
        year_text = (row.get("publication_year") or "").strip()
        if not year_text:
            continue
        year = int(float(year_text))
        if not START_YEAR <= year <= END_YEAR:
            continue
        decade_start = year // 10 * 10
        all_key_counts[decade_start] += 1
        if (row.get("work_type") or "").strip().lower() == "article":
            article_key_counts[decade_start] += 1

    article_url = public_url("article")
    all_works_url = public_url(None)
    article_payload = request_json(article_url)
    all_works_payload = request_json(all_works_url)
    article_counts = counts_by_year(article_payload)
    all_works_counts = counts_by_year(all_works_payload)
    retrieved_at = dt.datetime.now(dt.UTC).isoformat()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with ANNUAL_CSV.open("w", encoding="utf-8-sig", newline="") as fh:
        fieldnames = [
            "year",
            "openalex_article_count",
            "openalex_all_works_count",
            "article_query_url",
            "all_works_query_url",
            "retrieved_at_utc",
        ]
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for year in range(START_YEAR, END_YEAR + 1):
            writer.writerow(
                {
                    "year": year,
                    "openalex_article_count": article_counts.get(year, 0),
                    "openalex_all_works_count": all_works_counts.get(year, 0),
                    "article_query_url": article_url,
                    "all_works_query_url": all_works_url,
                    "retrieved_at_utc": retrieved_at,
                }
            )

    metadata = {
        "retrieved_at_utc": retrieved_at,
        "source": "OpenAlex Works API",
        "start_year": START_YEAR,
        "end_year": END_YEAR,
        "primary_definition": "Deduplicated Nobel key papers with OpenAlex work_type=article divided by OpenAlex type=article works in the same publication decade.",
        "sensitivity_definition": "All deduplicated Nobel key-paper works divided by all OpenAlex Works in the same publication decade.",
        "deduplication": "OpenAlex Work ID, then DOI, then normalized title-year (same as existing project scripts).",
        "article_query_url": article_url,
        "all_works_query_url": all_works_url,
        "analysis_source": "02_full_collection/06_analysis/analysis_ready_key_papers_full.csv",
        "unique_key_papers": len(unique_papers),
        "unique_article_key_papers": sum(article_key_counts.values()),
        "article_api_meta_count": int((article_payload.get("meta") or {}).get("count") or 0),
        "all_works_api_meta_count": int((all_works_payload.get("meta") or {}).get("count") or 0),
        "important_limit": "The 2020s row covers 2020-2022 only, matching the maximum publication year in the key-paper dataset and the prior OpenAlex journal-count file.",
    }
    METADATA_JSON.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_rows: list[dict[str, Any]] = []
    for decade_start in range(1880, 2030, 10):
        period_end = min(decade_start + 9, END_YEAR)
        if decade_start > END_YEAR:
            continue
        openalex_articles = sum(article_counts.get(year, 0) for year in range(decade_start, period_end + 1))
        openalex_all_works = sum(all_works_counts.get(year, 0) for year in range(decade_start, period_end + 1))
        key_articles = article_key_counts.get(decade_start, 0)
        all_key_works = all_key_counts.get(decade_start, 0)
        summary_rows.append(
            {
                "publication_decade": f"{decade_start}s",
                "period_start_year": decade_start,
                "period_end_year": period_end,
                "nobel_key_article_count": key_articles,
                "openalex_article_count": openalex_articles,
                "key_article_share": key_articles / openalex_articles if openalex_articles else 0,
                "key_articles_per_million_openalex_articles": key_articles / openalex_articles * 1_000_000 if openalex_articles else 0,
                "all_nobel_key_work_count": all_key_works,
                "openalex_all_works_count": openalex_all_works,
                "all_key_work_share": all_key_works / openalex_all_works if openalex_all_works else 0,
                "all_key_works_per_million_openalex_works": all_key_works / openalex_all_works * 1_000_000 if openalex_all_works else 0,
                "period_note": "partial decade: 2020-2022" if decade_start == 2020 else "full decade",
            }
        )

    fieldnames = list(summary_rows[0].keys())
    with SUMMARY_CSV.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)

    append_query_log(article_url, ANNUAL_CSV, "type=article; primary denominator")
    append_query_log(all_works_url, ANNUAL_CSV, "all OpenAlex work types; sensitivity denominator")
    return {
        "unique_key_papers": len(unique_papers),
        "unique_article_key_papers": sum(article_key_counts.values()),
        "annual_output": str(ANNUAL_CSV),
        "summary_output": str(SUMMARY_CSV),
        "metadata_output": str(METADATA_JSON),
        "summary_rows": len(summary_rows),
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
