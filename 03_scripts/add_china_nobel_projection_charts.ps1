$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$WorkbookPath = Join-Path $Root "02_full_collection\08_report\china_nobel_projection_visualization.xlsx"
$ChartExportDir = Join-Path $Root "02_full_collection\08_report\china_projection_chart_previews"
New-Item -ItemType Directory -Force -Path $ChartExportDir | Out-Null

$xlLineMarkers = 65
$xlXYScatter = -4169
$xlColumnClustered = 51
$xlLinear = -4132
$xlLegendBottom = -4107
$xlSecondary = 2

function Add-Series($Chart, [string]$Name, $XRange, $YRange, [int]$Rgb, [bool]$Trend = $false, [int]$AxisGroup = 1) {
    $s = $Chart.SeriesCollection().NewSeries()
    $s.Name = '="' + $Name + '"'
    $s.XValues = $XRange
    $s.Values = $YRange
    $s.AxisGroup = $AxisGroup
    $s.MarkerStyle = 8
    $s.MarkerSize = 5
    $s.Format.Line.ForeColor.RGB = $Rgb
    $s.Format.Line.Weight = 2
    if ($Trend) {
        $t = $s.Trendlines().Add($xlLinear)
        $t.Name = $Name + " linear trend"
        $t.Format.Line.ForeColor.RGB = $Rgb
        $t.Format.Line.DashStyle = 4
        $t.Format.Line.Weight = 1.25
    }
    return $s
}

function Add-ScatterSeries($Chart, [string]$Name, $XRange, $YRange, [int]$Rgb, [bool]$Trend = $true) {
    $s = $Chart.SeriesCollection().NewSeries()
    $s.Name = '="' + $Name + '"'
    $s.XValues = $XRange
    $s.Values = $YRange
    $s.MarkerStyle = 8
    $s.MarkerSize = 7
    $s.MarkerBackgroundColor = $Rgb
    $s.MarkerForegroundColor = $Rgb
    $s.Format.Line.Visible = 0
    if ($Trend) {
        $t = $s.Trendlines().Add($xlLinear)
        $t.Name = $Name + " linear trend"
        $t.Format.Line.ForeColor.RGB = $Rgb
        $t.Format.Line.DashStyle = 4
        $t.Format.Line.Weight = 1.5
    }
    return $s
}

function Add-LineTrendChart($Sheet, $DataSheet, [string]$Title, [string]$OutName, [double]$Left, [double]$Top, [string]$SourceKind) {
    $co = $Sheet.ChartObjects().Add($Left, $Top, 520, 300)
    $chart = $co.Chart
    $chart.ChartType = $xlLineMarkers
    $chart.HasTitle = $true
    $chart.ChartTitle.Text = $Title
    while ($chart.SeriesCollection().Count -gt 0) { $chart.SeriesCollection().Item(1).Delete() }
    Add-Series $chart "China" $DataSheet.Range("A2:A19") $DataSheet.Range("C2:C19") 192  $true | Out-Null
    Add-Series $chart "Japan" $DataSheet.Range("A2:A19") $DataSheet.Range("F2:F19") 10498160 $true | Out-Null
    Add-Series $chart "United States" $DataSheet.Range("A2:A19") $DataSheet.Range("H2:H19") 12611584 $true | Out-Null
    $chart.HasLegend = $true
    $chart.Legend.Position = $xlLegendBottom
    $chart.Axes(2).TickLabels.NumberFormat = "0%"
    $chart.Axes(1).TickLabelSpacing = 2
    $path = Join-Path $ChartExportDir $OutName
    $chart.Export($path) | Out-Null
}

function Add-AwardsLagChart($Sheet, $AwardsSheet) {
    $co = $Sheet.ChartObjects().Add(560, 30, 520, 300)
    $chart = $co.Chart
    $chart.ChartType = $xlLineMarkers
    $chart.HasTitle = $true
    $chart.ChartTitle.Text = "Nobel awards and average lag by decade"
    while ($chart.SeriesCollection().Count -gt 0) { $chart.SeriesCollection().Item(1).Delete() }
    Add-Series $chart "US awards" $AwardsSheet.Range("A2:A13") $AwardsSheet.Range("C2:C13") 12611584 $false | Out-Null
    Add-Series $chart "Japan awards" $AwardsSheet.Range("A2:A13") $AwardsSheet.Range("G2:G13") 10498160 $false | Out-Null
    Add-Series $chart "Average lag years" $AwardsSheet.Range("A2:A13") $AwardsSheet.Range("H2:H13") 49407 $true $xlSecondary | Out-Null
    $chart.HasLegend = $true
    $chart.Legend.Position = $xlLegendBottom
    $chart.Axes(1).TickLabelSpacing = 2
    $chart.Axes(2, 1).HasTitle = $true
    $chart.Axes(2, 1).AxisTitle.Text = "Awards"
    $chart.Axes(2, 2).HasTitle = $true
    $chart.Axes(2, 2).AxisTitle.Text = "Lag years"
    $path = Join-Path $ChartExportDir "fig3_awards_lag.png"
    $chart.Export($path) | Out-Null
}

function Add-CalibrationScatter($Sheet, $CalSheet, [string]$Title, [string]$OutName, [double]$Left, [double]$Top, [string]$UsX, [string]$JpX) {
    $co = $Sheet.ChartObjects().Add($Left, $Top, 520, 300)
    $chart = $co.Chart
    $chart.ChartType = $xlXYScatter
    $chart.HasTitle = $true
    $chart.ChartTitle.Text = $Title
    while ($chart.SeriesCollection().Count -gt 0) { $chart.SeriesCollection().Item(1).Delete() }
    Add-ScatterSeries $chart "United States calibration" $CalSheet.Range($UsX) $CalSheet.Range("F2:F13") 12611584 $true | Out-Null
    Add-ScatterSeries $chart "Japan calibration" $CalSheet.Range($JpX) $CalSheet.Range("G2:G13") 10498160 $true | Out-Null
    $chart.HasLegend = $true
    $chart.Legend.Position = $xlLegendBottom
    $chart.Axes(1).TickLabels.NumberFormat = "0%"
    $chart.Axes(2).TickLabels.NumberFormat = "0"
    $chart.Axes(1).HasTitle = $true
    $chart.Axes(1).AxisTitle.Text = "Lag-adjusted publication share"
    $chart.Axes(2).HasTitle = $true
    $chart.Axes(2).AxisTitle.Text = "Nobel awards in later decade"
    $path = Join-Path $ChartExportDir $OutName
    $chart.Export($path) | Out-Null
}

function Add-ChinaWindowChart($Sheet, $ProjectionSheet) {
    $co = $Sheet.ChartObjects().Add(560, 60, 520, 300)
    $chart = $co.Chart
    $chart.ChartType = $xlColumnClustered
    $chart.HasTitle = $true
    $chart.ChartTitle.Text = "China vs historical calibration references"
    while ($chart.SeriesCollection().Count -gt 0) { $chart.SeriesCollection().Item(1).Delete() }
    $s1 = $chart.SeriesCollection().NewSeries()
    $s1.Name = '="Top21 share"'
    $s1.XValues = $ProjectionSheet.Range("A2:A6")
    $s1.Values = $ProjectionSheet.Range("D2:D6")
    $s1.Format.Fill.ForeColor.RGB = 49407
    $s2 = $chart.SeriesCollection().NewSeries()
    $s2.Name = '="Top77 share"'
    $s2.XValues = $ProjectionSheet.Range("A2:A6")
    $s2.Values = $ProjectionSheet.Range("E2:E6")
    $s2.Format.Fill.ForeColor.RGB = 12611584
    $chart.HasLegend = $true
    $chart.Legend.Position = $xlLegendBottom
    $chart.Axes(2).TickLabels.NumberFormat = "0%"
    $path = Join-Path $ChartExportDir "fig6_china_window.png"
    $chart.Export($path) | Out-Null
}

$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false
$excel.ScreenUpdating = $false

try {
    $wb = $excel.Workbooks.Open((Resolve-Path $WorkbookPath).Path)

    $chartsSheet = $null
    try {
        $chartsSheet = $wb.Worksheets.Item("Charts")
    } catch {
        $chartsSheet = $wb.Worksheets.Add()
        $chartsSheet.Name = "Charts"
    }
    $chartsSheet.Cells.Clear()
    while ($chartsSheet.ChartObjects().Count -gt 0) {
        $chartsSheet.ChartObjects().Item(1).Delete()
    }
    $chartsSheet.Cells.Font.Name = "Microsoft YaHei"
    $chartsSheet.Range("A1").Value2 = "China Nobel timing projection visuals"
    $chartsSheet.Range("A1").Font.Bold = $true
    $chartsSheet.Range("A1").Font.Size = 16
    $chartsSheet.Range("A2").Value2 = "Charts are native Excel charts. Linear trendlines are added to key publication-share and calibration series."

    $projectionChartsSheet = $null
    try {
        $projectionChartsSheet = $wb.Worksheets.Item("Projection_Charts")
    } catch {
        $projectionChartsSheet = $wb.Worksheets.Add()
        $projectionChartsSheet.Name = "Projection_Charts"
    }
    $projectionChartsSheet.Cells.Clear()
    while ($projectionChartsSheet.ChartObjects().Count -gt 0) {
        $projectionChartsSheet.ChartObjects().Item(1).Delete()
    }
    $projectionChartsSheet.Cells.Font.Name = "Microsoft YaHei"
    $projectionChartsSheet.Range("A1").Value2 = "Calibration and China projection visuals"
    $projectionChartsSheet.Range("A1").Font.Bold = $true
    $projectionChartsSheet.Range("A1").Font.Size = 16
    $projectionChartsSheet.Range("A2").Value2 = "Top77 calibration and China window charts are placed here to keep rendering stable."

    foreach ($ws in $wb.Worksheets) {
        $ws.Cells.Font.Name = "Microsoft YaHei"
        $ws.Activate() | Out-Null
        $excel.ActiveWindow.DisplayGridlines = $false
    }

    Add-LineTrendChart $chartsSheet $wb.Worksheets.Item("Raw_Top21") "Top21 publication share trends" "fig1_top21_trends.png" 20 60 "Top21"
    Add-AwardsLagChart $chartsSheet $wb.Worksheets.Item("Raw_Awards_Lag")
    Add-LineTrendChart $chartsSheet $wb.Worksheets.Item("Raw_Top77") "Top77 publication share trends" "fig2_top77_trends.png" 20 365 "Top77"
    Add-CalibrationScatter $chartsSheet $wb.Worksheets.Item("Lag_Adjusted_Calibration") "Top21 calibration: publication share to later awards" "fig4_top21_calibration.png" 560 365 "H2:H13" "I2:I13"
    Add-CalibrationScatter $projectionChartsSheet $wb.Worksheets.Item("Lag_Adjusted_Calibration") "Top77 calibration: publication share to later awards" "fig5_top77_calibration.png" 20 60 "J2:J13" "K2:K13"
    Add-ChinaWindowChart $projectionChartsSheet $wb.Worksheets.Item("China_Projection")

    $chartsSheet.Columns("A:Q").ColumnWidth = 12
    $projectionChartsSheet.Columns("A:Q").ColumnWidth = 12
    $wb.Save()

    Get-ChildItem -LiteralPath $ChartExportDir -Filter "*.png" | Select-Object Name,Length | Format-Table -AutoSize
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
