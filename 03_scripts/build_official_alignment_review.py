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
BASELINE_CSV = ROOT / "02_full_collection" / "01_raw_sources" / "nobel_api" / "nobel_award_baseline_full.csv"
CANDIDATE_REGISTRY = ROOT / "02_full_collection" / "03_matched_metadata" / "candidate_registry_full.csv"
PRIMARY_CLUES = ROOT / "02_full_collection" / "02_candidate_key_papers" / "official_page_bibliographic_clues_full.csv"
SECONDARY_CLUES = ROOT / "02_full_collection" / "02_candidate_key_papers" / "official_secondary_page_bibliographic_clues_full.csv"
OUT_CSV = ROOT / "02_full_collection" / "03_matched_metadata" / "official_alignment_review_full.csv"
OUT_RECORD_SUMMARY = ROOT / "02_full_collection" / "03_matched_metadata" / "official_alignment_record_summary_full.csv"
OUT_GAP_QUEUE = ROOT / "02_full_collection" / "03_matched_metadata" / "official_alignment_gap_queue_full.csv"
OUT_SUMMARY = ROOT / "02_full_collection" / "05_outputs" / "official_alignment_review_summary_full.json"
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"


STOPWORDS = {
    "about",
    "after",
    "against",
    "also",
    "among",
    "analysis",
    "and",
    "are",
    "been",
    "between",
    "case",
    "containing",
    "contribution",
    "demonstration",
    "der",
    "des",
    "die",
    "das",
    "during",
    "effect",
    "effects",
    "eine",
    "from",
    "has",
    "have",
    "into",
    "its",
    "new",
    "not",
    "observations",
    "one",
    "part",
    "paper",
    "research",
    "some",
    "study",
    "the",
    "their",
    "there",
    "this",
    "through",
    "uber",
    "ueber",
    "und",
    "using",
    "was",
    "were",
    "with",
}


FIELDNAMES = [
    "registry_id",
    "validation_id",
    "laureate_id",
    "full_name",
    "award_year",
    "category",
    "title",
    "publication_year",
    "journal",
    "doi",
    "openalex_work_id",
    "candidate_year",
    "award_lag_years",
    "evidence_sources",
    "registry_status",
    "metadata_match_confidence",
    "metadata_match_methods",
    "motivation",
    "official_pages_available",
    "official_pdf_links_available",
    "official_snippet_count",
    "official_source_pages",
    "top_official_snippets",
    "title_keyword_count",
    "official_overlap_count",
    "official_overlap_terms",
    "motivation_overlap_count",
    "motivation_overlap_terms",
    "candidate_year_mentioned_in_official_text",
    "alignment_signal",
    "alignment_review_priority",
    "alignment_next_action",
    "final_acceptance_status",
    "alignment_notes",
]


RECORD_FIELDNAMES = [
    "validation_id",
    "laureate_id",
    "full_name",
    "award_year",
    "category",
    "motivation",
    "registry_rows",
    "metadata_ready_rows",
    "official_reference_rows",
    "li2019_rows",
    "high_signal_rows",
    "medium_signal_rows",
    "weak_signal_rows",
    "no_signal_rows",
    "metadata_unresolved_rows",
    "official_snippet_count",
    "official_pages_available",
    "official_pdf_links_available",
    "record_alignment_status",
    "record_next_action",
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
    text = re.sub(r"<[^>]+>", " ", text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = text.replace("ß", "ss")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokenize(text: str) -> list[str]:
    normalized = normalize_text(text)
    tokens = []
    for token in normalized.split():
        if token in STOPWORDS:
            continue
        if len(token) < 4 and not token.isdigit():
            continue
        tokens.append(token)
    return tokens


def unique_tokens(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for token in tokenize(text):
        if token not in seen:
            seen.add(token)
            out.append(token)
    return out


def clipped(text: str, limit: int = 300) -> str:
    text = re.sub(r"\s+", " ", html.unescape(text or "")).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def build_official_context() -> dict[str, dict[str, object]]:
    baseline = {row["validation_id"]: row for row in read_csv(BASELINE_CSV)}
    context: dict[str, dict[str, object]] = {}
    for validation_id, row in baseline.items():
        context[validation_id] = {
            "baseline": row,
            "snippets": [],
            "source_pages": [],
            "pdf_links": [],
        }

    for path in (PRIMARY_CLUES, SECONDARY_CLUES):
        for row in read_csv(path):
            validation_id = row.get("validation_id", "")
            if not validation_id:
                continue
            ctx = context.setdefault(
                validation_id,
                {"baseline": {}, "snippets": [], "source_pages": [], "pdf_links": []},
            )
            source_page = row.get("source_page", "")
            clue_type = row.get("clue_type", "")
            clue_text = row.get("clue_text", "")
            href = row.get("href", "")
            if source_page and source_page not in ctx["source_pages"]:
                ctx["source_pages"].append(source_page)
            if clue_type == "pdf_link" and href:
                if href not in ctx["pdf_links"]:
                    ctx["pdf_links"].append(href)
            elif clue_text:
                ctx["snippets"].append(
                    {
                        "target_type": row.get("target_type", ""),
                        "clue_type": clue_type,
                        "text": clue_text,
                        "source_page": source_page,
                    }
                )
    return context


def select_top_snippets(snippets: list[dict[str, str]], overlap_terms: set[str], limit: int = 3) -> list[str]:
    scored = []
    for snippet in snippets:
        text = snippet.get("text", "")
        tokens = set(tokenize(text))
        score = len(tokens & overlap_terms)
        if snippet.get("target_type") in {"secondary_lecture", "secondary_biographical", "facts", "advanced-information"}:
            score += 1
        scored.append((score, len(text), snippet))
    scored.sort(key=lambda item: (-item[0], item[1]))
    chosen = []
    for _, _, snippet in scored[:limit]:
        label = first_nonempty(snippet.get("target_type", ""), snippet.get("clue_type", ""), "official")
        chosen.append(f"[{label}] {clipped(snippet.get('text', ''))}")
    return chosen


def first_nonempty(*values: str) -> str:
    for value in values:
        if value and str(value).strip():
            return str(value).strip()
    return ""


def alignment_classification(
    row: dict[str, str],
    title_tokens: list[str],
    official_overlap: set[str],
    motivation_overlap: set[str],
    candidate_year_mentioned: bool,
) -> tuple[str, str, str, str]:
    registry_status = row.get("registry_status", "")
    evidence_sources = row.get("evidence_sources", "")

    if "metadata_unresolved" in registry_status:
        return (
            "metadata_unresolved",
            "P4",
            "Resolve identifier or bibliographic metadata before official alignment.",
            "Candidate has no exact metadata match yet.",
        )

    if "nobel_official_reference_doi" in evidence_sources:
        signal = "official_reference_present"
        if len(official_overlap) >= 2 or len(motivation_overlap) >= 1:
            signal = "official_reference_with_text_overlap"
        return (
            signal,
            "P2",
            "Review whether this official reference is a prize-winning key paper or contextual citation.",
            "Official Nobel reference and exact DOI metadata are present; relevance is not yet final.",
        )

    token_count = max(len(title_tokens), 1)
    overlap_ratio = len(official_overlap) / token_count
    if len(motivation_overlap) >= 2 or len(official_overlap) >= 4 or (len(official_overlap) >= 3 and candidate_year_mentioned):
        return (
            "strong_official_text_overlap",
            "P1",
            "Manually verify as likely key-paper candidate against official Nobel contribution text.",
            f"Title terms overlap official text strongly; overlap_ratio={overlap_ratio:.2f}.",
        )
    if len(motivation_overlap) >= 1 or len(official_overlap) >= 2:
        return (
            "moderate_official_text_overlap",
            "P2",
            "Review official snippets and candidate source side by side.",
            f"Some title terms overlap official text; overlap_ratio={overlap_ratio:.2f}.",
        )
    if len(official_overlap) == 1:
        return (
            "weak_official_text_overlap",
            "P3",
            "Keep in review queue; seek stronger official or bibliographic evidence.",
            f"Only one title term overlaps official text; overlap_ratio={overlap_ratio:.2f}.",
        )
    return (
        "no_automatic_alignment_signal",
        "P3",
        "Use targeted official reading or external historical bibliography for alignment.",
        "No reliable automatic title-term overlap with official text.",
    )


def build_review() -> dict[str, object]:
    context = build_official_context()
    registry_rows = read_csv(CANDIDATE_REGISTRY)
    out_rows: list[dict[str, str]] = []

    for row in registry_rows:
        validation_id = row.get("validation_id", "")
        ctx = context.get(validation_id, {"baseline": {}, "snippets": [], "source_pages": [], "pdf_links": []})
        baseline = ctx.get("baseline", {})
        motivation = baseline.get("motivation", "")
        snippets = ctx.get("snippets", [])
        source_pages = ctx.get("source_pages", [])
        pdf_links = ctx.get("pdf_links", [])

        title_tokens = unique_tokens(row.get("title", ""))
        official_text = " ".join([motivation] + [snippet.get("text", "") for snippet in snippets])
        official_tokens = set(tokenize(official_text))
        motivation_tokens = set(tokenize(motivation))
        title_token_set = set(title_tokens)
        official_overlap = title_token_set & official_tokens
        motivation_overlap = title_token_set & motivation_tokens
        candidate_year = first_nonempty(row.get("candidate_year", ""), row.get("publication_year", ""))
        candidate_year_mentioned = bool(candidate_year and re.search(rf"\b{re.escape(candidate_year)}\b", official_text))

        signal, priority, next_action, notes = alignment_classification(
            row,
            title_tokens,
            official_overlap,
            motivation_overlap,
            candidate_year_mentioned,
        )
        top_snippets = select_top_snippets(snippets, official_overlap, limit=3)

        out = {field: row.get(field, "") for field in FIELDNAMES}
        out.update(
            {
                "motivation": motivation,
                "official_pages_available": str(len(source_pages)),
                "official_pdf_links_available": str(len(pdf_links)),
                "official_snippet_count": str(len(snippets)),
                "official_source_pages": " || ".join(source_pages[:8]),
                "top_official_snippets": " || ".join(top_snippets),
                "title_keyword_count": str(len(title_tokens)),
                "official_overlap_count": str(len(official_overlap)),
                "official_overlap_terms": "; ".join(sorted(official_overlap)),
                "motivation_overlap_count": str(len(motivation_overlap)),
                "motivation_overlap_terms": "; ".join(sorted(motivation_overlap)),
                "candidate_year_mentioned_in_official_text": "yes" if candidate_year_mentioned else "no",
                "alignment_signal": signal,
                "alignment_review_priority": priority,
                "alignment_next_action": next_action,
                "final_acceptance_status": "not_final_review_required",
                "alignment_notes": notes,
            }
        )
        out_rows.append(out)

    write_csv(OUT_CSV, out_rows, FIELDNAMES)
    record_rows = build_record_summary(out_rows, context)
    write_csv(OUT_RECORD_SUMMARY, record_rows, RECORD_FIELDNAMES)
    gap_rows = [
        row
        for row in record_rows
        if row["record_alignment_status"] in {"no_candidate_registry_rows_yet", "only_metadata_unresolved_candidates"}
    ]
    write_csv(OUT_GAP_QUEUE, gap_rows, RECORD_FIELDNAMES)

    summary = {
        "input_registry_rows": len(registry_rows),
        "alignment_review_rows": len(out_rows),
        "record_summary_rows": len(record_rows),
        "gap_queue_rows": len(gap_rows),
        "records_with_registry_rows": len({row["validation_id"] for row in out_rows}),
        "baseline_records": len(context),
        "by_alignment_signal": dict(Counter(row["alignment_signal"] for row in out_rows)),
        "by_alignment_review_priority": dict(Counter(row["alignment_review_priority"] for row in out_rows)),
        "by_final_acceptance_status": dict(Counter(row["final_acceptance_status"] for row in out_rows)),
        "by_record_alignment_status": dict(Counter(row["record_alignment_status"] for row in record_rows)),
        "output": str(OUT_CSV),
        "record_summary_output": str(OUT_RECORD_SUMMARY),
        "gap_queue_output": str(OUT_GAP_QUEUE),
    }
    OUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    append_query_log(summary)
    return summary


def build_record_summary(
    alignment_rows: list[dict[str, str]],
    context: dict[str, dict[str, object]],
) -> list[dict[str, str]]:
    rows_by_record: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in alignment_rows:
        rows_by_record[row["validation_id"]].append(row)

    record_rows: list[dict[str, str]] = []
    for validation_id, ctx in sorted(context.items()):
        baseline = ctx.get("baseline", {})
        rows = rows_by_record.get(validation_id, [])
        counts = Counter(row["alignment_signal"] for row in rows)
        metadata_unresolved = sum(1 for row in rows if row["alignment_signal"] == "metadata_unresolved")
        metadata_ready = len(rows) - metadata_unresolved
        official_reference_rows = sum(1 for row in rows if "nobel_official_reference_doi" in row["evidence_sources"])
        li2019_rows = sum(1 for row in rows if "li2019_prize_winning_paper" in row["evidence_sources"])

        if not rows:
            status = "no_candidate_registry_rows_yet"
            next_action = "Create candidates from official narrative, targeted bibliography, or post-2016 sources."
        elif counts.get("strong_official_text_overlap", 0) or counts.get("official_reference_with_text_overlap", 0):
            status = "has_high_priority_alignment_candidates"
            next_action = "Review P1/P2 rows for final acceptance."
        elif metadata_ready:
            status = "has_metadata_candidates_needing_official_review"
            next_action = "Read official snippets and align candidate titles manually."
        else:
            status = "only_metadata_unresolved_candidates"
            next_action = "Resolve identifiers or historical bibliographic metadata first."

        record_rows.append(
            {
                "validation_id": validation_id,
                "laureate_id": baseline.get("laureate_id", ""),
                "full_name": baseline.get("full_name", ""),
                "award_year": baseline.get("award_year", ""),
                "category": baseline.get("category", ""),
                "motivation": baseline.get("motivation", ""),
                "registry_rows": str(len(rows)),
                "metadata_ready_rows": str(metadata_ready),
                "official_reference_rows": str(official_reference_rows),
                "li2019_rows": str(li2019_rows),
                "high_signal_rows": str(counts.get("strong_official_text_overlap", 0) + counts.get("official_reference_with_text_overlap", 0)),
                "medium_signal_rows": str(counts.get("moderate_official_text_overlap", 0) + counts.get("official_reference_present", 0)),
                "weak_signal_rows": str(counts.get("weak_official_text_overlap", 0)),
                "no_signal_rows": str(counts.get("no_automatic_alignment_signal", 0)),
                "metadata_unresolved_rows": str(metadata_unresolved),
                "official_snippet_count": str(len(ctx.get("snippets", []))),
                "official_pages_available": str(len(ctx.get("source_pages", []))),
                "official_pdf_links_available": str(len(ctx.get("pdf_links", []))),
                "record_alignment_status": status,
                "record_next_action": next_action,
            }
        )
    return record_rows


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
        "query_id": "build_official_alignment_review",
        "run_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "phase": "full_collection",
        "source": "Local Nobel official clues; local candidate registry",
        "query_or_url": f"{CANDIDATE_REGISTRY}; {PRIMARY_CLUES}; {SECONDARY_CLUES}",
        "parameters": "lexical title-to-official-text overlap; no final acceptance; no network calls",
        "output_path": str(OUT_CSV),
        "status": "ok",
        "notes": (
            f"rows={summary['alignment_review_rows']}; "
            f"records={summary['records_with_registry_rows']}; "
            f"baseline_records={summary['baseline_records']}"
        ),
    }
    with QUERY_LOG.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary-only", action="store_true")
    parser.parse_args()
    summary = build_review()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
