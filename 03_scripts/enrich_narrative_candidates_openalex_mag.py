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
INPUT_CSV = ROOT / "01_validation" / "02_candidate_key_papers" / "narrative_reconstruction_candidates_all45.csv"
OUT_CSV = ROOT / "01_validation" / "03_matched_metadata" / "narrative_reconstruction_openalex_mag_matches_all45.csv"
OUT_SUMMARY = ROOT / "01_validation" / "04_outputs" / "narrative_reconstruction_openalex_mag_summary_all45.json"
CACHE_DIR = ROOT / "01_validation" / "01_raw_sources" / "metadata_api_cache" / "openalex_mag"
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"

OPENALEX_WORKS = "https://api.openalex.org/works"
MAG_RE = re.compile(r"MAG Paper ID=([0-9]+)")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def cache_path(url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    return CACHE_DIR / f"{digest}.json"


def openalex_mag_url(mag_id: str) -> str:
    params = {
        "filter": f"ids.mag:{mag_id}",
        "per-page": "1",
    }
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
    raise RuntimeError("OpenAlex request failed")


def source_fields(work: dict[str, Any]) -> dict[str, str]:
    primary_location = work.get("primary_location") or {}
    source = primary_location.get("source") or {}
    return {
        "openalex_journal": str(source.get("display_name") or ""),
        "openalex_source_id": str(source.get("id") or ""),
        "issn_l": str(source.get("issn_l") or ""),
    }


def best_work(payload: dict[str, Any]) -> dict[str, Any]:
    results = payload.get("results") or []
    if not results:
        return {}
    return results[0]


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
                "query_id": "enrich_narrative_candidates_openalex_mag",
                "run_at": dt.datetime.now(dt.UTC).isoformat(),
                "phase": "validation",
                "source": "OpenAlex",
                "query_or_url": str(INPUT_CSV),
                "parameters": "filter=ids.mag:<MAG Paper ID>",
                "output_path": str(out_csv),
                "status": "ok" if errors == 0 else "partial",
                "notes": f"rows={rows}; matched={matched}; errors={errors}",
            }
        )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Enrich narrative reconstruction candidates using Li 2019 MAG ids and OpenAlex.")
    parser.add_argument("--input-csv", type=Path, default=INPUT_CSV)
    parser.add_argument("--out-csv", type=Path, default=OUT_CSV)
    parser.add_argument("--summary-json", type=Path, default=OUT_SUMMARY)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--delay", type=float, default=0.15)
    parser.add_argument("--progress-every", type=int, default=10)
    args = parser.parse_args()

    input_rows = read_csv(args.input_csv)
    out_rows: list[dict[str, str]] = []
    errors = 0
    matched = 0
    queryable = 0

    for idx, row in enumerate(input_rows, start=1):
        detail = row.get("candidate_source_detail", "")
        mag_match = MAG_RE.search(detail)
        mag_id = mag_match.group(1) if mag_match else ""
        output = dict(row)
        output.update(
            {
                "mag_paper_id": mag_id,
                "openalex_work_id": "",
                "openalex_title": "",
                "openalex_publication_year": "",
                "openalex_journal": "",
                "openalex_source_id": "",
                "issn_l": "",
                "openalex_doi": "",
                "openalex_type": "",
                "openalex_match_status": "not_queried_no_mag_id",
                "openalex_match_notes": "",
            }
        )

        if mag_id:
            queryable += 1
            try:
                payload = request_json(openalex_mag_url(mag_id), args.timeout, args.retries, args.delay)
                work = best_work(payload)
                if work:
                    matched += 1
                    output.update(
                        {
                            "openalex_work_id": str(work.get("id") or ""),
                            "openalex_title": str(work.get("display_name") or work.get("title") or ""),
                            "openalex_publication_year": str(work.get("publication_year") or ""),
                            "openalex_doi": str(work.get("doi") or ""),
                            "openalex_type": str(work.get("type") or ""),
                            "openalex_match_status": "matched_by_mag_id",
                            "openalex_match_notes": "OpenAlex exact ids.mag match from Li 2019 MAG Paper ID",
                        }
                    )
                    output.update(source_fields(work))
                else:
                    output["openalex_match_status"] = "no_openalex_result_for_mag_id"
            except Exception as exc:
                errors += 1
                output["openalex_match_status"] = "openalex_error"
                output["openalex_match_notes"] = f"{type(exc).__name__}: {exc}"

        out_rows.append(output)
        if args.progress_every and idx % args.progress_every == 0:
            print(f"processed {idx}/{len(input_rows)}", flush=True)

    fields = list(input_rows[0].keys()) if input_rows else []
    fields.extend(
        [
            "mag_paper_id",
            "openalex_work_id",
            "openalex_title",
            "openalex_publication_year",
            "openalex_journal",
            "openalex_source_id",
            "issn_l",
            "openalex_doi",
            "openalex_type",
            "openalex_match_status",
            "openalex_match_notes",
        ]
    )
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.out_csv.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out_rows)

    summary: dict[str, object] = {
        "input_rows": len(input_rows),
        "rows_with_mag_id": queryable,
        "matched_rows": matched,
        "errors": errors,
        "by_openalex_match_status": {},
        "output": str(args.out_csv),
    }
    for row in out_rows:
        bucket = summary["by_openalex_match_status"]
        assert isinstance(bucket, dict)
        status = row["openalex_match_status"]
        bucket[status] = int(bucket.get(status, 0)) + 1

    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    append_query_log(len(input_rows), matched, errors, args.out_csv)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
