# 脚本索引

`03_scripts/` 保留了原项目全部脚本。下表给出其在证据链中的位置；带“人工”字样的步骤只生成复核材料，不会自动作出最终学术判断。

| 环节 | 脚本 | 作用 |
| --- | --- | --- |
| 验证准备 | `probe_nobel_api.py`、`select_validation_sample.py`、`build_validation_official_targets.py` | 连通性检查、抽样与验证页面目标构建 |
| 奖项基准 | `build_full_nobel_baseline.py`、`build_full_official_targets.py` | 获取自然科学获奖人—奖项基准和官网页面清单 |
| 官网抓取 | `fetch_validation_official_pages.py`、`extract_official_secondary_targets.py`、`fetch_official_pdfs.py` | 下载官网HTML、二级页面与PDF |
| 官网页面提取 | `extract_official_page_clues.py`、`extract_official_pdf_clues.py`、`extract_official_pdf_reference_sections.py` | 提取PDF链接、DOI、叙述性书目信息和参考文献段 |
| 参考文献分类 | `classify_official_references.py` | 区分DOI、期刊论文、图书、历史文献、聚合阅读和待复核条目 |
| 官网参考文献匹配 | `match_full_official_doi_references.py`、`match_official_references_metadata.py`、`match_gap_a_tier_references_metadata.py` | DOI精确匹配及题名—年份—期刊等书目匹配 |
| 补充候选 | `build_full_candidates_from_li2019.py`、`build_validation_candidates_from_li2019.py`、`enrich_full_li2019_candidates_openalex_mag.py`、`enrich_narrative_candidates_openalex_mag.py` | 使用公开数据生成补充候选，并以MAG/OpenAlex标识符补齐元数据 |
| 候选整合 | `build_full_candidate_registry.py`、`build_candidate_registry_with_gap_matches.py`、`build_duplicate_candidate_resolution_table.py` | 合并、去重、补充官网缺口匹配 |
| 官方贡献对齐 | `build_official_alignment_review.py`、`build_gap_official_reference_candidates.py`、`build_early_official_review_queue.py` | 将候选论文与官网获奖理由、页面片段和PDF线索对齐 |
| 人工复核 | `build_manual_verification_queues.py`、`build_remaining_manual_review_queue.py`、`build_historical_bibliographic_verification_table.py`、`build_narrative_reconstruction_candidates.py`、`build_narrative_candidate_review_table.py`、`enrich_review_table_openalex_doi.py`、`build_non_paper_contribution_table.py` | 生成优先级队列、处理历史书目、叙述性证据和非论文贡献 |
| 质量审计 | `build_validation_coverage_audit.py`、`build_validation_official_targets.py`、`build_official_alignment_review.py` | 覆盖率、证据层级和待复核缺口审计 |
| 主分析入库 | `build_analysis_ready_key_papers.py`、`build_report_inputs_and_workbook.py`、`build_excel_base_workbook.py`、`build_excel_pivot_workbook.ps1`、`add_excel_pivots_and_charts.ps1` | 形成主分析表和工作簿 |
| 后续统计与报告 | `analyze_three_questions.py`、`build_key_paper_openalex_share.py`、`extend_journal_coverage_analysis.py`、`build_nobel_report_docx.py`、`add_report_excel_charts.ps1`、`build_china_nobel_projection_workbook.mjs`、`add_china_nobel_projection_charts.ps1` | 时滞、期刊、国家年度统计与报告产出 |
| 诊断工具 | `probe_openalex_counts.py` | OpenAlex计数口径和API诊断 |

运行主链时应优先使用 `RUNBOOK.md` 的顺序；本索引用于定位辅助脚本和审计脚本。
