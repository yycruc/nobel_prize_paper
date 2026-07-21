from __future__ import annotations

import csv
import datetime as dt
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_CSV = ROOT / "01_validation" / "validation_sample.csv"
LI2019_TAB = ROOT / "01_validation" / "01_raw_sources" / "public_datasets" / "li_2019_prize_winning_paper_record.tab"
OUT_CSV = ROOT / "01_validation" / "02_candidate_key_papers" / "key_paper_candidates_validation.csv"
OUT_REPORT = ROOT / "01_validation" / "04_outputs" / "li2019_candidate_coverage_report.json"
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"


FIELD_MAP = {
    "Physics": "Physics",
    "Chemistry": "Chemistry",
    "Physiology or Medicine": "Medicine",
}


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text or "")
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    ascii_text = ascii_text.lower()
    ascii_text = ascii_text.replace("'", "")
    ascii_text = re.sub(r"[^a-z0-9]+", " ", ascii_text)
    return re.sub(r"\s+", " ", ascii_text).strip()


def likely_family_names(full_name: str) -> set[str]:
    text = normalize(full_name)
    parts = text.split()
    if not parts:
        return set()
    names = {parts[-1]}
    if len(parts) >= 2:
        names.add(" ".join(parts[-2:]))
    if len(parts) >= 3:
        names.add(" ".join(parts[-3:]))
    for particle in ("de", "van", "von"):
        if particle in parts:
            idx = parts.index(particle)
            names.add(" ".join(parts[idx:]))
    return names


def li_family_name(li_name: str) -> str:
    raw = li_name or ""
    if "," in raw:
        return normalize(raw.split(",")[0])
    parts = normalize(raw).split()
    if not parts:
        return ""
    if len(parts) >= 2 and len(parts[-1]) <= 3 and len(parts[0]) > 3:
        return parts[0]
    return parts[-1]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def read_li2019(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def matched_li_rows(sample_row: dict[str, str], li_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    field = FIELD_MAP[sample_row["category"]]
    award_year = sample_row["award_year"]
    family_candidates = likely_family_names(sample_row["full_name"])
    matches: list[dict[str, str]] = []
    for row in li_rows:
        if row.get("Field") != field or row.get("Prize year") != award_year:
            continue
        li_last = li_family_name(row.get("Laureate name", ""))
        if li_last in family_candidates or any(li_last and li_last in candidate for candidate in family_candidates):
            matches.append(row)
    return matches


def write_candidates(rows: list[dict[str, str]]) -> None:
    fields = [
        "candidate_id",
        "validation_id",
        "laureate_id",
        "award_year",
        "category",
        "candidate_title",
        "candidate_year",
        "candidate_journal",
        "candidate_doi",
        "candidate_pmid",
        "source_name",
        "source_url_or_path",
        "key_paper_role",
        "notes",
    ]
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def append_query_log(rows: int, covered: int) -> None:
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
                "query_id": "build_validation_candidates_from_li2019",
                "run_at": dt.datetime.now(dt.UTC).isoformat(),
                "phase": "validation",
                "source": "Li et al. 2019 Prize-winning paper record",
                "query_or_url": str(LI2019_TAB),
                "parameters": "match by category/prize year/family name",
                "output_path": str(OUT_CSV),
                "status": "ok",
                "notes": f"candidate_rows={rows}; covered_sample_records={covered}",
            }
        )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    sample = read_csv(SAMPLE_CSV)
    li_rows = read_li2019(LI2019_TAB)

    out_rows: list[dict[str, str]] = []
    coverage: dict[str, int] = {}
    misses: list[dict[str, str]] = []
    counter = 1
    for sample_row in sample:
        matches = matched_li_rows(sample_row, li_rows)
        coverage[sample_row["validation_id"]] = len(matches)
        if not matches:
            misses.append(
                {
                    "validation_id": sample_row["validation_id"],
                    "full_name": sample_row["full_name"],
                    "award_year": sample_row["award_year"],
                    "category": sample_row["category"],
                    "reason": "not covered by Li2019 or name match failed",
                }
            )
            continue
        for match in matches:
            out_rows.append(
                {
                    "candidate_id": f"LI2019_{counter:04d}",
                    "validation_id": sample_row["validation_id"],
                    "laureate_id": sample_row["laureate_id"],
                    "award_year": sample_row["award_year"],
                    "category": sample_row["category"],
                    "candidate_title": match.get("Title", ""),
                    "candidate_year": match.get("Pub year", ""),
                    "candidate_journal": "",
                    "candidate_doi": "",
                    "candidate_pmid": "",
                    "source_name": "Li et al. 2019 Prize-winning paper record",
                    "source_url_or_path": str(LI2019_TAB),
                    "key_paper_role": "key_paper_set",
                    "notes": f"MAG Paper ID={match.get('Paper ID', '')}; Li2019 Laureate name={match.get('Laureate name', '')}; {match.get('Additional information', '')}",
                }
            )
            counter += 1

    write_candidates(out_rows)
    covered = sum(1 for count in coverage.values() if count > 0)
    by_cell = Counter()
    for row in sample:
        by_cell[f"{row['category']}|{row['period_bucket']}"] += 1

    report = {
        "sample_records": len(sample),
        "covered_sample_records": covered,
        "candidate_rows": len(out_rows),
        "coverage_rate": covered / len(sample) if sample else 0,
        "misses": misses,
        "sample_cell_counts": dict(sorted(by_cell.items())),
    }
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    append_query_log(len(out_rows), covered)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
