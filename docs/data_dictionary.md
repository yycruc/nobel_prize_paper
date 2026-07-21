# Data Dictionary

## nobel_award_baseline

| field | description |
| --- | --- |
| laureate_id | Nobel API laureate id |
| full_name | Laureate full name |
| award_year | Nobel award year |
| category | Physics, Chemistry, or Physiology or Medicine |
| motivation | Nobel motivation text |
| prize_share | Prize portion |
| affiliation_name | Affiliation at award, if available |
| affiliation_country | Affiliation country at award, if available |
| wikidata_id | Wikidata id from Nobel API, if available |
| nobel_url | Nobel official page |

## key_paper_candidates

| field | description |
| --- | --- |
| candidate_id | Local candidate id |
| laureate_id | Nobel API laureate id |
| award_year | Nobel award year |
| category | Nobel category |
| candidate_title | Candidate paper title |
| candidate_year | Candidate publication year |
| candidate_journal | Candidate journal/source |
| candidate_doi | DOI if available |
| candidate_pmid | PMID if available |
| source_name | Source that identified this candidate |
| source_url_or_path | URL or local path |
| key_paper_role | key_paper_set or main_key_paper |
| notes | Notes on interpretation |

## li2019_key_paper_candidates_full

Full-collection supplementary candidate table created by matching Li et al. 2019 prize-winning paper records to the Nobel full natural-science baseline.

| field | description |
| --- | --- |
| candidate_id | Local Li 2019 full-collection candidate id |
| validation_id | Full-collection laureate-award id, using the `FULL000001` format |
| laureate_id | Nobel API laureate id |
| full_name | Nobel API laureate name |
| award_year | Nobel award year |
| category | Nobel prize category |
| motivation | Nobel official motivation text |
| candidate_title | Candidate title from Li et al. 2019 |
| candidate_year | Candidate publication year from Li et al. 2019 |
| award_lag_years | Award year minus candidate year |
| li2019_field | Field value from Li et al. 2019 |
| li2019_laureate_id | Li et al. 2019 laureate id, not the Nobel API id |
| li2019_laureate_name | Laureate name string from Li et al. 2019 |
| mag_paper_id | MAG Paper ID from Li et al. 2019 when available |
| additional_information | Additional notes from Li et al. 2019 |
| candidate_source_role | supplementary_candidate_generator |
| alignment_status | Whether candidate still needs official-contribution alignment |

## li2019_openalex_mag_matches_full

Full-collection metadata enrichment for Li et al. 2019 candidates using exact OpenAlex `ids.mag` lookup.

| field | description |
| --- | --- |
| mag_paper_id | MAG Paper ID from Li et al. 2019 |
| openalex_work_id | OpenAlex work id returned by exact MAG lookup |
| openalex_title | OpenAlex work title |
| openalex_publication_year | OpenAlex publication year |
| openalex_source | OpenAlex primary source display name |
| openalex_source_id | OpenAlex source id |
| issn_l | OpenAlex source ISSN-L |
| openalex_doi | OpenAlex DOI |
| openalex_type | OpenAlex work type |
| openalex_match_status | matched_by_mag_id, no_openalex_result_for_mag_id, not_queried_no_mag_id, or openalex_error |
| openalex_match_notes | Cache/reuse or error notes |

## candidate_registry_full

Full-collection merged candidate registry built from exact-identifier metadata layers. This is an auditable candidate table, not the final accepted Nobel key-paper table.

| field | description |
| --- | --- |
| registry_id | Local registry id |
| validation_id | Full-collection laureate-award id, using the `FULL000001` format |
| laureate_id | Nobel API laureate id |
| full_name | Nobel API laureate name |
| award_year | Nobel award year |
| category | Nobel prize category |
| work_key | Deduplication key based on OpenAlex work id, DOI, unresolved MAG id, or source row id |
| openalex_work_id | OpenAlex work id when available |
| doi | Normalized DOI when available |
| title | Preferred title from OpenAlex metadata or candidate source |
| publication_year | Preferred publication year from OpenAlex metadata or candidate source |
| journal | OpenAlex primary source display name when available |
| openalex_source_id | OpenAlex source id when available |
| issn_l | OpenAlex source ISSN-L when available |
| work_type | OpenAlex work type when available |
| candidate_year | Candidate publication year from Li 2019 when available |
| award_lag_years | Award year minus candidate year when available |
| evidence_sources | Candidate evidence sources merged into this row |
| source_record_ids | Original source row ids merged into this row |
| li2019_candidate_ids | Li 2019 candidate ids merged into this row |
| li2019_mag_paper_ids | MAG Paper IDs from Li 2019 when available |
| official_reference_ids | Nobel official reference row ids merged into this row |
| source_candidate_titles | Candidate titles from supplementary source datasets |
| official_reference_texts | Official Nobel reference strings when this row came from official DOI references |
| metadata_match_confidence | Metadata confidence only; `A` means exact identifier metadata match, not final key-paper acceptance |
| metadata_match_methods | Exact matching or unresolved status values from source matching layers |
| registry_status | Current candidate interpretation status before final key-paper acceptance |
| review_priority | P1-P5 review priority for official alignment and metadata completion |
| analysis_readiness | Whether metadata is ready for review, not whether the row is final-analysis eligible |
| notes | Interpretation notes |

## candidate_registry_review_queue_full

Review-prioritized copy of `candidate_registry_full`, sorted by `review_priority`, `validation_id`, year, and title. It uses the same fields as `candidate_registry_full`.

## candidate_registry_with_gap_matches_full

Updated candidate registry that preserves `candidate_registry_full` and adds non-D metadata matches from the A-tier official-gap batch.

It uses the same fields as `candidate_registry_full`. Additional rows have `evidence_sources = nobel_official_gap_reference_a_tier` and statuses such as `official_gap_metadata_matched_needs_official_alignment` or `official_gap_metadata_candidate_needs_review`.

## candidate_registry_with_gap_matches_review_queue_full

Review-prioritized copy of `candidate_registry_with_gap_matches_full`, sorted by `review_priority`, `validation_id`, year, and title.

## official_alignment_review_full

Candidate-level official-alignment review table. It joins `candidate_registry_full` with Nobel official motivation text and official-page snippets, then assigns review-priority signals. This table is not a final accepted key-paper table.

| field | description |
| --- | --- |
| registry_id | Local candidate registry id |
| validation_id | Full-collection laureate-award id |
| laureate_id | Nobel API laureate id |
| full_name | Nobel API laureate name |
| award_year | Nobel award year |
| category | Nobel prize category |
| title | Candidate or matched publication title |
| publication_year | Candidate or matched publication year |
| journal | Matched journal/source when available |
| doi | DOI when available |
| openalex_work_id | OpenAlex work id when available |
| candidate_year | Candidate year from the candidate source when available |
| award_lag_years | Award year minus candidate year when available |
| evidence_sources | Candidate evidence sources from the registry |
| registry_status | Registry status before official alignment |
| metadata_match_confidence | Metadata confidence only; not final key-paper confidence |
| metadata_match_methods | Metadata matching status from upstream exact matching |
| motivation | Nobel official motivation text |
| official_pages_available | Count of official Nobel source pages available for this laureate-award record |
| official_pdf_links_available | Count of official Nobel PDF links detected for this record |
| official_snippet_count | Count of official text snippets available for this record |
| official_source_pages | Official source page URLs used for review context |
| top_official_snippets | Selected official snippets most relevant to candidate title terms |
| title_keyword_count | Number of non-stopword title terms used for lexical overlap |
| official_overlap_count | Number of candidate title terms appearing in official motivation or snippets |
| official_overlap_terms | Candidate title terms found in official motivation or snippets |
| motivation_overlap_count | Number of candidate title terms appearing directly in the Nobel motivation |
| motivation_overlap_terms | Candidate title terms found directly in the Nobel motivation |
| candidate_year_mentioned_in_official_text | Whether the candidate year appears in official text snippets |
| alignment_signal | Automatic review signal, such as strong overlap, no signal, official reference present, or metadata unresolved |
| alignment_review_priority | P1-P4 manual review priority |
| alignment_next_action | Recommended next review action |
| final_acceptance_status | Always `not_final_review_required` at this stage |
| alignment_notes | Short explanation of the assigned alignment signal |

## official_alignment_record_summary_full

Record-level summary of official-alignment readiness across the 662 Nobel natural-science laureate-award records.

| field | description |
| --- | --- |
| validation_id | Full-collection laureate-award id |
| laureate_id | Nobel API laureate id |
| full_name | Nobel API laureate name |
| award_year | Nobel award year |
| category | Nobel prize category |
| motivation | Nobel official motivation text |
| registry_rows | Candidate registry rows for this record |
| metadata_ready_rows | Candidate rows with exact metadata ready for review |
| official_reference_rows | Candidate rows from official DOI reference evidence |
| li2019_rows | Candidate rows from Li 2019 |
| high_signal_rows | Rows with strong official text overlap or official reference plus overlap |
| medium_signal_rows | Rows with moderate official text overlap or official reference evidence |
| weak_signal_rows | Rows with weak official text overlap |
| no_signal_rows | Rows with no automatic alignment signal |
| metadata_unresolved_rows | Rows needing identifier or bibliographic metadata completion |
| official_snippet_count | Count of official text snippets available for the record |
| official_pages_available | Count of official source pages available for the record |
| official_pdf_links_available | Count of official PDF links detected for the record |
| record_alignment_status | Record-level readiness class |
| record_next_action | Recommended next action for the record |

## official_alignment_gap_queue_full

Subset of `official_alignment_record_summary_full` containing records with `no_candidate_registry_rows_yet` or `only_metadata_unresolved_candidates`. This is the priority queue for additional candidate collection.

## official_gap_reference_candidates_full

Candidate queue extracted from Nobel official PDF reference sections for records in `official_alignment_gap_queue_full`.

| field | description |
| --- | --- |
| gap_candidate_id | Local id for the gap reference candidate |
| validation_id | Full-collection laureate-award id |
| laureate_id | Nobel API laureate id |
| full_name | Nobel API laureate name |
| award_year | Nobel award year |
| category | Nobel prize category |
| record_alignment_status | Gap status from `official_alignment_record_summary_full` |
| reference_candidate_id | Source row id from official PDF reference extraction |
| pdf_type | Nobel PDF type, such as scientific background or lecture |
| reference_class | Reference classification from `official_reference_classification_full` |
| reference_text | Official Nobel reference text |
| detected_doi | DOI detected in the official reference text, if any |
| detected_years | Years detected in the official reference text |
| candidate_year_for_ranking | Candidate year selected for ranking, usually latest detected year at or before award year |
| year_relation_to_award | Whether the candidate year is before/at award, after award, or unavailable |
| motivation_overlap_count | Number of Nobel motivation terms found in the reference text |
| motivation_overlap_terms | Motivation terms found in the reference text |
| laureate_name_in_reference | Whether laureate family name appears in the reference text |
| ranking_score | Rule-based score for metadata matching priority |
| ranking_tier | A/B/C/D priority tier for next metadata work |
| metadata_next_action | Recommended metadata matching action |
| official_alignment_next_action | Recommended official-alignment action after metadata resolution |
| dedupe_fingerprint | Normalized reference-text fingerprint used for within-record deduplication |

## official_gap_no_reference_queue_full

Subset of `official_alignment_gap_queue_full` for records where no usable official PDF reference candidates were found after boilerplate and Nobel lecture filtering. It uses the same fields as `official_alignment_record_summary_full`.

## official_gap_a_tier_metadata_matches_full

Metadata matching output for the A-tier rows in `official_gap_reference_candidates_full`.

| field | description |
| --- | --- |
| gap_candidate_id | Local id from `official_gap_reference_candidates_full` |
| validation_id | Full-collection laureate-award id |
| laureate_id | Nobel API laureate id |
| full_name | Nobel API laureate name |
| award_year | Nobel award year |
| category | Nobel prize category |
| reference_candidate_id | Source row id from official PDF reference extraction |
| reference_text | Official Nobel reference text |
| detected_years | Years detected in the official reference text |
| detected_doi | DOI detected in the official reference text, if any |
| ranking_score | A-tier source ranking score |
| ranking_tier | Source ranking tier; this table currently contains A-tier inputs |
| crossref_status | Crossref query status |
| crossref_doi | DOI returned by Crossref |
| crossref_title | Title returned by Crossref |
| crossref_year | Publication year returned by Crossref |
| crossref_journal | Journal/source returned by Crossref |
| crossref_type | Crossref work type |
| crossref_score | Internal conservative matching score |
| crossref_match_note | Title/source/year overlap diagnostics; may include OpenAlex search diagnostics |
| openalex_status | OpenAlex DOI or search status |
| openalex_work_id | OpenAlex work id when available |
| openalex_title | OpenAlex title |
| openalex_year | OpenAlex publication year |
| openalex_source | OpenAlex primary source display name |
| openalex_source_id | OpenAlex source id |
| issn_l | OpenAlex source ISSN-L |
| openalex_type | OpenAlex work type |
| openalex_doi | OpenAlex DOI |
| metadata_match_confidence | A, B, C, or D metadata confidence |
| metadata_match_method | Conservative matching method used |
| review_status | metadata_matched_needs_official_alignment, metadata_candidate_needs_review, or no_match |
| notes | API or fallback notes |

## matched_key_papers

| field | description |
| --- | --- |
| candidate_id | Local candidate id |
| openalex_work_id | OpenAlex work id |
| doi | DOI after matching |
| pmid | PMID after matching |
| title | Matched title |
| publication_year | Matched publication year |
| journal | Matched journal/source |
| issn_l | ISSN-L |
| openalex_source_id | OpenAlex source id |
| match_confidence | A, B, C, or D |
| match_method | Exact DOI, title-year-journal, manual, etc. |
| review_status | pending, accepted, rejected, needs_discussion |

## official_reference_metadata_matches

Validation output from matching official Nobel PDF reference strings to Crossref and OpenAlex.

| field | description |
| --- | --- |
| reference_candidate_id | Local id from official PDF reference extraction |
| validation_id | Validation sample id |
| reference_text | Official Nobel PDF reference string |
| reference_years | Years detected in the reference string |
| reference_doi | DOI detected directly in the official reference string |
| crossref_doi | DOI returned by Crossref bibliographic matching |
| crossref_title | Title returned by Crossref |
| crossref_year | Publication year returned by Crossref |
| crossref_journal | Journal/source returned by Crossref |
| openalex_work_id | OpenAlex work id from DOI lookup |
| openalex_journal | OpenAlex primary source display name |
| openalex_source_id | OpenAlex source id |
| issn_l | OpenAlex ISSN-L for the source |
| match_confidence | A, B, C, or D metadata match confidence |
| match_method | Rule used to assign confidence |
| review_status | accepted, needs_review, or no_match |

## official_reference_doi_matches_full

Full-collection metadata output for official Nobel reference strings classified as `doi_present`, matched by exact DOI only.

| field | description |
| --- | --- |
| reference_candidate_id | Local official-reference candidate id |
| validation_id | Full-collection laureate-award record id, using the `FULL000001` format |
| reference_text | Official Nobel reference text from the PDF reference section |
| reference_doi | DOI extracted and repaired from the official reference text |
| openalex_match_status | matched_openalex_doi, no_openalex_result, openalex_error, or not_queried |
| openalex_work_id | OpenAlex work id returned by exact DOI lookup |
| openalex_title | OpenAlex work title |
| openalex_year | OpenAlex publication year |
| openalex_source | OpenAlex primary source display name |
| openalex_source_id | OpenAlex source id |
| issn_l | OpenAlex source ISSN-L |
| openalex_type | OpenAlex work type |
| crossref_match_status | Crossref fallback status; normally not_queried when OpenAlex matched |
| metadata_match_status | matched_openalex_exact_doi, matched_crossref_exact_doi, unmatched |
| match_confidence | A for exact DOI metadata match; D for unmatched |
| review_status | metadata_matched or needs_review |
| notes | Cache/reuse, repair, or error notes |

## official_reference_classification

Validation output from classifying official Nobel PDF reference strings before API metadata matching.

| field | description |
| --- | --- |
| reference_candidate_id | Local id from official PDF reference extraction |
| validation_id | Validation sample id |
| reference_text | Official Nobel PDF reference string |
| detected_doi | DOI detected in the reference string |
| detected_years | Years detected in the reference string |
| reference_class | doi_present, likely_journal_article, historical_nonindexed_reference, book_or_chapter, aggregate_further_reading, or needs_manual_review |
| api_matchable | Whether the row should be sent to metadata APIs in the current stage |
| matching_priority | Lower number means earlier matching stage |
| classification_reason | Rule-based explanation for the classification |
| review_status | ready_for_metadata_matching or manual_or_later_review |

## early_official_narrative_review_queue

Validation queue for Nobel records where official materials define the contribution but do not provide structured paper-level references.

| field | description |
| --- | --- |
| validation_id | Validation sample id |
| official_contribution_text | Nobel motivation text from the validation sample |
| official_evidence_level | Current evidence type, usually narrative-only |
| official_source_pages | Nobel official pages containing supporting narrative |
| official_evidence_snippets | Extracted official snippets to guide review |
| recommended_external_query | Suggested targeted query for external bibliographic metadata |
| review_action | Next review action |
| review_status | Manual review state |

## validation_coverage_audit

Validation-level coverage audit by laureate-award record.

| field | description |
| --- | --- |
| validation_id | Validation sample id |
| li2019_candidate_rows | Candidate rows from Li et al. 2019 |
| official_pdf_reference_rows | Official Nobel PDF reference rows extracted |
| api_matchable_official_reference_rows | Official reference rows classified as ready for API metadata matching |
| manual_or_later_official_reference_rows | Official reference rows held for manual or later review |
| accepted_metadata_match_rows_partial | A/B metadata matches currently available from partial validation |
| in_early_narrative_review_queue | Whether official evidence is narrative-only and requires targeted review |
| coverage_status | Current validation coverage state |

## narrative_reconstruction_candidates

Candidate reconstruction table for validation records where Nobel official materials provide narrative evidence but no structured official reference section.

| field | description |
| --- | --- |
| reconstruction_id | Local reconstruction row id |
| validation_id | Validation sample id |
| official_contribution_text | Nobel official motivation/contribution text |
| official_source_pages | Nobel official pages used as evidence anchors |
| official_evidence_snippets | Short official snippets guiding reconstruction |
| candidate_title | Candidate key work title, if currently known |
| candidate_year | Candidate publication or contribution year |
| award_lag_years | Award year minus candidate year |
| candidate_journal | Journal/source if known |
| candidate_source | Candidate generator source, such as Li 2019 or manual seed |
| candidate_source_detail | Source-specific notes or URL |
| metadata_needed | Remaining metadata fields to verify |
| recommended_metadata_query | Query string for targeted verification |
| reconstruction_status | public_dataset_candidate_needs_official_alignment_and_metadata, needs_manual_verification, non_paper_contribution_review, or no_public_dataset_candidate_needs_targeted_bibliographic_search |
| review_notes | Interpretation and acceptance notes |

## narrative_reconstruction_openalex_mag_matches

Metadata enrichment table for narrative reconstruction candidates using Li et al. 2019 MAG Paper IDs and OpenAlex `ids.mag` exact lookup.

| field | description |
| --- | --- |
| mag_paper_id | MAG Paper ID parsed from Li et al. 2019 candidate notes |
| openalex_work_id | OpenAlex work id matched by MAG id |
| openalex_title | OpenAlex title |
| openalex_publication_year | OpenAlex publication year |
| openalex_journal | OpenAlex primary source display name |
| openalex_source_id | OpenAlex source id |
| issn_l | OpenAlex source ISSN-L |
| openalex_doi | DOI from OpenAlex |
| openalex_type | OpenAlex work type |
| openalex_match_status | matched_by_mag_id, no_openalex_result_for_mag_id, openalex_error, or not_queried_no_mag_id |

## narrative_candidate_review_table

Review-ready table combining narrative reconstruction candidates and OpenAlex MAG metadata.

| field | description |
| --- | --- |
| matched_title | Preferred title after metadata matching |
| matched_year | Preferred publication year after metadata matching |
| matched_journal | Preferred journal/source after metadata matching |
| doi | Normalized DOI when available |
| analysis_eligibility | journal_candidate_matched, manual_seed_review, non_paper_review, matched_missing_source, mag_unresolved, or unresolved_metadata |
| review_status | provisionally_accept_metadata or needs_manual_review |
| review_note | Reason for review status |

## remaining_manual_review_queue

Prioritized queue of narrative candidate rows still requiring review after MAG and DOI exact matching.

| field | description |
| --- | --- |
| review_priority | P1 method decision, P2 historical bibliographic verification, P3 identifier/source gap, or P4 general unresolved metadata |
| next_action | Recommended next action |
| analysis_eligibility | Current eligibility class from the review table |
| reconstruction_status | Original reconstruction status |
| review_note | Reason the row remains unresolved |

## historical_bibliographic_verification_table

Manually verified bibliographic metadata for early or historically important key-paper candidates that are not fully resolved by OpenAlex/Crossref API matching.

| field | description |
| --- | --- |
| candidate_title_original | Candidate title before manual normalization |
| canonical_title | Manually verified title used for analysis |
| canonical_year | Manually verified publication year |
| canonical_source | Manually verified journal or source title |
| volume_issue_pages | Volume, issue, and page metadata when available |
| stable_identifier | DOI, OpenAlex id, or blank if no stable identifier is available |
| award_lag_years | Award year minus canonical publication year |
| verification_source_1 | Primary bibliographic verification URL |
| verification_source_2 | Secondary verification URL |
| verification_status | Current manual verification status |
| metadata_match_status | How this record should be interpreted in metadata matching |
| main_journal_analysis_status | Whether the record can enter journal-level analysis |
| verification_note | Short explanation of the verification decision |

## duplicate_candidate_resolution_table

Manual resolution table for duplicate candidate rows where a weaker or alternate title should be excluded because a stronger matched record already represents the same key work.

| field | description |
| --- | --- |
| duplicate_candidate_title | Candidate title being excluded as duplicate |
| duplicate_candidate_year | Candidate publication year from the source dataset |
| duplicate_of_title | Accepted matched title representing the same key work |
| duplicate_of_openalex_work_id | OpenAlex work id for the retained record |
| duplicate_of_doi | DOI for the retained record |
| duplicate_of_source | Journal/source for the retained record |
| resolution_status | Duplicate-resolution status |
| main_analysis_status | Whether the duplicate candidate enters main analysis |
| resolution_note | Reason for excluding the duplicate |

## non_paper_contribution_table

Separate table for Nobel-recognized contributions that are patent-, process-, method-, or monograph-centered rather than journal-paper-centered.

| field | description |
| --- | --- |
| contribution_type | patent_or_process, monograph_or_book, or non_journal_contribution |
| candidate_title_or_record | Candidate non-paper key work or record |
| source_or_record | Patent record, publisher, lecture series, or other non-journal source |
| main_journal_analysis_status | Whether excluded from top-journal main analysis |
| comprehensive_dataset_status | How the contribution is retained in the comprehensive Nobel coverage dataset |
| sensitivity_analysis_status | Whether proxy-paper sensitivity analysis may be added later |

## country_journal_year_counts

| field | description |
| --- | --- |
| journal_rank | Rank among Nobel key-paper journals |
| journal | Journal/source display name |
| issn_l | ISSN-L |
| openalex_source_id | OpenAlex source id |
| country_code | US, JP, GB, FR, DE, CN |
| country_name | Country display name |
| year | Publication year |
| publication_count | OpenAlex work count |
| count_filter | Exact OpenAlex filter used |
| retrieved_at | Retrieval timestamp |

## analysis_ready_key_papers_full

Main analysis table used for the three research questions. It includes metadata-ready key-paper candidates only; lower-confidence and review-only rows are excluded into a separate table.

| field | description |
| --- | --- |
| analysis_id | Local analysis-row id |
| registry_id | Source row id in `candidate_registry_with_gap_matches_full` |
| validation_id | Full-collection laureate-award id |
| laureate_id | Nobel API laureate id |
| full_name | Nobel laureate name |
| award_year | Nobel award year |
| category | Nobel category |
| title | Key-paper candidate title |
| publication_year | Publication year used for lag calculation |
| award_lag_years | Award year minus publication year |
| journal | Journal/source used for journal ranking |
| openalex_source_id | OpenAlex source id |
| issn_l | Source ISSN-L |
| doi | DOI when available |
| openalex_work_id | OpenAlex work id |
| work_type | OpenAlex/Crossref work type |
| evidence_sources | Candidate evidence source |
| registry_status | Source registry status |
| analysis_inclusion | `main` for rows included in analysis |
| analysis_confidence | B-level main-analysis confidence in the current workflow |
| analysis_role | Inclusion route, such as Li 2019 exact MAG or official gap metadata match |
| notes | Inclusion caveat |

## analysis_excluded_or_review_key_paper_candidates_full

Rows from the updated registry that were not included in the main analysis table because metadata or key-paper relevance remained insufficient.

## q1_lag_by_award_year

Annual summary of key-paper publication-to-award lag.

| field | description |
| --- | --- |
| award_year | Nobel award year |
| key_paper_rows | Key-paper rows in that award year |
| covered_nobel_records | Nobel records represented in that award year |
| mean_lag_years | Mean publication-to-award lag |
| median_lag_years | Median publication-to-award lag |
| min_lag_years | Minimum lag |
| max_lag_years | Maximum lag |

## q1_lag_by_award_decade

Decade-level summary of key-paper publication-to-award lag.

## q2_top10_key_paper_journals

Top 10 journals/sources by count of main-analysis Nobel key-paper rows.

## q3_country_journal_year_counts_top10

OpenAlex country-journal-year article count panel for the top 10 Nobel key-paper journals, six countries, and 1880-2025.

## q3_country_year_counts_top10_aggregate

Country-year aggregate of article counts across the top 10 Nobel key-paper journals.
