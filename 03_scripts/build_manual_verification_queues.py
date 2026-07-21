from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "02_full_collection" / "01_raw_sources" / "nobel_api" / "nobel_award_baseline_full.csv"
REGISTRY = ROOT / "02_full_collection" / "03_matched_metadata" / "candidate_registry_with_gap_matches_full.csv"
ANALYSIS = ROOT / "02_full_collection" / "06_analysis" / "analysis_ready_key_papers_full.csv"
EXCLUDED = ROOT / "02_full_collection" / "06_analysis" / "analysis_excluded_or_review_key_paper_candidates_full.csv"
OUT_DIR = ROOT / "02_full_collection" / "06_analysis"
REPORT = ROOT / "02_full_collection" / "05_outputs" / "manual_verification_plan_and_collection_process.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def period(year: int) -> str:
    if year < 1940:
        return "1901-1939"
    if year < 1970:
        return "1940-1969"
    if year < 2000:
        return "1970-1999"
    return "2000-2025"


def priority_for_no_candidate(year: int) -> tuple[str, str]:
    if year >= 2000:
        return "P2", "No registered candidate; recent award period likely benefits from targeted Nobel page/OpenAlex/manual web search."
    if year >= 1940:
        return "P3", "No registered candidate; mid-period record may require historical bibliography and title search."
    return "P4", "No registered candidate; early historical record, often weak official bibliography or non-article contribution."


def priority_for_candidate(statuses: set[str]) -> tuple[str, str, str]:
    if "official_gap_metadata_candidate_needs_review" in statuses:
        return "P1", "review_candidate_match", "Metadata candidate exists; verify title/year/journal and whether reference is truly key to the Nobel contribution."
    if "official_reference_needs_key_relevance_review" in statuses:
        return "P1", "review_official_reference_relevance", "Official DOI/reference exists; decide whether it is a key paper or contextual/background reference."
    if "metadata_unresolved_needs_manual_or_identifier_search" in statuses:
        return "P2", "resolve_metadata", "Title/reference clue exists but DOI/OpenAlex/journal metadata is unresolved."
    return "P2", "review_non_main_candidate", "Candidate exists but did not meet main-analysis rules."


def build() -> dict[str, Any]:
    baseline = read_csv(BASELINE)
    registry = read_csv(REGISTRY)
    analysis = read_csv(ANALYSIS)
    excluded = read_csv(EXCLUDED)

    base_by_id = {row["validation_id"]: row for row in baseline}
    reg_by_id: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in registry:
        reg_by_id[row["validation_id"]].append(row)
    excluded_by_id: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in excluded:
        excluded_by_id[row["validation_id"]].append(row)

    main_ids = {row["validation_id"] for row in analysis}
    reg_ids = set(reg_by_id)
    record_rows: list[dict[str, Any]] = []

    for validation_id in sorted(set(base_by_id) - main_ids):
        base = base_by_id[validation_id]
        year = int(base["award_year"])
        reg_rows = reg_by_id.get(validation_id, [])
        statuses = {row.get("registry_status", "") for row in reg_rows}
        if reg_rows:
            priority, action, reason = priority_for_candidate(statuses)
            queue_type = "has_candidate_not_in_main"
        else:
            priority, reason = priority_for_no_candidate(year)
            action = "find_candidate_from_official_and_metadata_sources"
            queue_type = "no_registered_candidate"
        sample_titles = " | ".join(row.get("title", "")[:100] for row in reg_rows[:4])
        record_rows.append(
            {
                "priority": priority,
                "queue_type": queue_type,
                "recommended_action": action,
                "validation_id": validation_id,
                "laureate_id": base.get("laureate_id", ""),
                "full_name": base.get("full_name", ""),
                "award_year": year,
                "award_period": period(year),
                "category": base.get("category", ""),
                "motivation": base.get("motivation", ""),
                "registered_candidate_rows": len(reg_rows),
                "review_candidate_rows": len(excluded_by_id.get(validation_id, [])),
                "candidate_statuses": "; ".join(sorted(s for s in statuses if s)),
                "sample_candidate_titles": sample_titles,
                "verification_reason": reason,
                "assignee": "",
                "verification_status": "not_started",
                "verified_key_paper_decision": "",
                "verified_title": "",
                "verified_year": "",
                "verified_journal": "",
                "verified_doi_or_openalex": "",
                "verification_notes": "",
            }
        )

    candidate_rows: list[dict[str, Any]] = []
    for row in excluded:
        validation_id = row["validation_id"]
        base = base_by_id.get(validation_id, {})
        candidate_rows.append(
            {
                "priority": "P1" if row.get("analysis_inclusion") == "sensitivity" else "P2",
                "validation_id": validation_id,
                "full_name": row.get("full_name", base.get("full_name", "")),
                "award_year": row.get("award_year", base.get("award_year", "")),
                "category": row.get("category", base.get("category", "")),
                "title": row.get("title", ""),
                "publication_year": row.get("publication_year", ""),
                "journal": row.get("journal", ""),
                "doi": row.get("doi", ""),
                "openalex_work_id": row.get("openalex_work_id", ""),
                "registry_status": row.get("registry_status", ""),
                "analysis_inclusion": row.get("analysis_inclusion", ""),
                "analysis_role": row.get("analysis_role", ""),
                "review_task": review_task(row),
                "assignee": "",
                "verification_status": "not_started",
                "decision": "",
                "notes": "",
            }
        )

    record_rows.sort(key=lambda r: (r["priority"], r["award_year"], r["validation_id"]))
    candidate_rows.sort(key=lambda r: (r["priority"], r["award_year"], r["validation_id"], r["title"].lower()))

    write_csv(
        OUT_DIR / "manual_verification_record_queue.csv",
        record_rows,
        [
            "priority",
            "queue_type",
            "recommended_action",
            "validation_id",
            "laureate_id",
            "full_name",
            "award_year",
            "award_period",
            "category",
            "motivation",
            "registered_candidate_rows",
            "review_candidate_rows",
            "candidate_statuses",
            "sample_candidate_titles",
            "verification_reason",
            "assignee",
            "verification_status",
            "verified_key_paper_decision",
            "verified_title",
            "verified_year",
            "verified_journal",
            "verified_doi_or_openalex",
            "verification_notes",
        ],
    )
    write_csv(
        OUT_DIR / "manual_verification_candidate_queue.csv",
        candidate_rows,
        [
            "priority",
            "validation_id",
            "full_name",
            "award_year",
            "category",
            "title",
            "publication_year",
            "journal",
            "doi",
            "openalex_work_id",
            "registry_status",
            "analysis_inclusion",
            "analysis_role",
            "review_task",
            "assignee",
            "verification_status",
            "decision",
            "notes",
        ],
    )

    summary = {
        "baseline_records": len(baseline),
        "registry_rows": len(registry),
        "registry_covered_records": len(reg_ids),
        "main_analysis_rows": len(analysis),
        "main_analysis_records": len(main_ids),
        "review_or_excluded_candidate_rows": len(excluded),
        "review_or_excluded_records": len({row["validation_id"] for row in excluded}),
        "manual_record_queue_rows": len(record_rows),
        "manual_candidate_queue_rows": len(candidate_rows),
        "record_queue_by_priority": dict(Counter(row["priority"] for row in record_rows)),
        "record_queue_by_type": dict(Counter(row["queue_type"] for row in record_rows)),
        "candidate_queue_by_role": dict(Counter(row["analysis_role"] for row in candidate_rows)),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(render_report(summary), encoding="utf-8")
    (OUT_DIR / "manual_verification_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def review_task(row: dict[str, str]) -> str:
    role = row.get("analysis_role", "")
    if role == "official_doi_reference_relevance_review":
        return "Verify whether official DOI/reference is a Nobel key paper or only contextual reading."
    if role == "official_gap_reference_candidate_review":
        return "Check metadata match quality and key-paper relevance against Nobel official text."
    if role == "missing_journal":
        return "Resolve journal/source metadata from DOI, OpenAlex, Crossref, PubMed, publisher page, or original scan."
    if role == "post_award_publication":
        return "Exclude unless publication year is wrong; verify bibliographic year."
    return "Manual review required before main analysis inclusion."


def render_report(summary: dict[str, Any]) -> str:
    return f"""# 诺奖关键论文数据采集与人工核验方案

## 一、需要人工核验哪些记录

本轮自然科学类诺奖基线共有 {summary['baseline_records']} 条“获奖人-奖项”记录。候选注册表共有 {summary['registry_rows']} 条候选论文行，覆盖 {summary['registry_covered_records']} 条诺奖记录。最终主分析采用 {summary['main_analysis_rows']} 条高可信“诺奖记录-论文”行，覆盖 {summary['main_analysis_records']} 条诺奖记录。

因此，人工核验对象是未进入主分析的 {summary['manual_record_queue_rows']} 条记录：

- P1：已有候选且最容易转入主分析，优先核验。主要是官网 DOI/参考文献是否真为关键论文，或 gap reference 元数据候选是否准确。
- P2：有题名线索但元数据未解析，或近年奖项尚无候选，需要 DOI/OpenAlex/Crossref/PubMed/官网页面补查。
- P3：1940-1999 年未进入候选表的记录，通常需要历史文献库或题名检索补充。
- P4：1901-1939 年未进入候选表的记录，很多是早期实验、理论、方法或非单篇论文型贡献，核验难度最高。

已生成两张分工表：

- `02_full_collection/06_analysis/manual_verification_record_queue.csv`：按诺奖记录分工，共 {summary['manual_record_queue_rows']} 条。
- `02_full_collection/06_analysis/manual_verification_candidate_queue.csv`：按候选论文逐条核验，共 {summary['manual_candidate_queue_rows']} 条。

建议先安排人员处理 P1 和 P2。P1/P2 完成后，预计能较快提高 504 条主分析覆盖率；P3/P4 更适合后续专题补充或历史文献人工核查。

## 二、人工核验流程

每条记录建议按以下顺序核验：

1. 先读诺奖官网该奖项的 facts、press release、advanced information、popular information、lecture、biographical / other resources 页面，确认获奖贡献的官方表述。
2. 检查候选论文是否直接对应获奖贡献：题名、年份、作者、期刊、研究对象是否与官方表述一致。
3. 用 DOI、OpenAlex、Crossref、PubMed、publisher page 或 Google Scholar 补全元数据；优先记录 DOI 和 OpenAlex work id。
4. 判断该文献角色：`key_paper`、`supporting_context`、`not_relevant`、`uncertain`。
5. 对多人共享奖，允许同一篇论文对应多个获奖人记录；对系列成果，允许多篇关键论文对应同一获奖人记录。
6. 只有满足“发表年份不晚于获奖年份、元数据可追溯、与官方贡献直接相关”的论文，才建议转入主分析表。

## 三、数据采集流程汇报描述

本项目采用“官方来源优先、公开数据集辅助、元数据平台校验”的流程收集诺奖关键论文数据。首先，以 Nobel Prize API 建立 1901-2025 年自然科学类诺奖基线，共得到 {summary['baseline_records']} 条“获奖人-奖项”记录。随后抓取诺奖官网 facts、press release、popular information、advanced information 等页面，以及 lecture、biographical、other resources 等二级页面和 PDF 材料；共构建官网主页面抓取目标 3310 个，成功 2084 个，二级页面目标 2024 个，成功 1875 个，PDF 链接 1537 个，成功下载 1535 个，并从 PDF/网页中抽取参考文献 15331 条。

在候选论文构建阶段，先引入 Li 2019 prize-winning paper 数据集作为结构化候选来源。该数据集原始 874 行，整理为 863 条候选论文，覆盖 530 条诺奖记录；其中 830 行带 MAG 标识，807 行成功匹配到 OpenAlex。随后，对诺奖官网参考文献中含 DOI 的条目做精确匹配，69 条 DOI-present 参考文献全部匹配成功。对于 Li 2019 和 DOI 仍未覆盖的 gap 记录，再从官网参考文献中筛选高信号候选，共形成 2540 条 gap reference 候选，其中 A-tier 57 条；进一步通过 DOI/OpenAlex/Crossref 等方式匹配元数据，得到 52 条可并入候选注册表的记录。

综合以上来源后，候选注册表共有 {summary['registry_rows']} 条候选论文行，覆盖 {summary['registry_covered_records']} 条诺奖记录；仍有 99 条记录没有进入候选表。为了保证分析稳健性，最终主分析只纳入元数据完整、发表年份不晚于获奖年份、且关键论文属性相对明确的候选，包括 Li 2019 精确 MAG/OpenAlex 匹配候选和诺奖官网 gap reference 高可信匹配候选。主分析表最终包含 {summary['main_analysis_rows']} 条“诺奖记录-论文”行，覆盖 {summary['main_analysis_records']} 条诺奖记录。另有 {summary['review_or_excluded_candidate_rows']} 条候选被放入 sensitivity/review/excluded 队列，原因包括官网参考文献需判断关键性、元数据未解析、缺期刊信息或发表年份晚于获奖年份。

在分析阶段，基于主分析表统计关键论文发表到获奖的时间滞后、关键论文来源期刊排名，并选取累计覆盖 90% 诺奖关键论文行的 77 本期刊，进一步从 OpenAlex 采集 1850-2025 年这些期刊中美国、日本、英国、法国、德国、中国逐年发文量及全球总发文量，用于计算六国在诺奖高频期刊中的年度参与式发文占比。
"""


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
