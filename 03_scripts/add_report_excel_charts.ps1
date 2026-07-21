$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ReportDir = Join-Path $Root "02_full_collection\08_report"
$WorkbookPath = Join-Path $ReportDir "nobel_report_figures.xlsx"
$ChartDir = Join-Path $ReportDir "charts"
New-Item -ItemType Directory -Force -Path $ChartDir | Out-Null

function Add-LineChart($Sheet, $RangeAddress, [string]$Title, [string]$OutName, [bool]$PercentAxis = $false) {
    $chartObject = $Sheet.ChartObjects().Add(420, 30, 720, 390)
    $chart = $chartObject.Chart
    $chart.SetSourceData($Sheet.Range($RangeAddress))
    $chart.ChartType = 4
    $chart.HasTitle = $true
    $chart.ChartTitle.Text = $Title
    $chart.HasLegend = $true
    $chart.Legend.Position = -4107
    if ($PercentAxis) {
        $chart.Axes(2).TickLabels.NumberFormat = "0%"
    }
    $path = Join-Path $ChartDir $OutName
    $chart.Export($path) | Out-Null
    return $chartObject
}

function Add-SeriesLineChart($Sheet, [string]$Title, [string]$OutName, [string]$XAxisRange, [string[]]$SeriesCols, [string[]]$SeriesNames, [bool]$PercentAxis = $false) {
    $chartObject = $Sheet.ChartObjects().Add(420, 30, 720, 390)
    $chart = $chartObject.Chart
    $chart.ChartType = 4
    $chart.HasTitle = $true
    $chart.ChartTitle.Text = $Title
    while ($chart.SeriesCollection().Count -gt 0) { $chart.SeriesCollection().Item(1).Delete() }

    for ($i = 0; $i -lt $SeriesCols.Count; $i++) {
        $col = $SeriesCols[$i]
        $s = $chart.SeriesCollection().NewSeries()
        $s.Name = '="' + $SeriesNames[$i] + '"'
        $s.XValues = $Sheet.Range($XAxisRange)
        $lastRow = $Sheet.Cells($Sheet.Rows.Count, $col).End(-4162).Row
        $s.Values = $Sheet.Range("${col}2:${col}${lastRow}")
        $s.MarkerStyle = 8
        $s.MarkerSize = 4
        $s.Format.Line.Weight = 1.8
    }

    $chart.HasLegend = $true
    $chart.Legend.Position = -4107
    if ($PercentAxis) {
        $chart.Axes(2).TickLabels.NumberFormat = "0%"
    }
    $path = Join-Path $ChartDir $OutName
    $chart.Export($path) | Out-Null
    return $chartObject
}

function Add-CoverageChart($Sheet) {
    $chartObject = $Sheet.ChartObjects().Add(420, 30, 720, 390)
    $chart = $chartObject.Chart
    $chart.ChartType = 4
    $chart.HasTitle = $true
    $chart.ChartTitle.Text = "Journal concentration: top 77 cover about 90%"
    while ($chart.SeriesCollection().Count -gt 0) { $chart.SeriesCollection().Item(1).Delete() }

    $s1 = $chart.SeriesCollection().NewSeries()
    $s1.Name = "Cumulative share"
    $s1.XValues = $Sheet.Range("A2:A78")
    $s1.Values = $Sheet.Range("D2:D78")
    $s1.Format.Line.ForeColor.RGB = 12611584
    $s1.Format.Line.Weight = 2.25

    $s2 = $chart.SeriesCollection().NewSeries()
    $s2.Name = "90% threshold"
    $s2.XValues = $Sheet.Range("A2:A78")
    $s2.Values = $Sheet.Range("E2:E78")
    $s2.Format.Line.ForeColor.RGB = 255
    $s2.Format.Line.DashStyle = 4
    $s2.Format.Line.Weight = 1.75

    $chart.Axes(2).TickLabels.NumberFormat = "0%"
    $chart.HasLegend = $true
    $chart.Legend.Position = -4107
    $path = Join-Path $ChartDir "fig3_journal_coverage.png"
    $chart.Export($path) | Out-Null
    return $chartObject
}

$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false
$excel.ScreenUpdating = $false

try {
    $wb = $excel.Workbooks.Open((Resolve-Path $WorkbookPath).Path)

    foreach ($ws in $wb.Worksheets) {
        $ws.Cells.Font.Name = "Microsoft YaHei"
        $ws.Activate() | Out-Null
        $excel.ActiveWindow.DisplayGridlines = $false
        while ($ws.ChartObjects().Count -gt 0) {
            $ws.ChartObjects().Item(1).Delete()
        }
    }

    Add-LineChart $wb.Worksheets.Item("PDF_AwardsByDecade") "A1:F13" "Science Nobel awards by country and decade" "fig1_awards_by_decade.png" $false | Out-Null
    Add-LineChart $wb.Worksheets.Item("LagByCategory") "A1:E14" "Lag from key paper to Nobel award, median years" "fig2_lag_by_category.png" $false | Out-Null
    Add-CoverageChart $wb.Worksheets.Item("JournalCoverage") | Out-Null
    Add-SeriesLineChart $wb.Worksheets.Item("Top77CountryShare") "Country publication shares in Top77 Nobel journals, 1980-2025" "fig4_top77_country_share.png" "A2:A47" @("B","C","D","E","F","G") @("USA","China","Japan","UK","Germany","France") $true | Out-Null
    Add-SeriesLineChart $wb.Worksheets.Item("ChinaTop77Top20") "China publication share in Top77 and Top20 journals, 2000-2025" "fig5_china_top77_top20.png" "A2:A27" @("B","C") @("Top77","Top20") $true | Out-Null

    $wb.Save()
    Get-ChildItem -LiteralPath $ChartDir -Filter "*.png" | Select-Object Name,Length | Format-Table -AutoSize
}
finally {
    if ($null -ne $wb) {
        $wb.Close($true)
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($wb) | Out-Null
    }
    if ($null -ne $excel) {
        $excel.Quit()
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($excel) | Out-Null
    }
    [gc]::Collect()
    [gc]::WaitForPendingFinalizers()
}
