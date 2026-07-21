# Nobel Key Papers Analysis

This project collects and validates data for three research questions:

1. For natural science Nobel laureates since 1901, measure the lag between key paper publication and Nobel award year.
2. Identify the journals where key Nobel-related papers were published, and rank the top 10 journals.
3. Since 1880, count annual publications by the United States, Japan, United Kingdom, France, Germany, and China in those top 10 journals.

The workflow is validation-first. Do not run full collection until the validation sample passes the quality gates in `00_admin/stop_conditions.md`.

## Directory Layout

```text
00_admin/
  project_readme.md
  scope_definition.md
  data_collection_strategy.md
  stop_conditions.md
  data_dictionary.md
  source_registry.csv
  query_log.csv
  issue_log.csv

01_validation/
  validation_protocol.md
  validation_sample_template.csv
  01_raw_sources/
  02_candidate_key_papers/
  03_matched_metadata/
  04_outputs/

02_full_collection/
  01_raw_sources/
  02_candidate_key_papers/
  03_matched_metadata/
  04_country_journal_counts/
  05_outputs/

03_scripts/
  probe_nobel_api.py
  probe_openalex_counts.py

04_logs/
  errors/

05_final_inputs_for_report/
  final_tables/
  final_figures/
  final_references/
```

## Execution Rule

Phase 1 is a validation study only. It should test coverage, matching quality, and ambiguous cases on a small sample before any full-scale collection.

Full collection begins only after:

- Nobel API baseline table can be reproduced.
- Key-paper candidate sources are compared on the validation sample.
- OpenAlex/Crossref/PubMed matching rules produce acceptable confidence.
- Ambiguous key-paper definitions are reviewed.
- API rate limits and cache strategy are confirmed.

