from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INPUT_CSV = ROOT / "01_validation" / "03_matched_metadata" / "narrative_candidate_review_table_all45.csv"
OUT_CSV = ROOT / "01_validation" / "03_matched_metadata" / "narrative_candidate_review_table_all45_doi_enriched.csv"
OUT_SUMMARY = ROOT / "01_validation" / "04_outputs" / "narrative_candidate_review_table_doi_enrichment_summary_all45.json"
CACHE_DIR = ROOT / "01_validation" / "01_raw_sources" / "metadata_api_cache" / "openalex_doi"
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"

OPENALEX_WORKS = "https://api.openalex.org/works"
DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"<>]+", re.IGNORECASE)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def clean_doi(value: str) -> str:
    match = DOI_RE.search(value or "")
    if not match:
        return ""
    return match.group(0).strip().rstrip(".,;:)").lower()


def cache_path(url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    return CACHE_DIR / f"{digest}.json"


def openalex_doi_url(doi: str) -> str:
    params = {"filter": f"doi:https://doi.org/{doi}", "per-page": "1"}
    mailto = os.environ.get("OPENALEX_MAILTO", "")
    if mailto:
        params["mailto"] = mailto
    api_key = os.environ.get("OPENALEX_API_KEY", "")
    if api_key:
        params["api_key"] = api_key
    return OPENALEX_WORKS + "?" + urllib.parse.urlencode(params)


def request_json(url: str, timeout: float, retries: int, delay: float) -> dict[str, Any]:
    path = cache_path(url)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    req = urllib.request.Request(url, headers={"User-Agent": "nobel-key-papers-validation/0.1"})
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            if delay:
                time.sleep(delay)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            return payload
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code in {429, 500, 502, 503, 504}:
                retry_after = exc.headers.get("Retry-After")
                wait = float(retry_after) if retry_after and retry_after.isdigit() else min(30, 2**attempt)
                time.sleep(wait)
                continue
            raise
        except urllib.error.URLError as exc:
            last_error = exc
            time.sleep(min(30, 2**attempt))
    if last_error:
        raise last_error
    raise RuntimeError("OpenAlex DOI request failed")


def first_work(payload: dict[str, Any]) -> dict[str, Any]:
    results = payload.get("results") or []
    return results[0] if results else {}


def source_fields(work: dict[str, Any]) -> dict[str, str]:
    source = ((work.get("primary_location") or {}).get("source") or {})
    return {
        "matched_journal": str(source.get("display_name") or ""),
        "openalex_source_id": str(source.get("id") or ""),
        "issn_l": str(source.get("issn_l") or ""),
    }


def append_query_log(rows: int, matched: int, errors: int, out_csv: Path) -> None:
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
                "query_id": "enrich_review_table_openalex_doi",
                "run_at": dt.datetime.now(dt.UTC).isoformat(),
                "phase": "validation",
                "source": "OpenAlex",
                "query_or_url": str(INPUT_CSV),
                "parameters": "filter=doi:https://doi.org/<doi>",
                "output_path": str(out_csv),
                "status": "ok" if errors == 0 else "partial",
                "notes": f"doi_query_rows={rows}; matched={matched}; errors={errors}",
            }
        )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Enrich narrative candidate review table using exact DOI lookup in OpenAlex.")
    parser.add_argument("--input-csv", type=Path, default=INPUT_CSV)
    parser.add_argument("--out-csv", type=Path, default=OUT_CSV)
    parser.add_argument("--summary-json", type=Path, default=OUT_SUMMARY)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--delay", type=float, default=0.15)
    args = parser.parse_args()

    rows = read_csv(args.input_csv)
    out_rows: list[dict[str, str]] = []
    doi_query_rows = 0
    matched = 0
    errors = 0

    for row in rows:
        out = dict(row)
        doi = clean_doi(row.get("doi", ""))
        if doi and not row.get("openalex_work_id"):
            doi_query_rows += 1
            try:
                payload = request_json(openalex_doi_url(doi), args.timeout, args.retries, args.delay)
                work = first_work(payload)
                if work:
                    matched += 1
                    out["matched_title"] = str(work.get("display_name") or work.get("title") or row.get("matched_title", ""))
                    out["matched_year"] = str(work.get("publication_year") or row.get("matched_year", ""))
                    out["doi"] = clean_doi(str(work.get("doi") or doi))
                    out["openalex_work_id"] = str(work.get("id") or "")
                    out.update(source_fields(work))
                    out["analysis_eligibility"] = "journal_candidate_matched"
                    out["review_status"] = "provisionally_accept_metadata"
                    out["review_note"] = "OpenAlex exact DOI match added to manual seed candidate."
                else:
                    out["review_note"] = f"{row.get('review_note', '')} | DOI lookup returned no OpenAlex result."
            except Exception as exc:
                errors += 1
                out["review_note"] = f"{row.get('review_note', '')} | DOI lookup error: {type(exc).__name__}: {exc}"
        out_rows.append(out)

    fields = list(rows[0].keys()) if rows else []
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.out_csv.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out_rows)

    summary: dict[str, object] = {
        "input_rows": len(rows),
        "doi_query_rows": doi_query_rows,
        "matched_rows": matched,
        "errors": errors,
        "by_analysis_eligibility": {},
        "by_review_status": {},
        "output": str(args.out_csv),
    }
    for row in out_rows:
        for bucket_name, field in [
            ("by_analysis_eligibility", "analysis_eligibility"),
            ("by_review_status", "review_status"),
        ]:
            bucket = summary[bucket_name]
            assert isinstance(bucket, dict)
            key = row.get(field, "")
            bucket[key] = int(bucket.get(key, 0)) + 1

    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    append_query_log(doi_query_rows, matched, errors, args.out_csv)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
