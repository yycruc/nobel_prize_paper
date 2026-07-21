from __future__ import annotations

import csv
import datetime as dt
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASELINE_CSV = ROOT / "01_validation" / "04_outputs" / "nobel_award_baseline_probe.csv"
OUT_CSV = ROOT / "01_validation" / "validation_sample.csv"
OUT_SUMMARY = ROOT / "01_validation" / "04_outputs" / "validation_sample_summary.json"
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"

PERIODS = {
    "early": (1901, 1939),
    "middle": (1940, 1989),
    "recent": (1990, 9999),
}
CATEGORIES = ["Physics", "Chemistry", "Physiology or Medicine"]
SAMPLE_PER_CELL = 5


def read_baseline() -> list[dict[str, str]]:
    with BASELINE_CSV.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def period_bucket(year: int) -> str:
    for bucket, (start, end) in PERIODS.items():
        if start <= year <= end:
            return bucket
    raise ValueError(f"award year outside defined periods: {year}")


def evenly_spaced(rows: list[dict[str, str]], count: int) -> list[dict[str, str]]:
    if len(rows) < count:
        raise ValueError(f"not enough rows to sample {count}: only {len(rows)}")
    if count == 1:
        return [rows[len(rows) // 2]]
    indexes = [round(i * (len(rows) - 1) / (count - 1)) for i in range(count)]
    selected: list[dict[str, str]] = []
    used: set[int] = set()
    for index in indexes:
        if index in used:
            for candidate in range(len(rows)):
                if candidate not in used:
                    index = candidate
                    break
        used.add(index)
        selected.append(rows[index])
    return selected


def build_sample(baseline: list[dict[str, str]]) -> list[dict[str, str]]:
    by_cell: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in baseline:
        category = row["category"]
        if category not in CATEGORIES:
            continue
        year = int(row["award_year"])
        bucket = period_bucket(year)
        by_cell.setdefault((category, bucket), []).append(row)

    out_rows: list[dict[str, str]] = []
    validation_number = 1
    for category in CATEGORIES:
        for bucket in ["early", "middle", "recent"]:
            cell_rows = sorted(
                by_cell.get((category, bucket), []),
                key=lambda r: (int(r["award_year"]), r["full_name"], r["laureate_id"]),
            )
            selected = evenly_spaced(cell_rows, SAMPLE_PER_CELL)
            for row in selected:
                out_rows.append(
                    {
                        "validation_id": f"V{validation_number:03d}",
                        "laureate_id": row["laureate_id"],
                        "full_name": row["full_name"],
                        "award_year": row["award_year"],
                        "category": category,
                        "period_bucket": bucket,
                        "reason_for_selection": "deterministic stratified time-spread validation sample",
                        "review_status": "pending",
                        "notes": row["motivation"],
                    }
                )
                validation_number += 1
    return out_rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fields = [
        "validation_id",
        "laureate_id",
        "full_name",
        "award_year",
        "category",
        "period_bucket",
        "reason_for_selection",
        "review_status",
        "notes",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def append_query_log(rows: int) -> None:
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
                "query_id": "select_validation_sample",
                "run_at": dt.datetime.now(dt.UTC).isoformat(),
                "phase": "validation",
                "source": "nobel_award_baseline_probe.csv",
                "query_or_url": str(BASELINE_CSV),
                "parameters": "5 per category-period cell; deterministic time-spread sampling",
                "output_path": str(OUT_CSV),
                "status": "ok",
                "notes": f"rows={rows}",
            }
        )


def main() -> None:
    baseline = read_baseline()
    sample = build_sample(baseline)
    write_csv(OUT_CSV, sample)

    counts = Counter((row["category"], row["period_bucket"]) for row in sample)
    summary = {
        "sample_rows": len(sample),
        "cells": {f"{category}|{bucket}": count for (category, bucket), count in sorted(counts.items())},
        "output": str(OUT_CSV),
    }
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    append_query_log(len(sample))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

