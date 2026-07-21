$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$AnalysisCsv = Join-Path $Root "02_full_collection\06_analysis\analysis_ready_key_papers_full.csv"
$Q2Csv = Join-Path $Root "02_full_collection\06_analysis\q2_top10_key_paper_journals.csv"
$Q3PanelCsv = Join-Path $Root "02_full_collection\06_analysis\q3_country_journal_year_counts_top10.csv"
$Q3AggCsv = Join-Path $Root "02_full_collection\06_analysis\q3_country_year_counts_top10_aggregate.csv"
$OutputDir = Join-Path $Root "02_full_collection\07_excel"
$OutputXlsx = Join-Path $OutputDir "nobel_key_papers_pivot_analysis.xlsx"
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

function To-Decade([int]$Year) {
    return ("{0}s" -f ([math]::Floor($Year / 10) * 10))
}

function Convert-ToMatrix($Rows, [string[]]$Columns) {
    $rowCount = $Rows.Count + 1
    $colCount = $Columns.Count
    $matrix = New-Object "object[,]" $rowCount, $colCount
    for ($c = 0; $c -lt $colCount; $c++) {
        $matrix[0, $c] = $Columns[$c]
    }
    for ($r = 0; $r -lt $Rows.Count; $r++) {
        $props = $Rows[$r].PSObject.Properties
        for ($c = 0; $c -lt $colCount; $c++) {
            $value = $props.Item($Columns[$c]).Value
            if ($null -eq $value) {
                $matrix[$r + 1, $c] = $null
            } elseif ($value -is [int] -or $value -is [double]) {
                $matrix[$r + 1, $c] = $value
            } else {
                $matrix[$r + 1, $c] = [string]$value
            }
        }
    }
    return ,$matrix
}

function Add-DataSheet($Workbook, [string]$Name, $Rows, [string[]]$Columns, [string]$TableName) {
    Write-Host "Adding data sheet $Name ($($Rows.Count) rows)"
    $sheet = $Workbook.Worksheets.Add()
    $sheet.Name = $Name
    Write-Host "Building matrix for $Name"
    $matrix = Convert-ToMatrix $Rows $Columns
    $rowCount = $Rows.Count + 1
    $colCount = $Columns.Count
    $range = $sheet.Range($sheet.Cells(1, 1), $sheet.Cells($rowCount, $colCount))
    Write-Host "Writing range for $Name"
    $range.Value2 = $matrix
    Write-Host "Adding Excel table for $Name"
    $table = $sheet.ListObjects.Add(1, $range, $null, 1)
    $table.Name = $TableName
    $table.TableStyle = "TableStyleMedium2"
    $sheet.Rows.Item(1).Font.Bold = $true
    for ($i = 1; $i -le $colCount; $i++) {
        $sheet.Columns.Item($i).ColumnWidth = 16
    }
    Write-Host "Data sheet $Name done"
    return @{ Sheet = $sheet; Table = $table }
}

function Set-Header($Sheet, [string]$Title, [string]$Subtitle) {
    $Sheet.Range("A1:H1").Merge() | Out-Null
    $Sheet.Range("A1").Value2 = $Title
    $Sheet.Range("A1").Font.Bold = $true
    $Sheet.Range("A1").Font.Size = 16
    $Sheet.Range("A2:H3").Merge() | Out-Null
    $Sheet.Range("A2").Value2 = $Subtitle
    $Sheet.Range("A2").WrapText = $true
    $Sheet.Range("A1:H3").Interior.Color = 15921906
    $Sheet.Range("A1:H3").Borders.LineStyle = 1
}

function Add-PivotChart($Sheet, $PivotTable, [string]$Title, [int]$ChartType, [double]$Left, [double]$Top, [double]$Width, [double]$Height) {
    $chartObject = $Sheet.ChartObjects().Add($Left, $Top, $Width, $Height)
    $chart = $chartObject.Chart
    $chart.SetSourceData($PivotTable.TableRange1)
    $chart.ChartType = $ChartType
    $chart.HasTitle = $true
    $chart.ChartTitle.Text = $Title
    $chart.HasLegend = $true
    return $chartObject
}

function Add-PivotTable($Workbook, $SourceTable, $DestSheet, [string]$Name, [string]$DestCell) {
    $cache = $Workbook.PivotCaches().Create(1, $SourceTable.Range)
    $pivot = $cache.CreatePivotTable($DestSheet.Range($DestCell), $Name)
    return $pivot
}

$keyRows = Import-Csv -LiteralPath $AnalysisCsv | ForEach-Object {
    $awardYear = [int]$_.award_year
    $pubYear = [int]$_.publication_year
    [pscustomobject]@{
        analysis_id = $_.analysis_id
        registry_id = $_.registry_id
        validation_id = $_.validation_id
        laureate_id = $_.laureate_id
        full_name = $_.full_name
        award_year = $awardYear
        award_decade = To-Decade $awardYear
        category = $_.category
        title = $_.title
        publication_year = $pubYear
        publication_decade = To-Decade $pubYear
        award_lag_years = [int]$_.award_lag_years
        journal = $_.journal
        openalex_source_id = $_.openalex_source_id
        issn_l = $_.issn_l
        doi = $_.doi
        openalex_work_id = $_.openalex_work_id
        evidence_sources = $_.evidence_sources
        analysis_role = $_.analysis_role
    }
}
$keyColumns = @("analysis_id","registry_id","validation_id","laureate_id","full_name","award_year","award_decade","category","title","publication_year","publication_decade","award_lag_years","journal","openalex_source_id","issn_l","doi","openalex_work_id","evidence_sources","analysis_role")

$topRows = Import-Csv -LiteralPath $Q2Csv | ForEach-Object {
    [pscustomobject]@{
        rank = [int]$_.rank
        journal = $_.journal
        key_paper_rows = [int]$_.key_paper_rows
        covered_nobel_records = [int]$_.covered_nobel_records
        openalex_source_id = $_.openalex_source_id
        issn_l = $_.issn_l
    }
}
$topColumns = @("rank","journal","key_paper_rows","covered_nobel_records","openalex_source_id","issn_l")

$panelRows = Import-Csv -LiteralPath $Q3PanelCsv | ForEach-Object {
    $year = [int]$_.year
    [pscustomobject]@{
        journal_rank = [int]$_.journal_rank
        journal = $_.journal
        openalex_source_id = $_.openalex_source_id
        issn_l = $_.issn_l
        country_code = $_.country_code
        country_name = $_.country_name
        year = $year
        year_decade = To-Decade $year
        publication_count = [int]$_.publication_count
    }
}
$panelColumns = @("journal_rank","journal","openalex_source_id","issn_l","country_code","country_name","year","year_decade","publication_count")

$aggRows = Import-Csv -LiteralPath $Q3AggCsv | ForEach-Object {
    $year = [int]$_.year
    [pscustomobject]@{
        country_code = $_.country_code
        country_name = $_.country_name
        year = $year
        year_decade = To-Decade $year
        top10_journal_publication_count = [int]$_.top10_journal_publication_count
    }
}
$aggColumns = @("country_code","country_name","year","year_decade","top10_journal_publication_count")

$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false
$excel.ScreenUpdating = $false
$excel.EnableEvents = $false
$excel.AskToUpdateLinks = $false

try {
    Write-Output "Creating workbook"
    $workbook = $excel.Workbooks.Add(-4167)
    Write-Output "Workbook created"
    $workbook.Worksheets.Item(1).Name = "Readme"
    $readme = $workbook.Worksheets.Item("Readme")
    Write-Output "Writing readme"
    $readme.Range("A1").Value2 = "Nobel Key Papers: Data, Pivot Tables, and Charts"
    $readme.Range("A1").Font.Bold = $true
    $readme.Range("A1").Font.Size = 18
    $readme.Range("A3").Value2 = "Workbook contents"
    $readme.Range("A3").Font.Bold = $true
    $readme.Range("A4").Value2 = "1. Data_KeyPapers: main analysis table, 823 key-paper rows covering 504 Nobel records."
    $readme.Range("A5").Value2 = "2. Data_Top10Journals: top 10 journals by Nobel key-paper rows."
    $readme.Range("A6").Value2 = "3. Data_CountryJournalYear: 10 journals x 6 countries x 1880-2025 yearly article count panel."
    $readme.Range("A7").Value2 = "4. Data_CountryYearAgg: six-country annual article-count totals across the top 10 journals."
    $readme.Range("A8").Value2 = "5. Q1/Q2/Q3 sheets: native Excel PivotTables and charts."
    $readme.Range("A10").Value2 = "Scope notes"
    $readme.Range("A10").Font.Bold = $true
    $readme.Range("A11").Value2 = "The main analysis table includes only rows with title, year, journal/source, and auditable metadata matching. Lower-confidence or key-relevance-review candidates are excluded from the main statistics."
    $readme.Range("A12").Value2 = "Q3 country article counts come from OpenAlex using the top 10 journal sources, authorships.countries, and type:article filters."
    $readme.Range("A14").Value2 = "Source files"
    $readme.Range("A14").Font.Bold = $true
    $readme.Range("A15").Value2 = "analysis_ready_key_papers_full.csv; q2_top10_key_paper_journals.csv; q3_country_journal_year_counts_top10.csv; q3_country_year_counts_top10_aggregate.csv"
    $readme.Columns.Item(1).ColumnWidth = 120
    $readme.Range("A1:A15").WrapText = $true
    Write-Output "Readme done"

    $dataKey = Add-DataSheet $workbook "Data_KeyPapers" $keyRows $keyColumns "tblKeyPapers"
    $dataTop = Add-DataSheet $workbook "Data_Top10Journals" $topRows $topColumns "tblTopJournals"
    $dataPanel = Add-DataSheet $workbook "Data_CountryJournalYear" $panelRows $panelColumns "tblCountryJournalYear"
    $dataAgg = Add-DataSheet $workbook "Data_CountryYearAgg" $aggRows $aggColumns "tblCountryYearAgg"

    Write-Output "Creating Q1 pivot"
    $q1 = $workbook.Worksheets.Add()
    $q1.Name = "Q1_LagTrend"
    Set-Header $q1 "Q1 Publication-to-award lag trend" "PivotTable: average lag years and row counts by award decade and category. Chart shows lag trend by category."
    $pivot1 = Add-PivotTable $workbook $dataKey.Table $q1 "ptLagByDecadeCategory" "A5"
    $pivot1.PivotFields("award_decade").Orientation = 1
    $pivot1.PivotFields("category").Orientation = 2
    $df1 = $pivot1.AddDataField($pivot1.PivotFields("award_lag_years"), "Avg lag years", -4106)
    $df1.NumberFormat = "0.0"
    $df2 = $pivot1.AddDataField($pivot1.PivotFields("analysis_id"), "Key-paper rows", -4112)
    $df2.NumberFormat = "#,##0"
    $pivot1.RowAxisLayout(1)
    $pivot1.RefreshTable() | Out-Null
    Add-PivotChart $q1 $pivot1 "Publication-to-award lag by award decade" 4 420 80 620 330 | Out-Null
    $q1.Columns.Item(1).ColumnWidth = 18

    Write-Output "Creating Q2 pivot"
    $q2 = $workbook.Worksheets.Add()
    $q2.Name = "Q2_Top10Journals"
    Set-Header $q2 "Q2 Top 10 key-paper journals" "PivotTable: key-paper rows and covered Nobel records for the top 10 journals. Chart is sorted by key-paper rows."
    $pivot2 = Add-PivotTable $workbook $dataTop.Table $q2 "ptTop10Journals" "A5"
    $pivot2.PivotFields("journal").Orientation = 1
    $df21 = $pivot2.AddDataField($pivot2.PivotFields("key_paper_rows"), "Key-paper rows", -4157)
    $df21.NumberFormat = "#,##0"
    $df22 = $pivot2.AddDataField($pivot2.PivotFields("covered_nobel_records"), "Covered Nobel records", -4157)
    $df22.NumberFormat = "#,##0"
    $pivot2.PivotFields("journal").AutoSort(2, "Key-paper rows")
    $pivot2.RefreshTable() | Out-Null
    Add-PivotChart $q2 $pivot2 "Top 10 journals for Nobel key-paper rows" 57 520 80 620 360 | Out-Null
    $q2.Columns.Item(1).ColumnWidth = 38

    Write-Output "Creating Q3 pivot"
    $q3 = $workbook.Worksheets.Add()
    $q3.Name = "Q3_CountryTrend"
    Set-Header $q3 "Q3 Six-country article-count trend in top 10 journals" "PivotTable 1: annual article counts by year and country across the top 10 journals. PivotTable 2: decade-country detail with journal filter."
    $pivot3 = Add-PivotTable $workbook $dataAgg.Table $q3 "ptCountryYearTrend" "A5"
    $pivot3.PivotFields("year").Orientation = 1
    $pivot3.PivotFields("country_name").Orientation = 2
    $df31 = $pivot3.AddDataField($pivot3.PivotFields("top10_journal_publication_count"), "Article count", -4157)
    $df31.NumberFormat = "#,##0"
    $pivot3.RowAxisLayout(1)
    $pivot3.RefreshTable() | Out-Null
    Add-PivotChart $q3 $pivot3 "Six-country annual article counts in top 10 Nobel journals (1880-2025)" 4 520 80 720 360 | Out-Null

    $pivot4 = Add-PivotTable $workbook $dataPanel.Table $q3 "ptCountryJournalDetail" "A170"
    $pivot4.PivotFields("journal").Orientation = 3
    $pivot4.PivotFields("year_decade").Orientation = 1
    $pivot4.PivotFields("country_name").Orientation = 2
    $df41 = $pivot4.AddDataField($pivot4.PivotFields("publication_count"), "Article count", -4157)
    $df41.NumberFormat = "#,##0"
    $pivot4.RowAxisLayout(1)
    $pivot4.RefreshTable() | Out-Null
    $q3.Columns.Item(1).ColumnWidth = 14

    foreach ($ws in @($q1, $q2, $q3)) {
        $ws.Range("A1:H3").Font.Name = "Microsoft YaHei"
        $ws.Cells.Font.Name = "Microsoft YaHei"
        $ws.Rows.Item(1).RowHeight = 26
        $ws.Rows.Item(2).RowHeight = 42
        $ws.Activate() | Out-Null
        $excel.ActiveWindow.DisplayGridlines = $false
    }

    foreach ($ws in @($readme, $dataKey.Sheet, $dataTop.Sheet, $dataPanel.Sheet, $dataAgg.Sheet)) {
        $ws.Cells.Font.Name = "Microsoft YaHei"
        $ws.Activate() | Out-Null
        $excel.ActiveWindow.DisplayGridlines = $false
    }

    $readme.Activate() | Out-Null
    Write-Output "Saving workbook"
    $workbook.SaveAs($OutputXlsx, 51)
    Write-Output $OutputXlsx
}
finally {
    if ($null -ne $workbook) {
        $workbook.Close($true)
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($workbook) | Out-Null
    }
    if ($null -ne $excel) {
        $excel.Quit()
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($excel) | Out-Null
    }
    [gc]::Collect()
    [gc]::WaitForPendingFinalizers()
}
