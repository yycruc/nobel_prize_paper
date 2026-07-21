from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import shutil
import sys
import unicodedata
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASELINE_CSV = ROOT / "02_full_collection" / "01_raw_sources" / "nobel_api" / "nobel_award_baseline_full.csv"
LI2019_SOURCE_TAB = ROOT / "01_validation" / "01_raw_sources" / "public_datasets" / "li_2019_prize_winning_paper_record.tab"
LI2019_FULL_TAB = ROOT / "02_full_collection" / "01_raw_sources" / "public_datasets" / "li_2019_prize_winning_paper_record.tab"
OUT_CSV = ROOT / "02_full_collection" / "02_candidate_key_papers" / "li2019_key_paper_candidates_full.csv"
OUT_REPORT = ROOT / "02_full_collection" / "05_outputs" / "li2019_candidate_coverage_report_full.json"
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"

FIELD_MAP = {
    "Physics": "Physics",
    "Chemistry": "Chemistry",
    "Physiology or Medicine": "Medicine",
}


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text or "")
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    ascii_text = ascii_text.lower().replace("'", "")
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
    for particle in ("de", "del", "du", "van", "von", "der", "zu"):
        if particle in parts:
            idx = parts.index(particle)
            names.add(" ".join(parts[idx:]))
    return names


def li_family_name(li_name: str) -> str:
    raw = li_name or ""
    if "," in raw:
        return normalize(raw.split(",", 1)[0])
    parts = normalize(raw).split()
    if not parts:
        return ""
    if len(parts) >= 2 and len(parts[-1]) <= 3 and len(parts[0]) > 3:
        return parts[0]
    return parts[-1]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def read_tab(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def copy_source_if_needed(source: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or dest.stat().st_size != source.stat().st_size:
        shutil.copyfile(source, dest)


def matched_li_rows(baseline_row: dict[str, str], li_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    field = FIELD_MAP[baseline_row["category"]]
    award_year = baseline_row["award_year"]
    family_candidates = likely_family_names(baseline_row["full_name"])
    matches: list[dict[str, str]] = []
    for row in li_rows:
        if row.get("Field") != field or row.get("Prize year") != award_year:
            continue
        li_last = li_family_name(row.get("Laureate name", ""))
        if li_last in family_candidates or any(li_last and li_last in candidate for candidate in family_candidates):
            matches.append(row)
    return matches


def append_query_log(rows: int, covered: int, out_csv: Path, li_tab: Path) -> None:
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
                "query_id": "build_full_candidates_from_li2019",
                "run_at": dt.datetime.now(dt.UTC).isoformat(),
                "phase": "full_collection",
                "source": "Li et al. 2019 Prize-winning paper record",
                "query_or_url": str(li_tab),
                "parameters": "match by category/prize year/family name; supplementary candidate source",
                "output_path": str(out_csv),
                "status": "ok",
                "notes": f"candidate_rows={rows}; covered_full_records={covered}",
            }
        )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build full Li 2019 candidate table matched to Nobel full baseline.")
    parser.add_argument("--baseline-csv", type=Path, default=BASELINE_CSV)
    parser.add_argument("--li2019-source-tab", type=Path, default=LI2019_SOURCE_TAB)
    parser.add_argument("--li2019-full-tab", type=Path, default=LI2019_FULL_TAB)
    parser.add_argument("--out-csv", type=Path, default=OUT_CSV)
    parser.add_argument("--report-json", type=Path, default=OUT_REPORT)
    args = parser.parse_args()

    copy_source_if_needed(args.li2019_source_tab, args.li2019_full_tab)
    baseline = read_csv(args.baseline_csv)
    li_rows = read_tab(args.li2019_full_tab)

    out_rows: list[dict[str, str]] = []
    coverage: dict[str, int] = {}
    misses: list[dict[str, str]] = []
    counter = 1
    for base_row in baseline:
        matches = matched_li_rows(base_row, li_rows)
        coverage[base_row["validation_id"]] = len(matches)
        if not matches:
            misses.append(
                {
                    "validation_id": base_row["validation_id"],
                    "laureate_id": base_row["laureate_id"],
                    "full_name": base_row["full_name"],
                    "award_year": base_row["award_year"],
                    "category": base_row["category"],
                    "reason": "not covered by Li2019, outside 1900-2016 scope, or name match failed",
                }
            )
            continue
        for match in matches:
            out_rows.append(
                {
                    "candidate_id": f"LI2019FULL_{counter:05d}",
                    "validation_id": base_row["validation_id"],
                    "laureate_id": base_row["laureate_id"],
                    "full_name": base_row["full_name"],
                    "award_year": base_row["award_year"],
                    "category": base_row["category"],
                    "motivation": base_row.get("motivation", ""),
                    "candidate_title": match.get("Title", ""),
                    "candidate_year": match.get("Pub year", ""),
                    "award_lag_years": str(int(base_row["award_year"]) - int(match.get("Pub year", "0")))
                    if match.get("Pub year", "").isdigit()
                    else "",
                    "li2019_field": match.get("Field", ""),
                    "li2019_laureate_id": match.get("Laureate ID", ""),
                    "li2019_laureate_name": match.get("Laureate name", ""),
                    "mag_paper_id": match.get("Paper ID", ""),
                    "additional_information": match.get("Additional information", ""),
                    "source_name": "Li et al. 2019 Prize-winning paper record",
                    "source_url_or_path": str(args.li2019_full_tab),
                    "candidate_source_role": "supplementary_candidate_generator",
                    "alignment_status": "needs_official_contribution_alignment",
                    "notes": "Li 2019 is supplementary; accept only after alignment with Nobel official contribution and metadata verification.",
                }
            )
            counter += 1

    fields = [
        "candidate_id",
        "validation_id",
        "laureate_id",
        "full_name",
        "award_year",
        "category",
        "motivation",
        "candidate_title",
        "candidate_year",
        "award_lag_years",
        "li2019_field",
        "li2019_laureate_id",
        "li2019_laureate_name",
        "mag_paper_id",
        "additional_information",
        "source_name",
        "source_url_or_path",
        "candidate_source_role",
        "alignment_status",
        "notes",
    ]
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.out_csv.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out_rows)

    by_category = Counter(row["category"] for row in out_rows)
    covered = sum(1 for count in coverage.values() if count > 0)
    report = {
        "baseline_records": len(baseline),
        "li2019_rows": len(li_rows),
        "covered_full_records": covered,
        "candidate_rows": len(out_rows),
        "coverage_rate": covered / len(baseline) if baseline else 0,
        "records_not_covered": len(misses),
        "by_candidate_category": dict(sorted(by_category.items())),
        "misses": misses,
        "output": str(args.out_csv),
    }
    args.report_json.parent.mkdir(parents=True, exist_ok=True)
    args.report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    append_query_log(len(out_rows), covered, args.out_csv, args.li2019_full_tab)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
