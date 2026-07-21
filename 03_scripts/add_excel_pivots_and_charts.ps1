$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$BaseXlsx = Join-Path $Root "02_full_collection\07_excel\nobel_key_papers_pivot_base.xlsx"
$OutputXlsx = Join-Path $Root "02_full_collection\07_excel\nobel_key_papers_pivot_analysis.xlsx"

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

function Add-PivotTable($Workbook, $SourceTable, $DestSheet, [string]$Name, [string]$DestCell) {
    $cache = $Workbook.PivotCaches().Create(1, $SourceTable.Range)
    $pivot = $cache.CreatePivotTable($DestSheet.Range($DestCell), $Name)
    return $pivot
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

function Add-NormalChart([object]$Sheet, [object]$CategoryRange, [object]$ValueRange, [string]$SeriesName, [string]$Title, [int]$ChartType, [double]$Left, [double]$Top, [double]$Width, [double]$Height) {
    $chartObject = $Sheet.ChartObjects().Add($Left, $Top, $Width, $Height)
    $chart = $chartObject.Chart
    $chart.ChartType = $ChartType
    while ($chart.SeriesCollection().Count -gt 0) {
        $chart.SeriesCollection().Item(1).Delete()
    }
    $series = $chart.SeriesCollection().NewSeries()
    $series.Name = $SeriesName
    $series.XValues = $CategoryRange
    $series.Values = $ValueRange
    $chart.HasTitle = $true
    $chart.ChartTitle.Text = $Title
    $chart.HasLegend = $false
    $chartObject.Left = $Left
    $chartObject.Top = $Top
    $chartObject.Width = $Width
    $chartObject.Height = $Height
    return $chartObject
}

function Try-SetPageFilter($PivotTable, [string]$FieldName, [string]$Value) {
    try {
        $field = $PivotTable.PivotFields($FieldName)
        $field.Orientation = 3
        $field.ClearAllFilters()
        $field.CurrentPage = $Value
    }
    catch {
        Write-Output "Warning: could not set page filter $FieldName=$Value"
    }
}

function Set-PercentAxis($ChartObject) {
    try {
        $ChartObject.Chart.Axes(2).TickLabels.NumberFormat = "0%"
    }
    catch {
        Write-Output "Warning: could not set percent axis format"
    }
}

$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false
$excel.ScreenUpdating = $false
$excel.EnableEvents = $false
$excel.AskToUpdateLinks = $false

try {
    Write-Output "Opening base workbook"
    $workbook = $excel.Workbooks.Open((Resolve-Path $BaseXlsx).Path)

    $keyTable = $workbook.Worksheets.Item("Data_KeyPapers").ListObjects.Item("tblKeyPapers")
    $topTable = $workbook.Worksheets.Item("Data_Top10Journals").ListObjects.Item("tblTopJournals")
    $panelTable = $workbook.Worksheets.Item("Data_CountryJournalYear").ListObjects.Item("tblCountryJournalYear")
    $aggTable = $workbook.Worksheets.Item("Data_CountryYearAgg").ListObjects.Item("tblCountryYearAgg")
    $basicTable = $workbook.Worksheets.Item("Data_BasicStats").ListObjects.Item("tblBasicStats")
    $distTable = $workbook.Worksheets.Item("Data_RecordPaperDist").ListObjects.Item("tblRecordPaperDist")
    $coverageTable = $workbook.Worksheets.Item("Data_JournalCoverage").ListObjects.Item("tblJournalCoverage")
    $periodTable = $workbook.Worksheets.Item("Data_JournalPeriod").ListObjects.Item("tblJournalPeriod")
    $sharePanelTable = $workbook.Worksheets.Item("Data_CountryWorldShare").ListObjects.Item("tblCountryWorldShare")
    $shareAggTable = $workbook.Worksheets.Item("Data_CountryWorldAgg").ListObjects.Item("tblCountryWorldAgg")

    Write-Output "Creating Q1 pivot"
    $q1 = $workbook.Worksheets.Add()
    $q1.Name = "Q1_LagTrend"
    Set-Header $q1 "Q1 Publication-to-award lag trend" "PivotTable: average lag years and row counts by award decade and category. Chart shows lag trend by category."
    $pivot1 = Add-PivotTable $workbook $keyTable $q1 "ptLagByDecadeCategory" "A5"
    $pivot1.PivotFields("award_decade").Orientation = 1
    $pivot1.PivotFields("category").Orientation = 2
    $df1 = $pivot1.AddDataField($pivot1.PivotFields("award_lag_years"), "Avg lag years", -4106)
    $df1.NumberFormat = "0.0"
    $pivot1.RowAxisLayout(1)
    $pivot1.RefreshTable() | Out-Null
    Add-PivotChart $q1 $pivot1 "Publication-to-award lag by award decade" 4 420 80 620 330 | Out-Null
    $q1.Columns.Item(1).ColumnWidth = 18

    Write-Output "Creating Q2 pivot"
    $q2 = $workbook.Worksheets.Add()
    $q2.Name = "Q2_Top10Journals"
    Set-Header $q2 "Q2 Top 10 key-paper journals" "PivotTable: key-paper rows and covered Nobel records for the top 10 journals. Chart is sorted by key-paper rows."
    $pivot2 = Add-PivotTable $workbook $topTable $q2 "ptTop10Journals" "A5"
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
    $pivot3 = Add-PivotTable $workbook $aggTable $q3 "ptCountryYearTrend" "A5"
    $pivot3.PivotFields("year").Orientation = 1
    $pivot3.PivotFields("country_name").Orientation = 2
    $df31 = $pivot3.AddDataField($pivot3.PivotFields("top10_journal_publication_count"), "Article count", -4157)
    $df31.NumberFormat = "#,##0"
    $pivot3.RowAxisLayout(1)
    $pivot3.RefreshTable() | Out-Null
    Add-PivotChart $q3 $pivot3 "Six-country annual article counts in top 10 Nobel journals (1880-2025)" 4 520 80 720 360 | Out-Null

    $pivot4 = Add-PivotTable $workbook $panelTable $q3 "ptCountryJournalDetail" "A170"
    $pivot4.PivotFields("journal").Orientation = 3
    $pivot4.PivotFields("year_decade").Orientation = 1
    $pivot4.PivotFields("country_name").Orientation = 2
    $df41 = $pivot4.AddDataField($pivot4.PivotFields("publication_count"), "Article count", -4157)
    $df41.NumberFormat = "#,##0"
    $pivot4.RowAxisLayout(1)
    $pivot4.RefreshTable() | Out-Null
    $q3.Columns.Item(1).ColumnWidth = 14

    Write-Output "Creating Q4 additional basic stats pivot"
    $q4 = $workbook.Worksheets.Add()
    $q4.Name = "Q4_BasicStats"
    Set-Header $q4 "Q4 Basic statistics and papers per Nobel record" "Top block: core record/paper/journal statistics. PivotTable: distribution of unique key papers per Nobel record, including zero-paper records."
    $q4.Range("A5").Value2 = "Metric"
    $q4.Range("B5").Value2 = "Value"
    $q4.Range("C5").Value2 = "Notes"
    $basicTable.DataBodyRange.Copy($q4.Range("A6")) | Out-Null
    $q4.Range("A5:C5").Font.Bold = $true
    $q4.Range("A5:C5").Interior.Color = 15921906
    $q4.Range("A5:C5").Borders.LineStyle = 1
    $q4.Range("A6:C20").WrapText = $true
    $q4.Columns.Item(1).ColumnWidth = 38
    $q4.Columns.Item(2).ColumnWidth = 14
    $q4.Columns.Item(3).ColumnWidth = 58
    $pivot5 = Add-PivotTable $workbook $distTable $q4 "ptRecordPaperDistribution" "A22"
    $pivot5.PivotFields("paper_count_per_nobel_record").Orientation = 1
    $df51 = $pivot5.AddDataField($pivot5.PivotFields("nobel_records"), "Nobel records", -4157)
    $df51.NumberFormat = "#,##0"
    $pivot5.RowAxisLayout(1)
    $pivot5.RefreshTable() | Out-Null
    $q4.Range("E22").Value2 = "Paper count"
    $q4.Range("F22").Value2 = "Nobel records"
    for ($i = 0; $i -lt 9; $i++) {
        $targetRow = 23 + $i
        $sourceRow = 2 + $i
        $q4.Range("E$targetRow").Formula = "='Data_RecordPaperDist'!A$sourceRow"
        $q4.Range("F$targetRow").Formula = "='Data_RecordPaperDist'!B$sourceRow"
    }
    $q4.Range("E22:F22").Font.Bold = $true
    $chartObject5 = $q4.ChartObjects().Add(480, 300, 620, 330)
    $chart5 = $chartObject5.Chart
    $chart5.ChartType = 51
    while ($chart5.SeriesCollection().Count -gt 0) { $chart5.SeriesCollection().Item(1).Delete() }
    $series5 = $chart5.SeriesCollection().NewSeries()
    $series5.Name = "Nobel records"
    $series5.XValues = $q4.Range("E23:E31")
    $series5.Values = $q4.Range("F23:F31")
    $chart5.HasTitle = $true
    $chart5.ChartTitle.Text = "Distribution of key papers per Nobel record"
    $chart5.HasLegend = $false
    $chartObject5.Left = 480
    $chartObject5.Top = 300
    $chartObject5.Width = 620
    $chartObject5.Height = 330

    Write-Output "Creating Q5 additional journal coverage pivots"
    $q5 = $workbook.Worksheets.Add()
    $q5.Name = "Q5_JournalCoverage"
    Set-Header $q5 "Q5 Journal concentration and 90% coverage set" "PivotTable 1: journals ranked by Nobel key-paper rows; the page filter keeps the 77 journals needed to reach 90.0% row coverage. PivotTable 2: top journals by award-period segment."
    $pivot6 = Add-PivotTable $workbook $coverageTable $q5 "ptJournalCoverage90" "A5"
    Try-SetPageFilter $pivot6 "selected_for_90pct_row_panel" "1"
    $pivot6.PivotFields("journal").Orientation = 1
    $df61 = $pivot6.AddDataField($pivot6.PivotFields("key_paper_rows"), "Key-paper rows", -4157)
    $df61.NumberFormat = "#,##0"
    $pivot6.PivotFields("journal").AutoSort(2, "Key-paper rows")
    $pivot6.RowAxisLayout(1)
    $pivot6.RefreshTable() | Out-Null
    $q5.Range("J5").Value2 = "Rank"
    $q5.Range("K5").Value2 = "Cumulative row share"
    for ($i = 0; $i -lt 77; $i++) {
        $targetRow = 6 + $i
        $sourceRow = 2 + $i
        $q5.Range("J$targetRow").Formula = "='Data_JournalCoverage'!A$sourceRow"
        $q5.Range("K$targetRow").Formula = "='Data_JournalCoverage'!F$sourceRow"
    }
    $q5.Range("J5:K5").Font.Bold = $true
    $q5.Range("K6:K82").NumberFormat = "0.0%"
    $chartObject6 = $q5.ChartObjects().Add(620, 80, 700, 420)
    $chart6 = $chartObject6.Chart
    $chart6.ChartType = 4
    while ($chart6.SeriesCollection().Count -gt 0) { $chart6.SeriesCollection().Item(1).Delete() }
    $series6 = $chart6.SeriesCollection().NewSeries()
    $series6.Name = "Cumulative row share"
    $series6.XValues = $q5.Range("J6:J82")
    $series6.Values = $q5.Range("K6:K82")
    $chart6.HasTitle = $true
    $chart6.ChartTitle.Text = "Cumulative coverage of Nobel key-paper rows by journal rank"
    $chart6.HasLegend = $false
    $chartObject6.Left = 620
    $chartObject6.Top = 80
    $chartObject6.Width = 700
    $chartObject6.Height = 420
    Set-PercentAxis $chartObject6
    $q5.Columns.Item(1).ColumnWidth = 46

    $pivot7 = Add-PivotTable $workbook $periodTable $q5 "ptJournalCoverageByPeriod" "A100"
    $pivot7.PivotFields("award_period").Orientation = 1
    $pivot7.PivotFields("journal").Orientation = 2
    $df71 = $pivot7.AddDataField($pivot7.PivotFields("key_paper_rows"), "Key-paper rows", -4157)
    $df71.NumberFormat = "#,##0"
    $pivot7.RowAxisLayout(1)
    $pivot7.RefreshTable() | Out-Null

    Write-Output "Creating Q6 additional country share pivots"
    $q6 = $workbook.Worksheets.Add()
    $q6.Name = "Q6_CountryShare1850"
    Set-Header $q6 "Q6 Country shares in selected Nobel-journal set" "PivotTable 1: six countries' annual article share in the 77 journals that cover 90.0% of Nobel key-paper rows, using all-world OpenAlex article counts as denominator. PivotTable 2: journal-level detail with year-decade grouping."
    $pivot8 = Add-PivotTable $workbook $shareAggTable $q6 "ptCountryWorldShareTrend" "A5"
    $pivot8.PivotFields("year").Orientation = 1
    $pivot8.PivotFields("country_name").Orientation = 2
    $df81 = $pivot8.AddDataField($pivot8.PivotFields("country_world_share"), "Country share of world", -4106)
    $df81.NumberFormat = "0.0%"
    $pivot8.RowAxisLayout(1)
    $pivot8.RefreshTable() | Out-Null
    $chart8 = Add-PivotChart $q6 $pivot8 "Country share of world articles in 90%-coverage Nobel journals (1850-2025)" 4 520 80 760 380
    Set-PercentAxis $chart8

    $pivot9 = Add-PivotTable $workbook $sharePanelTable $q6 "ptCountryWorldShareJournalDetail" "A185"
    $pivot9.PivotFields("journal").Orientation = 3
    $pivot9.PivotFields("year_decade").Orientation = 1
    $pivot9.PivotFields("country_name").Orientation = 2
    $df91 = $pivot9.AddDataField($pivot9.PivotFields("country_world_share"), "Country share of world", -4106)
    $df91.NumberFormat = "0.0%"
    $pivot9.RowAxisLayout(1)
    $pivot9.RefreshTable() | Out-Null
    $q6.Columns.Item(1).ColumnWidth = 14

    foreach ($ws in @($q1, $q2, $q3, $q4, $q5, $q6)) {
        $ws.Cells.Font.Name = "Microsoft YaHei"
        $ws.Activate() | Out-Null
        $excel.ActiveWindow.DisplayGridlines = $false
    }

    $q4.ChartObjects().Item(1).Left = 480
    $q4.ChartObjects().Item(1).Top = 300
    $q4.ChartObjects().Item(1).Width = 620
    $q4.ChartObjects().Item(1).Height = 330
    $q5.ChartObjects().Item(1).Left = 620
    $q5.ChartObjects().Item(1).Top = 80
    $q5.ChartObjects().Item(1).Width = 700
    $q5.ChartObjects().Item(1).Height = 420

    Write-Output "Saving final workbook"
    if (Test-Path -LiteralPath $OutputXlsx) {
        Remove-Item -LiteralPath $OutputXlsx -Force
    }
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
