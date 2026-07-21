param(
    [ValidateSet('baseline', 'targets', 'fetch', 'extract', 'match', 'review', 'analysis', 'all')]
    [string]$Stage = 'all',
    [switch]$Execute
)

$ErrorActionPreference = 'Stop'
$PackageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $PackageRoot
$Python = 'python'

# These commands operate on the package's prescribed directory structure.
# They are intentionally printed by default. Use -Execute only after reading RUNBOOK.md.
$Stages = [ordered]@{
    baseline = @(
        @($Python, '03_scripts/build_full_nobel_baseline.py')
    )
    targets = @(
        @($Python, '03_scripts/build_full_official_targets.py')
    )
    fetch = @(
        @($Python, '03_scripts/fetch_validation_official_pages.py', '--all', '--resume', '--targets-csv', '02_full_collection/01_raw_sources/nobel_official_pages/official_targets_full.csv', '--status-csv', '02_full_collection/01_raw_sources/nobel_official_pages/official_page_fetch_status_full.csv', '--pages-dir', '02_full_collection/01_raw_sources/nobel_official_pages/pages'),
        @($Python, '03_scripts/extract_official_secondary_targets.py', '--status-csv', '02_full_collection/01_raw_sources/nobel_official_pages/official_page_fetch_status_full.csv', '--out-csv', '02_full_collection/01_raw_sources/nobel_official_pages/official_secondary_targets_full.csv'),
        @($Python, '03_scripts/fetch_validation_official_pages.py', '--all', '--resume', '--targets-csv', '02_full_collection/01_raw_sources/nobel_official_pages/official_secondary_targets_full.csv', '--status-csv', '02_full_collection/01_raw_sources/nobel_official_pages/official_page_fetch_status_full.csv', '--pages-dir', '02_full_collection/01_raw_sources/nobel_official_pages/pages')
    )
    extract = @(
        @($Python, '03_scripts/extract_official_page_clues.py', '--status-csv', '02_full_collection/01_raw_sources/nobel_official_pages/official_page_fetch_status_full.csv', '--out-csv', '02_full_collection/02_candidate_key_papers/official_page_bibliographic_clues_full.csv', '--summary-json', '02_full_collection/05_outputs/official_page_clues_summary_full.json'),
        @($Python, '03_scripts/fetch_official_pdfs.py', '--clue-files', '02_full_collection/02_candidate_key_papers/official_page_bibliographic_clues_full.csv', '--pdf-dir', '02_full_collection/01_raw_sources/nobel_official_pages/pdfs', '--status-csv', '02_full_collection/01_raw_sources/nobel_official_pages/official_pdf_fetch_status_full.csv'),
        @($Python, '03_scripts/extract_official_pdf_clues.py', '--pdf-status-csv', '02_full_collection/01_raw_sources/nobel_official_pages/official_pdf_fetch_status_full.csv', '--out-csv', '02_full_collection/02_candidate_key_papers/official_pdf_bibliographic_clues_full.csv', '--summary-json', '02_full_collection/05_outputs/official_pdf_clues_summary_full.json'),
        @($Python, '03_scripts/extract_official_pdf_reference_sections.py', '--pdf-status-csv', '02_full_collection/01_raw_sources/nobel_official_pages/official_pdf_fetch_status_full.csv', '--out-csv', '02_full_collection/02_candidate_key_papers/official_reference_classification_input_full.csv', '--summary-json', '02_full_collection/05_outputs/official_pdf_reference_sections_summary_full.json'),
        @($Python, '03_scripts/classify_official_references.py', '--refs-csv', '02_full_collection/02_candidate_key_papers/official_reference_classification_input_full.csv', '--out-csv', '02_full_collection/02_candidate_key_papers/official_reference_classification_full.csv', '--summary-json', '02_full_collection/05_outputs/official_reference_classification_summary_full.json')
    )
    match = @(
        @($Python, '03_scripts/match_full_official_doi_references.py'),
        @($Python, '03_scripts/build_full_candidates_from_li2019.py'),
        @($Python, '03_scripts/enrich_full_li2019_candidates_openalex_mag.py'),
        @($Python, '03_scripts/build_full_candidate_registry.py')
    )
    review = @(
        @($Python, '03_scripts/build_official_alignment_review.py'),
        @($Python, '03_scripts/build_gap_official_reference_candidates.py'),
        @($Python, '03_scripts/match_gap_a_tier_references_metadata.py'),
        @($Python, '03_scripts/build_candidate_registry_with_gap_matches.py'),
        @($Python, '03_scripts/build_manual_verification_queues.py')
    )
    analysis = @(
        @($Python, '03_scripts/build_analysis_ready_key_papers.py'),
        @($Python, '03_scripts/analyze_three_questions.py')
    )
}

$Selected = if ($Stage -eq 'all') { @('baseline', 'targets', 'fetch', 'extract', 'match', 'review', 'analysis') } else { @($Stage) }
foreach ($CurrentStage in $Selected) {
    Write-Host "`n[$CurrentStage]"
    foreach ($Command in $Stages[$CurrentStage]) {
        $Display = $Command | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }
        Write-Host ('  ' + ($Display -join ' '))
        if ($Execute) {
            & $Command[0] $Command[1..($Command.Count - 1)]
            if ($LASTEXITCODE -ne 0) { throw "Command failed in stage $CurrentStage" }
        }
    }
}

if (-not $Execute) {
    Write-Host "`nPreview only. Read RUNBOOK.md, place required external inputs, then rerun with -Execute."
}
