# Stop Conditions

Stop and discuss before continuing if any of these occur.

## Key Paper Scope Problems

- A laureate's Nobel contribution is not traceable to a paper or paper set.
- Sources disagree materially on the key paper.
- A Nobel award is for an instrument, method, discovery, or theory where a single paper is misleading.
- More than 20 percent of validation records only reach confidence level C or D.

## Metadata Matching Problems

- OpenAlex cannot match a large share of early key papers.
- DOI/PMID metadata conflicts with title, year, or journal.
- Journal identity is unclear because of title changes, translations, mergers, or series names.
- Laureate author matching is ambiguous due to common names or transliteration.

## Count Data Problems

- OpenAlex source matching fails for any top 10 journal.
- OpenAlex country affiliation coverage is too sparse before a critical year.
- Publication counts are unexpectedly zero or implausibly high for major journals.
- API rate limiting prevents reproducible collection.

## Governance Problems

- A source requires institutional login, account credentials, cookies, or captcha handling.
- A source's terms do not allow automated download.
- A dataset license does not allow the planned reuse.

## Required Response

When a stop condition is hit:

1. Write the issue to `00_admin/issue_log.csv`.
2. Preserve raw evidence if already downloaded.
3. Do not continue to full collection.
4. Ask for a decision on the specific issue.

