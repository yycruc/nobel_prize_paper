from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GAP_QUEUE = ROOT / "02_full_collection" / "03_matched_metadata" / "official_alignment_gap_queue_full.csv"
OFFICIAL_REFERENCES = ROOT / "02_full_collection" / "02_candidate_key_papers" / "official_reference_classification_full.csv"
OUT_CSV = ROOT / "02_full_collection" / "02_candidate_key_papers" / "official_gap_reference_candidates_full.csv"
OUT_NO_REF_QUEUE = ROOT / "02_full_collection" / "03_matched_metadata" / "official_gap_no_reference_queue_full.csv"
OUT_SUMMARY = ROOT / "02_full_collection" / "05_outputs" / "official_gap_reference_candidates_summary_full.json"
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"


USABLE_CLASSES = {
    "doi_present",
    "likely_journal_article",
    "historical_nonindexed_reference",
    "needs_manual_review",
}

BOILERPLATE_PATTERNS = (
    "additional information on this year s prizes",
    "delivered in stockholm",
    "nobel lecture entitled",
    "the royal swedish academy of sciences has decided to award",
    "science editors",
    "nobelprizemuseum",
    "nobel prize outreach",
)

STOPWORDS = {
    "about",
    "after",
    "against",
    "also",
    "among",
    "analysis",
    "and",
    "application",
    "are",
    "been",
    "being",
    "between",
    "case",
    "chapter",
    "chemical",
    "chemistry",
    "contribution",
    "de",
    "der",
    "des",
    "die",
    "discovery",
    "during",
    "effects",
    "for",
    "from",
    "has",
    "have",
    "his",
    "into",
    "its",
    "new",
    "not",
    "one",
    "paper",
    "part",
    "physics",
    "physiology",
    "recognition",
    "research",
    "services",
    "some",
    "study",
    "the",
    "their",
    "there",
    "this",
    "through",
    "und",
    "using",
    "was",
    "were",
    "which",
    "with",
    "work",
}

FIELDNAMES = [
    "gap_candidate_id",
    "validation_id",
    "laureate_id",
    "full_name",
    "award_year",
    "category",
    "record_alignment_status",
    "reference_candidate_id",
    "pdf_type",
    "reference_class",
    "reference_text",
    "detected_doi",
    "detected_years",
    "candidate_year_for_ranking",
    "year_relation_to_award",
    "motivation_overlap_count",
    "motivation_overlap_terms",
    "laureate_name_in_reference",
    "ranking_score",
    "ranking_tier",
    "metadata_next_action",
    "official_alignment_next_action",
    "dedupe_fingerprint",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def normalize_text(text: str) -> str:
    text = html.unescape(text or "")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().replace("ß", "ss")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokenize(text: str) -> list[str]:
    out = []
    for token in normalize_text(text).split():
        if token in STOPWORDS:
            continue
        if len(token) < 4 and not token.isdigit():
            continue
        out.append(token)
    return out


def parse_years(text: str) -> list[int]:
    years = []
    for match in re.findall(r"\b(18[0-9]{2}|19[0-9]{2}|20[0-2][0-9])\b", text or ""):
        year = int(match)
        if 1800 <= year <= 2026:
            years.append(year)
    return sorted(set(years))


def family_name_tokens(full_name: str) -> set[str]:
    tokens = tokenize(full_name)
    if not tokens:
        return set()
    names = {tokens[-1]}
    particles = {"van", "von", "de", "del", "der", "du"}
    for idx, token in enumerate(tokens):
        if token in particles and idx + 1 < len(tokens):
            names.add(tokens[idx + 1])
    return names


def fingerprint(text: str) -> str:
    normalized = normalize_text(text)
    return normalized[:240]


def is_boilerplate_reference(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return True
    hits = sum(1 for pattern in BOILERPLATE_PATTERNS if pattern in normalized)
    if hits >= 2:
        return True
    if (
        "additional information on this year s prizes" in normalized
        and "nobel lectures" in normalized
        and "press conferences" in normalized
    ):
        return True
    if "nobel lecture entitled" in normalized or "delivered in stockholm" in normalized:
        return True
    return False


def candidate_year_for_award(years: list[int], award_year: int) -> int | None:
    before_or_at = [year for year in years if year <= award_year]
    if before_or_at:
        return max(before_or_at)
    if years:
        return min(years)
    return None


def score_reference(
    gap_row: dict[str, str],
    ref_row: dict[str, str],
    motivation_tokens: set[str],
    name_tokens: set[str],
) -> dict[str, object]:
    award_year = int(gap_row["award_year"])
    ref_text = ref_row.get("reference_text", "")
    years = parse_years(ref_row.get("detected_years", "") + " " + ref_text)
    candidate_year = candidate_year_for_award(years, award_year)
    ref_tokens = set(tokenize(ref_text))
    overlap = sorted(ref_tokens & motivation_tokens)
    name_overlap = bool(ref_tokens & name_tokens)
    reference_class = ref_row.get("reference_class", "")
    pdf_type = ref_row.get("pdf_type", "")
    score = 0

    if reference_class == "doi_present":
        score += 8
    elif reference_class == "likely_journal_article":
        score += 6
    elif reference_class == "historical_nonindexed_reference":
        score += 5
    elif reference_class == "needs_manual_review":
        score += 2

    if pdf_type == "scientific_background":
        score += 4
    elif "lecture" in pdf_type:
        score += 2

    if candidate_year is not None:
        if candidate_year <= award_year:
            score += 5
            lag = award_year - candidate_year
            if lag <= 5:
                score += 2
            elif lag <= 25:
                score += 1
        else:
            score -= 5

    score += min(len(overlap), 6) * 2
    if name_overlap:
        score += 3
    if ref_row.get("detected_doi", ""):
        score += 3

    if candidate_year is None:
        relation = "no_year_detected"
    elif candidate_year <= award_year:
        relation = "before_or_at_award"
    else:
        relation = "after_award"

    if score >= 22:
        tier = "A_high_priority_official_gap_candidate"
    elif score >= 14:
        tier = "B_reviewable_official_gap_candidate"
    elif score >= 7:
        tier = "C_low_signal_official_gap_candidate"
    else:
        tier = "D_hold_for_manual_triage"

    if reference_class == "doi_present":
        metadata_next = "Exact DOI lookup, then official relevance review."
    elif reference_class == "likely_journal_article":
        metadata_next = "Parse title/journal/year and run conservative OpenAlex/Crossref metadata lookup."
    elif reference_class == "historical_nonindexed_reference":
        metadata_next = "Use historical bibliography or manual source verification."
    else:
        metadata_next = "Manual triage before API matching."

    return {
        "candidate_year": candidate_year,
        "relation": relation,
        "overlap": overlap,
        "name_overlap": name_overlap,
        "score": score,
        "tier": tier,
        "metadata_next": metadata_next,
    }


def build_candidates() -> dict[str, object]:
    gap_rows = read_csv(GAP_QUEUE)
    refs = read_csv(OFFICIAL_REFERENCES)
    gap_by_id = {row["validation_id"]: row for row in gap_rows}
    refs_by_record: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in refs:
        validation_id = row.get("validation_id", "")
        if validation_id in gap_by_id and row.get("reference_class", "") in USABLE_CLASSES:
            refs_by_record[validation_id].append(row)

    out_rows: list[dict[str, str]] = []
    no_ref_rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for validation_id, gap_row in sorted(gap_by_id.items()):
        motivation_tokens = set(tokenize(gap_row.get("motivation", "")))
        name_tokens = family_name_tokens(gap_row.get("full_name", ""))
        record_refs = refs_by_record.get(validation_id, [])
        record_candidates = []
        for ref_row in record_refs:
            if is_boilerplate_reference(ref_row.get("reference_text", "")):
                continue
            fp = fingerprint(ref_row.get("reference_text", ""))
            key = (validation_id, fp)
            if key in seen:
                continue
            seen.add(key)
            scored = score_reference(gap_row, ref_row, motivation_tokens, name_tokens)
            record_candidates.append((scored["score"], ref_row.get("reference_candidate_id", ""), ref_row, scored, fp))

        if not record_candidates:
            no_ref_rows.append(gap_row)
            continue

        record_candidates.sort(key=lambda item: (-int(item[0]), item[1]))
        for _, _, ref_row, scored, fp in record_candidates:
            out_rows.append(
                {
                    "gap_candidate_id": f"GAPOFFREF_{len(out_rows) + 1:06d}",
                    "validation_id": validation_id,
                    "laureate_id": gap_row.get("laureate_id", ""),
                    "full_name": gap_row.get("full_name", ""),
                    "award_year": gap_row.get("award_year", ""),
                    "category": gap_row.get("category", ""),
                    "record_alignment_status": gap_row.get("record_alignment_status", ""),
                    "reference_candidate_id": ref_row.get("reference_candidate_id", ""),
                    "pdf_type": ref_row.get("pdf_type", ""),
                    "reference_class": ref_row.get("reference_class", ""),
                    "reference_text": ref_row.get("reference_text", ""),
                    "detected_doi": ref_row.get("detected_doi", ""),
                    "detected_years": ref_row.get("detected_years", ""),
                    "candidate_year_for_ranking": "" if scored["candidate_year"] is None else str(scored["candidate_year"]),
                    "year_relation_to_award": str(scored["relation"]),
                    "motivation_overlap_count": str(len(scored["overlap"])),
                    "motivation_overlap_terms": "; ".join(scored["overlap"]),
                    "laureate_name_in_reference": "yes" if scored["name_overlap"] else "no",
                    "ranking_score": str(scored["score"]),
                    "ranking_tier": str(scored["tier"]),
                    "metadata_next_action": str(scored["metadata_next"]),
                    "official_alignment_next_action": "After metadata resolution, compare candidate work to Nobel official contribution language.",
                    "dedupe_fingerprint": fp,
                }
            )

    write_csv(OUT_CSV, out_rows, FIELDNAMES)
    write_csv(OUT_NO_REF_QUEUE, no_ref_rows, list(gap_rows[0].keys()) if gap_rows else [])

    records_with_candidates = {row["validation_id"] for row in out_rows}
    summary = {
        "gap_records": len(gap_rows),
        "gap_records_with_official_reference_candidates": len(records_with_candidates),
        "gap_records_without_usable_official_references": len(no_ref_rows),
        "official_gap_reference_candidate_rows": len(out_rows),
        "by_category": dict(Counter(row["category"] for row in out_rows)),
        "by_reference_class": dict(Counter(row["reference_class"] for row in out_rows)),
        "by_ranking_tier": dict(Counter(row["ranking_tier"] for row in out_rows)),
        "by_record_alignment_status": dict(Counter(row["record_alignment_status"] for row in out_rows)),
        "output": str(OUT_CSV),
        "no_reference_queue_output": str(OUT_NO_REF_QUEUE),
    }
    OUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    append_query_log(summary)
    return summary


def append_query_log(summary: dict[str, object]) -> None:
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
        "query_id": "build_gap_official_reference_candidates",
        "run_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "phase": "full_collection",
        "source": "Nobel official PDF reference classifications",
        "query_or_url": f"{GAP_QUEUE}; {OFFICIAL_REFERENCES}",
        "parameters": "gap records only; dedupe exact reference text; score by reference class/year/motivation/name/PDF type; no network calls",
        "output_path": str(OUT_CSV),
        "status": "ok",
        "notes": (
            f"gap_records={summary['gap_records']}; "
            f"candidate_rows={summary['official_gap_reference_candidate_rows']}; "
            f"records_with_candidates={summary['gap_records_with_official_reference_candidates']}"
        ),
    }
    with QUERY_LOG.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary-only", action="store_true")
    parser.parse_args()
    summary = build_candidates()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
