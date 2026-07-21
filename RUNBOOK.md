# 运行手册：官网证据链采集、匹配与复核

## 0. 方法原则

本包严格区分三件事：

1. **官网证据**：获奖理由界定成果范围；`Advanced information` / `Scientific background` 的参考文献、明确论文叙述和官网PDF链接构成论文候选线索。
2. **书目匹配**：OpenAlex、Crossref 和补充数据仅用于把候选线索解析为结构化论文记录。
3. **关键论文认定**：必须检查候选论文与获奖者、获奖理由和官网贡献叙述是否直接相关；此步骤保留人工复核。

不要把官网参考文献自动当成获奖论文，也不要把外部数据库或公开数据集生成的候选论文自动当成官网认定结果。

## 1. 环境与外部输入

安装 Python 依赖后运行 `python preflight.py`。程序的网络访问使用 Python 标准库；无需在代码中写入密钥。

全量匹配阶段还需要将公开的 Li et al. (2019) 论文候选数据保存为：

```text
02_full_collection/01_raw_sources/public_datasets/li_2019_prize_winning_paper_record.tab
```

该数据仅作为补充候选生成器。若该文件不可用，官网参考文献采集、分类和精确DOI匹配仍可运行，但“官网证据不足时的补充候选”部分会缺失。

## 2. 先做验证样本

原始项目采用“验证优先”策略。建议先按以下顺序运行验证脚本，再扩大到全量：

```powershell
python 03_scripts/probe_nobel_api.py
python 03_scripts/select_validation_sample.py
python 03_scripts/build_validation_official_targets.py
python 03_scripts/fetch_validation_official_pages.py --all --resume
python 03_scripts/extract_official_page_clues.py
python 03_scripts/fetch_official_pdfs.py
python 03_scripts/extract_official_pdf_reference_sections.py
python 03_scripts/classify_official_references.py
python 03_scripts/match_official_references_metadata.py
python 03_scripts/build_validation_coverage_audit.py
```

验证阶段检查：官网页面覆盖率、PDF可下载性、参考文献分类质量、DOI/书目信息匹配率，以及叙述性证据所需人工复核的规模。停止条件见 `docs/stop_conditions.md`。

## 3. 全量采集与提取

可用 `run_pipeline.ps1` 预览全量主要命令。下列阶段均会在 `02_full_collection/` 下生成原始响应、状态表和日志。

| 阶段 | 主要脚本 | 作用 | 主要输出 |
| --- | --- | --- | --- |
| 奖项基准 | `build_full_nobel_baseline.py` | 从 Nobel Prize API 生成自然科学“获奖人—奖项”基准表 | `nobel_award_baseline_full.csv` |
| 官网目标 | `build_full_official_targets.py` | 为每条奖项记录生成 facts、summary、press release、popular、advanced 页面目标 | `official_targets_full.csv` |
| 页面抓取 | `fetch_validation_official_pages.py` | 下载官网页面；通过参数用于全量路径 | 页面缓存和抓取状态表 |
| 二级页面 | `extract_official_secondary_targets.py` | 从 facts 页面提取官网讲座、传记、文章等二级链接 | `official_secondary_targets_full.csv` |
| 网页线索 | `extract_official_page_clues.py` | 提取PDF链接、DOI与参考文献样式文本 | `official_page_bibliographic_clues_full.csv` |
| PDF线索 | `fetch_official_pdfs.py`、`extract_official_pdf_clues.py` | 下载官方PDF并提取可能的书目信息 | PDF状态表和线索表 |
| 参考文献段 | `extract_official_pdf_reference_sections.py` | 从官方PDF抽取参考文献条目 | 分类前参考文献表 |
| 分类 | `classify_official_references.py` | 区分 DOI、期刊论文、图书/章节、综述性阅读、历史资料和待复核项 | `official_reference_classification_full.csv` |

## 4. 元数据匹配

匹配遵循“精确标识符优先”的顺序：

1. `match_full_official_doi_references.py`：从官方参考文献中的 DOI 出发，优先用 OpenAlex 精确匹配，必要时再用 Crossref；这是A类元数据匹配。
2. `match_official_references_metadata.py`：用于验证样本或非DOI参考文献的题名、作者、年份和期刊匹配；会保留匹配分数与不确定项。
3. `build_full_candidates_from_li2019.py` 与 `enrich_full_li2019_candidates_openalex_mag.py`：将 Li et al. (2019) 的公开记录作为补充候选，再通过 MAG/OpenAlex 标识符补齐元数据。
4. `build_full_candidate_registry.py`：以 DOI、OpenAlex Work ID、MAG ID 或源记录ID合并去重，形成可审计候选总表。

匹配置信度：A为 DOI/PMID/OpenAlex ID 精确匹配；B为题名、年份、期刊及作者等多字段一致；C为模糊匹配；D为未充分确认。A/B可进入下一步官方贡献复核，C/D保留待复核或敏感性分析。

## 5. 官方贡献对齐与人工复核

`build_official_alignment_review.py` 将候选论文与获奖理由、官网页面片段和PDF链接合并，生成优先级队列；`build_gap_official_reference_candidates.py` 专门处理“有官网记录但候选不足”的奖项记录；`match_gap_a_tier_references_metadata.py` 处理其中优先级最高的参考文献；`build_manual_verification_queues.py`、`build_historical_bibliographic_verification_table.py`、`build_duplicate_candidate_resolution_table.py` 和 `build_non_paper_contribution_table.py` 支持人工决策。

人工复核至少检查：

- 论文是否在获奖前发表；
- 作者、研究主题和技术路线是否与官网获奖理由或科学背景直接对应；
- 该条参考文献是核心发现论文、背景文献、综述、图书还是非论文贡献；
- 是否存在同一工作被不同题名、预印本/期刊版或重复来源重复记录的情形。

人工确认的结论应保存在复核表中，而不是直接覆盖原始网页线索或元数据匹配表。

## 6. 最终入库与分析

`build_analysis_ready_key_papers.py` 将通过元数据与贡献对齐要求的记录写入主分析表，同时将不满足条件的候选单列；`analyze_three_questions.py`、`build_key_paper_openalex_share.py`、`extend_journal_coverage_analysis.py` 和报表脚本用于后续时滞、期刊与国家年度统计分析。

建议每次全量运行后保留：`00_admin/query_log.csv`、各阶段 `*_summary*.json`、原始官网页面/PDF状态表、候选注册表、官方对齐复核表和人工复核决策表。这样可从最终一条关键论文回溯到官网页面、参考条目和元数据匹配过程。

