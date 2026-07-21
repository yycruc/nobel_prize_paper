from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import os
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_CSV = ROOT / "02_full_collection" / "06_analysis" / "analysis_ready_key_papers_full.csv"
BASELINE_CSV = ROOT / "02_full_collection" / "01_raw_sources" / "nobel_api" / "nobel_award_baseline_full.csv"
OUT_DIR = ROOT / "02_full_collection" / "06_analysis"
CACHE_DIR = ROOT / "02_full_collection" / "01_raw_sources" / "metadata_api_cache" / "openalex_country_shares"
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"
OPENALEX_WORKS = "https://api.openalex.org/works"

COUNTRIES = [
    ("US", "United States"),
    ("JP", "Japan"),
    ("GB", "United Kingdom"),
    ("FR", "France"),
    ("DE", "Germany"),
    ("CN", "China"),
]
START_YEAR = 1850
END_YEAR = 2025
ROW_COVERAGE_THRESHOLD = 0.90


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_int(value: Any) -> int | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def decade(year: int) -> str:
    return f"{year // 10 * 10}s"


def period_label(year: int) -> str:
    if year < 1940:
        return "1901-1939"
    if year < 1970:
        return "1940-1969"
    if year < 2000:
        return "1970-1999"
    return "2000-2025"


def paper_key(row: dict[str, str]) -> str:
    for field in ("openalex_work_id", "doi"):
        value = (row.get(field) or "").strip().lower()
        if value:
            return f"{field}:{value}"
    title = " ".join((row.get("title") or "").lower().split())
    year = (row.get("publication_year") or "").strip()
    return f"title_year:{title}|{year}"


def source_id_short(source_id: str) -> str:
    return (source_id or "").rstrip("/").rsplit("/", 1)[-1]


def basic_stats(baseline: list[dict[str, str]], rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    all_records = {row["validation_id"] for row in baseline if row.get("validation_id")}
    papers_by_record: dict[str, set[str]] = {record_id: set() for record_id in all_records}
    row_count_by_record: Counter[str] = Counter()
    for row in rows:
        record_id = row.get("validation_id", "")
        if not record_id:
            continue
        papers_by_record.setdefault(record_id, set()).add(paper_key(row))
        row_count_by_record[record_id] += 1

    dist = Counter(len(papers) for papers in papers_by_record.values())
    distribution_rows = [
        {
            "paper_count_per_nobel_record": paper_count,
            "nobel_records": dist[paper_count],
            "share_of_all_nobel_records": round(dist[paper_count] / len(all_records), 6) if all_records else 0,
        }
        for paper_count in sorted(dist)
    ]
    nonzero_counts = [len(papers) for papers in papers_by_record.values() if papers]
    summary_rows = [
        {"metric": "all_natural_science_nobel_records", "value": len(all_records), "notes": "Nobel API baseline, laureate-award record level"},
        {"metric": "records_with_analysis_ready_key_papers", "value": sum(1 for papers in papers_by_record.values() if papers), "notes": "Records with at least one main-analysis key paper"},
        {"metric": "records_without_analysis_ready_key_papers", "value": sum(1 for papers in papers_by_record.values() if not papers), "notes": "No main-analysis key paper row"},
        {"metric": "key_paper_rows", "value": len(rows), "notes": "Row-level key-paper links; one paper may link to more than one Nobel record"},
        {"metric": "unique_key_papers", "value": len({paper_key(row) for row in rows}), "notes": "Deduplicated by OpenAlex work id, then DOI, then title-year"},
        {"metric": "unique_journals", "value": len({row.get("journal", "").strip() for row in rows if row.get("journal", "").strip()}), "notes": "Non-empty journal/source names in analysis table"},
        {"metric": "mean_unique_papers_per_covered_record", "value": round(statistics.mean(nonzero_counts), 3) if nonzero_counts else 0, "notes": "Covered records only"},
        {"metric": "median_unique_papers_per_covered_record", "value": round(statistics.median(nonzero_counts), 3) if nonzero_counts else 0, "notes": "Covered records only"},
        {"metric": "max_unique_papers_per_covered_record", "value": max(nonzero_counts) if nonzero_counts else 0, "notes": "Covered records only"},
    ]
    return summary_rows, distribution_rows


def journal_coverage(rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    total_rows = len(rows)
    all_records = {row.get("validation_id", "") for row in rows if row.get("validation_id", "")}
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        journal = (row.get("journal") or "").strip()
        if journal:
            groups[journal].append(row)

    ranked = sorted(groups.items(), key=lambda item: (-len(item[1]), item[0].lower()))
    cumulative_rows = 0
    cumulative_records: set[str] = set()
    coverage_rows = []
    selected_n = 0
    for rank, (journal, group) in enumerate(ranked, start=1):
        cumulative_rows += len(group)
        cumulative_records.update(row.get("validation_id", "") for row in group if row.get("validation_id", ""))
        source_counts = Counter(row.get("openalex_source_id", "") for row in group if row.get("openalex_source_id", ""))
        issn_counts = Counter(row.get("issn_l", "") for row in group if row.get("issn_l", ""))
        row_share = len(group) / total_rows if total_rows else 0
        cumulative_row_share = cumulative_rows / total_rows if total_rows else 0
        coverage_rows.append(
            {
                "rank": rank,
                "journal": journal,
                "key_paper_rows": len(group),
                "row_share": round(row_share, 6),
                "cumulative_key_paper_rows": cumulative_rows,
                "cumulative_row_share": round(cumulative_row_share, 6),
                "covered_nobel_records": len({row.get("validation_id", "") for row in group if row.get("validation_id", "")}),
                "cumulative_covered_nobel_records": len(cumulative_records),
                "cumulative_record_share_among_covered_records": round(len(cumulative_records) / len(all_records), 6) if all_records else 0,
                "openalex_source_id": source_counts.most_common(1)[0][0] if source_counts else "",
                "issn_l": issn_counts.most_common(1)[0][0] if issn_counts else "",
                "selected_for_90pct_row_panel": cumulative_row_share <= ROW_COVERAGE_THRESHOLD or selected_n == 0,
            }
        )
        if selected_n == 0 and cumulative_row_share >= ROW_COVERAGE_THRESHOLD:
            selected_n = rank
            coverage_rows[-1]["selected_for_90pct_row_panel"] = True
    if selected_n == 0:
        selected_n = len(coverage_rows)
    for row in coverage_rows:
        row["selected_for_90pct_row_panel"] = int(int(row["rank"]) <= selected_n)

    period_rows = []
    periods = ["1901-1939", "1940-1969", "1970-1999", "2000-2025"]
    for period in periods:
        period_group = [row for row in rows if (year := parse_int(row.get("award_year"))) is not None and period_label(year) == period]
        period_total = len(period_group)
        period_journal_counts = Counter((row.get("journal") or "").strip() for row in period_group if (row.get("journal") or "").strip())
        period_cumulative = 0
        for rank, (journal, count) in enumerate(period_journal_counts.most_common(15), start=1):
            period_cumulative += count
            period_rows.append(
                {
                    "award_period": period,
                    "rank_within_period": rank,
                    "journal": journal,
                    "key_paper_rows": count,
                    "period_key_paper_rows": period_total,
                    "period_row_share": round(count / period_total, 6) if period_total else 0,
                    "period_cumulative_row_share_top15": round(period_cumulative / period_total, 6) if period_total else 0,
                }
            )
    return coverage_rows, period_rows, selected_n


def openalex_counts_url(source_id: str, country_code: str | None) -> str:
    filters = [
        f"primary_location.source.id:{source_id_short(source_id)}",
        "type:article",
        f"from_publication_date:{START_YEAR}-01-01",
        f"to_publication_date:{END_YEAR}-12-31",
    ]
    if country_code:
        filters.insert(1, f"authorships.countries:{country_code}")
    params = {"filter": ",".join(filters), "group_by": "publication_year", "per-page": "200"}
    mailto = os.environ.get("OPENALEX_MAILTO", "")
    if mailto:
        params["mailto"] = mailto
    api_key = os.environ.get("OPENALEX_API_KEY", "")
    if api_key:
        params["api_key"] = api_key
    return OPENALEX_WORKS + "?" + urllib.parse.urlencode(params)


def request_json(url: str, retries: int = 4, timeout: float = 60.0) -> dict[str, Any]:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    path = CACHE_DIR / f"{digest}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    req = urllib.request.Request(url, headers={"User-Agent": "nobel-key-papers-analysis/0.2 (journal country shares)"})
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            time.sleep(0.15)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            return payload
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code in {429, 500, 502, 503, 504}:
                retry_after = exc.headers.get("Retry-After")
                wait = float(retry_after) if retry_after and retry_after.isdigit() else min(45, 2**attempt)
                time.sleep(wait)
                continue
            raise
        except urllib.error.URLError as exc:
            last_error = exc
            time.sleep(min(45, 2**attempt))
    if last_error:
        raise last_error
    raise RuntimeError("OpenAlex request failed")


def counts_by_year(source_id: str, country_code: str | None) -> tuple[dict[int, int], str]:
    url = openalex_counts_url(source_id, country_code)
    payload = request_json(url)
    counts = {int(item["key"]): int(item["count"]) for item in payload.get("group_by") or [] if str(item.get("key", "")).isdigit()}
    return counts, urllib.parse.urlparse(url).query


def fetch_selected_journal_shares(coverage_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    selected = [row for row in coverage_rows if int(row["selected_for_90pct_row_panel"]) == 1 and row.get("openalex_source_id")]
    panel_rows: list[dict[str, Any]] = []
    aggregate_totals: dict[tuple[str, int], int] = defaultdict(int)
    world_totals: dict[int, int] = defaultdict(int)
    errors: list[str] = []
    retrieved_at = dt.datetime.now(dt.timezone.utc).isoformat()

    for journal in selected:
        source_id = journal["openalex_source_id"]
        try:
            world_counts, world_query = counts_by_year(source_id, None)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{journal['journal']}|WORLD|{type(exc).__name__}:{exc}")
            world_counts, world_query = {}, ""
        country_counts_by_code: dict[str, tuple[dict[int, int], str]] = {}
        for country_code, _country_name in COUNTRIES:
            try:
                country_counts_by_code[country_code] = counts_by_year(source_id, country_code)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{journal['journal']}|{country_code}|{type(exc).__name__}:{exc}")
                country_counts_by_code[country_code] = ({}, "")

        for year in range(START_YEAR, END_YEAR + 1):
            world_count = world_counts.get(year, 0)
            world_totals[year] += world_count
            for country_code, country_name in COUNTRIES:
                country_counts, country_query = country_counts_by_code[country_code]
                count = country_counts.get(year, 0)
                aggregate_totals[(country_code, year)] += count
                panel_rows.append(
                    {
                        "journal_rank": journal["rank"],
                        "journal": journal["journal"],
                        "openalex_source_id": source_id,
                        "issn_l": journal["issn_l"],
                        "country_code": country_code,
                        "country_name": country_name,
                        "year": year,
                        "year_decade": decade(year),
                        "country_publication_count": count,
                        "world_publication_count": world_count,
                        "country_world_share": round(count / world_count, 8) if world_count else 0,
                        "country_count_filter": country_query,
                        "world_count_filter": world_query,
                        "retrieved_at": retrieved_at,
                    }
                )

    aggregate_rows = []
    for country_code, country_name in COUNTRIES:
        for year in range(START_YEAR, END_YEAR + 1):
            country_total = aggregate_totals[(country_code, year)]
            world_total = world_totals[year]
            aggregate_rows.append(
                {
                    "country_code": country_code,
                    "country_name": country_name,
                    "year": year,
                    "year_decade": decade(year),
                    "selected_journal_country_count": country_total,
                    "selected_journal_world_count": world_total,
                    "country_world_share": round(country_total / world_total, 8) if world_total else 0,
                }
            )
    return panel_rows, aggregate_rows, errors


def append_query_log(summary: dict[str, Any]) -> None:
    if not QUERY_LOG.exists():
        return
    fieldnames = ["query_id", "run_at", "phase", "source", "query_or_url", "parameters", "output_path", "status", "notes"]
    with QUERY_LOG.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writerow(
            {
                "query_id": "extend_journal_coverage_analysis",
                "run_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "phase": "analysis_extension",
                "source": "analysis-ready key papers; OpenAlex",
                "query_or_url": str(ANALYSIS_CSV),
                "parameters": f"journal coverage; selected journals to {ROW_COVERAGE_THRESHOLD:.0%} row coverage; country/world shares {START_YEAR}-{END_YEAR}; type=article",
                "output_path": str(OUT_DIR / "additional_statistics_summary.json"),
                "status": "ok" if not summary.get("openalex_errors") else "partial",
                "notes": f"selected_journals={summary.get('selected_journals_for_90pct_rows')}; share_panel_rows={summary.get('country_share_panel_rows')}; errors={len(summary.get('openalex_errors') or [])}",
            }
        )


def run(skip_openalex: bool = False) -> dict[str, Any]:
    baseline = read_csv(BASELINE_CSV)
    rows = read_csv(ANALYSIS_CSV)
    summary_rows, distribution_rows = basic_stats(baseline, rows)
    coverage_rows, period_rows, selected_n = journal_coverage(rows)

    write_csv(OUT_DIR / "additional_basic_stats.csv", summary_rows, ["metric", "value", "notes"])
    write_csv(OUT_DIR / "additional_record_paper_count_distribution.csv", distribution_rows, ["paper_count_per_nobel_record", "nobel_records", "share_of_all_nobel_records"])
    write_csv(
        OUT_DIR / "additional_journal_coverage_rank.csv",
        coverage_rows,
        [
            "rank",
            "journal",
            "key_paper_rows",
            "row_share",
            "cumulative_key_paper_rows",
            "cumulative_row_share",
            "covered_nobel_records",
            "cumulative_covered_nobel_records",
            "cumulative_record_share_among_covered_records",
            "openalex_source_id",
            "issn_l",
            "selected_for_90pct_row_panel",
        ],
    )
    write_csv(
        OUT_DIR / "additional_journal_coverage_by_award_period.csv",
        period_rows,
        ["award_period", "rank_within_period", "journal", "key_paper_rows", "period_key_paper_rows", "period_row_share", "period_cumulative_row_share_top15"],
    )

    panel_rows: list[dict[str, Any]] = []
    aggregate_rows: list[dict[str, Any]] = []
    errors: list[str] = []
    if not skip_openalex:
        panel_rows, aggregate_rows, errors = fetch_selected_journal_shares(coverage_rows)
        write_csv(
            OUT_DIR / "additional_country_journal_year_world_shares_1850.csv",
            panel_rows,
            [
                "journal_rank",
                "journal",
                "openalex_source_id",
                "issn_l",
                "country_code",
                "country_name",
                "year",
                "year_decade",
                "country_publication_count",
                "world_publication_count",
                "country_world_share",
                "country_count_filter",
                "world_count_filter",
                "retrieved_at",
            ],
        )
        write_csv(
            OUT_DIR / "additional_country_year_world_shares_1850_aggregate.csv",
            aggregate_rows,
            [
                "country_code",
                "country_name",
                "year",
                "year_decade",
                "selected_journal_country_count",
                "selected_journal_world_count",
                "country_world_share",
            ],
        )

    summary = {
        "baseline_records": len({row.get("validation_id") for row in baseline if row.get("validation_id")}),
        "analysis_key_paper_rows": len(rows),
        "analysis_unique_key_papers": len({paper_key(row) for row in rows}),
        "covered_records": len({row.get("validation_id", "") for row in rows if row.get("validation_id", "")}),
        "unique_journals": len({row.get("journal", "").strip() for row in rows if row.get("journal", "").strip()}),
        "selected_journals_for_90pct_rows": selected_n,
        "selected_journal_cumulative_row_share": coverage_rows[selected_n - 1]["cumulative_row_share"] if coverage_rows else 0,
        "selected_journal_cumulative_record_share_among_covered_records": coverage_rows[selected_n - 1]["cumulative_record_share_among_covered_records"] if coverage_rows else 0,
        "country_share_panel_rows": len(panel_rows),
        "country_share_aggregate_rows": len(aggregate_rows),
        "openalex_errors": errors,
    }
    (OUT_DIR / "additional_statistics_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    append_query_log(summary)
    return summary


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-openalex", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(skip_openalex=args.skip_openalex), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
