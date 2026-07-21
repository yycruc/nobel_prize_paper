from __future__ import annotations

import argparse
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
OUT_DIR = ROOT / "02_full_collection" / "06_analysis"
FIG_DIR = OUT_DIR / "figures"
CACHE_DIR = ROOT / "02_full_collection" / "01_raw_sources" / "metadata_api_cache" / "openalex_country_counts"
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
START_YEAR = 1880
END_YEAR = 2025


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_int(value: str) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def median(values: list[int]) -> float:
    return float(statistics.median(values)) if values else 0.0


def mean(values: list[int]) -> float:
    return float(statistics.mean(values)) if values else 0.0


def percentile(values: list[int], pct: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    idx = (len(values) - 1) * pct
    lo = int(idx)
    hi = min(lo + 1, len(values) - 1)
    frac = idx - lo
    return values[lo] * (1 - frac) + values[hi] * frac


def decade(year: int) -> str:
    return f"{year // 10 * 10}s"


def source_id_short(source_id: str) -> str:
    return (source_id or "").rstrip("/").rsplit("/", 1)[-1]


def build_lag_outputs(rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_year: dict[int, list[int]] = defaultdict(list)
    by_decade: dict[str, list[int]] = defaultdict(list)
    records_by_year: dict[int, set[str]] = defaultdict(set)
    for row in rows:
        award_year = parse_int(row.get("award_year", ""))
        lag = parse_int(row.get("award_lag_years", ""))
        if award_year is None or lag is None or lag < 0:
            continue
        by_year[award_year].append(lag)
        by_decade[decade(award_year)].append(lag)
        records_by_year[award_year].add(row.get("validation_id", ""))

    year_rows = []
    for year in sorted(by_year):
        values = by_year[year]
        year_rows.append(
            {
                "award_year": year,
                "key_paper_rows": len(values),
                "covered_nobel_records": len(records_by_year[year]),
                "mean_lag_years": round(mean(values), 2),
                "median_lag_years": round(median(values), 2),
                "min_lag_years": min(values),
                "max_lag_years": max(values),
            }
        )

    decade_rows = []
    for dec in sorted(by_decade, key=lambda d: int(d[:4])):
        values = by_decade[dec]
        decade_rows.append(
            {
                "award_decade": dec,
                "key_paper_rows": len(values),
                "mean_lag_years": round(mean(values), 2),
                "median_lag_years": round(median(values), 2),
                "p25_lag_years": round(percentile(values, 0.25), 2),
                "p75_lag_years": round(percentile(values, 0.75), 2),
                "min_lag_years": min(values),
                "max_lag_years": max(values),
            }
        )
    return year_rows, decade_rows


def build_top_journals(rows: list[dict[str, str]], top_n: int = 10) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        journal = row.get("journal", "").strip()
        if journal:
            groups[journal].append(row)
    ranked = sorted(groups.items(), key=lambda item: (-len(item[1]), item[0].lower()))
    out = []
    for rank, (journal, group) in enumerate(ranked[:top_n], start=1):
        source_counts = Counter(row.get("openalex_source_id", "") for row in group if row.get("openalex_source_id", ""))
        issn_counts = Counter(row.get("issn_l", "") for row in group if row.get("issn_l", ""))
        out.append(
            {
                "rank": rank,
                "journal": journal,
                "key_paper_rows": len(group),
                "covered_nobel_records": len({row.get("validation_id", "") for row in group}),
                "openalex_source_id": source_counts.most_common(1)[0][0] if source_counts else "",
                "issn_l": issn_counts.most_common(1)[0][0] if issn_counts else "",
            }
        )
    return out


def openalex_counts_url(source_id: str, country_code: str) -> str:
    sid = source_id_short(source_id)
    filters = ",".join(
        [
            f"primary_location.source.id:{sid}",
            f"authorships.countries:{country_code}",
            "type:article",
            f"from_publication_date:{START_YEAR}-01-01",
            f"to_publication_date:{END_YEAR}-12-31",
        ]
    )
    params = {
        "filter": filters,
        "group_by": "publication_year",
        "per-page": "200",
    }
    mailto = os.environ.get("OPENALEX_MAILTO", "")
    if mailto:
        params["mailto"] = mailto
    api_key = os.environ.get("OPENALEX_API_KEY", "")
    if api_key:
        params["api_key"] = api_key
    return OPENALEX_WORKS + "?" + urllib.parse.urlencode(params)


def request_json(url: str, retries: int = 3, timeout: float = 35.0) -> dict[str, Any]:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    path = CACHE_DIR / f"{digest}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    headers = {"User-Agent": "nobel-key-papers-analysis/0.1 (country journal counts)"}
    req = urllib.request.Request(url, headers=headers)
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            time.sleep(0.2)
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


def fetch_country_journal_counts(top_journals: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    rows = []
    errors = []
    for journal in top_journals:
        source_id = journal["openalex_source_id"]
        if not source_id:
            errors.append(f"missing_source_id:{journal['journal']}")
            continue
        for country_code, country_name in COUNTRIES:
            url = openalex_counts_url(source_id, country_code)
            try:
                payload = request_json(url)
                counts = {int(item["key"]): int(item["count"]) for item in payload.get("group_by") or []}
                for year in range(START_YEAR, END_YEAR + 1):
                    rows.append(
                        {
                            "journal_rank": journal["rank"],
                            "journal": journal["journal"],
                            "openalex_source_id": source_id,
                            "issn_l": journal["issn_l"],
                            "country_code": country_code,
                            "country_name": country_name,
                            "year": year,
                            "publication_count": counts.get(year, 0),
                            "count_filter": urllib.parse.urlparse(url).query,
                            "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                        }
                    )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{journal['journal']}|{country_code}|{type(exc).__name__}:{exc}")
    return rows, errors


def aggregate_country_counts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    totals: dict[tuple[str, int], int] = defaultdict(int)
    names: dict[str, str] = {}
    for row in rows:
        key = (row["country_code"], int(row["year"]))
        totals[key] += int(row["publication_count"])
        names[row["country_code"]] = row["country_name"]
    out = []
    for country_code, country_name in COUNTRIES:
        for year in range(START_YEAR, END_YEAR + 1):
            out.append(
                {
                    "country_code": country_code,
                    "country_name": country_name,
                    "year": year,
                    "top10_journal_publication_count": totals.get((country_code, year), 0),
                }
            )
    return out


def try_make_figures(decade_rows: list[dict[str, Any]], top_journals: list[dict[str, Any]], country_totals: list[dict[str, Any]]) -> list[str]:
    made = []
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        return made
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(9, 5))
    x = [row["award_decade"] for row in decade_rows]
    y = [row["median_lag_years"] for row in decade_rows]
    plt.plot(x, y, marker="o")
    plt.xticks(rotation=45, ha="right")
    plt.ylabel("Median lag years")
    plt.title("Nobel Key Paper Publication-to-Award Lag by Award Decade")
    plt.tight_layout()
    path = FIG_DIR / "q1_lag_by_decade.png"
    plt.savefig(path, dpi=180)
    plt.close()
    made.append(str(path))

    plt.figure(figsize=(9, 5))
    journals = [row["journal"] for row in top_journals][::-1]
    counts = [row["key_paper_rows"] for row in top_journals][::-1]
    plt.barh(journals, counts)
    plt.xlabel("Key paper rows")
    plt.title("Top 10 Journals for Nobel Key Paper Candidates")
    plt.tight_layout()
    path = FIG_DIR / "q2_top10_journals.png"
    plt.savefig(path, dpi=180)
    plt.close()
    made.append(str(path))

    by_country: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for row in country_totals:
        by_country[row["country_code"]].append((int(row["year"]), int(row["top10_journal_publication_count"])))
    plt.figure(figsize=(10, 5))
    for country_code, country_name in COUNTRIES:
        points = sorted(by_country[country_code])
        years = [p[0] for p in points]
        counts = [p[1] for p in points]
        plt.plot(years, counts, label=country_name)
    plt.ylabel("Article count in top 10 Nobel journals")
    plt.title("Annual Article Counts in Top 10 Nobel Key-Paper Journals by Country")
    plt.legend(ncol=2, fontsize=8)
    plt.tight_layout()
    path = FIG_DIR / "q3_country_top10_journal_counts.png"
    plt.savefig(path, dpi=180)
    plt.close()
    made.append(str(path))
    return made


def analyze(skip_openalex: bool = False) -> dict[str, Any]:
    rows = read_csv(ANALYSIS_CSV)
    year_rows, decade_rows = build_lag_outputs(rows)
    top_journals = build_top_journals(rows, top_n=10)
    write_csv(OUT_DIR / "q1_lag_by_award_year.csv", year_rows, ["award_year", "key_paper_rows", "covered_nobel_records", "mean_lag_years", "median_lag_years", "min_lag_years", "max_lag_years"])
    write_csv(OUT_DIR / "q1_lag_by_award_decade.csv", decade_rows, ["award_decade", "key_paper_rows", "mean_lag_years", "median_lag_years", "p25_lag_years", "p75_lag_years", "min_lag_years", "max_lag_years"])
    write_csv(OUT_DIR / "q2_top10_key_paper_journals.csv", top_journals, ["rank", "journal", "key_paper_rows", "covered_nobel_records", "openalex_source_id", "issn_l"])

    country_rows: list[dict[str, Any]] = []
    country_totals: list[dict[str, Any]] = []
    errors: list[str] = []
    if not skip_openalex:
        country_rows, errors = fetch_country_journal_counts(top_journals)
        country_totals = aggregate_country_counts(country_rows)
        write_csv(
            OUT_DIR / "q3_country_journal_year_counts_top10.csv",
            country_rows,
            ["journal_rank", "journal", "openalex_source_id", "issn_l", "country_code", "country_name", "year", "publication_count", "count_filter", "retrieved_at"],
        )
        write_csv(
            OUT_DIR / "q3_country_year_counts_top10_aggregate.csv",
            country_totals,
            ["country_code", "country_name", "year", "top10_journal_publication_count"],
        )

    figures = try_make_figures(decade_rows, top_journals, country_totals) if country_totals else []
    summary = {
        "analysis_rows": len(rows),
        "lag_year_rows": len(year_rows),
        "lag_decade_rows": len(decade_rows),
        "top10_journals": top_journals,
        "country_journal_year_rows": len(country_rows),
        "country_year_aggregate_rows": len(country_totals),
        "openalex_errors": errors,
        "figures": figures,
        "outputs": {
            "q1_by_year": str(OUT_DIR / "q1_lag_by_award_year.csv"),
            "q1_by_decade": str(OUT_DIR / "q1_lag_by_award_decade.csv"),
            "q2_top10": str(OUT_DIR / "q2_top10_key_paper_journals.csv"),
            "q3_panel": str(OUT_DIR / "q3_country_journal_year_counts_top10.csv"),
            "q3_aggregate": str(OUT_DIR / "q3_country_year_counts_top10_aggregate.csv"),
        },
    }
    (OUT_DIR / "analysis_three_questions_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    append_query_log(summary)
    return summary


def append_query_log(summary: dict[str, Any]) -> None:
    if not QUERY_LOG.exists():
        return
    fieldnames = ["query_id", "run_at", "phase", "source", "query_or_url", "parameters", "output_path", "status", "notes"]
    row = {
        "query_id": "analyze_three_questions",
        "run_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "phase": "analysis",
        "source": "analysis-ready key papers; OpenAlex",
        "query_or_url": str(ANALYSIS_CSV),
        "parameters": f"top10 journals; country counts {START_YEAR}-{END_YEAR}; type=article",
        "output_path": str(OUT_DIR / "analysis_three_questions_summary.json"),
        "status": "ok" if not summary["openalex_errors"] else "partial",
        "notes": f"analysis_rows={summary['analysis_rows']}; q3_rows={summary['country_journal_year_rows']}; errors={len(summary['openalex_errors'])}",
    }
    with QUERY_LOG.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-openalex", action="store_true")
    args = parser.parse_args()
    print(json.dumps(analyze(skip_openalex=args.skip_openalex), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
