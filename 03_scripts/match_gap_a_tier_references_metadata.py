from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INPUT_CSV = ROOT / "02_full_collection" / "02_candidate_key_papers" / "official_gap_reference_candidates_full.csv"
OUT_CSV = ROOT / "02_full_collection" / "03_matched_metadata" / "official_gap_a_tier_metadata_matches_full.csv"
OUT_SUMMARY = ROOT / "02_full_collection" / "05_outputs" / "official_gap_a_tier_metadata_matches_summary_full.json"
CACHE_DIR = ROOT / "02_full_collection" / "01_raw_sources" / "metadata_api_cache"
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
    "using",
    "study",
    "research",
}

FIELDNAMES = [
    "gap_candidate_id",
    "validation_id",
    "laureate_id",
    "full_name",
    "award_year",
    "category",
    "reference_candidate_id",
    "reference_text",
    "detected_years",
    "detected_doi",
    "ranking_score",
    "ranking_tier",
    "crossref_status",
    "crossref_doi",
    "crossref_title",
    "crossref_year",
    "crossref_journal",
    "crossref_type",
    "crossref_score",
    "crossref_match_note",
    "openalex_status",
    "openalex_work_id",
    "openalex_title",
    "openalex_year",
    "openalex_source",
    "openalex_source_id",
    "issn_l",
    "openalex_type",
    "openalex_doi",
    "metadata_match_confidence",
    "metadata_match_method",
    "review_status",
    "notes",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.replace("\u00df", "ss").replace("\u00f8", "o").replace("\u00d8", "O")
    value = re.sub(r"https?://\S+", " ", value)
    value = re.sub(r"[^0-9A-Za-z]+", " ", value)
    return re.sub(r"\s+", " ", value).strip().casefold()


def tokens(value: str) -> set[str]:
    return {tok for tok in normalize_text(value).split() if len(tok) >= 3 and tok not in STOPWORDS}


def clean_doi(value: str) -> str:
    value = (value or "").strip().rstrip(".,;:)")
    value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value, flags=re.IGNORECASE)
    return value.lower()


def years_from_ref(value: str) -> set[str]:
    return sorted(set(match.group(0) for match in YEAR_RE.finditer(value or "")))


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


def cache_path(source: str, url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    return CACHE_DIR / source / f"{digest}.json"


def request_json(
    source: str,
    url: str,
    retries: int = 2,
    delay: float = 0.25,
    timeout: float = 25.0,
) -> dict[str, Any]:
    path = cache_path(source, url)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    headers = {"User-Agent": "nobel-key-papers-full-collection/0.1 (gap metadata matching)"}
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


def crossref_query_url(reference_text: str, rows: int = 5) -> str:
    params = {
        "query.bibliographic": reference_text[:1000],
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


def openalex_search_url(query: str) -> str:
    params = {"search": query[:500], "per-page": "5"}
    mailto = os.environ.get("OPENALEX_MAILTO", "")
    if mailto:
        params["mailto"] = mailto
    api_key = os.environ.get("OPENALEX_API_KEY", "")
    if api_key:
        params["api_key"] = api_key
    return OPENALEX_WORKS + "?" + urllib.parse.urlencode(params)


def candidate_search_queries(reference_text: str) -> list[str]:
    text = re.sub(r"\s+", " ", reference_text or "").strip()
    queries: list[str] = []
    patterns = [
        r"\),\s*([^,]{25,220}?),\s*(?:Phys\.|Physical Review|Nature|Science|Cell|Lancet|PNAS|Proc\.|Rev\.)",
        r"\.\s*([^\.]{25,220}?)\.\s*(?:Nature|Science|Cell|Lancet|PNAS|Physical Review|Phys\.|Proc\.|Rev\.)",
        r"\.\s*([^\.]{25,220}?),\s*(?:Phys\.|Physical Review|Nature|Science|Cell|Lancet|PNAS|Proc\.|Rev\.)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            candidate = match.group(1).strip(" .,;:")
            if len(tokens(candidate)) >= 4 and candidate not in queries:
                queries.append(candidate)
    if text not in queries:
        queries.append(text)
    return queries[:4]


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
    note = (
        f"title_overlap={title_overlap:.2f}; source_overlap={source_overlap:.2f}; "
        f"year_match={year_match}; doi_match={doi_match}"
    )
    return score, note


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
    doi_match = bool(ref_doi and doi and ref_doi == doi)
    if doi_match:
        return "A", "crossref_exact_doi", "metadata_matched"
    if title_overlap >= 0.75 and year_match:
        return "A", "crossref_title_year_high_overlap", "metadata_matched"
    if title_overlap >= 0.60 and year_match:
        return "B", "crossref_title_year_medium_overlap", "needs_review"
    if title_overlap >= 0.45 and (year_match or "source_overlap=1.00" in note):
        return "C", "crossref_partial_overlap", "needs_review"
    return "D", "crossref_low_overlap", "no_match"


def extract_openalex(payload: dict[str, Any]) -> dict[str, str]:
    results = payload.get("results") or []
    if not results:
        return {
            "openalex_status": "no_openalex_result",
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
        "openalex_status": "matched_openalex_doi",
        "openalex_work_id": str(work.get("id") or ""),
        "openalex_title": str(work.get("title") or ""),
        "openalex_year": str(work.get("publication_year") or ""),
        "openalex_source": str(source.get("display_name") or ""),
        "openalex_source_id": str(source.get("id") or ""),
        "issn_l": str(source.get("issn_l") or ""),
        "openalex_type": str(work.get("type") or ""),
        "openalex_doi": clean_doi(str(work.get("doi") or "")),
    }


def score_openalex_work(ref_text: str, ref_years: set[str], work: dict[str, Any]) -> tuple[float, str]:
    title = str(work.get("title") or "")
    source = (((work.get("primary_location") or {}).get("source") or {}).get("display_name") or "")
    year = str(work.get("publication_year") or "")
    title_tokens = tokens(title)
    ref_tokens = tokens(ref_text)
    title_overlap = len(title_tokens & ref_tokens) / len(title_tokens) if title_tokens else 0.0
    source_tokens = tokens(source)
    source_overlap = len(source_tokens & ref_tokens) / len(source_tokens) if source_tokens else 0.0
    year_match = bool(year and year in ref_years)
    score = 0.0
    if work.get("type") == "article":
        score += 10
    if year_match:
        score += 20
    score += 70 * title_overlap
    if source_overlap >= 0.5:
        score += 10
    note = f"openalex_title_overlap={title_overlap:.2f}; openalex_source_overlap={source_overlap:.2f}; openalex_year_match={year_match}"
    return score, note


def choose_openalex_work(ref_text: str, ref_years: set[str], payload: dict[str, Any]) -> tuple[dict[str, Any], str, float]:
    best: dict[str, Any] = {}
    best_note = ""
    best_score = -1.0
    for work in payload.get("results") or []:
        score, note = score_openalex_work(ref_text, ref_years, work)
        if score > best_score:
            best = work
            best_note = note
            best_score = score
    return best, best_note, best_score


def openalex_work_to_row(work: dict[str, Any], status: str) -> dict[str, str]:
    source = ((work.get("primary_location") or {}).get("source") or {})
    return {
        "openalex_status": status,
        "openalex_work_id": str(work.get("id") or ""),
        "openalex_title": str(work.get("title") or ""),
        "openalex_year": str(work.get("publication_year") or ""),
        "openalex_source": str(source.get("display_name") or ""),
        "openalex_source_id": str(source.get("id") or ""),
        "issn_l": str(source.get("issn_l") or ""),
        "openalex_type": str(work.get("type") or ""),
        "openalex_doi": clean_doi(str(work.get("doi") or "")),
    }


def match_rows(limit: int | None = None) -> dict[str, Any]:
    input_rows = [
        row
        for row in read_csv(INPUT_CSV)
        if row.get("ranking_tier") == "A_high_priority_official_gap_candidate"
    ]
    if limit is not None:
        input_rows = input_rows[:limit]

    output_rows: list[dict[str, str]] = []
    errors = 0
    for row in input_rows:
        ref_text = row.get("reference_text", "")
        ref_doi = clean_doi(row.get("detected_doi") or first(DOI_RE.findall(ref_text)))
        ref_years = set(years_from_ref(row.get("detected_years", "") + " " + ref_text))
        crossref_item: dict[str, Any] = {}
        crossref_note = ""
        crossref_score = -1.0
        crossref_status = "not_queried"
        openalex = extract_openalex({})
        notes = []

        try:
            payload = request_json("crossref_gap_a_tier", crossref_query_url(ref_text))
            items = ((payload.get("message") or {}).get("items") or [])
            crossref_item, crossref_note, crossref_score = choose_crossref_item(ref_text, ref_years, ref_doi, items)
            crossref_status = "matched_crossref_candidate" if crossref_item else "no_crossref_candidate"
        except Exception as exc:  # noqa: BLE001
            errors += 1
            crossref_status = "crossref_error"
            notes.append(f"crossref_error={type(exc).__name__}: {exc}")

        crossref_doi = clean_doi(str(crossref_item.get("DOI") or ""))
        if crossref_doi:
            try:
                openalex = extract_openalex(request_json("openalex_gap_a_tier_doi", openalex_doi_url(crossref_doi)))
            except Exception as exc:  # noqa: BLE001
                errors += 1
                openalex = extract_openalex({})
                openalex["openalex_status"] = "openalex_error"
                notes.append(f"openalex_error={type(exc).__name__}: {exc}")
        else:
            openalex["openalex_status"] = "not_queried_no_doi"

        conf, method, review_status = confidence(ref_text, ref_years, ref_doi, crossref_item, crossref_note)
        openalex_search_note = ""
        if conf == "D":
            for query in candidate_search_queries(ref_text):
                try:
                    search_payload = request_json("openalex_gap_a_tier_search", openalex_search_url(query), delay=0.25)
                    search_work, openalex_search_note, openalex_search_score = choose_openalex_work(ref_text, ref_years, search_payload)
                    if search_work:
                        title = str(search_work.get("title") or "")
                        title_tokens = tokens(title)
                        ref_tokens = tokens(ref_text)
                        title_overlap = len(title_tokens & ref_tokens) / len(title_tokens) if title_tokens else 0.0
                        year = str(search_work.get("publication_year") or "")
                        year_match = bool(year and year in ref_years)
                        if title_overlap >= 0.75 and year_match:
                            openalex = openalex_work_to_row(search_work, "matched_openalex_search")
                            conf, method, review_status = "A", "openalex_search_title_year_high_overlap", "metadata_matched_needs_official_alignment"
                            break
                        if title_overlap >= 0.60 and year_match:
                            openalex = openalex_work_to_row(search_work, "matched_openalex_search")
                            conf, method, review_status = "B", "openalex_search_title_year_medium_overlap", "metadata_candidate_needs_review"
                            break
                        if openalex_search_score >= 65 and year_match:
                            openalex = openalex_work_to_row(search_work, "matched_openalex_search_low_confidence")
                            conf, method, review_status = "C", "openalex_search_partial_overlap", "metadata_candidate_needs_review"
                            break
                except Exception as exc:  # noqa: BLE001
                    errors += 1
                    notes.append(f"openalex_search_error={type(exc).__name__}: {exc}")
                    continue
        if openalex.get("openalex_status") == "matched_openalex_doi" and conf in {"A", "B"}:
            review_status = "metadata_matched_needs_official_alignment"
        elif conf in {"A", "B", "C"}:
            review_status = "metadata_candidate_needs_review"

        output_rows.append(
            {
                "gap_candidate_id": row.get("gap_candidate_id", ""),
                "validation_id": row.get("validation_id", ""),
                "laureate_id": row.get("laureate_id", ""),
                "full_name": row.get("full_name", ""),
                "award_year": row.get("award_year", ""),
                "category": row.get("category", ""),
                "reference_candidate_id": row.get("reference_candidate_id", ""),
                "reference_text": ref_text,
                "detected_years": row.get("detected_years", ""),
                "detected_doi": ref_doi,
                "ranking_score": row.get("ranking_score", ""),
                "ranking_tier": row.get("ranking_tier", ""),
                "crossref_status": crossref_status,
                "crossref_doi": crossref_doi,
                "crossref_title": first(crossref_item.get("title")),
                "crossref_year": crossref_year(crossref_item),
                "crossref_journal": first(crossref_item.get("container-title")),
                "crossref_type": str(crossref_item.get("type") or ""),
                "crossref_score": "" if crossref_score < 0 else f"{crossref_score:.2f}",
                "crossref_match_note": " | ".join(note for note in (crossref_note, openalex_search_note) if note),
                "openalex_status": openalex.get("openalex_status", ""),
                "openalex_work_id": openalex.get("openalex_work_id", ""),
                "openalex_title": openalex.get("openalex_title", ""),
                "openalex_year": openalex.get("openalex_year", ""),
                "openalex_source": openalex.get("openalex_source", ""),
                "openalex_source_id": openalex.get("openalex_source_id", ""),
                "issn_l": openalex.get("issn_l", ""),
                "openalex_type": openalex.get("openalex_type", ""),
                "openalex_doi": openalex.get("openalex_doi", ""),
                "metadata_match_confidence": conf,
                "metadata_match_method": method,
                "review_status": review_status,
                "notes": " | ".join(notes),
            }
        )

    write_csv(OUT_CSV, output_rows)
    summary = {
        "input_a_tier_rows": len(input_rows),
        "output_rows": len(output_rows),
        "errors": errors,
        "by_crossref_status": dict(Counter(row["crossref_status"] for row in output_rows)),
        "by_openalex_status": dict(Counter(row["openalex_status"] for row in output_rows)),
        "by_metadata_match_confidence": dict(Counter(row["metadata_match_confidence"] for row in output_rows)),
        "by_review_status": dict(Counter(row["review_status"] for row in output_rows)),
        "output": str(OUT_CSV),
    }
    OUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    append_query_log(summary)
    return summary


def append_query_log(summary: dict[str, Any]) -> None:
    if not QUERY_LOG.exists():
        return
    fieldnames = [
        "query_id",
        "run_at",
        "phase",
        "source",
        "query_or_url",
        "parameters",
        "output_path",
        "status",
        "notes",
    ]
    row = {
        "query_id": "match_gap_a_tier_references_metadata",
        "run_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "phase": "full_collection",
        "source": "Crossref; OpenAlex",
        "query_or_url": str(INPUT_CSV),
        "parameters": "ranking_tier=A only; Crossref bibliographic query; OpenAlex exact DOI lookup; cached",
        "output_path": str(OUT_CSV),
        "status": "ok" if not summary["errors"] else "partial",
        "notes": (
            f"rows={summary['output_rows']}; "
            f"errors={summary['errors']}; "
            f"A={summary['by_metadata_match_confidence'].get('A', 0)}"
        ),
    }
    with QUERY_LOG.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    summary = match_rows(args.limit)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
