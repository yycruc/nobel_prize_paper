from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TARGETS_CSV = ROOT / "01_validation" / "01_raw_sources" / "nobel_official_pages" / "validation_official_targets.csv"
CANDIDATES_CSV = ROOT / "01_validation" / "02_candidate_key_papers" / "key_paper_candidates_validation.csv"
PAGES_DIR = ROOT / "01_validation" / "01_raw_sources" / "nobel_official_pages" / "pages"
STATUS_CSV = ROOT / "01_validation" / "01_raw_sources" / "nobel_official_pages" / "official_page_fetch_status.csv"
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def uncovered_validation_ids() -> set[str]:
    targets = read_csv(TARGETS_CSV)
    all_ids = {row["validation_id"] for row in targets}
    if not CANDIDATES_CSV.exists():
        return all_ids
    candidates = read_csv(CANDIDATES_CSV)
    covered = {row["validation_id"] for row in candidates if row.get("candidate_title")}
    return all_ids - covered


def safe_filename(validation_id: str, target_type: str, url: str) -> str:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    safe_type = re.sub(r"[^a-zA-Z0-9_]+", "_", target_type)
    return f"{validation_id}_{safe_type}_{digest}.html"


def extract_title(content: bytes, encoding: str) -> str:
    try:
        text = content.decode(encoding or "utf-8", errors="replace")
    except LookupError:
        text = content.decode("utf-8", errors="replace")
    match = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    title = re.sub(r"\s+", " ", match.group(1)).strip()
    return html.unescape(title)


def fetch_url(url: str, timeout: float = 90.0) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "nobel-key-papers-validation/0.1"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read()
            return {
                "status": "ok",
                "http_status": str(response.status),
                "final_url": response.geturl(),
                "content_type": response.headers.get("Content-Type", ""),
                "encoding": response.headers.get_content_charset() or "utf-8",
                "body": body,
                "error": "",
            }
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        return {
            "status": "http_error",
            "http_status": str(exc.code),
            "final_url": exc.geturl() if hasattr(exc, "geturl") else url,
            "content_type": exc.headers.get("Content-Type", "") if exc.headers else "",
            "encoding": exc.headers.get_content_charset() if exc.headers else "utf-8",
            "body": body,
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "status": "error",
            "http_status": "",
            "final_url": url,
            "content_type": "",
            "encoding": "utf-8",
            "body": b"",
            "error": f"{type(exc).__name__}: {exc}",
        }


def write_status(path: Path, rows: list[dict[str, str]]) -> None:
    fields = [
        "validation_id",
        "laureate_id",
        "full_name",
        "award_year",
        "category",
        "target_type",
        "url",
        "fetch_status",
        "http_status",
        "final_url",
        "content_type",
        "content_length",
        "page_title",
        "local_path",
        "error",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def append_query_log(status_csv: Path, rows: int, ok_rows: int) -> None:
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
                "query_id": "fetch_validation_official_pages",
                "run_at": dt.datetime.now(dt.UTC).isoformat(),
                "phase": "validation",
                "source": "Nobel official pages",
                "query_or_url": str(TARGETS_CSV),
                "parameters": "uncovered validation records only",
                "output_path": str(status_csv),
                "status": "ok",
                "notes": f"target_rows={rows}; ok_rows={ok_rows}",
            }
        )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Fetch Nobel official target pages for validation records.")
    parser.add_argument("--all", action="store_true", help="Fetch all validation targets instead of uncovered records only.")
    parser.add_argument("--delay", type=float, default=0.35, help="Delay between requests in seconds.")
    parser.add_argument("--targets-csv", type=Path, default=TARGETS_CSV)
    parser.add_argument("--status-csv", type=Path, default=STATUS_CSV)
    parser.add_argument("--pages-dir", type=Path, default=PAGES_DIR)
    parser.add_argument("--timeout", type=float, default=90.0, help="Per-request timeout in seconds.")
    parser.add_argument("--progress-every", type=int, default=10, help="Write partial status and print progress every N rows.")
    parser.add_argument("--resume", action="store_true", help="Skip targets already present in the output status CSV.")
    args = parser.parse_args()

    targets = read_csv(args.targets_csv)
    selected_ids = {row["validation_id"] for row in targets} if args.all else uncovered_validation_ids()
    selected_targets = [row for row in targets if row["validation_id"] in selected_ids and row.get("url")]
    existing_rows = read_csv(args.status_csv) if args.resume else []
    existing_keys = {
        (row.get("validation_id", ""), row.get("target_type", ""), row.get("url", ""))
        for row in existing_rows
    }
    if args.resume:
        selected_targets = [
            row for row in selected_targets
            if (row.get("validation_id", ""), row.get("target_type", ""), row.get("url", "")) not in existing_keys
        ]

    args.pages_dir.mkdir(parents=True, exist_ok=True)
    status_rows: list[dict[str, str]] = list(existing_rows)
    for idx, target in enumerate(selected_targets, start=1):
        result = fetch_url(target["url"], timeout=args.timeout)
        local_path = ""
        body = result.pop("body")
        if body:
            local = args.pages_dir / safe_filename(target["validation_id"], target["target_type"], target["url"])
            local.write_bytes(body)
            local_path = str(local)
        page_title = extract_title(body, str(result.get("encoding") or "utf-8")) if body else ""
        status_rows.append(
            {
                **{key: target.get(key, "") for key in ["validation_id", "laureate_id", "full_name", "award_year", "category", "target_type", "url"]},
                "fetch_status": str(result["status"]),
                "http_status": str(result["http_status"]),
                "final_url": str(result["final_url"]),
                "content_type": str(result["content_type"]),
                "content_length": str(len(body)),
                "page_title": page_title,
                "local_path": local_path,
                "error": str(result["error"]),
            }
        )
        if idx < len(selected_targets):
            time.sleep(args.delay)
        if args.progress_every and idx % args.progress_every == 0:
            write_status(args.status_csv, status_rows)
            print(f"processed new {idx}/{len(selected_targets)}; total_status_rows={len(status_rows)}", flush=True)

    write_status(args.status_csv, status_rows)
    ok_rows = sum(1 for row in status_rows if row["fetch_status"] == "ok")
    append_query_log(args.status_csv, len(status_rows), ok_rows)
    print(
        json.dumps(
            {
                "selected_validation_records": len(selected_ids),
                "target_rows": len(status_rows),
                "new_target_rows": len(selected_targets),
                "ok_rows": ok_rows,
                "status": str(args.status_csv),
                "pages_dir": str(args.pages_dir),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
