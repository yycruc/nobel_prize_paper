# Scope Definition

## Nobel Categories

Include only natural science Nobel categories:

- Physics
- Chemistry
- Physiology or Medicine

Exclude:

- Literature
- Peace
- Economic Sciences

## Time Windows

- Nobel laureate and award baseline: 1901 to latest available Nobel API year.
- Key paper publication lag: key paper publication year to Nobel award year.
- Country-journal publication counts: 1880 to latest complete year available from OpenAlex, with the final year marked if incomplete.

## Country Scope

For country-journal counts, use OpenAlex country codes:

- United States: US
- Japan: JP
- United Kingdom: GB
- France: FR
- Germany: DE
- China: CN

China is treated as China mainland where a source allows that distinction. OpenAlex country code `CN` should be documented as the source's country affiliation interpretation.

## Key Paper Definition

Do not force one paper per laureate. Use two related concepts:

- `key_paper_set`: all papers credibly linked to the Nobel-recognized contribution.
- `main_key_paper`: a representative paper only when a source clearly identifies one.

For lag analysis, compute at least:

- `earliest_key_paper_lag = award_year - earliest_key_paper_year`
- `main_key_paper_lag = award_year - main_key_paper_year`, when available

## Preferred Document Types

For key papers, include original articles, letters, reports, notes, and other historically valid primary research formats. Do not exclude early scientific communications merely because modern document types differ.

For country-journal publication counts, use OpenAlex `works` in the selected source. If document-type filtering is later applied, keep unfiltered counts as a baseline.

