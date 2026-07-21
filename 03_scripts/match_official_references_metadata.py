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
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REFS_CSV = ROOT / "01_validation" / "02_candidate_key_papers" / "official_pdf_reference_section_candidates.csv"
CLASSIFICATION_CSV = ROOT / "01_validation" / "02_candidate_key_papers" / "official_reference_classification_validation.csv"
OUT_CSV = ROOT / "01_validation" / "03_matched_metadata" / "official_reference_metadata_matches_validation.csv"
OUT_SUMMARY = ROOT / "01_validation" / "04_outputs" / "official_reference_metadata_match_summary.json"
CACHE_DIR = ROOT / "01_validation" / "01_raw_sources" / "metadata_api_cache"
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"

CROSSREF_WORKS = "https://api.crossref.org/works"
OPENALEX_WORKS = "https://api.openalex.org/works"
DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s\"<>]+", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(18|19|20)\d{2}\b")
STOPWORDS = {
    "and",
    "the",
    "for",
    "with",
    "from",
    "into",
    "that",
    "this",
    "eine",
    "uber",
    "ueber",
    "des",
    "der",
    "die",
    "dans",
    "les",
    "sur",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


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
        "reference_years",
        "reference_doi",
        "crossref_doi",
        "crossref_title",
        "crossref_year",
        "crossref_journal",
        "crossref_type",
        "crossref_score",
        "openalex_work_id",
        "openalex_title",
        "openalex_year",
        "openalex_journal",
        "openalex_source_id",
        "issn_l",
        "doi",
        "match_confidence",
        "match_method",
        "review_status",
        "notes",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.replace("\u00df", "ss").replace("\u00f8", "o").replace("\u00d8", "O")
    value = re.sub(r"https?://\S+", " ", value)
    value = re.sub(r"[^0-9A-Za-z]+", " ", value)
    return re.sub(r"\s+", " ", value).strip().casefold()


def tokens(value: str) -> set[str]:
    return {tok for tok in normalize_text(value).split() if len(tok) >= 3 and tok not in STOPWORDS}


def clean_reference_text(value: str) -> str:
    value = value.replace("\u00ad", "")
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"\s+\d{1,3}\s*\(\d{1,3}\)\s*$", "", value)
    return value[:1200]


def clean_doi(value: str) -> str:
    value = value.strip().rstrip(".,;:)")
    value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value, flags=re.IGNORECASE)
    return value.lower()


def years_from_ref(value: str) -> list[str]:
    return sorted(set(match.group(0) for match in YEAR_RE.finditer(value)))


def cache_path(source: str, url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    return CACHE_DIR / source / f"{digest}.json"


def request_json(
    source: str,
    url: str,
    retries: int = 2,
    delay: float = 0.0,
    timeout: float = 25.0,
) -> dict[str, Any]:
    path = cache_path(source, url)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    headers = {"User-Agent": "nobel-key-papers-validation/0.1 (metadata matching)"}
    req = urllib.request.Request(url, headers=headers)
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
                wait = float(retry_after) if retry_after and retry_after.isdigit() else min(20, 2**attempt)
                time.sleep(wait)
                continue
            raise
        except urllib.error.URLError as exc:
            last_error = exc
            time.sleep(min(20, 2**attempt))
    if last_error:
        raise last_error
    raise RuntimeError(f"{source} request failed")


def crossref_query_url(reference_text: str, rows: int) -> str:
    params = {
        "query.bibliographic": reference_text,
        "rows": str(rows),
        "select": "DOI,title,container-title,published-print,published-online,issued,type,author,score,URL,ISSN",
    }
    mailto = os.environ.get("CROSSREF_MAILTO", "")
    if mailto:
        params["mailto"] = mailto
    return CROSSREF_WORKS + "?" + urllib.parse.urlencode(params)


def openalex_doi_url(doi: str) -> str:
    params = {"filter": f"doi:https://doi.org/{doi}", "per-page": "1"}
    mailto = os.environ.get("OPENALEX_MAILTO", "")
    if mailto:
        params["mailto"] = mailto
    api_key = os.environ.get("OPENALEX_API_KEY", "")
    if api_key:
        params["api_key"] = api_key
    return OPENALEX_WORKS + "?" + urllib.parse.urlencode(params)


def first(value: Any) -> str:
    if isinstance(value, list) and value:
        return str(value[0] or "")
    if value is None:
        return ""
    return str(value)


def crossref_year(item: dict[str, Any]) -> str:
    for key in ("published-print", "published-online", "issued"):
        parts = ((item.get(key) or {}).get("date-parts") or [])
        if parts and parts[0]:
            return str(parts[0][0])
    return ""


def score_crossref_item(ref_text: str, ref_years: set[str], ref_doi: str, item: dict[str, Any]) -> tuple[float, str]:
    title = first(item.get("title"))
    journal = first(item.get("container-title"))
    item_doi = clean_doi(str(item.get("DOI") or ""))
    item_year = crossref_year(item)

    title_tokens = tokens(title)
    ref_tokens = tokens(ref_text)
    title_overlap = len(title_tokens & ref_tokens) / len(title_tokens) if title_tokens else 0.0
    journal_tokens = tokens(journal)
    source_overlap = len(journal_tokens & ref_tokens) / len(journal_tokens) if journal_tokens else 0.0
    year_match = bool(item_year and item_year in ref_years)
    doi_match = bool(ref_doi and item_doi and ref_doi == item_doi)

    score = 0.0
    if doi_match:
        score += 70
    if item.get("type") == "journal-article":
        score += 10
    if year_match:
        score += 15
    score += 60 * title_overlap
    if source_overlap >= 0.5:
        score += 10
    score += min(float(item.get("score") or 0.0), 100.0) / 100.0

    diagnostics = (
        f"title_overlap={title_overlap:.2f}; source_overlap={source_overlap:.2f}; "
        f"year_match={year_match}; doi_match={doi_match}"
    )
    return score, diagnostics


def choose_crossref_item(ref_text: str, ref_years: set[str], ref_doi: str, items: list[dict[str, Any]]) -> tuple[dict[str, Any], str, float]:
    best: dict[str, Any] = {}
    best_note = ""
    best_score = -1.0
    for item in items:
        score, note = score_crossref_item(ref_text, ref_years, ref_doi, item)
        if score > best_score:
            best = item
            best_note = note
            best_score = score
    return best, best_note, best_score


def confidence(ref_text: str, ref_years: set[str], ref_doi: str, item: dict[str, Any], note: str) -> tuple[str, str, str]:
    if not item:
        return "D", "no_crossref_candidate", "no_match"
    title = first(item.get("title"))
    title_tokens = tokens(title)
    ref_tokens = tokens(ref_text)
    title_overlap = len(title_tokens & ref_tokens) / len(title_tokens) if title_tokens else 0.0
    year = crossref_year(item)
    year_match = bool(year and year in ref_years)
    doi = clean_doi(str(item.get("DOI") or ""))
    doi_match = bool(ref_doi and doi and doi == ref_doi)

    if doi_match:
        return "A", "crossref_exact_doi", "accepted"
    if title_overlap >= 0.75 and year_match:
        return "A", "crossref_title_year_high_overlap", "accepted"
    if title_overlap >= 0.60 and year_match:
        return "B", "crossref_title_year_medium_overlap", "needs_review"
    if title_overlap >= 0.45 and (year_match or "source_overlap=1.00" in note):
        return "C", "crossref_partial_overlap", "needs_review"
    return "D", "crossref_low_overlap", "no_match"


def extract_openalex(openalex_payload: dict[str, Any]) -> dict[str, str]:
    results = openalex_payload.get("results") or []
    if not results:
        return {
            "openalex_work_id": "",
            "openalex_title": "",
            "openalex_year": "",
            "openalex_journal": "",
            "openalex_source_id": "",
            "issn_l": "",
        }
    work = results[0]
    source = ((work.get("primary_location") or {}).get("source") or {})
    return {
        "openalex_work_id": str(work.get("id") or ""),
        "openalex_title": str(work.get("title") or ""),
        "openalex_year": str(work.get("publication_year") or ""),
        "openalex_journal": str(source.get("display_name") or ""),
        "openalex_source_id": str(source.get("id") or ""),
        "issn_l": str(source.get("issn_l") or ""),
    }


def is_aggregate_reference(ref_text: str) -> bool:
    lowered = ref_text.casefold()
    markers = ["books", "videos", "scientific article", "websites", "additional information"]
    return len(ref_text) > 900 and sum(1 for marker in markers if marker in lowered) >= 3


def classification_map(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    return {row["reference_candidate_id"]: row for row in read_csv(path)}


def append_query_log(rows: int, status: str, notes: str, output_path: Path) -> None:
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
                "query_id": "match_official_references_metadata",
                "run_at": dt.datetime.now(dt.UTC).isoformat(),
                "phase": "validation",
                "source": "Crossref; OpenAlex",
                "query_or_url": str(REFS_CSV),
                "parameters": "Crossref bibliographic query; OpenAlex DOI lookup",
                "output_path": str(output_path),
                "status": status,
                "notes": f"rows={rows}; {notes}",
            }
        )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Match Nobel official PDF reference strings to Crossref/OpenAlex metadata.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of references to process, for smoke tests.")
    parser.add_argument("--rows", type=int, default=3, help="Crossref candidate rows per reference.")
    parser.add_argument("--delay", type=float, default=0.15, help="Delay before uncached HTTP requests.")
    parser.add_argument("--timeout", type=float, default=25.0, help="HTTP timeout per request in seconds.")
    parser.add_argument("--retries", type=int, default=2, help="Retries per uncached HTTP request.")
    parser.add_argument("--pdf-types", default="scientific_background,nobel_lecture,popular_background")
    parser.add_argument("--classification-csv", type=Path, default=CLASSIFICATION_CSV)
    parser.add_argument(
        "--reference-classes",
        default="doi_present,likely_journal_article,historical_nonindexed_reference",
        help="Comma-separated reference classes to send to metadata APIs.",
    )
    parser.add_argument("--start-index", type=int, default=1, help="1-based index into the filtered reference list.")
    parser.add_argument("--output-csv", type=Path, default=OUT_CSV, help="Output CSV path.")
    args = parser.parse_args()

    allowed_pdf_types = {item.strip() for item in args.pdf_types.split(",") if item.strip()}
    allowed_classes = {item.strip() for item in args.reference_classes.split(",") if item.strip()}
    class_by_id = classification_map(args.classification_csv)
    source_rows = [row for row in read_csv(REFS_CSV) if row.get("pdf_type") in allowed_pdf_types]
    if class_by_id and allowed_classes:
        source_rows = [
            row
            for row in source_rows
            if class_by_id.get(row.get("reference_candidate_id", ""), {}).get("reference_class") in allowed_classes
        ]
    if args.start_index < 1:
        raise ValueError("--start-index must be >= 1")
    source_rows = source_rows[args.start_index - 1 :]
    if args.limit:
        source_rows = source_rows[: args.limit]

    out_rows: list[dict[str, str]] = []
    errors = 0
    for idx, row in enumerate(source_rows, start=1):
        ref_text = clean_reference_text(row.get("reference_text", ""))
        ref_dois = [clean_doi(item) for item in DOI_RE.findall(ref_text)]
        ref_doi = ref_dois[0] if ref_dois else clean_doi(row.get("doi", ""))
        ref_years = set(years_from_ref(ref_text))
        notes: list[str] = []
        crossref_item: dict[str, Any] = {}
        crossref_note = ""
        crossref_pick_score = -1.0
        openalex_fields = extract_openalex({})

        if is_aggregate_reference(ref_text):
            notes.append("skipped_aggregate_further_reading_reference")
        else:
            try:
                crossref_payload = request_json(
                    "crossref",
                    crossref_query_url(ref_text, args.rows),
                    retries=args.retries,
                    delay=args.delay,
                    timeout=args.timeout,
                )
                items = ((crossref_payload.get("message") or {}).get("items") or [])
                crossref_item, crossref_note, crossref_pick_score = choose_crossref_item(ref_text, ref_years, ref_doi, items)
                notes.append(crossref_note)
            except Exception as exc:
                errors += 1
                notes.append(f"crossref_error={type(exc).__name__}: {exc}")

        crossref_doi = clean_doi(str(crossref_item.get("DOI") or "")) if crossref_item else ""
        lookup_doi = ref_doi or crossref_doi
        if lookup_doi:
            try:
                openalex_payload = request_json(
                    "openalex",
                    openalex_doi_url(lookup_doi),
                    retries=args.retries,
                    delay=args.delay,
                    timeout=args.timeout,
                )
                openalex_fields = extract_openalex(openalex_payload)
            except Exception as exc:
                errors += 1
                notes.append(f"openalex_error={type(exc).__name__}: {exc}")

        conf, method, review_status = confidence(ref_text, ref_years, ref_doi, crossref_item, crossref_note)
        if crossref_item and crossref_pick_score >= 0:
            notes.append(f"crossref_pick_score={crossref_pick_score:.2f}")
        out_rows.append(
            {
                "reference_candidate_id": row.get("reference_candidate_id", ""),
                "validation_id": row.get("validation_id", ""),
                "laureate_id": row.get("laureate_id", ""),
                "full_name": row.get("full_name", ""),
                "award_year": row.get("award_year", ""),
                "category": row.get("category", ""),
                "pdf_type": row.get("pdf_type", ""),
                "reference_text": ref_text,
                "reference_years": ";".join(sorted(ref_years)),
                "reference_doi": ref_doi,
                "crossref_doi": crossref_doi,
                "crossref_title": first(crossref_item.get("title")) if crossref_item else "",
                "crossref_year": crossref_year(crossref_item) if crossref_item else "",
                "crossref_journal": first(crossref_item.get("container-title")) if crossref_item else "",
                "crossref_type": str(crossref_item.get("type") or "") if crossref_item else "",
                "crossref_score": str(crossref_item.get("score") or "") if crossref_item else "",
                **openalex_fields,
                "doi": lookup_doi,
                "match_confidence": conf,
                "match_method": method,
                "review_status": review_status,
                "notes": " | ".join(note for note in notes if note),
            }
        )
        if idx % 10 == 0:
            write_csv(args.output_csv, out_rows)
            print(f"processed {idx}/{len(source_rows)}", flush=True)

    write_csv(args.output_csv, out_rows)

    summary: dict[str, Any] = {
        "input_rows": len(source_rows),
        "output_rows": len(out_rows),
        "errors": errors,
        "by_confidence": {},
        "by_review_status": {},
        "by_validation_id": {},
        "start_index": args.start_index,
        "output": str(args.output_csv),
    }
    for row in out_rows:
        for key, field in [
            ("by_confidence", "match_confidence"),
            ("by_review_status", "review_status"),
            ("by_validation_id", "validation_id"),
        ]:
            bucket = summary[key]
            bucket[row[field]] = int(bucket.get(row[field], 0)) + 1

    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    append_query_log(len(out_rows), "ok" if errors == 0 else "partial", f"errors={errors}", args.output_csv)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
