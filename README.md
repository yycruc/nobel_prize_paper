# 诺奖关键论文证据链

本仓库实现从 Nobel Prize 官方页面检索、网页/PDF 证据提取、参考文献分类、Crossref/OpenAlex 元数据匹配、候选论文登记、人工复核到分析数据生成的完整流程。

## 重要说明

诺奖官网通常提供获奖理由和背景材料，不一定直接指定完整的获奖论文。因此，自动程序生成候选结果，最终纳入论文仍需人工核查并保留决策记录。

仓库不包含原始网页/PDF缓存、Li et al. (2019) 原始数据、API响应缓存和最终人工判断结果。使用者须自行取得具有合法使用权的数据。

## 快速开始（Windows）

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python preflight.py
```

完整使用方法请阅读 [RUNBOOK.md](RUNBOOK.md)。建议先运行验证样本，再按阶段执行全量流程。

## 外部数据

完整流程需要将 Li et al. (2019) 的公开候选数据放置于：

```text
02_full_collection/01_raw_sources/public_datasets/li_2019_prize_winning_paper_record.tab
```

程序还会访问 Nobel Prize 官方网站、Crossref 和 OpenAlex，因此需要网络连接，并应遵守各服务的使用条款和请求频率限制。

## 目录说明

- `03_scripts/`：采集、提取、匹配、复核和分析脚本；
- `docs/`：研究范围、数据字典、来源登记表和停止条件；
- `RUNBOOK.md`：分阶段运行手册；
- `run_pipeline.ps1`：主流程预览/执行器；
- `preflight.py`：环境、依赖和语法检查。

## 研究边界

官方 reference、Crossref/OpenAlex 候选记录和最终“关键论文”认定必须区分。外部数据库只能帮助标准化标题、作者、年份、期刊和 DOI，不能自动证明一篇论文就是诺奖关键论文。

## 许可

本仓库代码采用 MIT License；第三方数据、官网内容和下载文件不包含在许可范围内，请分别遵守其来源许可。
