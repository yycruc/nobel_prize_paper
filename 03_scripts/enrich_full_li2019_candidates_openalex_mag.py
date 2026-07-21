from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INPUT_CSV = ROOT / "02_full_collection" / "02_candidate_key_papers" / "li2019_key_paper_candidates_full.csv"
OUT_CSV = ROOT / "02_full_collection" / "03_matched_metadata" / "li2019_openalex_mag_matches_full.csv"
OUT_SUMMARY = ROOT / "02_full_collection" / "05_outputs" / "li2019_openalex_mag_matches_summary_full.json"
CACHE_DIR = ROOT / "02_full_collection" / "01_raw_sources" / "metadata_api_cache" / "openalex_mag"
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"

OPENALEX_WORKS = "https://api.openalex.org/works"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def cache_path(url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    return CACHE_DIR / f"{digest}.json"


def openalex_mag_url(mag_id: str) -> str:
    params = {"filter": f"ids.mag:{mag_id}", "per-page": "1"}
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

    req = urllib.request.Request(url, headers={"User-Agent": "nobel-key-papers-full-collection/0.1 (mag exact metadata)"})
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
    raise RuntimeError("OpenAlex MAG request failed")


def first_work(payload: dict[str, Any]) -> dict[str, Any]:
    results = payload.get("results") or []
    return results[0] if results else {}


def source_fields(work: dict[str, Any]) -> dict[str, str]:
    source = ((work.get("primary_location") or {}).get("source") or {})
    return {
        "openalex_source": str(source.get("display_name") or ""),
        "openalex_source_id": str(source.get("id") or ""),
        "issn_l": str(source.get("issn_l") or ""),
    }


def append_query_log(rows: int, unique_mag_ids: int, matched: int, errors: int, out_csv: Path) -> None:
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
                "query_id": "enrich_full_li2019_candidates_openalex_mag",
                "run_at": dt.datetime.now(dt.UTC).isoformat(),
                "phase": "full_collection",
                "source": "OpenAlex",
                "query_or_url": str(INPUT_CSV),
                "parameters": "filter=ids.mag:<MAG Paper ID>; exact identifier only",
                "output_path": str(out_csv),
                "status": "ok" if errors == 0 else "partial",
                "notes": f"rows={rows}; unique_mag_ids={unique_mag_ids}; matched={matched}; errors={errors}",
            }
        )


def write_csv(path: Path, rows: list[dict[str, str]], input_fields: list[str]) -> None:
    fields = input_fields + [
        "openalex_work_id",
        "openalex_title",
        "openalex_publication_year",
        "openalex_source",
        "openalex_source_id",
        "issn_l",
        "openalex_doi",
        "openalex_type",
        "openalex_match_status",
        "openalex_match_notes",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Exact OpenAlex MAG enrichment for full Li 2019 candidates.")
    parser.add_argument("--input-csv", type=Path, default=INPUT_CSV)
    parser.add_argument("--out-csv", type=Path, default=OUT_CSV)
    parser.add_argument("--summary-json", type=Path, default=OUT_SUMMARY)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--delay", type=float, default=0.15)
    parser.add_argument("--progress-every", type=int, default=50)
    args = parser.parse_args()

    input_rows = read_csv(args.input_csv)
    input_fields = list(input_rows[0].keys()) if input_rows else []
    out_rows: list[dict[str, str]] = []
    mag_cache: dict[str, tuple[dict[str, str], str]] = {}
    errors = 0
    matched_rows = 0

    for idx, row in enumerate(input_rows, start=1):
        mag_id = row.get("mag_paper_id", "")
        out = dict(row)
        oa_fields = {
            "openalex_work_id": "",
            "openalex_title": "",
            "openalex_publication_year": "",
            "openalex_source": "",
            "openalex_source_id": "",
            "issn_l": "",
            "openalex_doi": "",
            "openalex_type": "",
        }
        status = "not_queried_no_mag_id"
        notes = ""
        if mag_id:
            if mag_id in mag_cache:
                oa_fields, status = mag_cache[mag_id]
                notes = "reused MAG result from in-run cache"
            else:
                try:
                    payload = request_json(openalex_mag_url(mag_id), args.timeout, args.retries, args.delay)
                    work = first_work(payload)
                    if work:
                        status = "matched_by_mag_id"
                        oa_fields.update(
                            {
                                "openalex_work_id": str(work.get("id") or ""),
                                "openalex_title": str(work.get("display_name") or work.get("title") or ""),
                                "openalex_publication_year": str(work.get("publication_year") or ""),
                                "openalex_doi": str(work.get("doi") or ""),
                                "openalex_type": str(work.get("type") or ""),
                            }
                        )
                        oa_fields.update(source_fields(work))
                    else:
                        status = "no_openalex_result_for_mag_id"
                    mag_cache[mag_id] = (dict(oa_fields), status)
                except Exception as exc:
                    errors += 1
                    status = "openalex_error"
                    notes = f"{type(exc).__name__}: {exc}"
        if status == "matched_by_mag_id":
            matched_rows += 1
        out.update(oa_fields)
        out["openalex_match_status"] = status
        out["openalex_match_notes"] = notes
        out_rows.append(out)

        if args.progress_every and idx % args.progress_every == 0:
            write_csv(args.out_csv, out_rows, input_fields)
            print(f"processed {idx}/{len(input_rows)}; unique_mag_ids={len(mag_cache)}", flush=True)

    write_csv(args.out_csv, out_rows, input_fields)
    summary: dict[str, object] = {
        "input_rows": len(input_rows),
        "rows_with_mag_id": sum(1 for row in input_rows if row.get("mag_paper_id")),
        "unique_mag_ids": len({row.get("mag_paper_id", "") for row in input_rows if row.get("mag_paper_id")}),
        "matched_rows": matched_rows,
        "errors": errors,
        "by_openalex_match_status": {},
        "output": str(args.out_csv),
    }
    for row in out_rows:
        bucket = summary["by_openalex_match_status"]
        assert isinstance(bucket, dict)
        key = row["openalex_match_status"]
        bucket[key] = int(bucket.get(key, 0)) + 1

    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    append_query_log(len(input_rows), int(summary["unique_mag_ids"]), matched_rows, errors, args.out_csv)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
