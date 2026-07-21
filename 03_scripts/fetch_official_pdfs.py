from __future__ import annotations

import csv
import datetime as dt
import argparse
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLUE_FILES = [
    ROOT / "01_validation" / "02_candidate_key_papers" / "official_page_bibliographic_clues.csv",
    ROOT / "01_validation" / "02_candidate_key_papers" / "official_secondary_page_bibliographic_clues.csv",
]
PDF_DIR = ROOT / "01_validation" / "01_raw_sources" / "nobel_official_pages" / "pdfs"
STATUS_CSV = ROOT / "01_validation" / "01_raw_sources" / "nobel_official_pages" / "official_pdf_fetch_status.csv"
QUERY_LOG = ROOT / "00_admin" / "query_log.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def classify_pdf(label: str, href: str) -> str:
    text = f"{label} {href}".lower()
    if "advanced" in text or "scientific background" in text:
        return "scientific_background"
    if "popular" in text:
        return "popular_background"
    if "lecture" in text:
        return "nobel_lecture"
    if "press" in text or re.search(r"/prize-announcement", text):
        return "press_release"
    return "other_pdf"


def should_download(label: str, href: str) -> bool:
    text = f"{label} {href}".lower()
    if "image" in text or "illustration" in text:
        return False
    return ".pdf" in href.lower()


def safe_pdf_name(validation_id: str, pdf_type: str, href: str) -> str:
    digest = hashlib.sha1(href.encode("utf-8")).hexdigest()[:10]
    return f"{validation_id}_{pdf_type}_{digest}.pdf"


def fetch_pdf(url: str, timeout: float = 90.0) -> dict[str, object]:
    req = urllib.request.Request(url, headers={"User-Agent": "nobel-key-papers-validation/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read()
            return {
                "fetch_status": "ok",
                "http_status": str(response.status),
                "final_url": response.geturl(),
                "content_type": response.headers.get("Content-Type", ""),
                "body": body,
                "error": "",
            }
    except urllib.error.HTTPError as exc:
        return {
            "fetch_status": "http_error",
            "http_status": str(exc.code),
            "final_url": exc.geturl() if hasattr(exc, "geturl") else url,
            "content_type": exc.headers.get("Content-Type", "") if exc.headers else "",
            "body": b"",
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "fetch_status": "error",
            "http_status": "",
            "final_url": url,
            "content_type": "",
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
        "pdf_type",
        "label",
        "url",
        "fetch_status",
        "http_status",
        "final_url",
        "content_type",
        "content_length",
        "local_path",
        "source_page",
        "error",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def append_query_log(clue_files: list[Path], status_csv: Path, rows: int, ok_rows: int) -> None:
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
                "query_id": "fetch_official_pdfs",
                "run_at": dt.datetime.now(dt.UTC).isoformat(),
                "phase": "validation",
                "source": "Nobel official PDF links",
                "query_or_url": "; ".join(str(path) for path in clue_files),
                "parameters": "download non-image PDF links from official page clues",
                "output_path": str(status_csv),
                "status": "ok",
                "notes": f"pdf_rows={rows}; ok_rows={ok_rows}",
            }
        )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Fetch Nobel official PDFs from extracted clue files.")
    parser.add_argument("--clue-files", nargs="+", type=Path, default=CLUE_FILES)
    parser.add_argument("--pdf-dir", type=Path, default=PDF_DIR)
    parser.add_argument("--status-csv", type=Path, default=STATUS_CSV)
    parser.add_argument("--delay", type=float, default=0.35)
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--progress-every", type=int, default=10)
    args = parser.parse_args()

    clues: list[dict[str, str]] = []
    for path in args.clue_files:
        clues.extend(read_csv(path))

    pdf_links: dict[str, dict[str, str]] = {}
    for clue in clues:
        if clue.get("clue_type") != "pdf_link":
            continue
        href = clue.get("href", "")
        label = clue.get("clue_text", "")
        if not should_download(label, href):
            continue
        key = f"{clue.get('validation_id')}|{href}"
        pdf_links.setdefault(key, clue)

    args.pdf_dir.mkdir(parents=True, exist_ok=True)
    status_rows: list[dict[str, str]] = []
    for idx, clue in enumerate(pdf_links.values(), start=1):
        href = clue["href"]
        pdf_type = classify_pdf(clue.get("clue_text", ""), href)
        local = args.pdf_dir / safe_pdf_name(clue["validation_id"], pdf_type, href)
        if local.exists() and local.stat().st_size > 0:
            body = b""
            result = {
                "fetch_status": "ok",
                "http_status": "cached",
                "final_url": href,
                "content_type": "application/pdf",
                "content_length": str(local.stat().st_size),
                "error": "",
            }
            local_path = str(local)
        else:
            result = fetch_pdf(href, timeout=args.timeout)
            body = result.pop("body")
            local_path = ""
            if body:
                local.write_bytes(body)
                local_path = str(local)
        status_rows.append(
            {
                "validation_id": clue.get("validation_id", ""),
                "laureate_id": clue.get("laureate_id", ""),
                "full_name": clue.get("full_name", ""),
                "award_year": clue.get("award_year", ""),
                "category": clue.get("category", ""),
                "pdf_type": pdf_type,
                "label": clue.get("clue_text", ""),
                "url": href,
                "fetch_status": str(result["fetch_status"]),
                "http_status": str(result["http_status"]),
                "final_url": str(result["final_url"]),
                "content_type": str(result["content_type"]),
                "content_length": str(result.get("content_length") or len(body)),
                "local_path": local_path,
                "source_page": clue.get("source_page", ""),
                "error": str(result["error"]),
            }
        )
        if idx < len(pdf_links):
            time.sleep(args.delay)
        if args.progress_every and idx % args.progress_every == 0:
            write_status(args.status_csv, status_rows)
            print(f"processed {idx}/{len(pdf_links)}", flush=True)

    write_status(args.status_csv, status_rows)
    ok_rows = sum(1 for row in status_rows if row["fetch_status"] == "ok")
    append_query_log(args.clue_files, args.status_csv, len(status_rows), ok_rows)
    summary = {
        "pdf_links": len(status_rows),
        "ok_rows": ok_rows,
        "status": str(args.status_csv),
        "pdf_dir": str(args.pdf_dir),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
