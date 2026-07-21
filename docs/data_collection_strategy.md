# Data Collection Strategy

## Overview

Use a layered strategy:

1. Build the Nobel award baseline from the official Nobel Prize API.
2. Build a candidate key-paper pool from Nobel official materials first, then public datasets.
3. Match candidate papers to bibliographic metadata using OpenAlex, Crossref, PubMed, DOI, and manual review where needed.
4. Score match confidence.
5. Run validation before full collection.
6. Use the validated top 10 journals to collect country-journal-year counts from OpenAlex.

## Source Priority

### Baseline Laureates and Awards

Primary source:

- Nobel Prize API v2.1

Fields:

- laureate id
- full name
- award year
- category
- motivation
- prize share
- affiliation at award
- Nobel page links
- Wikidata and Wikipedia links

### Candidate Key Papers

Use multiple sources because no single source is complete enough.

Priority sources:

1. Nobel official scientific background, advanced information, Nobel lecture, biography, press release, popular information, and prize pages.
2. Published public datasets of Nobel prize-winning papers.
3. Wikidata references and identifiers.
4. PubMed for biomedical papers.
5. Crossref and OpenAlex for DOI, journal, year, source id, and author metadata.

Nobel official materials should define the primary analytical scope wherever they provide enough bibliographic detail. Public datasets should be treated as candidate generators and cross-checks, not as the final authority.

### Reference Classification Before API Matching

Do not send every official reference string directly to Crossref/OpenAlex. First classify official references into:

- doi_present
- likely_journal_article
- book_or_chapter
- aggregate_further_reading
- historical_nonindexed_reference
- needs_manual_review

Then match in stages:

1. DOI-bearing references by DOI.
2. Short journal-article references by title, year, and journal.
3. Unmatched but plausible references through fallback OpenAlex/Crossref/PubMed searches.
4. Narrative-only or historical cases by manual review anchored to Nobel official contribution text.

This staged design is required because validation found Crossref free-text matching can stall on batches of official reference strings.

## Matching Confidence

Assign one of these levels:

- A: DOI, PMID, or OpenAlex ID exact match.
- B: normalized title plus year plus journal plus at least one laureate author match.
- C: fuzzy title plus year tolerance plus journal alias or translated title match.
- D: source-only claim without enough bibliographic confirmation.

Main analysis should use A and B records. C and D records should be reviewed or used only in sensitivity checks.

## Validation Sample

Target about 45 laureate-award records:

- Physics: 5 early, 5 middle, 5 recent
- Chemistry: 5 early, 5 middle, 5 recent
- Physiology or Medicine: 5 early, 5 middle, 5 recent

Suggested windows:

- early: 1901-1939
- middle: 1940-1989
- recent: 1990-latest

## Full Collection Trigger

Proceed to full collection only if validation shows:

- high recall of key papers from the candidate-source pool
- acceptable match confidence
- manageable manual review burden
- stable OpenAlex source matching for the top journals
- API rate limits are controlled through caching and retries
