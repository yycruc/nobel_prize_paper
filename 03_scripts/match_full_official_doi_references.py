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
CLASSIFICATION_CSV = ROOT / "02_full_collection" / "02_candidate_key_papers" / "official_reference_classification_full.csv"
OUT_CSV = ROOT / "02_full_collection" / "03_matched_metadata" / "official_reference_doi_matches_full.csv"
OUT_SUMMARY = ROOT / "02_full_collection" / "05_outputs" / "official_reference_doi_matches_summary_full.json"
CACHE_DIR = ROOT / "02_full_collection" / "01_raw_sources" / "metadata_api_cache"
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"

OPENALEX_WORKS = "https://api.openalex.org/works"
CROSSREF_WORKS = "https://api.crossref.org/works"
DOI_START_RE = re.compile(r"\b10\.\d{4,9}/", re.IGNORECASE)
DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s\"<>]+", re.IGNORECASE)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def clean_doi(value: str) -> str:
    match = DOI_RE.search(value or "")
    if not match:
        return ""
    doi = match.group(0)
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
    return doi.strip().rstrip(".,;:)]}").lower()


def extract_pdf_doi(value: str) -> str:
    text = (value or "").replace("\u00ad", "")
    match = DOI_START_RE.search(text)
    if not match:
        return clean_doi(text)

    kept: list[str] = []
    idx = match.start()
    while idx < len(text):
        char = text[idx]
        if re.match(r"[A-Za-z0-9._;()/:-]", char):
            kept.append(char)
            idx += 1
            continue
        if char.isspace():
            next_idx = idx + 1
            while next_idx < len(text) and text[next_idx].isspace():
                next_idx += 1
            prev = kept[-1] if kept else ""
            nxt = text[next_idx] if next_idx < len(text) else ""
            if nxt and (nxt in ".:-" or (prev in "/-" and (nxt.isdigit() or nxt.islower()))):
                idx = next_idx
                continue
            break
        break

    doi = "".join(kept)
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
    return doi.strip().rstrip(".,;:)]}").lower()


def cache_path(source: str, url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    return CACHE_DIR / source / f"{digest}.json"


def request_json(source: str, url: str, timeout: float, retries: int, delay: float) -> dict[str, Any]:
    path = cache_path(source, url)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "nobel-key-papers-full-collection/0.1 (doi exact metadata)"},
    )
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
    raise RuntimeError("request failed")


def openalex_doi_url(doi: str) -> str:
    params = {"filter": f"doi:https://doi.org/{doi}", "per-page": "1"}
    mailto = os.environ.get("OPENALEX_MAILTO", "")
    if mailto:
        params["mailto"] = mailto
    api_key = os.environ.get("OPENALEX_API_KEY", "")
    if api_key:
        params["api_key"] = api_key
    return OPENALEX_WORKS + "?" + urllib.parse.urlencode(params)


def crossref_doi_url(doi: str) -> str:
    url = CROSSREF_WORKS + "/" + urllib.parse.quote(doi, safe="")
    mailto = os.environ.get("CROSSREF_MAILTO", "")
    if mailto:
        url += "?" + urllib.parse.urlencode({"mailto": mailto})
    return url


def first(value: Any) -> str:
    if isinstance(value, list) and value:
        return str(value[0] or "")
    if value is None:
        return ""
    return str(value)


def date_year(value: dict[str, Any]) -> str:
    for key in ("published-print", "published-online", "issued", "published"):
        parts = ((value.get(key) or {}).get("date-parts") or [])
        if parts and parts[0]:
            return str(parts[0][0])
    return ""


def openalex_fields(payload: dict[str, Any]) -> dict[str, str]:
    results = payload.get("results") or []
    if not results:
        return {
            "openalex_match_status": "no_openalex_result",
            "openalex_work_id": "",
            "openalex_title": "",
            "openalex_year": "",
            "openalex_source": "",
            "openalex_source_id": "",
            "issn_l": "",
            "openalex_type": "",
            "openalex_doi": "",
        }
    work = results[0]
    source = ((work.get("primary_location") or {}).get("source") or {})
    return {
        "openalex_match_status": "matched_openalex_doi",
        "openalex_work_id": str(work.get("id") or ""),
        "openalex_title": str(work.get("display_name") or work.get("title") or ""),
        "openalex_year": str(work.get("publication_year") or ""),
        "openalex_source": str(source.get("display_name") or ""),
        "openalex_source_id": str(source.get("id") or ""),
        "issn_l": str(source.get("issn_l") or ""),
        "openalex_type": str(work.get("type") or ""),
        "openalex_doi": clean_doi(str(work.get("doi") or "")),
    }


def crossref_fields(payload: dict[str, Any]) -> dict[str, str]:
    item = payload.get("message") or {}
    return {
        "crossref_match_status": "matched_crossref_doi" if item else "no_crossref_result",
        "crossref_doi": clean_doi(str(item.get("DOI") or "")),
        "crossref_title": first(item.get("title")),
        "crossref_year": date_year(item),
        "crossref_source": first(item.get("container-title")),
        "crossref_type": str(item.get("type") or ""),
        "crossref_url": str(item.get("URL") or ""),
    }


def empty_crossref_fields(status: str) -> dict[str, str]:
    return {
        "crossref_match_status": status,
        "crossref_doi": "",
        "crossref_title": "",
        "crossref_year": "",
        "crossref_source": "",
        "crossref_type": "",
        "crossref_url": "",
    }


def append_query_log(rows: int, unique_dois: int, matched_openalex: int, matched_crossref_only: int, errors: int) -> None:
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
                "query_id": "match_full_official_doi_references",
                "run_at": dt.datetime.now(dt.UTC).isoformat(),
                "phase": "full_collection",
                "source": "OpenAlex; Crossref",
                "query_or_url": str(CLASSIFICATION_CSV),
                "parameters": "reference_class=doi_present; exact DOI lookup only",
                "output_path": str(OUT_CSV),
                "status": "ok" if errors == 0 else "partial",
                "notes": (
                    f"rows={rows}; unique_dois={unique_dois}; "
                    f"matched_openalex={matched_openalex}; matched_crossref_only={matched_crossref_only}; errors={errors}"
                ),
            }
        )


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fields = [
        "reference_candidate_id",
        "validation_id",
        "laureate_id",
        "full_name",
        "award_year",
        "category",
        "pdf_type",
        "reference_text",
        "reference_doi",
        "detected_years",
        "openalex_match_status",
        "openalex_work_id",
        "openalex_title",
        "openalex_year",
        "openalex_source",
        "openalex_source_id",
        "issn_l",
        "openalex_type",
        "openalex_doi",
        "crossref_match_status",
        "crossref_doi",
        "crossref_title",
        "crossref_year",
        "crossref_source",
        "crossref_type",
        "crossref_url",
        "metadata_match_status",
        "match_confidence",
        "review_status",
        "notes",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Exact DOI metadata matching for full official Nobel references.")
    parser.add_argument("--classification-csv", type=Path, default=CLASSIFICATION_CSV)
    parser.add_argument("--out-csv", type=Path, default=OUT_CSV)
    parser.add_argument("--summary-json", type=Path, default=OUT_SUMMARY)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--delay", type=float, default=0.15)
    parser.add_argument("--progress-every", type=int, default=10)
    args = parser.parse_args()

    doi_rows = [row for row in read_csv(args.classification_csv) if row.get("reference_class") == "doi_present"]
    out_rows: list[dict[str, str]] = []
    doi_cache: dict[str, tuple[dict[str, str], dict[str, str], str]] = {}
    errors = 0

    for idx, row in enumerate(doi_rows, start=1):
        doi = extract_pdf_doi(row.get("reference_text", "")) or clean_doi(row.get("detected_doi", ""))
        notes: list[str] = []
        if doi in doi_cache:
            oa_fields, cr_fields, metadata_status = doi_cache[doi]
            notes.append("reused DOI result from in-run cache")
        else:
            oa_fields = {
                "openalex_match_status": "not_queried",
                "openalex_work_id": "",
                "openalex_title": "",
                "openalex_year": "",
                "openalex_source": "",
                "openalex_source_id": "",
                "issn_l": "",
                "openalex_type": "",
                "openalex_doi": "",
            }
            cr_fields = empty_crossref_fields("not_queried")
            metadata_status = "unmatched"
            try:
                oa_payload = request_json("openalex_doi", openalex_doi_url(doi), args.timeout, args.retries, args.delay)
                oa_fields = openalex_fields(oa_payload)
                if oa_fields["openalex_match_status"] == "matched_openalex_doi":
                    metadata_status = "matched_openalex_exact_doi"
            except Exception as exc:
                errors += 1
                oa_fields["openalex_match_status"] = "openalex_error"
                notes.append(f"openalex_error={type(exc).__name__}: {exc}")

            if metadata_status == "unmatched":
                try:
                    cr_payload = request_json("crossref_doi", crossref_doi_url(doi), args.timeout, args.retries, args.delay)
                    cr_fields = crossref_fields(cr_payload)
                    if cr_fields["crossref_match_status"] == "matched_crossref_doi":
                        metadata_status = "matched_crossref_exact_doi"
                except urllib.error.HTTPError as exc:
                    if exc.code == 404:
                        cr_fields = empty_crossref_fields("no_crossref_result")
                    else:
                        errors += 1
                        cr_fields = empty_crossref_fields("crossref_error")
                        notes.append(f"crossref_error={type(exc).__name__}: {exc}")
                except Exception as exc:
                    errors += 1
                    cr_fields = empty_crossref_fields("crossref_error")
                    notes.append(f"crossref_error={type(exc).__name__}: {exc}")
            doi_cache[doi] = (oa_fields, cr_fields, metadata_status)

        confidence = "A" if metadata_status.startswith("matched_") else "D"
        review_status = "metadata_matched" if confidence == "A" else "needs_review"
        out_rows.append(
            {
                "reference_candidate_id": row.get("reference_candidate_id", ""),
                "validation_id": row.get("validation_id", ""),
                "laureate_id": row.get("laureate_id", ""),
                "full_name": row.get("full_name", ""),
                "award_year": row.get("award_year", ""),
                "category": row.get("category", ""),
                "pdf_type": row.get("pdf_type", ""),
                "reference_text": row.get("reference_text", ""),
                "reference_doi": doi,
                "detected_years": row.get("detected_years", ""),
                **oa_fields,
                **cr_fields,
                "metadata_match_status": metadata_status,
                "match_confidence": confidence,
                "review_status": review_status,
                "notes": " | ".join(notes),
            }
        )
        if args.progress_every and idx % args.progress_every == 0:
            write_csv(args.out_csv, out_rows)
            print(f"processed {idx}/{len(doi_rows)} DOI rows; unique_dois={len(doi_cache)}", flush=True)

    write_csv(args.out_csv, out_rows)

    summary: dict[str, object] = {
        "doi_reference_rows": len(doi_rows),
        "unique_dois": len(doi_cache),
        "errors": errors,
        "by_metadata_match_status": {},
        "by_openalex_match_status": {},
        "by_crossref_match_status": {},
        "by_review_status": {},
        "output": str(args.out_csv),
    }
    for row in out_rows:
        for bucket_name, field in [
            ("by_metadata_match_status", "metadata_match_status"),
            ("by_openalex_match_status", "openalex_match_status"),
            ("by_crossref_match_status", "crossref_match_status"),
            ("by_review_status", "review_status"),
        ]:
            bucket = summary[bucket_name]
            assert isinstance(bucket, dict)
            key = row[field]
            bucket[key] = int(bucket.get(key, 0)) + 1

    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    matched_openalex = int(summary["by_metadata_match_status"].get("matched_openalex_exact_doi", 0))  # type: ignore[index, union-attr]
    matched_crossref_only = int(summary["by_metadata_match_status"].get("matched_crossref_exact_doi", 0))  # type: ignore[index, union-attr]
    append_query_log(len(doi_rows), len(doi_cache), matched_openalex, matched_crossref_only, errors)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
